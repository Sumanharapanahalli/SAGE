"""Tests for the sidecar solutions handler."""
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import handlers.solutions as solutions  # noqa: E402


def test_list_calls_framework_helper(monkeypatch, tmp_path):
    calls = []

    def fake(root):
        calls.append(root)
        return [{"name": "x", "path": "/x", "has_sage_dir": False}]

    monkeypatch.setattr(solutions, "_list_fn", fake)
    monkeypatch.setattr(solutions, "_sage_root", tmp_path)
    assert solutions.list_solutions({}) == [
        {"name": "x", "path": "/x", "has_sage_dir": False}
    ]
    assert calls == [tmp_path]


def test_list_missing_sage_root_returns_empty(monkeypatch):
    monkeypatch.setattr(solutions, "_sage_root", None)
    assert solutions.list_solutions({}) == []


def test_list_missing_list_fn_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(solutions, "_list_fn", None)
    monkeypatch.setattr(solutions, "_sage_root", tmp_path)
    assert solutions.list_solutions({}) == []


def test_get_current_returns_wired_values(monkeypatch):
    monkeypatch.setattr(solutions, "_current_name", "meditation_app")
    monkeypatch.setattr(solutions, "_current_path", Path("/abs/meditation_app"))
    assert solutions.get_current({}) == {
        "name": "meditation_app",
        "path": str(Path("/abs/meditation_app")),
    }


def test_get_current_returns_none_when_unwired(monkeypatch):
    monkeypatch.setattr(solutions, "_current_name", "")
    monkeypatch.setattr(solutions, "_current_path", None)
    assert solutions.get_current({}) is None


def test_get_current_treats_blank_name_as_unwired(monkeypatch):
    monkeypatch.setattr(solutions, "_current_name", "")
    monkeypatch.setattr(solutions, "_current_path", Path("/something"))
    assert solutions.get_current({}) is None
