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
