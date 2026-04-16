"""Tests for the status handler.

Returns a combined health/LLM/project snapshot plus a pending-approval
count so the UI can render a single-pane overview.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from handlers import status


@pytest.fixture
def wired(tmp_path, monkeypatch):
    """Wire up stub ProjectConfig + real ProposalStore + real LLMGateway stub."""
    from src.core.proposal_store import ProposalStore, RiskClass

    proj = SimpleNamespace(
        project_name="test-solution",
        project_path=str(tmp_path / "solutions" / "test-solution"),
    )
    store = ProposalStore(str(tmp_path / "proposals.db"))
    llm = SimpleNamespace(
        get_provider_name=lambda: "gemini",
        get_model_info=lambda: {"provider": "gemini", "model": "gemini-2.0-flash"},
    )
    monkeypatch.setattr(status, "_project", proj)
    monkeypatch.setattr(status, "_store", store)
    monkeypatch.setattr(status, "_llm", llm)
    return SimpleNamespace(project=proj, store=store, llm=llm, RiskClass=RiskClass)


# ---------- get ----------

def test_status_reports_ok_health(wired):
    out = status.get_status({})
    assert out["health"] == "ok"
    assert out["sidecar_version"] == status.SIDECAR_VERSION


def test_status_includes_llm_provider_and_model(wired):
    out = status.get_status({})
    assert out["llm"]["provider"] == "gemini"
    assert out["llm"]["model"] == "gemini-2.0-flash"


def test_status_includes_project_info(wired):
    out = status.get_status({})
    assert out["project"]["name"] == "test-solution"
    assert "path" in out["project"]


def test_status_counts_pending_approvals(wired):
    wired.store.create(
        action_type="t",
        risk_class=wired.RiskClass.INFORMATIONAL,
        payload={},
        description="d",
    )
    wired.store.create(
        action_type="t",
        risk_class=wired.RiskClass.INFORMATIONAL,
        payload={},
        description="d",
    )
    p3 = wired.store.create(
        action_type="t",
        risk_class=wired.RiskClass.INFORMATIONAL,
        payload={},
        description="d",
    )
    wired.store.approve(p3.trace_id)  # no longer pending

    out = status.get_status({})
    assert out["pending_approvals"] == 2


def test_status_gracefully_handles_missing_project(monkeypatch):
    monkeypatch.setattr(status, "_project", None)
    monkeypatch.setattr(status, "_store", None)
    monkeypatch.setattr(status, "_llm", None)
    out = status.get_status({})
    assert out["health"] == "ok"
    assert out["project"] is None
    assert out["llm"] is None
    assert out["pending_approvals"] == 0


def test_status_gracefully_handles_llm_errors(wired, monkeypatch):
    def boom():
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(wired.llm, "get_model_info", boom)
    out = status.get_status({})
    assert out["llm"] is None or out["llm"].get("error")
