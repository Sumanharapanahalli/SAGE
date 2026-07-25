"""Slice 0 — "the sidecar tells the truth".

These tests pin the four defects that make the shipped desktop app assert
things it does not do:

  X1  The audit DB the handler READS is not the one the framework's agents
      WRITE. `sidecar.rs` never exports SAGE_PROJECT, so
      `audit_logger._resolve_db_path()` freezes DB_PATH at the framework
      root while `_wire_handlers` points the handler at <solution>/.sage/.
      Result: in desktop-only operation the audit log is permanently empty.

  X2  No approve/reject is audit-logged at all (there is not one log_event
      call in sidecar production code) — while Approvals.tsx tells the
      operator "The decision is recorded in the Audit log."

  X3  Every decision is signed `decided_by="human"`; there is no operator
      identity, so the 21 CFR Part 11 §11.50 signer record is
      unattributable.

  X7  `agents.performance` is called by the Rust layer and the UI but was
      never registered on the dispatcher — every click throws -32601.

  X8  QueueTile's "Done" counter is structurally always 0: the handler keys
      on "done"; TaskStatus.COMPLETED is "completed".
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import app
from handlers import approvals as ap
from handlers import operator as op
from handlers import queue as q


# ---------- X1: the audit read path must equal the write path ----------


def test_bootstrap_env_exports_sage_project(tmp_path, monkeypatch):
    """The sidecar must export SAGE_PROJECT before any src/ import.

    Every framework global (audit_logger, vector_memory, project_config)
    resolves its solution from this env var AT IMPORT TIME. Without it they
    silently bind to the framework root instead of the active solution.
    """
    monkeypatch.delenv("SAGE_PROJECT", raising=False)
    monkeypatch.delenv("SAGE_SOLUTIONS_DIR", raising=False)
    solution_path = tmp_path / "solutions" / "acme"
    solution_path.mkdir(parents=True)

    app._bootstrap_env("acme", solution_path)

    assert os.environ["SAGE_PROJECT"] == "acme"
    # The solutions DIR is the solution's PARENT — this is what lets a
    # solution mounted outside the repo (SOUL.md: "solutions are tenants")
    # resolve correctly.
    assert Path(os.environ["SAGE_SOLUTIONS_DIR"]) == solution_path.parent


def test_audit_logger_global_resolves_to_the_solution_the_handler_reads(
    tmp_path, monkeypatch
):
    """The bug, stated as an equality: global write path == handler read path.

    The agents (analyst, developer, planner, build_orchestrator...) all write
    through the module-global AuditLogger. The audit handler reads
    <solution>/.sage/audit_log.db. If those differ, the operator's compliance
    record is empty no matter how much work the agents do.
    """
    monkeypatch.delenv("SAGE_PROJECT", raising=False)
    solution_path = tmp_path / "solutions" / "acme"
    solution_path.mkdir(parents=True)

    app._bootstrap_env("acme", solution_path)

    from src.memory.audit_logger import _resolve_db_path

    global_write_path = Path(_resolve_db_path())
    handler_read_path = solution_path / ".sage" / "audit_log.db"
    assert global_write_path == handler_read_path


def test_bootstrap_env_is_a_noop_without_a_solution(tmp_path, monkeypatch):
    """Minimal mode (no solution) must not invent a SAGE_PROJECT."""
    monkeypatch.delenv("SAGE_PROJECT", raising=False)
    app._bootstrap_env("", None)
    assert os.environ.get("SAGE_PROJECT", "") == ""


# ---------- operator identity (the honest replacement for OIDC) ----------


@pytest.fixture
def operator_file(tmp_path, monkeypatch):
    sage_dir = tmp_path / ".sage"
    sage_dir.mkdir(parents=True)
    monkeypatch.setattr(op, "_path", sage_dir / "operator.yaml")
    return sage_dir / "operator.yaml"


def test_operator_get_defaults_when_unset(operator_file):
    got = op.get({})
    assert got["name"] == ""
    assert got["email"] == ""
    # Never claim an identity provider we do not have. This is the field the
    # audit record is signed with, and it must not read "oidc".
    assert got["provider"] == "desktop-operator"


def test_operator_set_then_get_roundtrips(operator_file):
    op.set({"name": "Dana Scully", "email": "dana@acme.com"})
    got = op.get({})
    assert got["name"] == "Dana Scully"
    assert got["email"] == "dana@acme.com"
    assert operator_file.exists()


def test_operator_set_rejects_a_blank_name(operator_file):
    from rpc import RpcError

    with pytest.raises(RpcError):
        op.set({"name": "   ", "email": "x@y.com"})


# ---------- X2 + X3: approvals must write a signed audit record ----------


class _FakeLogger:
    """Captures log_event kwargs so the test asserts on the signer fields."""

    def __init__(self):
        self.events = []
        self.db_path = ":memory:"

    def log_event(self, **kwargs):
        self.events.append(kwargs)


@pytest.fixture
def store(tmp_path, monkeypatch):
    from src.core.proposal_store import ProposalStore

    s = ProposalStore(str(tmp_path / "proposals.db"))
    monkeypatch.setattr(ap, "_store", s)
    return s


@pytest.fixture
def logger(monkeypatch):
    lg = _FakeLogger()
    monkeypatch.setattr(ap, "_logger", lg)
    return lg


@pytest.fixture
def identity(monkeypatch):
    monkeypatch.setattr(
        ap,
        "_operator",
        lambda: {
            "name": "Dana Scully",
            "email": "dana@acme.com",
            "provider": "desktop-operator",
        },
    )


def _make(store, **kw):
    from src.core.proposal_store import RiskClass

    d = dict(
        action_type="yaml_edit",
        risk_class=RiskClass.STATEFUL,
        payload={"k": "v"},
        description="Test proposal",
    )
    d.update(kw)
    return store.create(**d)


def test_approve_writes_an_audit_event(store, logger, identity):
    p = _make(store)
    ap.approve({"trace_id": p.trace_id})

    assert len(logger.events) == 1, "approval wrote no audit record"
    e = logger.events[0]
    assert e["action_type"] == "PROPOSAL_APPROVED"
    assert p.trace_id in e["input_context"]
    assert e["metadata"]["trace_id"] == p.trace_id


def test_approve_signs_the_record_with_the_operator_identity(store, logger, identity):
    """21 CFR Part 11 §11.50 — the signed record must name a signer."""
    p = _make(store)
    ap.approve({"trace_id": p.trace_id})

    e = logger.events[0]
    assert e["approved_by"] == "Dana Scully"
    assert e["approver_email"] == "dana@acme.com"
    assert e["approver_provider"] == "desktop-operator"


def test_reject_writes_a_signed_audit_event(store, logger, identity):
    p = _make(store)
    ap.reject({"trace_id": p.trace_id, "feedback": "wrong module"})

    assert len(logger.events) == 1
    e = logger.events[0]
    assert e["action_type"] == "PROPOSAL_REJECTED"
    assert e["output_content"] == "wrong module"
    assert e["approved_by"] == "Dana Scully"


def test_signer_identity_cannot_be_spoofed_by_the_renderer(store, logger, identity):
    """The signer is resolved SIDECAR-side. A decided_by in the RPC params
    must never be able to forge the audit signature."""
    p = _make(store)
    ap.approve({"trace_id": p.trace_id, "decided_by": "Somebody Else"})

    assert logger.events[0]["approved_by"] == "Dana Scully"


def test_audit_failure_does_not_lose_the_decision(store, monkeypatch, identity):
    """If the audit write throws, the approval must still stand (and the
    error must surface in logs) — losing the decision is worse."""

    class _Boom:
        db_path = ":memory:"

        def log_event(self, **kw):
            raise RuntimeError("disk full")

    monkeypatch.setattr(ap, "_logger", _Boom())
    p = _make(store)
    got = ap.approve({"trace_id": p.trace_id})
    assert got["status"] == "approved"


# ---------- X7: agents.performance must be reachable ----------


def test_agents_performance_is_registered_on_the_dispatcher():
    """It is called by the Rust layer and the UI, but was never registered —
    so every click on an agent card throws -32601 (method not found)."""
    d = app._build_dispatcher()
    assert "agents.performance" in d._handlers


def test_operator_rpcs_are_registered():
    d = app._build_dispatcher()
    assert "operator.get" in d._handlers
    assert "operator.set" in d._handlers


# ---------- X8: the queue "Done" counter ----------


def test_empty_status_uses_the_real_task_status_keys():
    """TaskStatus.COMPLETED == "completed". The handler keyed on "done", so
    the `if key in status` guard silently dropped every finished task and the
    UI's Done tile was structurally pinned to 0."""
    empty = q._empty_status()
    assert "completed" in empty
    assert "cancelled" in empty
    assert "done" not in empty
