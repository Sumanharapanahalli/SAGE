"""Tests for the agentrun handler — running an agent from the desktop.

The load-bearing assertion in here is that agents.run PERSISTS. The web
API's POST /agent/run returns "status": "pending_review" and stores nothing,
so its approval banner is decorative. These tests pin the Law-1 behaviour:
the run lands in the SAME ProposalStore the Approvals inbox reads.
"""
from __future__ import annotations

import pytest

from handlers import agentrun as ar
from rpc import RpcError


@pytest.fixture
def store(tmp_path, monkeypatch):
    from src.core.proposal_store import ProposalStore

    s = ProposalStore(str(tmp_path / "proposals.db"))
    monkeypatch.setattr(ar, "_store", s)
    monkeypatch.setattr(ar, "_solution_name", "testsol")
    return s


class FakeProject:
    """Stand-in for ProjectConfig."""

    def __init__(self, roles=None, metadata=None):
        self._roles = roles if roles is not None else {
            "marketing_strategist": {
                "name": "Marketing Strategist",
                "description": "Go-to-market",
                "icon": "📣",
                "system_prompt": "You are a marketing strategist.",
            }
        }
        self._metadata = metadata if metadata is not None else {
            "project": "testsol",
            "name": "Test Solution",
            "domain": "medical_devices",
            "active_modules": ["analyst"],
            "ui_labels": {"input": "Log"},
            "dashboard": {"tiles": ["approvals"]},
            "theme": {"primary": "#123456"},
        }
        self.project_name = "testsol"

    def get_prompts(self):
        return {"analyst": {"system_prompt": "x"}, "roles": self._roles}

    @property
    def metadata(self):
        return self._metadata


class FakeAgent:
    """Stand-in for UniversalAgent — no LLM, no vector store."""

    def __init__(self, result=None, raise_exc=None):
        self.result = result if result is not None else {
            "trace_id": "agent-trace-1",
            "role_id": "marketing_strategist",
            "role_name": "Marketing Strategist",
            "icon": "📣",
            "summary": "Launch in two phases",
            "analysis": "long form",
            "recommendations": ["Do A"],
            "next_steps": ["Step 1"],
            "severity": "GREEN",
            "confidence": "HIGH",
            "status": "pending_review",
        }
        self.raise_exc = raise_exc
        self.calls = []

    def run(self, role_id, task, context="", actor="web-ui"):
        self.calls.append({"role_id": role_id, "task": task, "context": context, "actor": actor})
        if self.raise_exc:
            raise self.raise_exc
        return self.result


@pytest.fixture
def project(monkeypatch):
    p = FakeProject()
    monkeypatch.setattr(ar, "_project", p)
    return p


def _inject_agent(monkeypatch, agent):
    monkeypatch.setattr(ar, "_agent_factory", lambda: agent)
    return agent


# ---------- agents.run: validation ----------

def test_run_rejects_missing_role_id(store, project, monkeypatch):
    _inject_agent(monkeypatch, FakeAgent())
    with pytest.raises(RpcError):
        ar.run({"task": "Draft a plan"})


def test_run_rejects_empty_task(store, project, monkeypatch):
    _inject_agent(monkeypatch, FakeAgent())
    with pytest.raises(RpcError):
        ar.run({"role_id": "marketing_strategist", "task": "   "})


def test_run_requires_store_initialized(project, monkeypatch):
    monkeypatch.setattr(ar, "_store", None)
    _inject_agent(monkeypatch, FakeAgent())
    with pytest.raises(RpcError):
        ar.run({"role_id": "marketing_strategist", "task": "Draft a plan"})


def test_run_maps_unknown_role_value_error_to_invalid_params(store, project, monkeypatch):
    _inject_agent(monkeypatch, FakeAgent(raise_exc=ValueError("Role 'nope' not found")))
    with pytest.raises(RpcError) as exc:
        ar.run({"role_id": "nope", "task": "Draft a plan"})
    assert exc.value.code == -32602
    assert store.get_pending() == []


# ---------- agents.run: the Law-1 fix ----------

def test_run_persists_a_real_pending_proposal(store, project, monkeypatch):
    agent = _inject_agent(monkeypatch, FakeAgent())

    out = ar.run({
        "role_id": "marketing_strategist",
        "task": "Draft a go-to-market plan",
        "context": "B2B SaaS",
    })

    assert out["result"]["summary"] == "Launch in two phases"
    assert out["proposal"]["status"] == "pending"
    assert out["proposal"]["action_type"] == "agent_run"
    assert out["proposal"]["proposed_by"] == "marketing_strategist"
    assert agent.calls[0]["context"] == "B2B SaaS"
    assert agent.calls[0]["actor"] == "desktop-operator"

    # The point: it lands in the store the Approvals inbox reads.
    pending = store.get_pending()
    assert len(pending) == 1
    assert pending[0].payload["role_id"] == "marketing_strategist"
    assert pending[0].payload["result"]["summary"] == "Launch in two phases"


def test_run_adopts_the_agent_trace_id_so_the_audit_log_resolves(store, project, monkeypatch):
    _inject_agent(monkeypatch, FakeAgent())
    out = ar.run({"role_id": "marketing_strategist", "task": "Draft a plan"})
    assert out["proposal"]["trace_id"] == "agent-trace-1"
    assert out["result"]["trace_id"] == "agent-trace-1"


def test_run_description_surfaces_severity_and_role(store, project, monkeypatch):
    _inject_agent(monkeypatch, FakeAgent(result={
        "trace_id": "t2",
        "role_name": "Marketing Strategist",
        "summary": "Pricing is the blocker",
        "severity": "RED",
    }))
    out = ar.run({"role_id": "marketing_strategist", "task": "Review pricing"})
    assert "RED" in out["proposal"]["description"]
    assert "Pricing is the blocker" in out["proposal"]["description"]


def test_run_sanitizes_control_chars_and_caps_task_length(store, project, monkeypatch):
    agent = _inject_agent(monkeypatch, FakeAgent())
    ar.run({"role_id": "marketing_strategist", "task": "a\x00b" + "x" * 5000})
    sent = agent.calls[0]["task"]
    assert "\x00" not in sent
    assert len(sent) == 4000


def test_run_creates_no_proposal_when_the_agent_fails(store, project, monkeypatch):
    _inject_agent(monkeypatch, FakeAgent(raise_exc=RuntimeError("llm down")))
    with pytest.raises(RpcError):
        ar.run({"role_id": "marketing_strategist", "task": "Draft a plan"})
    assert store.get_pending() == []


# ---------- agents.hire: mutation => proposal, never a direct write ----------

_HIRE = {
    "role_id": "security_reviewer",
    "name": "Security Reviewer",
    "description": "Reviews diffs for security defects",
    "icon": "🔐",
    "system_prompt": "You are a senior security reviewer.",
    "task_types": ["REVIEW_SECURITY"],
}


def test_hire_creates_an_agent_hire_proposal(store, project):
    out = ar.hire(dict(_HIRE))
    assert out["action_type"] == "agent_hire"
    assert out["risk_class"] == "STATEFUL"
    assert out["status"] == "pending"
    assert out["payload"]["role_id"] == "security_reviewer"
    # proposal_executor._execute_agent_hire resolves the YAML files from this.
    assert out["payload"]["solution"] == "testsol"
    assert out["payload"]["task_types"] == ["REVIEW_SECURITY"]
    assert len(store.get_pending()) == 1


def test_hire_rejects_a_non_snake_case_role_id(store, project):
    with pytest.raises(RpcError):
        ar.hire({**_HIRE, "role_id": "Security Reviewer"})
    assert store.get_pending() == []


def test_hire_rejects_a_duplicate_role(store, project):
    with pytest.raises(RpcError):
        ar.hire({**_HIRE, "role_id": "marketing_strategist"})
    assert store.get_pending() == []


def test_hire_requires_a_system_prompt(store, project):
    payload = dict(_HIRE)
    payload.pop("system_prompt")
    with pytest.raises(RpcError):
        ar.hire(payload)


def test_hire_rejects_non_string_task_types(store, project):
    with pytest.raises(RpcError):
        ar.hire({**_HIRE, "task_types": [{"name": "X"}]})


# ---------- agents.analyze_jd ----------

def test_analyze_jd_returns_the_extracted_config(project, monkeypatch):
    captured = {}

    def fake_jd(jd_text, solution_context=""):
        captured["jd_text"] = jd_text
        captured["solution_context"] = solution_context
        return {"role_key": "security_reviewer", "name": "Security Reviewer"}

    monkeypatch.setattr(ar, "_jd_factory", lambda: fake_jd)
    out = ar.analyze_jd({"jd_text": "We need someone to review firmware diffs."})
    assert out["role_key"] == "security_reviewer"
    # Falls back to the solution's domain when no context is supplied.
    assert captured["solution_context"] == "medical_devices"


def test_analyze_jd_rejects_empty_jd(project, monkeypatch):
    monkeypatch.setattr(ar, "_jd_factory", lambda: lambda *a, **k: {})
    with pytest.raises(RpcError):
        ar.analyze_jd({"jd_text": "  "})


def test_analyze_jd_maps_unparseable_llm_output_to_invalid_params(project, monkeypatch):
    def boom(jd_text, solution_context=""):
        raise ValueError("Could not parse LLM response as JSON")

    monkeypatch.setattr(ar, "_jd_factory", lambda: boom)
    with pytest.raises(RpcError) as exc:
        ar.analyze_jd({"jd_text": "review firmware"})
    assert exc.value.code == -32602


def test_analyze_jd_maps_missing_llm_gateway_to_sidecar_error(project, monkeypatch):
    def boom(jd_text, solution_context=""):
        raise RuntimeError("LLM gateway is not configured.")

    monkeypatch.setattr(ar, "_jd_factory", lambda: boom)
    with pytest.raises(RpcError) as exc:
        ar.analyze_jd({"jd_text": "review firmware"})
    assert exc.value.code == -32000


# ---------- config.get_project ----------

def test_get_project_returns_the_parsed_project_yaml(project):
    out = ar.get_project({})
    assert out["ui_labels"] == {"input": "Log"}
    assert out["dashboard"] == {"tiles": ["approvals"]}
    assert out["active_modules"] == ["analyst"]
    assert out["theme"] == {"primary": "#123456"}


def test_get_project_lists_the_runnable_universal_agent_roles(project):
    out = ar.get_project({})
    assert out["agents"] == [
        {
            "id": "marketing_strategist",
            "name": "Marketing Strategist",
            "description": "Go-to-market",
            "icon": "📣",
        }
    ]


def test_get_project_errors_when_no_solution_is_loaded(monkeypatch):
    monkeypatch.setattr(ar, "_project", None)
    with pytest.raises(RpcError):
        ar.get_project({})
