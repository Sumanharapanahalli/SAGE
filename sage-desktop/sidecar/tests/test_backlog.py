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
    result = backlog.submit_feature_request({
        "title": "Add dark mode",
        "description": "Users want a dark theme",
        "scope": "solution",
    })
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
