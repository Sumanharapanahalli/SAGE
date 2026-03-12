"""
Unit tests for src/modules/trace_id.py
"""
import re

import pytest

pytestmark = pytest.mark.unit

from src.modules.trace_id import new, is_valid

_UUID4_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE
)


# ---------------------------------------------------------------------------
# new()
# ---------------------------------------------------------------------------

class TestNew:
    def test_returns_string(self):
        assert isinstance(new(), str)

    def test_matches_uuid4_pattern(self):
        tid = new()
        assert _UUID4_PATTERN.match(tid), f"'{tid}' does not match UUID4 pattern"

    def test_correct_length(self):
        # UUID4 string: 8-4-4-4-12 = 32 hex digits + 4 hyphens = 36 chars
        assert len(new()) == 36

    def test_two_calls_produce_different_ids(self):
        assert new() != new()

    def test_many_calls_are_unique(self):
        ids = {new() for _ in range(100)}
        assert len(ids) == 100

    def test_contains_four_hyphens(self):
        assert new().count("-") == 4


# ---------------------------------------------------------------------------
# is_valid()
# ---------------------------------------------------------------------------

class TestIsValid:
    def test_valid_uuid4_returns_true(self):
        tid = new()
        assert is_valid(tid) is True

    def test_valid_uppercase_uuid_returns_true(self):
        tid = new().upper()
        assert is_valid(tid) is True

    def test_valid_mixed_case_uuid_returns_true(self):
        tid = "550E8400-E29B-41D4-A716-446655440000"
        assert is_valid(tid) is True

    def test_empty_string_returns_false(self):
        assert is_valid("") is False

    def test_plain_string_returns_false(self):
        assert is_valid("not-a-uuid") is False

    def test_malformed_uuid_too_short_returns_false(self):
        assert is_valid("12345678-1234-1234-1234-12345678901") is False

    def test_malformed_uuid_missing_hyphen_returns_false(self):
        assert is_valid("550e8400e29b41d4a716446655440000") is False

    def test_malformed_uuid_wrong_segment_returns_false(self):
        assert is_valid("550e8400-e29b-41d4-a716-44665544000Z") is False

    def test_uuid_with_spaces_returns_false(self):
        tid = " " + new() + " "
        assert is_valid(tid) is False

    def test_none_input_returns_false(self):
        # is_valid relies on truthiness of value; None should return False
        assert is_valid(None) is False  # type: ignore[arg-type]
