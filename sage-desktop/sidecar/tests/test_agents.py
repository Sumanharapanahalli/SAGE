"""Tests for the agents handler.

The agents handler enumerates agent roles from prompts.yaml (via the
loaded ProjectConfig) and enriches each with activity stats pulled from
the audit log (event count + last-active timestamp per actor).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from handlers import agents


@pytest.fixture
def audit_logger(tmp_path, monkeypatch):
    """Shared fixture: fresh AuditLogger injected into handlers.audit module."""
    from src.memory.audit_logger import AuditLogger
    from handlers import audit

    db = tmp_path / "audit.db"
    lg = AuditLogger(db_path=str(db))
    monkeypatch.setattr(audit, "_logger", lg)
    monkeypatch.setattr(agents, "_logger", lg)
    return lg


@pytest.fixture
def project(monkeypatch):
    """Stub ProjectConfig with a known prompts/roles layout."""
    stub = SimpleNamespace(
        project_name="test-solution",
        get_prompts=lambda: {
            "analyst": {"system": "You are an analyst."},
            "developer": {"system": "You are a developer."},
            "planner": {"system": "You are a planner."},
            "monitor": {"system": "You are a monitor."},
            "roles": {
                "strategic_advisor": {
                    "description": "High-level strategy",
                    "system": "Be strategic.",
                },
                "technical_reviewer": {
                    "description": "Code review",
                    "system": "Review carefully.",
                },
            },
        },
    )
    monkeypatch.setattr(agents, "_project", stub)
    return stub


# ---------- list ----------

def test_list_returns_core_agent_roles(project, audit_logger):
    out = agents.list_agents({})
    names = {a["name"] for a in out}
    assert "analyst" in names
    assert "developer" in names
    assert "planner" in names
    assert "monitor" in names


def test_list_returns_custom_roles_under_roles_key(project, audit_logger):
    out = agents.list_agents({})
    names = {a["name"] for a in out}
    assert "strategic_advisor" in names
    assert "technical_reviewer" in names


def test_list_enriches_with_activity_counts_from_audit_log(project, audit_logger):
    audit_logger.log_event(
        actor="analyst", action_type="ANALYSIS",
        input_context="i", output_content="o",
    )
    audit_logger.log_event(
        actor="analyst", action_type="PROPOSAL",
        input_context="i", output_content="o",
    )
    audit_logger.log_event(
        actor="developer", action_type="PROPOSAL",
        input_context="i", output_content="o",
    )

    out = agents.list_agents({})
    by_name = {a["name"]: a for a in out}
    assert by_name["analyst"]["event_count"] == 2
    assert by_name["developer"]["event_count"] == 1
    assert by_name["planner"]["event_count"] == 0


def test_list_returns_last_active_timestamp_when_activity_exists(project, audit_logger):
    audit_logger.log_event(
        actor="analyst", action_type="ANALYSIS",
        input_context="i", output_content="o",
    )
    out = agents.list_agents({})
    by_name = {a["name"]: a for a in out}
    assert by_name["analyst"]["last_active"] is not None
    assert by_name["planner"]["last_active"] is None


def test_list_returns_empty_when_no_project_loaded(monkeypatch, audit_logger):
    monkeypatch.setattr(agents, "_project", None)
    out = agents.list_agents({})
    assert out == []


# ---------- get ----------

def test_get_returns_full_role_details(project, audit_logger):
    out = agents.get_agent({"name": "analyst"})
    assert out["name"] == "analyst"
    assert out["system_prompt"] == "You are an analyst."


def test_get_returns_custom_role_details(project, audit_logger):
    out = agents.get_agent({"name": "strategic_advisor"})
    assert out["name"] == "strategic_advisor"
    assert out["description"] == "High-level strategy"
    assert out["system_prompt"] == "Be strategic."


def test_get_raises_for_unknown_agent(project, audit_logger):
    from rpc import RpcError
    with pytest.raises(RpcError):
        agents.get_agent({"name": "does-not-exist"})


def test_get_requires_name_param(project, audit_logger):
    from rpc import RpcError
    with pytest.raises(RpcError):
        agents.get_agent({})
