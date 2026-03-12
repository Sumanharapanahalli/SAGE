"""
Unit tests for src/modules/json_extractor.py
"""
import pytest

pytestmark = pytest.mark.unit

from src.modules.json_extractor import extract, extract_or_default


# ---------------------------------------------------------------------------
# extract() — basic cases
# ---------------------------------------------------------------------------

class TestExtractBasic:
    def test_plain_json_object(self):
        result = extract('{"key": "value"}')
        assert result == {"key": "value"}

    def test_plain_json_array(self):
        result = extract('[1, 2, 3]')
        assert result == [1, 2, 3]

    def test_nested_object(self):
        result = extract('{"a": {"b": 42}}')
        assert result == {"a": {"b": 42}}

    def test_array_of_objects(self):
        result = extract('[{"id": 1}, {"id": 2}]')
        assert result == [{"id": 1}, {"id": 2}]

    def test_json_with_whitespace(self):
        result = extract('  { "x" : 1 }  ')
        assert result == {"x": 1}

    def test_integer_root_value_not_supported_as_object(self):
        # A bare integer is not a JSON object or array — returns None via pattern search
        result = extract('42')
        # json.loads("42") is valid JSON (number), so it succeeds on full-string parse
        assert result == 42


# ---------------------------------------------------------------------------
# extract() — markdown fence handling
# ---------------------------------------------------------------------------

class TestExtractMarkdownFences:
    def test_json_in_backtick_fence(self):
        text = '```json\n{"severity": "HIGH"}\n```'
        assert extract(text) == {"severity": "HIGH"}

    def test_json_in_plain_backtick_fence(self):
        text = '```\n{"severity": "LOW"}\n```'
        assert extract(text) == {"severity": "LOW"}

    def test_json_in_fence_with_extra_prose_before(self):
        text = 'Here is the result:\n```json\n{"ok": true}\n```'
        assert extract(text) == {"ok": True}

    def test_array_in_fence(self):
        text = '```json\n[1, 2, 3]\n```'
        assert extract(text) == [1, 2, 3]

    def test_multiline_json_in_fence(self):
        text = '```json\n{\n  "a": 1,\n  "b": 2\n}\n```'
        assert extract(text) == {"a": 1, "b": 2}


# ---------------------------------------------------------------------------
# extract() — JSON embedded in prose
# ---------------------------------------------------------------------------

class TestExtractEmbeddedInProse:
    def test_object_in_prose(self):
        text = 'Here is the result: {"data": 42} done'
        assert extract(text) == {"data": 42}

    def test_array_in_prose(self):
        text = 'The items are [1, 2, 3] and nothing else.'
        assert extract(text) == [1, 2, 3]

    def test_object_at_end_of_prose(self):
        text = 'Analysis complete. Output: {"status": "ok"}'
        assert extract(text) == {"status": "ok"}

    def test_object_preceded_by_label(self):
        text = 'Result\n{"key": "val"}'
        assert extract(text) == {"key": "val"}


# ---------------------------------------------------------------------------
# extract() — failure cases
# ---------------------------------------------------------------------------

class TestExtractFailureCases:
    def test_empty_string_returns_none(self):
        assert extract("") is None

    def test_none_input_returns_none(self):
        assert extract(None) is None  # type: ignore[arg-type]

    def test_broken_json_returns_none(self):
        assert extract("{bad json}") is None

    def test_partial_json_returns_none(self):
        assert extract('{"key":') is None

    def test_plain_prose_returns_none(self):
        assert extract("No JSON here at all.") is None

    def test_only_whitespace_returns_none(self):
        assert extract("   ") is None


# ---------------------------------------------------------------------------
# extract_or_default()
# ---------------------------------------------------------------------------

class TestExtractOrDefault:
    def test_returns_parsed_json_when_valid(self):
        assert extract_or_default('{"x": 1}', {}) == {"x": 1}

    def test_returns_default_on_empty_string(self):
        assert extract_or_default("", {"fallback": True}) == {"fallback": True}

    def test_returns_default_on_broken_json(self):
        assert extract_or_default("{broken}", []) == []

    def test_returns_default_on_prose_only(self):
        assert extract_or_default("no json here", "DEFAULT") == "DEFAULT"

    def test_default_can_be_none(self):
        assert extract_or_default("", None) is None

    def test_default_can_be_list(self):
        assert extract_or_default("broken", [1, 2]) == [1, 2]

    def test_does_not_return_default_when_json_present(self):
        result = extract_or_default('{"a": 1}', {"a": 999})
        assert result == {"a": 1}
