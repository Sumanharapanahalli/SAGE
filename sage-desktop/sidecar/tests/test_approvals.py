"""Tests for the approvals handler.

The approvals handler wraps src.core.proposal_store.ProposalStore and
translates ValueError into the domain-specific RpcError subclasses defined
in errors.py so the Rust side can map them to typed DesktopError variants.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from handlers import approvals as ap
from errors import ProposalNotFound, AlreadyDecided, ProposalExpired
from rpc import RpcError


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Fresh ProposalStore backed by a temp SQLite DB, injected into handler."""
    from src.core.proposal_store import ProposalStore

    db = tmp_path / "proposals.db"
    s = ProposalStore(str(db))
    monkeypatch.setattr(ap, "_store", s)
    return s


def _make_proposal(store, **kwargs):
    from src.core.proposal_store import RiskClass

    defaults = dict(
        action_type="test_action",
        risk_class=RiskClass.INFORMATIONAL,
        payload={"key": "value"},
        description="Test proposal",
    )
    defaults.update(kwargs)
    return store.create(**defaults)


# ---------- list_pending ----------

def test_list_pending_returns_empty_when_no_proposals(store):
    out = ap.list_pending({})
    assert out == []


def test_list_pending_returns_only_pending_proposals(store):
    p1 = _make_proposal(store, description="one")
    p2 = _make_proposal(store, description="two")
    p3 = _make_proposal(store, description="three")
    store.approve(p2.trace_id)  # no longer pending

    out = ap.list_pending({})
    trace_ids = {p["trace_id"] for p in out}
    assert trace_ids == {p1.trace_id, p3.trace_id}
    # JSON-safe: risk_class is a string, not enum
    assert all(isinstance(p["risk_class"], str) for p in out)


def test_list_pending_serializes_enums_and_datetimes_as_json(store):
    p = _make_proposal(store)
    out = ap.list_pending({})
    assert len(out) == 1
    row = out[0]
    assert row["trace_id"] == p.trace_id
    assert row["risk_class"] == "INFORMATIONAL"
    assert isinstance(row["created_at"], str)  # datetime serialized to ISO
    assert isinstance(row["expires_at"], str)
    assert row["status"] == "pending"


# ---------- get ----------

def test_get_returns_proposal_by_trace_id(store):
    p = _make_proposal(store)
    out = ap.get({"trace_id": p.trace_id})
    assert out["trace_id"] == p.trace_id
    assert out["description"] == "Test proposal"


def test_get_raises_proposal_not_found_for_unknown_trace_id(store):
    with pytest.raises(ProposalNotFound) as exc_info:
        ap.get({"trace_id": "does-not-exist"})
    assert "does-not-exist" in str(exc_info.value)


def test_get_requires_trace_id_param(store):
    with pytest.raises(RpcError):
        ap.get({})


# ---------- approve ----------

def test_approve_marks_proposal_as_approved(store):
    p = _make_proposal(store)
    out = ap.approve({"trace_id": p.trace_id, "decided_by": "alice"})
    assert out["status"] == "approved"
    assert out["decided_by"] == "alice"


def test_approve_passes_feedback_through(store):
    p = _make_proposal(store)
    out = ap.approve({
        "trace_id": p.trace_id,
        "decided_by": "alice",
        "feedback": "looks good",
    })
    assert out["feedback"] == "looks good"


def test_approve_raises_not_found_for_unknown_trace_id(store):
    with pytest.raises(ProposalNotFound):
        ap.approve({"trace_id": "nope", "decided_by": "alice"})


def test_approve_raises_already_decided_when_approved_twice(store):
    p = _make_proposal(store)
    ap.approve({"trace_id": p.trace_id, "decided_by": "alice"})
    with pytest.raises(AlreadyDecided) as exc_info:
        ap.approve({"trace_id": p.trace_id, "decided_by": "bob"})
    assert exc_info.value.data["status"] == "approved"


def test_approve_raises_already_decided_when_rejected_already(store):
    p = _make_proposal(store)
    store.reject(p.trace_id, decided_by="alice")
    with pytest.raises(AlreadyDecided) as exc_info:
        ap.approve({"trace_id": p.trace_id, "decided_by": "bob"})
    assert exc_info.value.data["status"] == "rejected"


def test_approve_raises_proposal_expired_when_expired(store):
    p = _make_proposal(store)
    # Manually mark the proposal as expired in the DB
    import sqlite3
    conn = sqlite3.connect(store.db_path)
    conn.execute("UPDATE proposals SET status='expired' WHERE trace_id=?", (p.trace_id,))
    conn.commit()
    conn.close()
    with pytest.raises(ProposalExpired):
        ap.approve({"trace_id": p.trace_id, "decided_by": "alice"})


# ---------- reject ----------

def test_reject_marks_proposal_as_rejected(store):
    p = _make_proposal(store)
    out = ap.reject({"trace_id": p.trace_id, "decided_by": "alice", "feedback": "nope"})
    assert out["status"] == "rejected"
    assert out["feedback"] == "nope"


def test_reject_raises_not_found_for_unknown_trace_id(store):
    with pytest.raises(ProposalNotFound):
        ap.reject({"trace_id": "nope", "decided_by": "alice"})


def test_reject_raises_already_decided_when_approved(store):
    p = _make_proposal(store)
    store.approve(p.trace_id)
    with pytest.raises(AlreadyDecided):
        ap.reject({"trace_id": p.trace_id, "decided_by": "alice"})


# ---------- batch_approve ----------

def test_batch_approve_approves_all_and_returns_per_item_results(store):
    p1 = _make_proposal(store)
    p2 = _make_proposal(store)
    out = ap.batch_approve({
        "trace_ids": [p1.trace_id, p2.trace_id],
        "decided_by": "alice",
    })
    assert len(out["results"]) == 2
    assert all(r["ok"] is True for r in out["results"])
    # Verify both are actually approved in the store
    assert store.get(p1.trace_id).status == "approved"
    assert store.get(p2.trace_id).status == "approved"


def test_batch_approve_reports_failures_without_aborting(store):
    p1 = _make_proposal(store)
    p2 = _make_proposal(store)
    store.approve(p2.trace_id)  # already decided → second entry will fail

    out = ap.batch_approve({
        "trace_ids": [p1.trace_id, p2.trace_id, "unknown"],
        "decided_by": "alice",
    })
    results = out["results"]
    assert len(results) == 3
    by_id = {r["trace_id"]: r for r in results}
    assert by_id[p1.trace_id]["ok"] is True
    assert by_id[p2.trace_id]["ok"] is False
    assert by_id[p2.trace_id]["error"]["code"] == AlreadyDecided("x", "approved").code
    assert by_id["unknown"]["ok"] is False
    assert by_id["unknown"]["error"]["code"] == ProposalNotFound("x").code


def test_batch_approve_with_empty_list_returns_empty_results(store):
    out = ap.batch_approve({"trace_ids": [], "decided_by": "alice"})
    assert out["results"] == []
