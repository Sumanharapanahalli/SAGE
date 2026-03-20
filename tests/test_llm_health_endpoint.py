"""Tests for GET /health/llm endpoint."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from src.interface.api import app

client = TestClient(app)


def test_llm_health_connected():
    """Should return connected=True when LLM responds."""
    mock_gw = MagicMock()
    mock_gw.get_provider_name.return_value = "gemini"
    mock_gw.generate.return_value = "ok"

    with patch("src.interface.api._get_llm_gateway", return_value=mock_gw):
        resp = client.get("/health/llm")

    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is True
    assert data["provider"] == "gemini"
    assert "latency_ms" in data


def test_llm_health_disconnected_on_exception():
    """Should return connected=False when LLM raises an exception."""
    mock_gw = MagicMock()
    mock_gw.get_provider_name.return_value = "ollama"
    mock_gw.generate.side_effect = RuntimeError("connection refused")

    with patch("src.interface.api._get_llm_gateway", return_value=mock_gw):
        resp = client.get("/health/llm")

    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is False
    assert "connection refused" in data["detail"]


def test_llm_health_disconnected_on_empty_response():
    """Should return connected=False when LLM returns empty string."""
    mock_gw = MagicMock()
    mock_gw.get_provider_name.return_value = "gemini"
    mock_gw.generate.return_value = ""

    with patch("src.interface.api._get_llm_gateway", return_value=mock_gw):
        resp = client.get("/health/llm")

    assert resp.status_code == 200
    assert resp.json()["connected"] is False
