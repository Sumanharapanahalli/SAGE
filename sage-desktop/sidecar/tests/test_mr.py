"""Tests for the mr handler — GitLab merge-request operations.

`handlers/mr.py` was fully written but never imported in `app.py`, so it never
reached `_build_dispatcher` and every `mr.*` call returned -32601 — the same
dead-module pattern as `safety.py` and `agentrun.py`.

Distinct from `mergegate.*`, which is SAGE's OWN Merge-Gate (Law 1a: agents own
the branch, the human approves the MR, the merge writes a signed audit record).
These wrap the DeveloperAgent's GitLab integration, addressed by numeric GitLab
project/MR IDs. They sit alongside mergegate rather than replacing it.

The load-bearing assertion is `test_propose_create_does_not_touch_gitlab`: the
web's `POST /mr/create` opens the MR *immediately* — an LLM-drafted,
irreversible write to an external system with no human in the loop. Desktop
files an EXTERNAL, non-reversible proposal instead, and only the approved
executor POSTs.
"""

from __future__ import annotations

import io
import json

import pytest

import app as sidecar_app
from handlers import mr as mr_handler
from rpc import RpcError

INVALID_PARAMS = -32602
SIDECAR_ERROR = -32000
METHOD_NOT_FOUND = -32601


class FakeAgent:
    # A distinctive value: "tok" would false-positive against "has_token".
    SECRET = "glpat-SECRET-VALUE"

    def __init__(self, url="https://gitlab.example.com", token=SECRET):
        self.gitlab_url = url
        self.gitlab_token = token
        self.default_project_id = "12"
        self.calls: list[tuple] = []

    def list_open_mrs(self, project_id):
        self.calls.append(("open", project_id))
        return {"merge_requests": [{"iid": 7, "title": "Add thing"}]}

    def get_pipeline_status(self, project_id, mr_iid):
        self.calls.append(("pipeline", project_id, mr_iid))
        return {"status": "success"}

    def add_mr_comment(self, project_id, mr_iid, comment):
        self.calls.append(("comment", project_id, mr_iid, comment))
        return {"posted": True}

    def create_mr_from_issue(self, project_id, issue_iid, source_branch=None):
        self.calls.append(("create", project_id, issue_iid, source_branch))
        return {"mr_iid": 7, "web_url": "https://gitlab/mr/7"}

    def review_merge_request(self, project_id, mr_iid):
        self.calls.append(("review", project_id, mr_iid))
        return {"review": "looks good"}

    def _gl_get(self, path):
        self.calls.append(("get", path))
        return {"title": "Fix the thing"}, None


@pytest.fixture
def agent(monkeypatch):
    fake = FakeAgent()
    monkeypatch.setattr(mr_handler, "_agent_factory", lambda: fake)
    return fake


@pytest.fixture
def store(tmp_path, monkeypatch):
    from src.core.proposal_store import ProposalStore

    s = ProposalStore(str(tmp_path / "proposals.db"))
    monkeypatch.setattr(mr_handler, "_store", s)
    return s


# ---------- registration (the defect this file exists for) ----------


def _drive(lines: list[str]) -> list[dict]:
    stdin = io.StringIO("".join(line + "\n" for line in lines))
    stdout = io.StringIO()
    sidecar_app.run(stdin=stdin, stdout=stdout, argv=[])
    stdout.seek(0)
    return [json.loads(ln) for ln in stdout.read().splitlines() if ln.strip()]


def test_all_mr_methods_are_registered():
    """A missing registration shows up as -32601. Unit tests cannot catch it:
    they import the handler directly and never cross the dispatcher."""
    methods = [
        "mr.config",
        "mr.list_open",
        "mr.pipeline",
        "mr.review",
        "mr.propose_create",
        "mr.comment",
    ]
    out = _drive(
        [
            json.dumps({"jsonrpc": "2.0", "id": str(i), "method": m, "params": {}})
            for i, m in enumerate(methods)
        ]
    )

    assert len(out) == len(methods)
    for resp, method in zip(out, methods):
        error = resp.get("error")
        assert (
            error is None or error["code"] != METHOD_NOT_FOUND
        ), f"{method} is not registered: {resp}"


# ---------- config: a state, never an error ----------


def test_config_reports_configured(agent):
    out = mr_handler.config({})
    assert out["configured"] is True
    assert out["gitlab_url"] == "https://gitlab.example.com"
    # The token itself must never reach the UI — only whether one exists.
    assert out["has_token"] is True
    assert FakeAgent.SECRET not in json.dumps(out)


def test_config_reports_missing_credentials_without_raising(monkeypatch):
    """The UI renders a setup prompt from this, so it must be a clean state."""
    monkeypatch.setattr(
        mr_handler, "_agent_factory", lambda: FakeAgent(url="", token="")
    )
    out = mr_handler.config({})

    assert out["configured"] is False
    assert out["message"]


def test_config_survives_an_unconstructable_agent(monkeypatch):
    def boom():
        raise ImportError("gitlab client missing")

    monkeypatch.setattr(mr_handler, "_agent_factory", boom)
    assert mr_handler.config({})["configured"] is False


def test_operations_refuse_when_unconfigured(monkeypatch):
    monkeypatch.setattr(
        mr_handler, "_agent_factory", lambda: FakeAgent(url="", token="")
    )
    with pytest.raises(RpcError) as e:
        mr_handler.list_open({"project_id": 12})
    assert "not configured" in str(e.value.message).lower()


# ---------- Law 1: creating an MR is proposed, never done ----------


def test_propose_create_does_not_touch_gitlab(agent, store):
    """The web endpoint opens the MR immediately. An LLM-drafted, irreversible
    write to an external system must be a proposal instead."""
    mr_handler.propose_create({"project_id": 12, "issue_iid": 45})

    assert ("create", 12, 45, None) not in agent.calls
    assert not any(c[0] == "create" for c in agent.calls)


def test_propose_create_files_an_external_irreversible_proposal(agent, store):
    out = mr_handler.propose_create({"project_id": 12, "issue_iid": 45})

    assert out["action_type"] == "mr_create"
    assert out["risk_class"] == "EXTERNAL"
    # An MR in a shared GitLab cannot be undone from here.
    assert out["reversible"] is False
    assert out["status"] == "pending"


def test_the_proposal_lands_in_the_approvals_inbox(agent, store):
    out = mr_handler.propose_create({"project_id": 12, "issue_iid": 45})
    assert out["trace_id"] in {p.trace_id for p in store.get_pending()}


def test_the_proposal_names_the_issue_so_the_approver_can_judge(agent, store):
    """Two integers are not enough to approve an irreversible external write."""
    out = mr_handler.propose_create({"project_id": 12, "issue_iid": 45})

    assert "Fix the thing" in out["description"]
    assert out["payload"]["issue_title"] == "Fix the thing"


def test_the_executor_is_registered_so_an_approved_proposal_can_run(agent, store):
    from src.core.proposal_executor import _DISPATCH

    mr_handler.propose_create({"project_id": 12, "issue_iid": 45})
    assert "mr_create" in _DISPATCH


# ---------- read/immediate operations ----------


def test_list_open_returns_merge_requests(agent):
    out = mr_handler.list_open({"project_id": 12})
    assert out["merge_requests"][0]["iid"] == 7


def test_pipeline_reports_status(agent):
    assert mr_handler.pipeline({"project_id": 12, "mr_iid": 7})["status"] == "success"


def test_comment_posts_immediately(agent):
    """Not gated: the operator clicking Post IS the decision. Law 1 gates AGENT
    proposals, not the human's own action."""
    mr_handler.comment({"project_id": 12, "mr_iid": 7, "comment": "LGTM"})
    assert ("comment", 12, 7, "LGTM") in agent.calls


def test_review_is_backgrounded_rather_than_blocking_the_loop(agent):
    """review_merge_request is a multi-round ReAct loop; running it inline would
    freeze every other RPC, including the 5s status polls."""
    out = mr_handler.review({"project_id": 12, "mr_iid": 7})
    assert out["job_id"]


# ---------- validation ----------


@pytest.mark.parametrize(
    "method,params",
    [
        ("list_open", {}),
        ("pipeline", {"project_id": 12}),
        ("comment", {"project_id": 12, "mr_iid": 7}),
        ("comment", {"project_id": 12, "mr_iid": 7, "comment": "   "}),
        ("propose_create", {"project_id": 12}),
    ],
)
def test_missing_params_are_rejected(agent, store, method, params):
    with pytest.raises(RpcError) as e:
        getattr(mr_handler, method)(params)
    assert e.value.code == INVALID_PARAMS


@pytest.mark.parametrize("bad", ["twelve", None, 1.5, True, 0, -1])
def test_project_id_must_be_a_positive_integer(agent, bad):
    with pytest.raises(RpcError) as e:
        mr_handler.list_open({"project_id": bad})
    assert e.value.code == INVALID_PARAMS


def test_an_agent_error_dict_surfaces_as_an_error(monkeypatch):
    """DeveloperAgent RETURNS {'error': ...} rather than raising; unchecked it
    would look like success."""

    class Failing(FakeAgent):
        def list_open_mrs(self, project_id):
            return {"error": "401 Unauthorized"}

    monkeypatch.setattr(mr_handler, "_agent_factory", lambda: Failing())
    with pytest.raises(RpcError) as e:
        mr_handler.list_open({"project_id": 12})
    assert "401" in str(e.value.message)
