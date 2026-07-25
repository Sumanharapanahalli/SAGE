from pathlib import Path

import pytest

from handlers import backlog
from rpc import RpcError


@pytest.fixture
def store(tmp_path: Path):
    from src.core.feature_request_store import FeatureRequestStore

    s = FeatureRequestStore(str(tmp_path / "fr.db"))
    s.init_schema()
    return s


@pytest.fixture(autouse=True)
def inject(store):
    backlog._store = store
    yield
    backlog._store = None


def test_submit_feature_request_returns_row():
    result = backlog.submit_feature_request(
        {
            "title": "Add dark mode",
            "description": "Users want a dark theme",
            "scope": "solution",
        }
    )
    assert result["title"] == "Add dark mode"
    assert result["scope"] == "solution"
    assert result["status"] == "pending"
    assert len(result["id"]) == 36


def test_submit_feature_request_missing_title_raises_invalid_params():
    with pytest.raises(RpcError) as exc:
        backlog.submit_feature_request({"description": "no title"})
    assert exc.value.code == -32602


def test_submit_feature_request_invalid_priority_maps_to_invalid_params():
    with pytest.raises(RpcError) as exc:
        backlog.submit_feature_request(
            {"title": "t", "description": "d", "priority": "urgent"}
        )
    assert exc.value.code == -32602


def test_list_feature_requests_returns_newest_first():
    backlog.submit_feature_request({"title": "a", "description": "a"})
    backlog.submit_feature_request({"title": "b", "description": "b", "scope": "sage"})
    result = backlog.list_feature_requests({})
    assert isinstance(result, list)
    assert len(result) == 2


def test_list_feature_requests_filters_by_scope():
    backlog.submit_feature_request({"title": "a", "description": "a"})
    backlog.submit_feature_request({"title": "b", "description": "b", "scope": "sage"})
    assert len(backlog.list_feature_requests({"scope": "sage"})) == 1


def test_update_feature_request_approve_sets_status():
    created = backlog.submit_feature_request({"title": "t", "description": "d"})
    updated = backlog.update_feature_request(
        {"id": created["id"], "action": "approve", "reviewer_note": "lgtm"}
    )
    assert updated["status"] == "approved"
    assert updated["reviewer_note"] == "lgtm"


def test_update_feature_request_unknown_id_maps_to_not_found():
    with pytest.raises(RpcError) as exc:
        backlog.update_feature_request({"id": "nope", "action": "approve"})
    assert exc.value.code == -32020


def test_update_feature_request_missing_id_is_invalid_params():
    with pytest.raises(RpcError) as exc:
        backlog.update_feature_request({"action": "approve"})
    assert exc.value.code == -32602


def test_store_unavailable_raises_sage_import_error():
    backlog._store = None
    with pytest.raises(RpcError) as exc:
        backlog.list_feature_requests({})
    assert exc.value.code == -32010


# ---------- backlog.plan ----------


@pytest.fixture
def proposal_store(tmp_path: Path, monkeypatch):
    """Fresh ProposalStore backed by a temp SQLite DB, injected into handler
    — the SAME ProposalStore instance approvals.py / analyze.py use."""
    from src.core.proposal_store import ProposalStore

    db = tmp_path / "proposals.db"
    s = ProposalStore(str(db))
    monkeypatch.setattr(backlog, "_proposal_store", s)
    return s


class FakePlanner:
    """Stand-in for PlannerAgent — avoids the real LLM/vector-store stack."""

    def __init__(self, steps=None, raise_exc=None):
        self.steps = (
            steps
            if steps is not None
            else [
                {
                    "step": 1,
                    "task_type": "DEVELOP",
                    "description": "do the thing",
                    "payload": {},
                },
            ]
        )
        self.raise_exc = raise_exc
        self.calls = []

    def create_plan(self, description):
        self.calls.append(description)
        if self.raise_exc:
            raise self.raise_exc
        return self.steps


def _inject_planner(monkeypatch, planner):
    monkeypatch.setattr(backlog, "_planner_factory", lambda: planner)


def test_plan_missing_req_id_raises_invalid_params():
    with pytest.raises(RpcError) as exc:
        backlog.plan({})
    assert exc.value.code == -32602


def test_plan_unknown_req_id_raises_not_found():
    with pytest.raises(RpcError) as exc:
        backlog.plan({"req_id": "nope"})
    assert exc.value.code == -32020


def test_plan_sage_scope_returns_github_pr_without_planner_call(monkeypatch):
    created = backlog.submit_feature_request(
        {"title": "Add MCP tool", "description": "desc", "scope": "sage"}
    )
    planner = FakePlanner()
    _inject_planner(monkeypatch, planner)

    result = backlog.plan({"req_id": created["id"]})

    assert result["status"] == "github_pr"
    assert result["request_id"] == created["id"]
    assert "github.com" in result["github_issue_url"]
    assert "issues/new" in result["github_issue_url"]
    assert result["message"]
    assert planner.calls == []  # no LLM/Planner call for sage-scope

    updated = backlog._store.get(created["id"])
    assert updated.status == "github_pr"


def test_plan_solution_scope_creates_real_proposal(proposal_store, monkeypatch):
    created = backlog.submit_feature_request(
        {
            "title": "Dark mode",
            "description": "Users want dark theme",
            "scope": "solution",
        }
    )
    planner = FakePlanner()
    _inject_planner(monkeypatch, planner)

    result = backlog.plan({"req_id": created["id"]})

    assert result["status"] == "pending"
    assert result["action_type"] == "implementation_plan"
    assert result["risk_class"] == "STATEFUL"
    assert result["reversible"] is False
    assert result["proposed_by"] == "PlannerAgent"
    assert result["payload"]["feature_request_id"] == created["id"]
    assert result["payload"]["scope"] == "solution"
    assert result["payload"]["steps"] == planner.steps
    assert planner.calls and "Dark mode" in planner.calls[0]

    # The real point of this feature: it must show up in the SAME store the
    # Approvals inbox reads (approvals.list_pending), not a second mechanism.
    pending = proposal_store.get_pending()
    assert len(pending) == 1
    assert pending[0].trace_id == result["trace_id"]

    updated = backlog._store.get(created["id"])
    assert updated.status == "in_planning"
    assert updated.plan_trace_id == result["trace_id"]


def test_plan_planner_empty_steps_raises_rpc_error(proposal_store, monkeypatch):
    created = backlog.submit_feature_request(
        {"title": "Vague idea", "description": "d", "scope": "solution"}
    )
    _inject_planner(monkeypatch, FakePlanner(steps=[]))

    with pytest.raises(RpcError):
        backlog.plan({"req_id": created["id"]})

    assert proposal_store.get_pending() == []
    updated = backlog._store.get(created["id"])
    assert updated.status == "pending"  # unchanged


def test_plan_planner_raises_wraps_as_rpc_error(proposal_store, monkeypatch):
    created = backlog.submit_feature_request(
        {"title": "Broken", "description": "d", "scope": "solution"}
    )
    _inject_planner(monkeypatch, FakePlanner(raise_exc=RuntimeError("llm down")))

    with pytest.raises(RpcError):
        backlog.plan({"req_id": created["id"]})

    assert proposal_store.get_pending() == []


def test_plan_solution_scope_requires_proposal_store():
    created = backlog.submit_feature_request(
        {"title": "t", "description": "d", "scope": "solution"}
    )
    with pytest.raises(RpcError) as exc:
        backlog.plan({"req_id": created["id"]})
    assert exc.value.code == -32010
