import sqlite3
from pathlib import Path

import pytest

from src.core.feature_request_store import FeatureRequestStore


@pytest.fixture
def store(tmp_path: Path) -> FeatureRequestStore:
    s = FeatureRequestStore(str(tmp_path / "fr.db"))
    s.init_schema()
    return s


def test_init_schema_creates_feature_requests_table(store: FeatureRequestStore):
    with sqlite3.connect(store.db_path) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='feature_requests'"
        ).fetchone()
    assert row is not None


def test_init_schema_is_idempotent(store: FeatureRequestStore):
    store.init_schema()
    store.init_schema()


def test_submit_assigns_uuid_and_defaults(store: FeatureRequestStore):
    fr = store.submit(title="Add dark mode", description="Users want a dark theme")
    assert len(fr.id) == 36
    assert fr.priority == "medium"
    assert fr.scope == "solution"
    assert fr.status == "pending"
    assert fr.requested_by == "anonymous"


def test_submit_rejects_empty_title(store: FeatureRequestStore):
    with pytest.raises(ValueError, match="title"):
        store.submit(title="", description="body")


def test_submit_rejects_invalid_priority(store: FeatureRequestStore):
    with pytest.raises(ValueError, match="priority"):
        store.submit(title="x", description="y", priority="urgent")


def test_submit_rejects_invalid_scope(store: FeatureRequestStore):
    with pytest.raises(ValueError, match="scope"):
        store.submit(title="x", description="y", scope="global")


def test_list_returns_all_by_default(store: FeatureRequestStore):
    store.submit(title="a", description="a")
    store.submit(title="b", description="b", scope="sage")
    rows = store.list()
    assert len(rows) == 2


def test_list_filters_by_scope(store: FeatureRequestStore):
    store.submit(title="a", description="a")
    store.submit(title="b", description="b", scope="sage")
    assert len(store.list(scope="sage")) == 1
    assert len(store.list(scope="solution")) == 1


def test_list_filters_by_status(store: FeatureRequestStore):
    store.submit(title="a", description="a")
    assert len(store.list(status="pending")) == 1
    assert len(store.list(status="approved")) == 0


def test_get_returns_none_for_unknown_id(store: FeatureRequestStore):
    assert store.get("nope") is None


def test_get_returns_submitted_row(store: FeatureRequestStore):
    fr = store.submit(title="t", description="d")
    fetched = store.get(fr.id)
    assert fetched is not None
    assert fetched.id == fr.id


def test_update_approve_sets_status(store: FeatureRequestStore):
    fr = store.submit(title="t", description="d")
    updated = store.update(fr.id, action="approve", reviewer_note="looks good")
    assert updated.status == "approved"
    assert updated.reviewer_note == "looks good"


def test_update_reject_sets_status(store: FeatureRequestStore):
    fr = store.submit(title="t", description="d")
    updated = store.update(fr.id, action="reject")
    assert updated.status == "rejected"


def test_update_complete_sets_status(store: FeatureRequestStore):
    fr = store.submit(title="t", description="d")
    updated = store.update(fr.id, action="complete")
    assert updated.status == "completed"


def test_update_raises_keyerror_for_unknown_id(store: FeatureRequestStore):
    with pytest.raises(KeyError):
        store.update("nope", action="approve")


def test_update_raises_valueerror_for_unknown_action(store: FeatureRequestStore):
    fr = store.submit(title="t", description="d")
    with pytest.raises(ValueError, match="action"):
        store.update(fr.id, action="zap")
