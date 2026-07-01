"""Tests for the workflow handler (``src.integrations.langgraph_runner``).

Like compliance_flags.py, langgraph_runner is a singleton *instance*
imported directly at call time (no ``_wire_handlers`` injection needed) —
so these tests monkeypatch the singleton's bound methods directly rather
than a handler-module-level variable (contrast with handlers.builds's
``_orch`` module var, which is wired at sidecar startup).

Error mapping mirrors handlers.builds's dict-with-"error"-key convention:
    ``{"error": "..."}`` from run/resume/status -> ``RPC_INVALID_PARAMS``
    Python exception -> ``RPC_SIDECAR_ERROR``
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import handlers.workflow as workflow  # noqa: E402
from rpc import RpcError  # noqa: E402
from src.integrations.langgraph_runner import langgraph_runner  # noqa: E402


def test_list_workflows_degrades_gracefully_with_no_workflows_loaded(monkeypatch):
    # langgraph_runner reads the framework-global project_config singleton
    # directly. Other tests in this same pytest process (e.g. test_main.py's
    # sidecar wiring tests) legitimately reload it to "starter", which DOES
    # have a workflows/ directory — so this test cannot rely on whatever
    # project_config._name happens to be right now. Force it to a solution
    # name guaranteed not to exist, to deterministically exercise the real
    # graceful-degradation path (no mocking of list_workflows itself):
    # confirms it cleanly returns an empty result instead of raising when
    # there's nothing to discover.
    from src.core.project_loader import project_config

    monkeypatch.setattr(project_config, "_name", "no-such-solution-xyz")
    out = workflow.list_workflows({})
    assert out == {"workflows": [], "count": 0}


def test_list_workflows_returns_names_and_count(monkeypatch):
    monkeypatch.setattr(
        langgraph_runner, "list_workflows", lambda: [{"name": "analysis_workflow"}]
    )
    out = workflow.list_workflows({})
    assert out == {"workflows": [{"name": "analysis_workflow"}], "count": 1}


def test_list_workflows_wraps_unexpected_exception_as_sidecar_error(monkeypatch):
    def boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(langgraph_runner, "list_workflows", boom)
    with pytest.raises(RpcError) as e:
        workflow.list_workflows({})
    assert e.value.code == -32000


def test_run_requires_workflow_name():
    with pytest.raises(RpcError) as e:
        workflow.run({})
    assert e.value.code == -32602


def test_run_rejects_non_dict_state():
    with pytest.raises(RpcError) as e:
        workflow.run({"workflow_name": "analysis_workflow", "state": "not-a-dict"})
    assert e.value.code == -32602


def test_run_happy_path_forwards_args(monkeypatch):
    captured = {}

    def fake_run(name, state):
        captured["name"] = name
        captured["state"] = state
        return {
            "run_id": "r1",
            "status": "completed",
            "workflow_name": name,
            "result": {"ok": True},
        }

    monkeypatch.setattr(langgraph_runner, "run", fake_run)
    out = workflow.run({"workflow_name": "analysis_workflow", "state": {"task": "x"}})
    assert out["run_id"] == "r1"
    assert out["status"] == "completed"
    assert captured["name"] == "analysis_workflow"
    assert captured["state"] == {"task": "x"}


def test_run_defaults_state_to_empty_dict(monkeypatch):
    captured = {}

    def fake_run(name, state):
        captured["state"] = state
        return {"run_id": "r1", "status": "completed", "workflow_name": name, "result": {}}

    monkeypatch.setattr(langgraph_runner, "run", fake_run)
    workflow.run({"workflow_name": "analysis_workflow"})
    assert captured["state"] == {}


def test_run_maps_error_key_to_invalid_params(monkeypatch):
    monkeypatch.setattr(
        langgraph_runner,
        "run",
        lambda *_a, **_kw: {
            "error": "Workflow 'x' not found. Available: []",
            "run_id": "r1",
        },
    )
    with pytest.raises(RpcError) as e:
        workflow.run({"workflow_name": "x"})
    assert e.value.code == -32602


def test_run_wraps_unexpected_exception_as_sidecar_error(monkeypatch):
    def boom(*_a, **_kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(langgraph_runner, "run", boom)
    with pytest.raises(RpcError) as e:
        workflow.run({"workflow_name": "analysis_workflow"})
    assert e.value.code == -32000


def test_resume_requires_run_id():
    with pytest.raises(RpcError) as e:
        workflow.resume({})
    assert e.value.code == -32602


def test_resume_rejects_non_dict_feedback():
    with pytest.raises(RpcError) as e:
        workflow.resume({"run_id": "r1", "feedback": "nope"})
    assert e.value.code == -32602


def test_resume_happy_path_forwards_args(monkeypatch):
    captured = {}

    def fake_resume(run_id, feedback):
        captured["run_id"] = run_id
        captured["feedback"] = feedback
        return {
            "run_id": run_id,
            "status": "completed",
            "workflow_name": "analysis_workflow",
            "result": {"ok": True},
        }

    monkeypatch.setattr(langgraph_runner, "resume", fake_resume)
    out = workflow.resume({"run_id": "r1", "feedback": {"approved": True}})
    assert out["status"] == "completed"
    assert captured["run_id"] == "r1"
    assert captured["feedback"] == {"approved": True}


def test_resume_defaults_feedback_to_empty_dict(monkeypatch):
    captured = {}

    def fake_resume(run_id, feedback):
        captured["feedback"] = feedback
        return {"run_id": run_id, "status": "completed", "workflow_name": "x", "result": {}}

    monkeypatch.setattr(langgraph_runner, "resume", fake_resume)
    workflow.resume({"run_id": "r1"})
    assert captured["feedback"] == {}


def test_resume_maps_error_key_to_invalid_params(monkeypatch):
    monkeypatch.setattr(
        langgraph_runner,
        "resume",
        lambda *_a, **_kw: {"error": "Run 'r1' not found", "run_id": "r1"},
    )
    with pytest.raises(RpcError) as e:
        workflow.resume({"run_id": "r1"})
    assert e.value.code == -32602


def test_resume_wraps_unexpected_exception_as_sidecar_error(monkeypatch):
    def boom(*_a, **_kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(langgraph_runner, "resume", boom)
    with pytest.raises(RpcError) as e:
        workflow.resume({"run_id": "r1"})
    assert e.value.code == -32000


def test_status_requires_run_id():
    with pytest.raises(RpcError) as e:
        workflow.status({})
    assert e.value.code == -32602


def test_status_happy_path(monkeypatch):
    monkeypatch.setattr(
        langgraph_runner,
        "get_status",
        lambda run_id: {
            "run_id": run_id,
            "workflow_name": "analysis_workflow",
            "status": "completed",
        },
    )
    out = workflow.status({"run_id": "r1"})
    assert out["status"] == "completed"
    assert out["run_id"] == "r1"


def test_status_maps_error_key_to_invalid_params(monkeypatch):
    monkeypatch.setattr(
        langgraph_runner,
        "get_status",
        lambda run_id: {"error": f"Run '{run_id}' not found", "run_id": run_id},
    )
    with pytest.raises(RpcError) as e:
        workflow.status({"run_id": "missing"})
    assert e.value.code == -32602


def test_status_wraps_unexpected_exception_as_sidecar_error(monkeypatch):
    def boom(_run_id):
        raise RuntimeError("boom")

    monkeypatch.setattr(langgraph_runner, "get_status", boom)
    with pytest.raises(RpcError) as e:
        workflow.status({"run_id": "r1"})
    assert e.value.code == -32000
