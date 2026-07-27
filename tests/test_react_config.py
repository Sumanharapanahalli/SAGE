"""Tests for src.core.react_config env substitution + loader.

Previously untested (SAGE self-improvement loop, issue #23).
"""

import pytest

from src.core.react_config import _load_yaml_with_env, _substitute_env


def test_substitute_uses_env_value(monkeypatch):
    monkeypatch.setenv("SAGE_TEST_VAR", "hello")
    assert _substitute_env("x=${SAGE_TEST_VAR}") == "x=hello"


def test_substitute_uses_default_when_unset(monkeypatch):
    monkeypatch.delenv("SAGE_MISSING_VAR", raising=False)
    assert _substitute_env("x=${SAGE_MISSING_VAR:-fallback}") == "x=fallback"


def test_substitute_empty_default_when_unset_and_no_default(monkeypatch):
    monkeypatch.delenv("SAGE_MISSING_VAR", raising=False)
    assert _substitute_env("x=${SAGE_MISSING_VAR}") == "x="


def test_substitute_leaves_plain_text_untouched():
    assert _substitute_env("no placeholders here") == "no placeholders here"


def test_load_yaml_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        _load_yaml_with_env("/nonexistent/react_pattern.yaml")
