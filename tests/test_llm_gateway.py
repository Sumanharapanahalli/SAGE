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


def test_provider_name_is_non_empty():
    """The configured LLM provider must return a non-empty provider name string."""
    from src.core.llm_gateway import LLMGateway
    gw = LLMGateway()
    provider_name = gw.get_provider_name()
    assert provider_name and provider_name != "None", (
        f"Expected a non-empty provider name, got: {provider_name!r}"
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
    """generate() should return the string produced by the provider."""
    from src.core.llm_gateway import LLMGateway
    gw = LLMGateway()
    with patch.object(gw.provider, "generate", return_value="OK"):
        result = gw.generate("test prompt", "test system")
    assert isinstance(result, str), "generate() must return a string."
    assert "OK" in result, f"Expected 'OK' in result, got: {result!r}"


def test_generate_handles_timeout():
    """When the provider raises TimeoutExpired, generate() should return a string mentioning 'timed out'."""
    from src.core.llm_gateway import LLMGateway
    gw = LLMGateway()
    with patch.object(gw.provider, "generate",
                      side_effect=subprocess.TimeoutExpired(cmd="llm", timeout=120)):
        result = gw.generate("test prompt", "test system")
    assert isinstance(result, str), "generate() must return a string on timeout."
    assert "timed out" in result.lower() or "timeout" in result.lower() or "error" in result.lower(), (
        f"Expected timeout/error message, got: {result!r}"
    )


def test_generate_handles_provider_error():
    """When the provider raises an exception, generate() should return a graceful error string."""
    from src.core.llm_gateway import LLMGateway
    gw = LLMGateway()
    with patch.object(gw.provider, "generate", side_effect=Exception("provider unavailable")):
        result = gw.generate("test prompt", "test system")
    assert isinstance(result, str), "generate() must return a string on exception."
    assert len(result) > 0, "Error message should be non-empty."


def test_thread_lock_serializes_calls():
    """
    Spawn 3 threads calling generate() simultaneously.
    All must complete without exception and return non-empty strings.
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

    with patch.object(gw.provider, "generate", return_value="thread_result"):
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
    GeminiCLIProvider.generate() should filter out hook registry noise lines
    and return only the actual response content.
    """
    _reset_llm_gateway_singleton()
    mock_config = {"llm": {"provider": "gemini", "gemini_model": "gemini-2.5-flash", "timeout": 30}}
    raw_output = "Loaded cached registry\nHook registry: test\nActual response"
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = raw_output
    mock_result.stderr = ""
    with patch("src.core.llm_gateway._load_config", return_value=mock_config), \
         patch("subprocess.run", return_value=mock_result):
        from src.core.llm_gateway import LLMGateway
        gw = LLMGateway()
        result = gw.generate("prompt", "system")
    assert result == "Actual response", (
        f"Expected filtered output 'Actual response', got: {result!r}"
    )
    _reset_llm_gateway_singleton()


def test_get_provider_name_returns_string():
    """get_provider_name() must return a non-empty string."""
    from src.core.llm_gateway import LLMGateway
    gw = LLMGateway()
    name = gw.get_provider_name()
    assert isinstance(name, str), "get_provider_name() must return a string."
    assert len(name) > 0, "get_provider_name() must return a non-empty string."


# ---------------------------------------------------------------------------
# Phase 0 — Langfuse observability tests
# ---------------------------------------------------------------------------

def test_langfuse_disabled_by_default():
    """When observability.langfuse_enabled is False, _langfuse_client must remain None."""
    import src.core.llm_gateway as gw_module
    cfg = {"llm": {"provider": "gemini"}, "observability": {"langfuse_enabled": False}}
    gw_module._langfuse_client = None
    gw_module._init_langfuse(cfg)
    assert gw_module._langfuse_client is None, (
        "_langfuse_client should be None when langfuse_enabled is False"
    )


def test_langfuse_no_keys_logs_warning(caplog):
    """When enabled but keys missing, _init_langfuse should warn and leave client None."""
    import logging
    import src.core.llm_gateway as gw_module
    gw_module._langfuse_client = None
    cfg = {"observability": {"langfuse_enabled": True, "langfuse_host": "http://localhost:3000"}}
    with caplog.at_level(logging.WARNING, logger="LLMGateway"):
        gw_module._init_langfuse(cfg)
    assert gw_module._langfuse_client is None
    assert any("LANGFUSE_PUBLIC_KEY" in r.message or "not set" in r.message for r in caplog.records), (
        "Expected a warning about missing Langfuse keys"
    )


def test_langfuse_import_error_graceful(caplog):
    """When langfuse package is not installed, _init_langfuse should warn and not crash."""
    import logging
    import src.core.llm_gateway as gw_module
    from unittest.mock import patch
    gw_module._langfuse_client = None
    cfg = {"observability": {"langfuse_enabled": True}}
    with patch.dict("os.environ", {"LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_SECRET_KEY": "sk"}), \
         patch.dict("sys.modules", {"langfuse": None}), \
         caplog.at_level(logging.WARNING, logger="LLMGateway"):
        gw_module._init_langfuse(cfg)
    assert gw_module._langfuse_client is None


def test_generate_works_without_langfuse():
    """generate() must work normally when _langfuse_client is None (no observability)."""
    import src.core.llm_gateway as gw_module
    gw_module._langfuse_client = None
    from src.core.llm_gateway import LLMGateway
    gw = LLMGateway()
    with patch.object(gw.provider, "generate", return_value="result_without_langfuse"):
        result = gw.generate("prompt", "system", trace_name="test_trace")
    assert result == "result_without_langfuse"


def test_generate_with_langfuse_mock():
    """When _langfuse_client is mocked, generate() must call trace() and generation.end()."""
    import src.core.llm_gateway as gw_module

    mock_generation = MagicMock()
    mock_trace = MagicMock()
    mock_trace.generation.return_value = mock_generation
    mock_lf_client = MagicMock()
    mock_lf_client.trace.return_value = mock_trace

    gw_module._langfuse_client = mock_lf_client
    try:
        from src.core.llm_gateway import LLMGateway
        gw = LLMGateway()
        with patch.object(gw.provider, "generate", return_value="traced_result"):
            result = gw.generate("prompt", "system", trace_name="test_agent")
        assert result == "traced_result"
        mock_lf_client.trace.assert_called_once()
        mock_trace.generation.assert_called_once()
        mock_generation.end.assert_called_once()
    finally:
        gw_module._langfuse_client = None  # always restore


# ---------------------------------------------------------------------------
# Task 7 — Domain agnosticism tests
# ---------------------------------------------------------------------------

def test_vector_store_collection_name_uses_solution_not_hardcoded():
    """VectorMemory collection name must not contain 'manufacturing' when using default config."""
    import os
    os.environ["SAGE_MINIMAL"] = "1"
    try:
        import importlib
        import src.memory.vector_store as vs_module
        importlib.reload(vs_module)
        vm = vs_module.VectorMemory()
        name = vm._get_collection_name()
        assert "manufacturing" not in name.lower(), (
            f"Collection name '{name}' must not contain 'manufacturing' — that's a medtech-specific term"
        )
    finally:
        del os.environ["SAGE_MINIMAL"]


def test_starter_solution_exists():
    """solutions/starter/ must exist with all three required YAML files."""
    import os
    base = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "solutions", "starter"
    )
    for fname in ("project.yaml", "prompts.yaml", "tasks.yaml"):
        path = os.path.join(base, fname)
        assert os.path.isfile(path), f"Missing starter template file: {path}"
