"""Slice 1 — compounding memory (Law 3 / the Phase-5 feedback loop).

SOUL.md: "Never short-circuit Phase 5 (feedback ingestion). Every rejection is
a learning opportunity." It was short-circuited. Desktop's reject was a bare
SQL UPDATE: no learn_from_feedback, no add_feedback, nothing written to the
vector store — while ApprovalCard.tsx told the operator the feedback "feeds the
compounding-memory signal."

The consequence is not subtle: an operator could correct the same wrong
analysis a hundred times and the system would be exactly as wrong on the
hundred-and-first.

These tests pin the loop closed.
"""
from __future__ import annotations

import pytest

from handlers import approvals as ap


class _FakeAnalyst:
    def __init__(self):
        self.calls = []

    def learn_from_feedback(self, log_entry, human_comment, original_analysis):
        self.calls.append((log_entry, human_comment, original_analysis))


class _FakeMemory:
    def __init__(self):
        self.remembered = []

    def remember(self, text, user_id=None, metadata=None):
        self.remembered.append({"text": text, "user_id": user_id, "metadata": metadata})


@pytest.fixture
def store(tmp_path, monkeypatch):
    from src.core.proposal_store import ProposalStore

    s = ProposalStore(str(tmp_path / "proposals.db"))
    monkeypatch.setattr(ap, "_store", s)
    monkeypatch.setattr(ap, "_logger", None)  # audit tested in slice 0
    return s


@pytest.fixture
def analyst(monkeypatch):
    a = _FakeAnalyst()
    monkeypatch.setattr(ap, "_analyst_factory", lambda: a)
    return a


@pytest.fixture
def memory(monkeypatch):
    m = _FakeMemory()
    monkeypatch.setattr(ap, "_long_term_memory_factory", lambda: m)
    return m


def _make(store, action_type="analysis", payload=None):
    from src.core.proposal_store import RiskClass

    return store.create(
        action_type=action_type,
        risk_class=RiskClass.INFORMATIONAL,
        payload=payload if payload is not None else {
            "log_entry": "NullPointerException in PumpDriver",
            "analysis": {"root_cause_hypothesis": "race condition"},
        },
        description="test",
    )


# ---------- the analysis path: the correction reaches the vector store ----------

def test_rejecting_an_analysis_teaches_the_analyst(store, analyst, memory):
    p = _make(store)
    ap.reject({"trace_id": p.trace_id, "feedback": "Actually it's a buffer overrun"})

    assert len(analyst.calls) == 1, "rejection did not feed the compounding-memory loop"
    log_entry, comment, original = analyst.calls[0]
    assert log_entry == "NullPointerException in PumpDriver"
    assert comment == "Actually it's a buffer overrun"
    # The AI's original guess must be part of the lesson — a correction without
    # the thing being corrected teaches nothing.
    assert original == {"root_cause_hypothesis": "race condition"}


def test_empty_feedback_teaches_nothing(store, analyst, memory):
    """No feedback = no lesson. (The UI gates the button; the sidecar must not
    invent a lesson from an empty string.)"""
    p = _make(store)
    ap.reject({"trace_id": p.trace_id, "feedback": ""})
    assert analyst.calls == []
    assert memory.remembered == []


def test_approval_does_not_teach(store, analyst, memory):
    """learn_from_feedback exists to ingest CORRECTIONS. An approval is not a
    correction, and feeding it as one would poison retrieval."""
    p = _make(store)
    ap.approve({"trace_id": p.trace_id, "feedback": "looks right"})
    assert analyst.calls == []


# ---------- the generic path: every other action type still compounds ----------

def test_rejecting_a_non_analysis_proposal_falls_back_to_long_term_memory(
    store, analyst, memory
):
    """Mirrors api.py:1545 — a rejected yaml_edit/code_diff still teaches, just
    without the analyst's structured lesson format."""
    p = _make(store, action_type="yaml_edit", payload={"file": "prompts.yaml"})
    ap.reject({"trace_id": p.trace_id, "feedback": "wrong prompt for this domain"})

    assert analyst.calls == [], "non-analysis proposals must not go through the analyst"
    assert len(memory.remembered) == 1
    entry = memory.remembered[0]
    assert "yaml_edit" in entry["text"]
    assert "wrong prompt for this domain" in entry["text"]
    assert entry["metadata"]["trace_id"] == p.trace_id


def test_a_learning_failure_does_not_lose_the_rejection(store, monkeypatch):
    """Compounding memory is valuable but non-critical. If the vector store is
    down, the human's decision must still stand."""

    class _Boom:
        def learn_from_feedback(self, *a, **kw):
            raise RuntimeError("chroma is down")

    monkeypatch.setattr(ap, "_analyst_factory", lambda: _Boom())
    p = _make(store)
    out = ap.reject({"trace_id": p.trace_id, "feedback": "nope"})
    assert out["status"] == "rejected"


# ---------- trace_id correlation (X6) ----------

def test_analyze_threads_its_audit_trace_id_into_the_proposal(tmp_path, monkeypatch):
    """The trace_id the operator sees on a proposal must resolve in
    audit.get_by_trace. ProposalStore.create() was minting a fresh uuid4, so the
    only trace_id desktop ever showed was the one that could not be audited."""
    from handlers import analyze
    from src.core.proposal_store import ProposalStore

    s = ProposalStore(str(tmp_path / "p.db"))
    monkeypatch.setattr(analyze, "_store", s)

    class _Analyst:
        def analyze_log(self, log_entry):
            return {"severity": "HIGH", "root_cause_hypothesis": "x", "trace_id": "trace-abc"}

    monkeypatch.setattr(analyze, "_analyst_factory", lambda: _Analyst())

    out = analyze.run({"log_entry": "boom"})
    assert out["trace_id"] == "trace-abc"
