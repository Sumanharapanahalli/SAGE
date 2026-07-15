"""Slice 2 — approval actually approves (Law 1 / the core vertical slice).

`execute_approved_proposal` appeared NOWHERE in sage-desktop. Approving an
implementation_plan — including one desktop itself created via backlog.plan —
flipped a status column and stopped. No task queued, no CodingAgent, no
code_diff. And rejecting a code_diff never called `_revert_code_diff`, so the
agent's edits stayed on disk after the human said no.

SOUL.md's five-phase loop is SURFACE -> CONTEXTUALIZE -> PROPOSE -> DECIDE ->
COMPOUND, and the framework's whole product is the DECIDE gate. On desktop that
gate recorded nothing (slice 0), taught nothing (slice 1), and did nothing
(this slice).

The sidecar's dispatch loop is serial (`for raw in stdin`), and the two
background action types are multi-minute LLM work, so they run on a worker
thread and return a job_id rather than stalling every other RPC.
"""

from __future__ import annotations

import time

import pytest

import jobs
from handlers import approvals as ap


@pytest.fixture(autouse=True)
def clean_jobs():
    jobs.reset()
    yield
    jobs.reset()


@pytest.fixture
def store(tmp_path, monkeypatch):
    from src.core.proposal_store import ProposalStore

    s = ProposalStore(str(tmp_path / "proposals.db"))
    monkeypatch.setattr(ap, "_store", s)
    monkeypatch.setattr(ap, "_logger", None)
    monkeypatch.setattr(ap, "_analyst_factory", lambda: _Noop())
    monkeypatch.setattr(ap, "_long_term_memory_factory", lambda: _Noop())
    return s


class _Noop:
    def learn_from_feedback(self, *a, **kw):
        pass

    def remember(self, *a, **kw):
        pass


def _make(store, action_type="yaml_edit"):
    from src.core.proposal_store import RiskClass

    return store.create(
        action_type=action_type,
        risk_class=RiskClass.STATEFUL,
        payload={"file": "prompts.yaml"},
        description="test",
    )


# ---------- the job runner ----------


def test_job_runs_an_async_coroutine_and_records_the_result():
    async def _work():
        return {"ok": True}

    job_id = jobs.submit("test", _work())
    _wait(job_id)

    st = jobs.status(job_id)
    assert st["state"] == "succeeded"
    assert st["result"] == {"ok": True}


def test_job_records_a_failure_instead_of_crashing_the_sidecar():
    async def _boom():
        raise RuntimeError("executor exploded")

    job_id = jobs.submit("test", _boom())
    _wait(job_id)

    st = jobs.status(job_id)
    assert st["state"] == "failed"
    assert "executor exploded" in st["error"]


def test_status_of_an_unknown_job_id_raises():
    from rpc import RpcError

    with pytest.raises(RpcError):
        jobs.status("no-such-job")


def _wait(job_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if jobs.status(job_id)["state"] in ("succeeded", "failed"):
            return
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not finish within {timeout}s")


# ---------- approve -> execute ----------


def test_approving_a_fast_proposal_executes_it_inline(store, monkeypatch):
    executed = []

    async def _fake_exec(proposal):
        executed.append(proposal.trace_id)
        return {"status": "applied"}

    monkeypatch.setattr(ap, "_executor_factory", lambda: _fake_exec)

    p = _make(store, "yaml_edit")
    out = ap.approve({"trace_id": p.trace_id})

    assert executed == [p.trace_id], "approval did not execute the proposal"
    assert out["execution"]["state"] == "succeeded"
    assert out["execution"]["result"] == {"status": "applied"}


def test_approving_a_background_proposal_returns_a_job_id(store, monkeypatch):
    """implementation_plan and code_diff are multi-minute LLM work. Running them
    inline would stall the serial dispatch loop — every poll, every page."""
    executed = []

    async def _fake_exec(proposal):
        executed.append(proposal.trace_id)
        return {"status": "planned"}

    monkeypatch.setattr(ap, "_executor_factory", lambda: _fake_exec)

    p = _make(store, "implementation_plan")
    out = ap.approve({"trace_id": p.trace_id})

    job_id = out["execution"]["job_id"]
    assert job_id
    assert out["execution"]["state"] in ("running", "queued", "succeeded")
    _wait(job_id)
    assert executed == [p.trace_id]


def test_an_execution_failure_does_not_undo_the_human_decision(store, monkeypatch):
    """The human approved. If the executor then fails, the approval still stands
    and the failure is surfaced — silently reverting a human decision would be
    worse than a failed execution."""

    async def _boom(proposal):
        raise RuntimeError("no LLM configured")

    monkeypatch.setattr(ap, "_executor_factory", lambda: _boom)

    p = _make(store, "yaml_edit")
    out = ap.approve({"trace_id": p.trace_id})

    assert out["status"] == "approved"
    assert out["execution"]["state"] == "failed"
    assert "no LLM configured" in out["execution"]["error"]


def test_an_unregistered_action_type_is_reported_not_swallowed(store, monkeypatch):
    """execute_approved_proposal raises RuntimeError for an action_type with no
    executor (e.g. "analysis", which is informational). That must surface as a
    clean execution state, not a crash and not a false success."""

    async def _raise(proposal):
        raise RuntimeError("No executor registered for action_type 'analysis'")

    monkeypatch.setattr(ap, "_executor_factory", lambda: _raise)

    p = _make(store, "analysis")
    out = ap.approve({"trace_id": p.trace_id})
    assert out["status"] == "approved"
    assert out["execution"]["state"] == "failed"


# ---------- reject -> revert ----------


def test_rejecting_a_code_diff_reverts_the_working_tree(store, monkeypatch):
    """The agent already wrote its edits to disk. Rejecting must undo them —
    otherwise "no" leaves the change in place, which is the opposite of a gate."""
    reverted = []

    async def _fake_revert(proposal):
        reverted.append(proposal.trace_id)

    monkeypatch.setattr(ap, "_revert_factory", lambda: _fake_revert)

    p = _make(store, "code_diff")
    ap.reject({"trace_id": p.trace_id, "feedback": "wrong approach"})

    assert reverted == [p.trace_id], "rejected code_diff left the agent's edits on disk"


def test_rejecting_a_non_code_diff_does_not_revert(store, monkeypatch):
    reverted = []

    async def _fake_revert(proposal):
        reverted.append(proposal.trace_id)

    monkeypatch.setattr(ap, "_revert_factory", lambda: _fake_revert)

    p = _make(store, "yaml_edit")
    ap.reject({"trace_id": p.trace_id, "feedback": "no"})
    assert reverted == []


# ---------- registration ----------


def test_jobs_rpcs_are_registered():
    import app

    d = app._build_dispatcher()
    assert "jobs.status" in d._handlers
    assert "jobs.list" in d._handlers
