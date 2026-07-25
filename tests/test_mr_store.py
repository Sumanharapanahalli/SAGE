"""Tests for the Merge-Gate Governance MRStore."""

import pytest

from src.core.mr_store import MRStore, MR_STATES

pytestmark = pytest.mark.unit


@pytest.fixture
def store(tmp_path):
    db_path = str(tmp_path / "test_mr.db")
    return MRStore(db_path)


def test_create_get_roundtrip(store: MRStore):
    mr_id = store.create("WI-101", "feature/login")
    assert mr_id
    row = store.get(mr_id)
    assert row is not None
    assert row["id"] == mr_id
    assert row["work_item"] == "WI-101"
    assert row["branch"] == "feature/login"
    assert row["state"] == "coding"
    assert row["created_at"]
    assert row["updated_at"]
    assert row["evidence"] == {}


def test_get_nonexistent_returns_none(store: MRStore):
    assert store.get("does-not-exist") is None


def test_update_state_lifecycle(store: MRStore):
    mr_id = store.create("WI-202", "feature/pay")
    for state in MR_STATES:
        store.update(mr_id, state=state)
        assert store.get(mr_id)["state"] == state


def test_update_invalid_state_raises(store: MRStore):
    mr_id = store.create("WI-303", "feature/x")
    with pytest.raises(ValueError):
        store.update(mr_id, state="bogus")
    # Rejected update must not have mutated the row.
    assert store.get(mr_id)["state"] == "coding"


def test_update_unknown_field_raises(store: MRStore):
    mr_id = store.create("WI-404", "feature/y")
    with pytest.raises(ValueError):
        store.update(mr_id, statuz="review")  # typo'd field name
    with pytest.raises(ValueError):
        store.update(mr_id, work_item="WI-999")  # not an updatable field


def test_evidence_dict_roundtrips(store: MRStore):
    mr_id = store.create("WI-505", "feature/z")
    evidence = {"tests": {"passed": 12, "failed": 0}, "verify": "8/8"}
    store.update(mr_id, evidence=evidence)
    row = store.get(mr_id)
    assert row["evidence"] == evidence
    assert row["evidence"]["tests"]["passed"] == 12
    assert row["evidence"]["verify"] == "8/8"


def test_list_newest_first(store: MRStore):
    first = store.create("WI-1", "b1")
    second = store.create("WI-2", "b2")
    third = store.create("WI-3", "b3")
    rows = store.list()
    ids = [r["id"] for r in rows]
    assert ids == [third, second, first]


def test_list_filter_by_state(store: MRStore):
    a = store.create("WI-A", "ba")
    b = store.create("WI-B", "bb")
    store.create("WI-C", "bc")
    store.update(a, state="merged")
    store.update(b, state="merged")

    merged = store.list(state="merged")
    assert len(merged) == 2
    assert {r["id"] for r in merged} == {a, b}
    assert all(r["state"] == "merged" for r in merged)

    # Empty string means "no filter" — returns all three.
    assert len(store.list()) == 3
    assert len(store.list(state="")) == 3


def test_pr_and_sha_and_error_fields_roundtrip(store: MRStore):
    mr_id = store.create("WI-606", "feature/pr")
    store.update(
        mr_id,
        pr_number=42,
        pr_url="https://example.com/pr/42",
        merged_sha="deadbeefcafe",
        error="flaky test on CI",
    )
    row = store.get(mr_id)
    assert row["pr_number"] == 42
    assert row["pr_url"] == "https://example.com/pr/42"
    assert row["merged_sha"] == "deadbeefcafe"
    assert row["error"] == "flaky test on CI"
