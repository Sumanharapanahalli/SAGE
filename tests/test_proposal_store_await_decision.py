"""Tests for ProposalStore.await_decision blocking helper."""
import threading
import time
import pytest

pytestmark = pytest.mark.unit


def test_await_decision_returns_on_approve(tmp_audit_db):
    from src.core.proposal_store import get_proposal_store
    from src.core.proposal_store import RiskClass

    store = get_proposal_store()
    proposal = store.create(
        action_type="test_action",
        risk_class=RiskClass.EPHEMERAL,
        payload={"foo": "bar"},
        description="test",
        proposed_by="test",
    )

    def approve_after_delay():
        time.sleep(0.1)
        store.approve(proposal.trace_id, decided_by="tester", feedback="ok")

    threading.Thread(target=approve_after_delay, daemon=True).start()

    decision = store.await_decision(proposal.trace_id, timeout_seconds=2.0)

    assert decision is not None
    assert decision.status == "approved"
    assert decision.feedback == "ok"


def test_await_decision_returns_on_reject(tmp_audit_db):
    from src.core.proposal_store import get_proposal_store
    from src.core.proposal_store import RiskClass

    store = get_proposal_store()
    proposal = store.create(
        action_type="test_action",
        risk_class=RiskClass.EPHEMERAL,
        payload={"foo": "bar"},
        description="test",
        proposed_by="test",
    )

    def reject_after_delay():
        time.sleep(0.1)
        store.reject(proposal.trace_id, decided_by="tester", feedback="nope")

    threading.Thread(target=reject_after_delay, daemon=True).start()

    decision = store.await_decision(proposal.trace_id, timeout_seconds=2.0)

    assert decision is not None
    assert decision.status == "rejected"
    assert decision.feedback == "nope"


def test_await_decision_returns_none_on_timeout(tmp_audit_db):
    from src.core.proposal_store import get_proposal_store
    from src.core.proposal_store import RiskClass

    store = get_proposal_store()
    proposal = store.create(
        action_type="test_action",
        risk_class=RiskClass.EPHEMERAL,
        payload={"foo": "bar"},
        description="test",
        proposed_by="test",
    )

    decision = store.await_decision(proposal.trace_id, timeout_seconds=0.2)

    assert decision is None
