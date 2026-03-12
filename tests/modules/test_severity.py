"""
Unit tests for src/modules/severity.py
"""
import pytest

pytestmark = pytest.mark.unit

from src.modules.severity import Severity, parse, requires_action, badge_color


# ---------------------------------------------------------------------------
# parse() — known aliases
# ---------------------------------------------------------------------------

class TestParse:
    def test_unknown_lowercase(self):
        assert parse("unknown") == Severity.UNKNOWN

    def test_green_lowercase(self):
        assert parse("green") == Severity.GREEN

    def test_low_lowercase(self):
        assert parse("low") == Severity.LOW

    def test_info_lowercase(self):
        assert parse("info") == Severity.INFO

    def test_amber_lowercase(self):
        assert parse("amber") == Severity.AMBER

    def test_medium_lowercase(self):
        assert parse("medium") == Severity.MEDIUM

    def test_warning_lowercase(self):
        assert parse("warning") == Severity.WARNING

    def test_red_lowercase(self):
        assert parse("red") == Severity.RED

    def test_high_lowercase(self):
        assert parse("high") == Severity.HIGH

    def test_critical_lowercase(self):
        assert parse("critical") == Severity.CRITICAL

    def test_uppercase(self):
        assert parse("CRITICAL") == Severity.CRITICAL
        assert parse("HIGH") == Severity.HIGH
        assert parse("AMBER") == Severity.AMBER
        assert parse("GREEN") == Severity.GREEN

    def test_mixed_case(self):
        assert parse("Critical") == Severity.CRITICAL
        assert parse("Warning") == Severity.WARNING
        assert parse("Medium") == Severity.MEDIUM

    def test_leading_trailing_whitespace(self):
        assert parse("  high  ") == Severity.HIGH
        assert parse(" critical ") == Severity.CRITICAL

    def test_unknown_string_returns_unknown(self):
        assert parse("bogus") == Severity.UNKNOWN
        assert parse("") == Severity.UNKNOWN
        assert parse("NOPE") == Severity.UNKNOWN
        assert parse("moderate") == Severity.UNKNOWN


# ---------------------------------------------------------------------------
# Severity IntEnum ordering
# ---------------------------------------------------------------------------

class TestSeverityOrdering:
    def test_unknown_is_zero(self):
        assert Severity.UNKNOWN == 0

    def test_green_less_than_amber(self):
        assert Severity.GREEN < Severity.AMBER

    def test_amber_less_than_red(self):
        assert Severity.AMBER < Severity.RED

    def test_red_less_than_critical(self):
        assert Severity.RED < Severity.CRITICAL

    def test_full_ascending_chain(self):
        assert Severity.UNKNOWN < Severity.GREEN < Severity.AMBER < Severity.RED < Severity.CRITICAL

    def test_aliases_share_numeric_value(self):
        assert Severity.GREEN == Severity.LOW == Severity.INFO
        assert Severity.AMBER == Severity.MEDIUM == Severity.WARNING
        assert Severity.RED == Severity.HIGH


# ---------------------------------------------------------------------------
# requires_action()
# ---------------------------------------------------------------------------

class TestRequiresAction:
    def test_critical_requires_action_at_amber_threshold(self):
        assert requires_action("critical") is True

    def test_high_requires_action_at_amber_threshold(self):
        assert requires_action("high") is True

    def test_amber_requires_action_at_amber_threshold(self):
        assert requires_action("amber") is True

    def test_green_does_not_require_action_at_amber_threshold(self):
        assert requires_action("green") is False

    def test_unknown_does_not_require_action_at_amber_threshold(self):
        assert requires_action("unknown") is False

    def test_custom_threshold_red(self):
        assert requires_action("critical", threshold="red") is True
        assert requires_action("high", threshold="red") is True
        assert requires_action("amber", threshold="red") is False
        assert requires_action("green", threshold="red") is False

    def test_custom_threshold_critical(self):
        assert requires_action("critical", threshold="critical") is True
        assert requires_action("high", threshold="critical") is False

    def test_low_threshold_green(self):
        assert requires_action("green", threshold="green") is True
        assert requires_action("unknown", threshold="green") is False


# ---------------------------------------------------------------------------
# badge_color()
# ---------------------------------------------------------------------------

class TestBadgeColor:
    def test_critical_returns_red(self):
        assert badge_color("critical") == "red"

    def test_high_returns_orange(self):
        assert badge_color("high") == "orange"

    def test_red_returns_orange(self):
        assert badge_color("red") == "orange"

    def test_amber_returns_yellow(self):
        assert badge_color("amber") == "yellow"

    def test_medium_returns_yellow(self):
        assert badge_color("medium") == "yellow"

    def test_warning_returns_yellow(self):
        assert badge_color("warning") == "yellow"

    def test_green_returns_green(self):
        assert badge_color("green") == "green"

    def test_low_returns_green(self):
        assert badge_color("low") == "green"

    def test_info_returns_green(self):
        assert badge_color("info") == "green"

    def test_unknown_returns_gray(self):
        assert badge_color("unknown") == "gray"

    def test_unrecognised_returns_gray(self):
        assert badge_color("bogus") == "gray"
