"""Tests for the code handler — plan, approve, execute in a sandbox.

This is NOT the Merge-Gate path. Merge-Gate (Law 1a) governs *merging* agent
code to main; this governs *executing* a generated script, and its approval
gate is enforced inside `autogen_runner.execute()` itself, not just in the UI.

One addition over the web API: `sandbox_status`. `autogen_runner` falls back to
a LOCAL SUBPROCESS with no isolation when Docker is unavailable, and the web
API only reveals that in the execute result — i.e. after the code has already
run on the operator's machine. Exposing it up front lets the UI say so while
the operator is still deciding whether to approve.
"""

from __future__ import annotations

import pytest

from handlers import code as code_handler
from rpc import RpcError

INVALID_PARAMS = -32602
SIDECAR_ERROR = -32000


class FakeRunner:
    """Stands in for autogen_runner, mirroring its dict-returning contract
    (it returns {"error": ...} rather than raising)."""

    def __init__(self):
        self.runs: dict[str, dict] = {}
        self.executed: list[str] = []

    def plan(self, task, trace_id=None):
        run_id = f"run-{len(self.runs) + 1}"
        self.runs[run_id] = {"status": "awaiting_approval", "task": task}
        return {
            "run_id": run_id,
            "status": "awaiting_approval",
            "plan": f"plan for {task}",
            "code": "print('hi')",
        }

    def approve(self, run_id, comment=""):
        meta = self.runs.get(run_id)
        if meta is None:
            return {"error": f"Run '{run_id}' not found", "run_id": run_id}
        if meta["status"] != "awaiting_approval":
            return {"error": "not awaiting approval", "run_id": run_id}
        meta["status"] = "approved"
        return {"run_id": run_id, "status": "approved"}

    def execute(self, run_id):
        meta = self.runs.get(run_id)
        if meta is None:
            return {"error": f"Run '{run_id}' not found", "run_id": run_id}
        if meta["status"] != "approved":
            return {"error": "has not been approved", "run_id": run_id}
        self.executed.append(run_id)
        return {
            "run_id": run_id,
            "status": "completed",
            "output": {"stdout": "hi\n", "stderr": "", "returncode": 0,
                       "sandbox": "docker"},
        }

    def get_status(self, run_id):
        meta = self.runs.get(run_id)
        if meta is None:
            return {"error": f"Run '{run_id}' not found", "run_id": run_id}
        return {"run_id": run_id, "status": meta["status"]}


@pytest.fixture
def runner(monkeypatch):
    fake = FakeRunner()
    monkeypatch.setattr(code_handler, "_runner", fake)
    monkeypatch.setattr(code_handler, "_docker_check", lambda: True)
    return fake


# ---------- plan ----------


def test_plan_returns_a_run_awaiting_approval(runner):
    out = code_handler.plan({"task": "sum a list"})

    assert out["run_id"]
    assert out["status"] == "awaiting_approval"
    assert out["code"] == "print('hi')"


@pytest.mark.parametrize("params", [{}, {"task": ""}, {"task": "   "}])
def test_plan_requires_a_task(runner, params):
    with pytest.raises(RpcError) as e:
        code_handler.plan(params)
    assert e.value.code == INVALID_PARAMS


def test_plan_does_not_execute_anything(runner):
    code_handler.plan({"task": "rm -rf /"})
    assert runner.executed == []


# ---------- the approval gate ----------


def test_execute_is_refused_before_approval(runner):
    """The gate is real: the runner itself refuses, so a UI slip cannot run
    unapproved code."""
    run_id = code_handler.plan({"task": "x"})["run_id"]

    with pytest.raises(RpcError) as e:
        code_handler.execute({"run_id": run_id})

    assert e.value.code == INVALID_PARAMS
    assert runner.executed == []


def test_execute_runs_once_approved(runner):
    run_id = code_handler.plan({"task": "x"})["run_id"]
    code_handler.approve({"run_id": run_id})

    out = code_handler.execute({"run_id": run_id})

    assert out["status"] == "completed"
    assert out["output"]["returncode"] == 0
    assert runner.executed == [run_id]


def test_approve_rejects_an_unknown_run(runner):
    with pytest.raises(RpcError) as e:
        code_handler.approve({"run_id": "nope"})
    assert e.value.code == INVALID_PARAMS


def test_approve_is_not_repeatable(runner):
    """Re-approving an already-approved run is an error, not a silent no-op."""
    run_id = code_handler.plan({"task": "x"})["run_id"]
    code_handler.approve({"run_id": run_id})

    with pytest.raises(RpcError) as e:
        code_handler.approve({"run_id": run_id})
    assert e.value.code == INVALID_PARAMS


@pytest.mark.parametrize("method", ["approve", "execute", "status"])
def test_run_id_is_required(runner, method):
    with pytest.raises(RpcError) as e:
        getattr(code_handler, method)({})
    assert e.value.code == INVALID_PARAMS


def test_status_reports_the_current_state(runner):
    run_id = code_handler.plan({"task": "x"})["run_id"]
    assert code_handler.status({"run_id": run_id})["status"] == "awaiting_approval"

    code_handler.approve({"run_id": run_id})
    assert code_handler.status({"run_id": run_id})["status"] == "approved"


def test_status_rejects_an_unknown_run(runner):
    with pytest.raises(RpcError) as e:
        code_handler.status({"run_id": "nope"})
    assert e.value.code == INVALID_PARAMS


# ---------- sandbox isolation, surfaced BEFORE approval ----------


def test_sandbox_status_reports_docker_available(runner):
    assert code_handler.sandbox_status({}) == {
        "docker_available": True,
        "sandbox": "docker",
        "isolated": True,
    }


def test_sandbox_status_warns_when_docker_is_missing(runner, monkeypatch):
    """Without Docker the generated code runs in a local subprocess with NO
    isolation. The operator must know that while deciding, not afterwards."""
    monkeypatch.setattr(code_handler, "_docker_check", lambda: False)

    out = code_handler.sandbox_status({})

    assert out["docker_available"] is False
    assert out["isolated"] is False
    assert out["sandbox"] == "local_subprocess"
    assert "no isolation" in out["warning"].lower()


def test_handlers_error_cleanly_when_unwired(monkeypatch):
    monkeypatch.setattr(code_handler, "_runner", None)
    with pytest.raises(RpcError) as e:
        code_handler.plan({"task": "x"})
    assert e.value.code == SIDECAR_ERROR
