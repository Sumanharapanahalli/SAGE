"""
SAGE[ai] - Unit tests for LLM Gateway (src/core/llm_gateway.py)

Tests the singleton pattern, provider selection, subprocess invocation,
error handling, and thread safety of the LLM gateway.
"""

import subprocess
import threading
import time
from unittest.mock import MagicMock, patch

import pytest


pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers — reset singleton between tests that need a fresh instance
# ---------------------------------------------------------------------------

def _reset_llm_gateway_singleton():
    """Force-reset the LLMGateway singleton so tests get a clean instance."""
    from src.core import llm_gateway as gw_module
    gw_module.LLMGateway._instance = None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_singleton_pattern():
    """Calling LLMGateway() twice must return the identical object."""
    from src.core.llm_gateway import LLMGateway
    instance_a = LLMGateway()
    instance_b = LLMGateway()
    assert instance_a is instance_b, "LLMGateway must be a singleton — both calls must return the same object."


def test_gemini_provider_selected_by_default():
    """With the default config (provider: gemini), the provider name should contain 'Gemini'."""
    from src.core.llm_gateway import LLMGateway
    gw = LLMGateway()
    provider_name = gw.get_provider_name()
    assert "Gemini" in provider_name or "gemini" in provider_name.lower(), (
        f"Expected provider name to contain 'Gemini', got: {provider_name}"
    )


def test_local_provider_selected_when_configured():
    """
    When config specifies provider: local and llama_cpp is mocked,
    LocalLlamaProvider should be instantiated.
    """
    _reset_llm_gateway_singleton()
    mock_config = {
        "llm": {
            "provider": "local",
            "model_path": "/tmp/fake_model.gguf",
            "max_tokens": 512,
        }
    }
    mock_llama_module = MagicMock()
    mock_llama_cls = MagicMock()
    mock_llama_module.Llama = mock_llama_cls

    with patch("src.core.llm_gateway._load_config", return_value=mock_config), \
         patch.dict("sys.modules", {"llama_cpp": mock_llama_module}), \
         patch("os.path.exists", return_value=True):
        from src.core.llm_gateway import LLMGateway, LocalLlamaProvider
        gw = LLMGateway()
        assert isinstance(gw.provider, LocalLlamaProvider), (
            f"Expected LocalLlamaProvider, got {type(gw.provider)}"
        )
    _reset_llm_gateway_singleton()


def test_generate_returns_string():
    """When subprocess returns stdout='OK', generate() should return 'OK'."""
    from src.core.llm_gateway import LLMGateway
    gw = LLMGateway()
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "OK"
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = gw.generate("test prompt", "test system")
    assert isinstance(result, str), "generate() must return a string."
    assert "OK" in result, f"Expected 'OK' in result, got: {result!r}"


def test_generate_handles_timeout():
    """When subprocess raises TimeoutExpired, generate() should return a string mentioning 'timed out'."""
    from src.core.llm_gateway import LLMGateway
    gw = LLMGateway()
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="gemini", timeout=120)):
        result = gw.generate("test prompt", "test system")
    assert isinstance(result, str), "generate() must return a string on timeout."
    assert "timed out" in result.lower() or "timeout" in result.lower(), (
        f"Expected timeout message, got: {result!r}"
    )


def test_generate_handles_missing_gemini_cli():
    """When subprocess raises FileNotFoundError, generate() should return a graceful error string."""
    from src.core.llm_gateway import LLMGateway
    gw = LLMGateway()
    with patch("subprocess.run", side_effect=FileNotFoundError("gemini not found")):
        result = gw.generate("test prompt", "test system")
    assert isinstance(result, str), "generate() must return a string on FileNotFoundError."
    assert len(result) > 0, "Error message should be non-empty."
    # Should contain some indication of error / not installed
    assert "error" in result.lower() or "not found" in result.lower() or "not installed" in result.lower(), (
        f"Expected error message, got: {result!r}"
    )


def test_thread_lock_serializes_calls():
    """
    Spawn 3 threads calling generate() simultaneously.
    All must complete without exception and return non-empty strings.
    Patch subprocess.run outside the threads to avoid thread-unsafe patch nesting.
    """
    from src.core.llm_gateway import LLMGateway
    gw = LLMGateway()
    results = []
    errors = []
    lock = threading.Lock()

    def worker():
        try:
            res = gw.generate("concurrent prompt", "system")
            with lock:
                results.append(res)
        except Exception as exc:
            with lock:
                errors.append(str(exc))

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "thread_result"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

    assert len(errors) == 0, f"Thread errors occurred: {errors}"
    assert len(results) == 3, f"Expected 3 results, got {len(results)}"
    for r in results:
        assert isinstance(r, str) and len(r) > 0, f"Expected non-empty string, got: {r!r}"


def test_gemini_cli_filters_hook_lines():
    """
    When subprocess stdout contains Gemini hook registry lines mixed with
    actual content, generate() should filter out the noise lines and
    return only the actual response.
    """
    from src.core.llm_gateway import LLMGateway
    gw = LLMGateway()
    raw_output = "Loaded cached registry\nHook registry: test\nActual response"
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = raw_output
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        result = gw.generate("prompt", "system")
    assert result == "Actual response", (
        f"Expected filtered output 'Actual response', got: {result!r}"
    )


def test_get_provider_name_returns_string():
    """get_provider_name() must return a non-empty string."""
    from src.core.llm_gateway import LLMGateway
    gw = LLMGateway()
    name = gw.get_provider_name()
    assert isinstance(name, str), "get_provider_name() must return a string."
    assert len(name) > 0, "get_provider_name() must return a non-empty string."
