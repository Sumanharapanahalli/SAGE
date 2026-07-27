"""Tests for src.integrations.composio_tools graceful-degradation surface.

The Composio SDK / API key are optional; the module must degrade gracefully when
absent. Previously untested (SAGE self-improvement loop, issue #23).
"""

from src.integrations import composio_tools


def test_is_available_false_without_api_key(monkeypatch):
    monkeypatch.delenv("COMPOSIO_API_KEY", raising=False)
    assert composio_tools.is_available() is False


def test_get_composio_tools_returns_dict_when_unavailable(monkeypatch):
    monkeypatch.delenv("COMPOSIO_API_KEY", raising=False)
    result = composio_tools.get_composio_tools(["github"])
    assert isinstance(result, dict)


def test_list_connected_apps_returns_list_when_unavailable(monkeypatch):
    monkeypatch.delenv("COMPOSIO_API_KEY", raising=False)
    assert isinstance(composio_tools.list_connected_apps(), list)
