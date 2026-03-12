"""Unit tests for src/modules/payload_validator.py"""
import pytest
from src.modules.payload_validator import validate, coerce_str, coerce_int, ValidationError

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
