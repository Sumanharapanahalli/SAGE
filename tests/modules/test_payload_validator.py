"""Unit tests for src/modules/payload_validator.py"""

import pytest
from src.modules.payload_validator import (
    validate,
    coerce_str,
    coerce_int,
    ValidationError,
    sanitize_task_input,
    MAX_TASK_LENGTH,
)

pytestmark = pytest.mark.unit


class TestValidate:
    def test_passes_when_all_present(self):
        validate({"a": "x", "b": "y"}, ["a", "b"])

    def test_raises_on_missing_field(self):
        with pytest.raises(ValidationError, match="missing_key"):
            validate({"a": "x"}, ["a", "missing_key"])

    def test_raises_on_empty_string(self):
        with pytest.raises(ValidationError, match="empty_field"):
            validate({"empty_field": ""}, ["empty_field"])

    def test_raises_on_none_value(self):
        with pytest.raises(ValidationError):
            validate({"key": None}, ["key"])

    def test_empty_required_list_always_passes(self):
        validate({}, [])

    def test_error_message_lists_all_missing(self):
        with pytest.raises(ValidationError) as exc_info:
            validate({}, ["a", "b", "c"])
        msg = str(exc_info.value)
        assert "a" in msg and "b" in msg and "c" in msg


class TestCoerceStr:
    def test_present_string(self):
        assert coerce_str({"k": "hello"}, "k") == "hello"

    def test_present_int_coerced(self):
        assert coerce_str({"k": 42}, "k") == "42"

    def test_missing_returns_default(self):
        assert coerce_str({}, "k", "fallback") == "fallback"

    def test_missing_returns_empty_default(self):
        assert coerce_str({}, "k") == ""

    def test_none_value_returns_default(self):
        assert coerce_str({"k": None}, "k", "x") == "x"


class TestCoerceInt:
    def test_present_int(self):
        assert coerce_int({"k": 5}, "k") == 5

    def test_string_int_coerced(self):
        assert coerce_int({"k": "7"}, "k") == 7

    def test_missing_returns_default(self):
        assert coerce_int({}, "k", 99) == 99

    def test_missing_returns_zero_default(self):
        assert coerce_int({}, "k") == 0

    def test_non_numeric_returns_default(self):
        assert coerce_int({"k": "abc"}, "k", 3) == 3

    def test_none_returns_default(self):
        assert coerce_int({"k": None}, "k", 1) == 1


class TestSanitizeTaskInput:
    # -- null byte / control char stripping --
    def test_strips_null_bytes(self):
        assert sanitize_task_input("ab\x00cd\x00") == "abcd"

    def test_strips_null_byte_only_to_empty_string(self):
        assert sanitize_task_input("\x00\x00\x00") == ""

    @pytest.mark.parametrize("ctrl", ["\x07", "\x0b", "\x0c", "\x1b", "\x1f"])
    def test_strips_individual_control_chars(self, ctrl):
        assert sanitize_task_input(f"x{ctrl}y") == "xy"

    def test_strips_full_control_range_except_tab_newline(self):
        raw = "".join(chr(c) for c in range(0x00, 0x20))
        assert sanitize_task_input(raw) == "\t\n"

    # -- tab / newline preservation --
    def test_preserves_tab_and_newline(self):
        assert sanitize_task_input("line1\tcol\nline2") == "line1\tcol\nline2"

    def test_preserves_tab_and_newline_among_stripped_controls(self):
        assert sanitize_task_input("a\x00\tb\x1b\nc") == "a\tb\nc"

    # -- length boundary --
    def test_exactly_4000_chars_accepted(self):
        s = "a" * MAX_TASK_LENGTH
        assert sanitize_task_input(s) == s
        assert len(sanitize_task_input(s)) == 4000

    def test_4001_chars_rejected(self):
        with pytest.raises(ValidationError):
            sanitize_task_input("a" * (MAX_TASK_LENGTH + 1))

    def test_length_measured_after_stripping(self):
        s = "a" * MAX_TASK_LENGTH + "\x00\x07\x1b"
        assert sanitize_task_input(s) == "a" * MAX_TASK_LENGTH

    def test_custom_max_length_boundary(self):
        assert sanitize_task_input("a" * 10, max_length=10) == "a" * 10
        with pytest.raises(ValidationError):
            sanitize_task_input("a" * 11, max_length=10)

    # -- purity / no new rejection behavior --
    def test_empty_input_not_rejected(self):
        assert sanitize_task_input("") == ""

    def test_whitespace_only_input_not_rejected(self):
        assert sanitize_task_input("   \t\n  ") == "   \t\n  "

    def test_none_coerced_to_empty_string(self):
        assert sanitize_task_input(None) == ""

    def test_non_string_coerced_to_string(self):
        assert sanitize_task_input(1234) == "1234"

    def test_pure_function_no_mutation_and_deterministic(self):
        s = "payload\x00with\x1bcontrols\tkept\n"
        first = sanitize_task_input(s)
        second = sanitize_task_input(s)
        assert first == second == "payloadwithcontrols\tkept\n"
        assert s == "payload\x00with\x1bcontrols\tkept\n"
