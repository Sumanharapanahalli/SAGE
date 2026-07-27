"""Tests for src.services.continuous_tester._parse_pytest_output.

Previously untested (SAGE self-improvement loop, issue #23).
"""

from src.services.continuous_tester import _parse_pytest_output


def test_parses_passed_and_skipped_and_duration():
    r = _parse_pytest_output("383 passed, 1 skipped in 10.80s")
    assert r["passed"] == 383
    assert r["skipped"] == 1
    assert r["failed"] == 0
    assert r["duration_sec"] == 10.80
    assert r["status"] == "passed"


def test_failed_marks_status_failed():
    r = _parse_pytest_output("10 passed, 2 failed in 3.5s")
    assert r["failed"] == 2
    assert r["status"] == "failed"


def test_errors_mark_status_failed():
    r = _parse_pytest_output("5 passed, 1 error in 1.0s")
    assert r["errors"] == 1
    assert r["status"] == "failed"


def test_empty_output_is_zeroed_and_passed():
    r = _parse_pytest_output("")
    assert r == {
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "errors": 0,
        "duration_sec": 0.0,
        "status": "passed",
    }
