"""Tests for the HIL handler (``src.integrations.hil_runner``).

Like workflow.py/compliance.py, hil_runner is a module-level singleton
(get_hil_runner()/_hil_runner) rather than an injected instance — no
_wire_handlers wiring needed, so tests monkeypatch the module's
_hil_runner attribute / get_hil_runner factory directly.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import handlers.hil as hil  # noqa: E402
from rpc import RpcError  # noqa: E402
from src.integrations import hil_runner as hr  # noqa: E402


@pytest.fixture(autouse=True)
def reset_runner():
    """hil_runner._hil_runner is a real module-level singleton — reset it
    around every test so tests don't leak state into each other."""
    hr._hil_runner = None
    yield
    hr._hil_runner = None


# ---------- hil.status ----------


def test_status_reports_not_initialised_when_no_runner():
    out = hil.status({})
    assert out["connected"] is False
    assert out["transport"] == "none"
    assert out["session_id"] is None
    assert "message" in out


def test_status_reports_real_runner_status():
    out = hil.connect({"transport": "mock"})
    assert out["connected"] is True
    status = hil.status({})
    assert status["connected"] is True
    assert status["transport"] == "mock"


# ---------- hil.connect ----------


def test_connect_defaults_to_mock_transport():
    out = hil.connect({})
    assert out["transport"] == "mock"
    assert out["connected"] is True
    assert out["session_id"]


def test_connect_rejects_unknown_transport():
    with pytest.raises(RpcError) as e:
        hil.connect({"transport": "carrier-pigeon"})
    assert e.value.code == -32602


def test_connect_rejects_non_dict_config():
    with pytest.raises(RpcError) as e:
        hil.connect({"config": "not-a-dict"})
    assert e.value.code == -32602


# ---------- hil.run_suite ----------


def test_run_suite_requires_nonempty_tests_list():
    with pytest.raises(RpcError) as e:
        hil.run_suite({})
    assert e.value.code == -32602

    with pytest.raises(RpcError) as e2:
        hil.run_suite({"tests": []})
    assert e2.value.code == -32602


def test_run_suite_mock_transport_runs_and_summarizes():
    out = hil.run_suite({
        "tests": [
            {
                "id": "TC-001",
                "name": "Power-on self test",
                "requirement_id": "REQ-001",
                "description": "Device boots cleanly",
                "procedure": ["Power on", "Observe LED"],
                "expected_result": "LED green within 2s",
            },
        ],
    })
    assert out["total"] == 1
    assert out["passed"] == 1
    assert out["transport"] == "mock"
    assert out["results"][0]["test_id"] == "TC-001"
    assert out["results"][0]["verdict"] == "PASS"


def test_run_suite_auto_connects_if_not_connected():
    out = hil.run_suite({"tests": [{"id": "TC-002", "name": "t", "requirement_id": "R",
                                     "description": "", "procedure": [], "expected_result": ""}]})
    assert out["results"][0]["verdict"] == "PASS"
    status = hil.status({})
    assert status["connected"] is True


# ---------- hil.report ----------


def test_report_requires_session_id():
    with pytest.raises(RpcError) as e:
        hil.report({})
    assert e.value.code == -32602


def test_report_rejects_unknown_session():
    hil.connect({"transport": "mock"})
    with pytest.raises(RpcError) as e:
        hil.report({"session_id": "no-such-session"})
    assert e.value.code == -32602


def test_report_returns_evidence_for_current_session():
    hil.run_suite({"tests": [{"id": "TC-003", "name": "t", "requirement_id": "REQ-003",
                               "description": "", "procedure": [], "expected_result": ""}]})
    session_id = hil.status({})["session_id"]
    out = hil.report({"session_id": session_id, "standard": "IEC62304"})
    assert out["standard"] == "IEC62304"
    assert out["session_id"] == session_id
    assert out["summary"]["total_tests"] == 1


def test_report_defaults_to_iec62304():
    hil.run_suite({"tests": [{"id": "TC-004", "name": "t", "requirement_id": "REQ-004",
                               "description": "", "procedure": [], "expected_result": ""}]})
    session_id = hil.status({})["session_id"]
    out = hil.report({"session_id": session_id})
    assert out["standard"] == "IEC62304"
