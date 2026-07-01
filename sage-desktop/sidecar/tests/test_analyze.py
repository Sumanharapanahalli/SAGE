"""Tests for the analyze handler — the desktop PROPOSE trigger.

Unlike the legacy web /analyze endpoint (which stashes its result in an
in-memory dict never read by ProposalStore-backed consumers), this handler
persists the AnalystAgent's result as a REAL ProposalStore proposal so it
flows through the already-verified approvals.list_pending / approve / reject
RPCs and the desktop Approvals page.
"""
from __future__ import annotations

import pytest

from handlers import analyze as az
from rpc import RpcError


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Fresh ProposalStore backed by a temp SQLite DB, injected into handler."""
    from src.core.proposal_store import ProposalStore

    db = tmp_path / "proposals.db"
    s = ProposalStore(str(db))
    monkeypatch.setattr(az, "_store", s)
    return s


class FakeAnalyst:
    """Stand-in for AnalystAgent — avoids the real LLM/vector-store stack."""

    def __init__(self, result=None, raise_exc=None):
        self.result = result or {
            "severity": "AMBER",
            "root_cause_hypothesis": "disk usage climbing",
            "recommended_action": "rotate logs",
            "trace_id": "analyst-trace-1",
        }
        self.raise_exc = raise_exc
        self.calls = []

    def analyze_log(self, log_entry):
        self.calls.append(log_entry)
        if self.raise_exc:
            raise self.raise_exc
        return self.result


def _inject_analyst(monkeypatch, analyst):
    monkeypatch.setattr(az, "_analyst_factory", lambda: analyst)


# ---------- validation ----------

def test_run_rejects_missing_log_entry(store, monkeypatch):
    _inject_analyst(monkeypatch, FakeAnalyst())
    with pytest.raises(RpcError):
        az.run({})


def test_run_rejects_empty_log_entry(store, monkeypatch):
    _inject_analyst(monkeypatch, FakeAnalyst())
    with pytest.raises(RpcError):
        az.run({"log_entry": "   "})


def test_run_requires_store_initialized(monkeypatch):
    monkeypatch.setattr(az, "_store", None)
    _inject_analyst(monkeypatch, FakeAnalyst())
    with pytest.raises(RpcError):
        az.run({"log_entry": "disk at 95%"})


# ---------- happy path: this IS the PROPOSE trigger ----------

def test_run_creates_a_pending_proposal_from_the_analysis(store, monkeypatch):
    analyst = FakeAnalyst()
    _inject_analyst(monkeypatch, analyst)

    result = az.run({"log_entry": "disk at 95%"})

    assert result["status"] == "pending"
    assert result["action_type"] == "analysis"
    assert result["risk_class"] == "INFORMATIONAL"
    assert analyst.calls == ["disk at 95%"]

    # The real point of this feature: it must show up in the SAME store the
    # Approvals inbox reads (approvals.list_pending), not a second mechanism.
    pending = store.get_pending()
    assert len(pending) == 1
    assert pending[0].trace_id == result["trace_id"]
    assert pending[0].payload["log_entry"] == "disk at 95%"
    assert pending[0].payload["analysis"]["severity"] == "AMBER"


def test_run_description_surfaces_severity_and_summary_for_triage(store, monkeypatch):
    _inject_analyst(monkeypatch, FakeAnalyst(result={
        "severity": "RED",
        "root_cause_hypothesis": "auth service down",
        "trace_id": "t2",
    }))
    result = az.run({"log_entry": "500s spiking"})
    assert "RED" in result["description"]
    assert "auth service down" in result["description"]


# ---------- failure handling: no partial/garbage proposals ----------

def test_run_raises_and_creates_no_proposal_when_analyst_raises(store, monkeypatch):
    _inject_analyst(monkeypatch, FakeAnalyst(raise_exc=RuntimeError("llm down")))
    with pytest.raises(RpcError):
        az.run({"log_entry": "disk at 95%"})
    assert store.get_pending() == []


def test_run_raises_and_creates_no_proposal_when_analysis_has_error_key(store, monkeypatch):
    # AnalystAgent.analyze_log() returns {"error": ...} on its own internal
    # failure path (e.g. audit logger exception) rather than raising.
    _inject_analyst(monkeypatch, FakeAnalyst(result={"error": "audit log unavailable"}))
    with pytest.raises(RpcError):
        az.run({"log_entry": "disk at 95%"})
    assert store.get_pending() == []
