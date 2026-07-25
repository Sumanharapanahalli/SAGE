"""Tests for the sidecar builds handler.

Covers:
- start: missing description → InvalidParams, happy path passes through.
- list: empty and populated results.
- get: missing run_id → InvalidParams, orchestrator-level "not found" →
  InvalidParams, happy path.
- approve_stage: plan → approve_plan; build → approve_build; approved=false
  → reject.
- missing ``_orch`` module var → SidecarDown.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import handlers.builds as builds  # noqa: E402
from rpc import RpcError  # noqa: E402


def _orch_stub(**methods):
    """Build a namespace whose methods return the given values."""
    return SimpleNamespace(**methods)


def test_start_requires_description(monkeypatch):
    monkeypatch.setattr(builds, "_orch", _orch_stub(start=lambda **_: {}))
    with pytest.raises(RpcError) as e:
        builds.start({"solution_name": "yoga"})
    assert e.value.code == -32602


def test_start_happy_path_forwards_args(monkeypatch):
    captured = {}

    def fake_start(**kw):
        captured.update(kw)
        return {"run_id": "r1", "state": "awaiting_plan"}

    monkeypatch.setattr(builds, "_orch", _orch_stub(start=fake_start))
    out = builds.start(
        {
            "product_description": "yoga app",
            "solution_name": "yoga",
            "hitl_level": "strict",
            "critic_threshold": 85,
        }
    )
    assert out["run_id"] == "r1"
    assert captured["product_description"] == "yoga app"
    assert captured["hitl_level"] == "strict"
    assert captured["critic_threshold"] == 85


def test_start_raises_sidecar_error_when_orchestrator_returns_error(monkeypatch):
    monkeypatch.setattr(
        builds,
        "_orch",
        _orch_stub(start=lambda **_: {"error": "planner dead"}),
    )
    with pytest.raises(RpcError) as e:
        builds.start({"product_description": "x" * 40})
    assert e.value.code == -32000


def test_list_empty(monkeypatch):
    monkeypatch.setattr(builds, "_orch", _orch_stub(list_runs=lambda: []))
    assert builds.list_runs({}) == []


def test_list_happy_path(monkeypatch):
    monkeypatch.setattr(
        builds,
        "_orch",
        _orch_stub(list_runs=lambda: [{"run_id": "r1", "state": "completed"}]),
    )
    out = builds.list_runs({})
    assert out[0]["run_id"] == "r1"


def test_get_requires_run_id(monkeypatch):
    monkeypatch.setattr(builds, "_orch", _orch_stub(get_status=lambda _r: {}))
    with pytest.raises(RpcError) as e:
        builds.get({})
    assert e.value.code == -32602


def test_get_not_found_maps_to_invalid_params(monkeypatch):
    monkeypatch.setattr(
        builds,
        "_orch",
        _orch_stub(get_status=lambda _r: {"error": "Run 'x' not found"}),
    )
    with pytest.raises(RpcError) as e:
        builds.get({"run_id": "x"})
    assert e.value.code == -32602


def test_get_happy_path(monkeypatch):
    monkeypatch.setattr(
        builds,
        "_orch",
        _orch_stub(get_status=lambda _r: {"run_id": "r1", "state": "building"}),
    )
    assert builds.get({"run_id": "r1"})["state"] == "building"


def test_approve_routes_to_approve_plan(monkeypatch):
    calls = []
    monkeypatch.setattr(
        builds,
        "_orch",
        _orch_stub(
            get_status=lambda _r: {"state": "awaiting_plan"},
            approve_plan=lambda rid, feedback="": (
                calls.append(("plan", rid, feedback)) or {"ok": True}
            ),
            approve_build=lambda *_a, **_kw: {"err": "wrong route"},
            reject=lambda *_a, **_kw: {"err": "wrong route"},
        ),
    )
    builds.approve_stage({"run_id": "r1", "approved": True, "feedback": "ok"})
    assert calls == [("plan", "r1", "ok")]


def test_approve_routes_to_approve_build(monkeypatch):
    calls = []
    monkeypatch.setattr(
        builds,
        "_orch",
        _orch_stub(
            get_status=lambda _r: {"state": "awaiting_build"},
            approve_plan=lambda *_a, **_kw: {"err": "wrong"},
            approve_build=lambda rid, feedback="": (
                calls.append(("build", rid, feedback)) or {"ok": True}
            ),
            reject=lambda *_a, **_kw: {"err": "wrong"},
        ),
    )
    builds.approve_stage({"run_id": "r1", "approved": True})
    assert calls == [("build", "r1", "")]


def test_reject_path(monkeypatch):
    calls = []
    monkeypatch.setattr(
        builds,
        "_orch",
        _orch_stub(
            get_status=lambda _r: {"state": "awaiting_plan"},
            approve_plan=lambda *_a, **_kw: {"err": "wrong"},
            approve_build=lambda *_a, **_kw: {"err": "wrong"},
            reject=lambda rid, feedback="": (
                calls.append(("reject", rid, feedback)) or {"ok": True}
            ),
        ),
    )
    builds.approve_stage({"run_id": "r1", "approved": False, "feedback": "no"})
    assert calls == [("reject", "r1", "no")]


def test_approve_rejects_when_state_does_not_allow(monkeypatch):
    monkeypatch.setattr(
        builds,
        "_orch",
        _orch_stub(
            get_status=lambda _r: {"state": "building"},
            approve_plan=lambda *_a, **_kw: {},
            approve_build=lambda *_a, **_kw: {},
            reject=lambda *_a, **_kw: {},
        ),
    )
    with pytest.raises(RpcError) as e:
        builds.approve_stage({"run_id": "r1", "approved": True})
    assert e.value.code == -32602


def test_missing_orch_returns_sidecar_error(monkeypatch):
    monkeypatch.setattr(builds, "_orch", None)
    with pytest.raises(RpcError) as e:
        builds.list_runs({})
    assert e.value.code == -32000


# ---------- builds.reject — the other half of the gate ----------


class _FakeAuditLogger:
    def __init__(self):
        self.events = []

    def log_event(self, **kw):
        self.events.append(kw)


class _FakeMemory:
    def __init__(self):
        self.remembered = []

    def remember(self, text, user_id=None, metadata=None):
        self.remembered.append({"text": text, "user_id": user_id, "metadata": metadata})


@pytest.fixture
def wired(monkeypatch):
    """Reject with an audit logger, vector memory, and a known operator."""
    audit = _FakeAuditLogger()
    memory = _FakeMemory()
    monkeypatch.setattr(builds, "_logger", audit)
    monkeypatch.setattr(builds, "_long_term_memory_factory", lambda: memory)
    monkeypatch.setattr(
        builds,
        "_operator",
        lambda: {"name": "Ada", "email": "ada@example.com", "provider": "local"},
    )
    return SimpleNamespace(audit=audit, memory=memory)


def _rejectable_orch(calls, state="awaiting_plan"):
    """Mirrors the REAL BuildOrchestrator.reject(), which returns a run summary
    whose ``error`` field is set to "Rejected: <feedback>" (build_orchestrator.py
    :1911). A stub that omitted that would hide the bug where the handler read
    any ``error`` key as an RPC failure and turned every successful rejection
    into -32602."""
    return _orch_stub(
        get_status=lambda _r: {"run_id": "r1", "state": state},
        reject=lambda rid, feedback="": (
            calls.append(("reject", rid, feedback))
            or {
                "run_id": rid,
                "state": "rejected",
                "error": f"Rejected: {feedback}" if feedback else "Rejected by human",
            }
        ),
        approve_plan=lambda *_a, **_kw: {"err": "wrong route"},
        approve_build=lambda *_a, **_kw: {"err": "wrong route"},
    )


def test_reject_success_is_not_reported_as_an_rpc_error(monkeypatch, wired):
    """The orchestrator records the reason IN the run's ``error`` field. Reading
    that as a failure meant a successful rejection surfaced in the UI as
    "InvalidParams: Rejected: ..." — and the audit + Phase 5 steps behind the
    check never ran at all."""
    monkeypatch.setattr(builds, "_orch", _rejectable_orch([]))
    out = builds.reject({"run_id": "r1", "feedback": "no rollback step"})

    assert out["state"] == "rejected"
    assert out["error"] == "Rejected: no rollback step"  # the record, not a failure
    assert len(wired.audit.events) == 1
    assert len(wired.memory.remembered) == 1


def test_get_can_still_display_a_failed_run(monkeypatch):
    """Same root cause: builds.get raised InvalidParams for any run carrying an
    error, so the detail view could never show a failed or rejected run — the
    two the operator most needs to read."""
    monkeypatch.setattr(
        builds,
        "_orch",
        _orch_stub(
            get_status=lambda _r: {
                "run_id": "r1",
                "state": "failed",
                "error": "decomposer crashed",
            }
        ),
    )
    out = builds.get({"run_id": "r1"})
    assert out["state"] == "failed"
    assert out["error"] == "decomposer crashed"


def test_reject_requires_run_id(monkeypatch, wired):
    monkeypatch.setattr(builds, "_orch", _rejectable_orch([]))
    with pytest.raises(RpcError) as e:
        builds.reject({"feedback": "no good"})
    assert e.value.code == -32602


def test_reject_calls_orchestrator_and_returns_rejected_state(monkeypatch, wired):
    calls = []
    monkeypatch.setattr(builds, "_orch", _rejectable_orch(calls))
    out = builds.reject({"run_id": "r1", "feedback": "scope is wrong"})
    assert out["state"] == "rejected"
    assert calls == [("reject", "r1", "scope is wrong")]


def test_reject_writes_a_signed_audit_record(monkeypatch, wired):
    monkeypatch.setattr(builds, "_orch", _rejectable_orch([]))
    builds.reject({"run_id": "r1", "feedback": "scope is wrong"})

    assert len(wired.audit.events) == 1
    ev = wired.audit.events[0]
    assert ev["action_type"] == "BUILD_STAGE_REJECTED"
    # The record must name the HUMAN, not the orchestrator.
    assert ev["actor"] == "Ada"
    assert ev["approved_by"] == "Ada"
    assert ev["approver_email"] == "ada@example.com"
    assert ev["output_content"] == "scope is wrong"
    assert ev["metadata"]["run_id"] == "r1"
    # Recorded against the gate that was refused, read BEFORE reject overwrote it.
    assert ev["metadata"]["stage"] == "awaiting_plan"


def test_reject_compounds_feedback_into_vector_memory(monkeypatch, wired):
    """Phase 5 / Law 3 — every rejection teaches. This is the defect that made
    a dedicated builds.reject necessary: nothing on the build path ever wrote
    the operator's reasoning to the vector store."""
    monkeypatch.setattr(builds, "_orch", _rejectable_orch([], state="awaiting_build"))
    builds.reject({"run_id": "r1", "feedback": "no error handling in the API layer"})

    assert len(wired.memory.remembered) == 1
    lesson = wired.memory.remembered[0]
    assert "no error handling in the API layer" in lesson["text"]
    assert "awaiting_build" in lesson["text"]
    assert lesson["user_id"] == "Ada"
    assert lesson["metadata"]["run_id"] == "r1"


def test_reject_without_feedback_does_not_invent_a_lesson(monkeypatch, wired):
    """Mirrors approvals._compound: a decision is valid without a reason, but
    silence is not a lesson."""
    monkeypatch.setattr(builds, "_orch", _rejectable_orch([]))
    builds.reject({"run_id": "r1"})
    assert wired.memory.remembered == []
    # The decision is still audited.
    assert len(wired.audit.events) == 1


def test_reject_refuses_when_run_is_not_at_a_gate(monkeypatch, wired):
    monkeypatch.setattr(builds, "_orch", _rejectable_orch([], state="building"))
    with pytest.raises(RpcError) as e:
        builds.reject({"run_id": "r1", "feedback": "stop"})
    assert e.value.code == -32602
    assert "not awaiting approval" in e.value.message


def test_reject_maps_unknown_run_to_invalid_params(monkeypatch, wired):
    monkeypatch.setattr(
        builds,
        "_orch",
        _orch_stub(
            get_status=lambda _r: {"error": "Run 'nope' not found"},
            reject=lambda *_a, **_kw: {},
        ),
    )
    with pytest.raises(RpcError) as e:
        builds.reject({"run_id": "nope", "feedback": "x"})
    assert e.value.code == -32602


def test_reject_survives_a_dead_vector_store(monkeypatch, wired):
    """Compounding memory must never cost us a decision the human already made."""

    def _boom():
        raise RuntimeError("chromadb is down")

    monkeypatch.setattr(builds, "_orch", _rejectable_orch([]))
    monkeypatch.setattr(builds, "_long_term_memory_factory", _boom)
    out = builds.reject({"run_id": "r1", "feedback": "bad plan"})
    assert out["state"] == "rejected"


def test_approve_stage_reject_branch_delegates_to_reject(monkeypatch, wired):
    """approve_stage(approved=False) must go through the SAME path, or we ship
    two rejects — one of which silently skips Phase 5."""
    calls = []
    monkeypatch.setattr(builds, "_orch", _rejectable_orch(calls))
    builds.approve_stage({"run_id": "r1", "approved": False, "feedback": "no"})

    assert calls == [("reject", "r1", "no")]
    assert len(wired.audit.events) == 1
    assert len(wired.memory.remembered) == 1
