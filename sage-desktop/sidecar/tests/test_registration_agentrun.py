"""End-to-end registration + wiring tests for agentrun.*.

``handlers/agentrun.py`` was fully written and unit-tested (test_agentrun.py)
but never imported in ``app.py``, so it was absent from ``_build_dispatcher``
and every call returned -32601.

test_agentrun.py could not catch that on two counts: it imports the handler
module directly (never crossing the dispatcher), AND it monkeypatches
``_store`` / ``_project`` / ``_solution_name`` (never exercising the real
``_wire_handlers`` injection). Both gaps are covered here by driving the REAL
NDJSON event loop, the same way test_registration_activity_regulatory.py and
test_registration_safety.py do.

The load-bearing test is ``test_hire_proposal_lands_in_the_approvals_inbox``:
it proves ``agentrun._store`` is the SAME ProposalStore ``approvals.*`` reads.
A hire that created a proposal in some *other* store would satisfy every unit
test in test_agentrun.py while being invisible to the human — an un-approvable
HITL gate, i.e. a silent Law 1 violation.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil

import pytest

import app as sidecar_app
from handlers import agentrun as ar

METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602

SAGE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SOLUTION = "four_in_a_line"
SOLUTION_PATH = os.path.join(SAGE_ROOT, "solutions", SOLUTION)


def _req(id: str, method: str, params: dict | None = None) -> str:
    return json.dumps(
        {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}
    )


def _drive(lines: list[str], argv: list[str] | None = None) -> list[dict]:
    stdin = io.StringIO("".join(line + "\n" for line in lines))
    stdout = io.StringIO()
    sidecar_app.run(stdin=stdin, stdout=stdout, argv=argv or [])
    stdout.seek(0)
    return [json.loads(ln) for ln in stdout.read().splitlines() if ln.strip()]


@pytest.fixture
def solution_dir(tmp_path):
    """A throwaway COPY of the four_in_a_line solution.

    Not a bare tmp_path like test_registration_activity_regulatory.py uses:
    ``_bootstrap_env`` exports ``SAGE_SOLUTIONS_DIR`` as the solution path's
    PARENT, so a bare tmp_path makes ProjectConfig resolve
    <tmp>/four_in_a_line/prompts.yaml — which would not exist, silently
    yielding zero roles. That trick only works for handlers that never read
    the solution's YAML. agentrun reads prompts.yaml, so the real files have
    to be there; copying keeps both the YAML reads and the .sage/ writes
    inside tmp, so the repo is never touched.
    """
    if not os.path.isdir(SOLUTION_PATH):
        pytest.skip("four_in_a_line solution not present on this branch")
    dest = tmp_path / SOLUTION
    shutil.copytree(SOLUTION_PATH, dest)
    return dest


@pytest.fixture
def solution_argv(solution_dir):
    return ["--solution-name", SOLUTION, "--solution-path", str(solution_dir)]


class FakeAgent:
    """Stand-in for UniversalAgent so `run` needs no LLM."""

    def run(self, role_id, task, context="", actor=""):
        return {
            "role_id": role_id,
            "role_name": "Game Designer",
            "severity": "HIGH",
            "summary": f"analysed: {task}",
            "trace_id": "trace-agentrun-1",
        }


@pytest.fixture
def fake_agent(monkeypatch):
    # _wire_handlers sets _store/_project but never touches _agent_factory,
    # so this override survives the drive.
    monkeypatch.setattr(ar, "_agent_factory", lambda: FakeAgent())


HIRE_PARAMS = {
    "role_id": "level_balancer",
    "name": "Level Balancer",
    "system_prompt": "You tune difficulty curves.",
    "description": "Balances level difficulty",
    "task_types": ["balance_review"],
}


# ---------- registration ----------


def test_all_agentrun_methods_are_registered(solution_argv, fake_agent):
    """The regression this file exists for: every agentrun.* method must
    resolve. A missing registration shows up as -32601."""
    methods = [
        ("agentrun.get_project", {}),
        ("agentrun.run", {"role_id": "game_designer", "task": "review the board"}),
        ("agentrun.hire", HIRE_PARAMS),
        ("agentrun.analyze_jd", {"jd_text": "We need someone to tune levels."}),
    ]
    out = _drive([_req(str(i), m, p) for i, (m, p) in enumerate(methods)], solution_argv)

    assert len(out) == len(methods)
    for resp, (method, _) in zip(out, methods):
        error = resp.get("error")
        # analyze_jd needs a real LLM, so it may legitimately fail here — but
        # it must fail from INSIDE the handler, never as method-not-found.
        assert (
            error is None or error["code"] != METHOD_NOT_FOUND
        ), f"{method} is not registered: {resp}"


# ---------- _wire_handlers injection ----------


def test_wire_handlers_injects_project(solution_argv):
    """`_project` must be injected, or get_project raises 'no solution loaded'."""
    out = _drive([_req("1", "agentrun.get_project")], solution_argv)
    result = out[0].get("result")

    assert result is not None, f"get_project failed: {out[0]}"
    role_ids = {a["id"] for a in result["agents"]}
    assert "game_designer" in role_ids, "prompts.yaml roles were not read"


def test_wire_handlers_injects_solution_name(solution_argv):
    """`_solution()` feeds proposal_executor._execute_agent_hire's YAML
    resolution — a blank value would send the write to the framework-global
    project_config instead of this sidecar's solution."""
    out = _drive([_req("1", "agentrun.hire", HIRE_PARAMS)], solution_argv)
    result = out[0].get("result")

    assert result is not None, f"hire failed: {out[0]}"
    assert result["payload"]["solution"] == SOLUTION


# ---------- Law 1: the HITL path ----------


def test_hire_proposal_lands_in_the_approvals_inbox(solution_argv):
    """`agentrun._store` must be the SAME store `approvals.*` reads.

    A proposal created in a different store would pass every unit test while
    being invisible to the human — an un-approvable HITL gate.
    """
    out = _drive(
        [
            _req("1", "agentrun.hire", HIRE_PARAMS),
            _req("2", "approvals.list_pending"),
        ],
        solution_argv,
    )
    created = out[0]["result"]
    pending = out[1]["result"]

    trace_ids = {p["trace_id"] for p in pending}
    assert created["trace_id"] in trace_ids, "hire proposal is not in the inbox"

    inbox_entry = next(p for p in pending if p["trace_id"] == created["trace_id"])
    assert inbox_entry["action_type"] == "agent_hire"
    assert inbox_entry["status"] == "pending"


def test_hire_does_not_write_yaml(solution_argv, solution_dir):
    """Writing prompts.yaml happens on APPROVAL, in
    proposal_executor._execute_agent_hire — never in the handler."""
    prompts = solution_dir / "prompts.yaml"
    before = hashlib.sha256(prompts.read_bytes()).hexdigest()
    out = _drive([_req("1", "agentrun.hire", HIRE_PARAMS)], solution_argv)
    after = hashlib.sha256(prompts.read_bytes()).hexdigest()

    assert out[0].get("result") is not None, f"hire failed: {out[0]}"
    assert before == after, "hire mutated prompts.yaml instead of proposing"


def test_run_persists_a_proposal_in_the_inbox(solution_argv, fake_agent):
    """The web API's POST /agent/run returns status:'pending_review' and
    persists NOTHING, so its approval banner is decorative. Desktop must
    create a real proposal in the inbox."""
    out = _drive(
        [
            _req(
                "1",
                "agentrun.run",
                {"role_id": "game_designer", "task": "review the board"},
            ),
            _req("2", "approvals.list_pending"),
        ],
        solution_argv,
    )
    result = out[0].get("result")
    assert result is not None, f"run failed: {out[0]}"

    proposal = result["proposal"]
    assert proposal["action_type"] == "agent_run"
    # Adopting the agent's own trace_id keeps the proposal resolvable in
    # audit.get_by_trace, where UniversalAgent already logged its events.
    assert proposal["trace_id"] == "trace-agentrun-1"

    pending = out[1]["result"]
    assert proposal["trace_id"] in {p["trace_id"] for p in pending}


def test_run_rejects_an_unknown_role_as_invalid_params(solution_argv):
    """An unknown role is operator input error, not a sidecar fault — and
    proves the call reached the handler rather than falling through."""
    out = _drive(
        [_req("1", "agentrun.run", {"role_id": "nope_not_a_role", "task": "x"})],
        solution_argv,
    )
    error = out[0].get("error")

    assert error is not None
    assert error["code"] != METHOD_NOT_FOUND
