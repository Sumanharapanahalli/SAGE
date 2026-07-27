"""Tests for src.integrations.hil_runner mock-transport behaviour.

The HIL runner must work with a mock transport (no hardware) for CI/dev.
Previously untested (SAGE self-improvement loop, issue #23).
"""

from src.integrations.hil_runner import (
    HILRunner,
    HILTransport,
    get_hil_runner,
)
from src.integrations.hil_runner import TestVerdict as Verdict  # avoid pytest collect


def test_verdict_and_transport_enums():
    assert Verdict.PASS.value == "PASS"
    assert Verdict.BLOCKED.value == "BLOCKED"
    assert HILTransport("mock") is HILTransport.MOCK


def test_get_hil_runner_returns_mock_runner():
    runner = get_hil_runner("mock")
    assert isinstance(runner, HILRunner)
    assert runner.transport is HILTransport.MOCK


def test_mock_transport_connects_without_hardware():
    runner = get_hil_runner("mock")
    # Mock transport must connect successfully with no real device attached.
    assert runner.connect() is True
    runner.disconnect()
