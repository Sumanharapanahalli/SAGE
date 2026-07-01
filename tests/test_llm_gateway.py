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


def test_generate_retries_transient_then_succeeds():
    """A transient provider failure (e.g. 429) is retried; the later success returns."""
    _reset_llm_gateway_singleton()
    from src.core.llm_gateway import LLMGateway
    gw = LLMGateway()
    gw._retry_max = 2
    gw._retry_base_delay = 0.0  # no real sleeping in tests
    calls = {"n": 0}

    def flaky(prompt, system_prompt):
        calls["n"] += 1
        if calls["n"] < 3:
            return "Error: rate limit exceeded (429)"
        return "recovered"

    with patch.object(gw.provider, "generate", side_effect=flaky):
        result = gw.generate("p", "s")
    assert result == "recovered", f"expected recovered result, got {result!r}"
    assert calls["n"] == 3, f"expected 3 attempts (2 retries), got {calls['n']}"
    _reset_llm_gateway_singleton()


def test_generate_does_not_retry_permanent_error():
    """A permanent error (not transient) is returned immediately — no wasted retries."""
    _reset_llm_gateway_singleton()
    from src.core.llm_gateway import LLMGateway
    gw = LLMGateway()
    gw._retry_max = 3
    gw._retry_base_delay = 0.0
    calls = {"n": 0}

    def permanent(prompt, system_prompt):
        calls["n"] += 1
        return "Error: No LLM provider configured."

    with patch.object(gw.provider, "generate", side_effect=permanent):
        result = gw.generate("p", "s")
    assert "Error" in result
    assert calls["n"] == 1, f"permanent error must not be retried, got {calls['n']} calls"
    _reset_llm_gateway_singleton()


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


# ---------------------------------------------------------------------------
# Circuit breaker tests (Task 4)
# ---------------------------------------------------------------------------


def test_circuit_breaker_state_machine_transitions_with_logging(caplog):
    """Direct unit test of CircuitBreaker: CLOSED -> OPEN -> HALF_OPEN -> CLOSED,
    with each transition logged."""
    import logging
    from src.core.llm_gateway import CircuitBreaker

    clock = {"t": 0.0}
    cb = CircuitBreaker(name="test-provider", failure_threshold=3, reset_timeout=60.0,
                        clock=lambda: clock["t"])

    assert cb.state == CircuitBreaker.CLOSED

    with caplog.at_level(logging.WARNING, logger="CircuitBreaker"):
        # 2 failures — not enough to trip
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitBreaker.CLOSED

        # 3rd consecutive failure trips the breaker
        cb.record_failure()
        assert cb.state == CircuitBreaker.OPEN
        assert any("CLOSED -> OPEN" in r.message for r in caplog.records)

        # While OPEN and before the cooldown, requests are rejected without a probe.
        assert cb.allow_request() is False

        # Advance the clock past reset_timeout — next request is admitted as a probe.
        clock["t"] = 61.0
        assert cb.allow_request() is True
        assert cb.state == CircuitBreaker.HALF_OPEN
        assert any("OPEN -> HALF_OPEN" in r.message for r in caplog.records)

        # A second concurrent caller is rejected while the probe is in flight.
        assert cb.allow_request() is False

        # The probe succeeds -> circuit closes.
        cb.record_success()
        assert cb.state == CircuitBreaker.CLOSED
        assert any("HALF_OPEN -> CLOSED" in r.message for r in caplog.records)


def test_circuit_breaker_reopens_on_half_open_probe_failure():
    """A failed HALF_OPEN probe re-opens the circuit for another cooldown window."""
    from src.core.llm_gateway import CircuitBreaker

    clock = {"t": 0.0}
    cb = CircuitBreaker(name="test-provider", failure_threshold=3, reset_timeout=60.0,
                        clock=lambda: clock["t"])
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitBreaker.OPEN

    clock["t"] = 61.0
    assert cb.allow_request() is True  # admits the probe
    assert cb.state == CircuitBreaker.HALF_OPEN

    cb.record_failure()  # probe fails
    assert cb.state == CircuitBreaker.OPEN
    assert cb.allow_request() is False  # cooldown restarted, still rejecting


def test_generate_opens_circuit_after_threshold_consecutive_failures():
    """After N consecutive provider failures, generate() fails fast without
    calling the provider again."""
    _reset_llm_gateway_singleton()
    from src.core.llm_gateway import LLMGateway
    gw = LLMGateway()
    gw._cb_failure_threshold = 3
    gw._cb_reset_timeout = 60.0

    with patch.object(gw.provider, "generate", return_value="Error: boom") as mock_gen:
        for _ in range(3):
            result = gw.generate("p", "s")
            assert result.startswith("Error")
        assert mock_gen.call_count == 3

        # Circuit is now OPEN — the 4th call must fail fast without a provider call.
        result = gw.generate("p", "s")
        assert "circuit breaker" in result.lower() or "circuit" in result.lower()
        assert mock_gen.call_count == 3, "provider must NOT be called while circuit is OPEN"
    _reset_llm_gateway_singleton()


def test_generate_circuit_recovers_after_cooldown():
    """Once the cooldown elapses, generate() admits a probe and can close the
    circuit again on success."""
    _reset_llm_gateway_singleton()
    from src.core.llm_gateway import LLMGateway
    gw = LLMGateway()
    gw._cb_failure_threshold = 2
    gw._cb_reset_timeout = 30.0

    with patch.object(gw.provider, "generate", return_value="Error: boom"):
        gw.generate("p", "s")
        gw.generate("p", "s")

    provider_name = gw.provider.provider_name()
    breaker = gw._get_circuit_breaker(provider_name)
    assert breaker.state == "OPEN"

    # Fast-forward the breaker's clock past the cooldown window.
    breaker._opened_at -= (gw._cb_reset_timeout + 1)

    with patch.object(gw.provider, "generate", return_value="recovered") as mock_gen:
        result = gw.generate("p", "s")
        assert result == "recovered"
        assert mock_gen.call_count == 1
    assert breaker.state == "CLOSED"
    _reset_llm_gateway_singleton()


# ---------------------------------------------------------------------------
# Structured logging tests (Task 5)
# ---------------------------------------------------------------------------


def test_generate_success_emits_structured_log_record(caplog):
    """A successful generate() call logs a record carrying the canonical
    structured fields (event, provider, duration_ms, status) via extra=."""
    import logging
    from src.core.llm_gateway import LLMGateway
    gw = LLMGateway()
    with caplog.at_level(logging.INFO, logger="LLMGateway"), \
         patch.object(gw.provider, "generate", return_value="OK"):
        gw.generate("prompt", "system")

    matches = [r for r in caplog.records if getattr(r, "event", None) == "generation"
               and getattr(r, "status", None) == "completed"]
    assert matches, "expected a structured 'generation'/'completed' log record"
    record = matches[-1]
    assert record.provider  # non-empty provider name attached
    assert isinstance(record.duration_ms, int)
    assert record.duration_ms >= 0


def test_generate_failure_emits_structured_error_log_record(caplog):
    """A raised provider exception logs a structured record with status='error'."""
    import logging
    from src.core.llm_gateway import LLMGateway
    gw = LLMGateway()
    with caplog.at_level(logging.ERROR, logger="LLMGateway"), \
         patch.object(gw.provider, "generate", side_effect=RuntimeError("boom")):
        gw._retry_max = 0  # no retries — fail fast for a deterministic single log record
        gw.generate("prompt", "system")

    matches = [r for r in caplog.records if getattr(r, "event", None) == "generation"
               and getattr(r, "status", None) == "error"]
    assert matches, "expected a structured 'generation'/'error' log record"


# ---------------------------------------------------------------------------
# Provider fallback tests (Task 18 — validation pass)
# ---------------------------------------------------------------------------


def _mock_provider(name, *, returns=None, raises=None):
    """Build a mock LLMProvider whose generate() is fully mocked."""
    provider = MagicMock()
    provider.provider_name.return_value = name
    if raises is not None:
        provider.generate.side_effect = raises
    else:
        provider.generate.return_value = returns
    return provider


def test_fallback_to_secondary_when_primary_raises():
    """When the primary provider raises, the gateway falls back to the secondary."""
    _reset_llm_gateway_singleton()
    from src.core.llm_gateway import LLMGateway
    gw = LLMGateway()

    primary = _mock_provider("Primary", raises=RuntimeError("primary unavailable"))
    secondary = _mock_provider("Secondary", returns="secondary response")
    gw.provider_pool.register("primary", primary)
    gw.provider_pool.register("secondary", secondary)

    result = gw.generate_with_fallback(
        "test prompt", "test system", provider_names=["primary", "secondary"]
    )

    assert result == "secondary response", (
        f"Expected fallback to secondary, got: {result!r}"
    )
    primary.generate.assert_called_once_with("test prompt", "test system")
    secondary.generate.assert_called_once_with("test prompt", "test system")
    _reset_llm_gateway_singleton()


def test_fallback_returns_first_success_without_calling_others():
    """A healthy primary short-circuits the chain — the secondary is never called."""
    _reset_llm_gateway_singleton()
    from src.core.llm_gateway import LLMGateway
    gw = LLMGateway()

    primary = _mock_provider("Primary", returns="primary response")
    secondary = _mock_provider("Secondary", returns="secondary response")
    gw.provider_pool.register("primary", primary)
    gw.provider_pool.register("secondary", secondary)

    result = gw.generate_with_fallback(
        "test prompt", "test system", provider_names=["primary", "secondary"]
    )

    assert result == "primary response"
    primary.generate.assert_called_once()
    secondary.generate.assert_not_called()
    _reset_llm_gateway_singleton()


def test_all_providers_fail_raises_error_listing_all_providers():
    """When every provider raises, LLMProviderError is raised naming all of them."""
    _reset_llm_gateway_singleton()
    from src.core.llm_gateway import LLMGateway, LLMProviderError
    gw = LLMGateway()

    primary = _mock_provider("Primary", raises=RuntimeError("primary boom"))
    secondary = _mock_provider("Secondary", raises=ValueError("secondary boom"))
    gw.provider_pool.register("primary", primary)
    gw.provider_pool.register("secondary", secondary)

    with pytest.raises(LLMProviderError) as exc_info:
        gw.generate_with_fallback(
            "test prompt", "test system", provider_names=["primary", "secondary"]
        )

    message = str(exc_info.value)
    assert "primary" in message, f"Error must list the primary provider: {message!r}"
    assert "secondary" in message, f"Error must list the secondary provider: {message!r}"
    primary.generate.assert_called_once_with("test prompt", "test system")
    secondary.generate.assert_called_once_with("test prompt", "test system")
    failed_names = [name for name, _ in exc_info.value.failures]
    assert failed_names == ["primary", "secondary"]
    _reset_llm_gateway_singleton()


def test_fallback_with_only_failing_primary_raises_llm_provider_error():
    """No secondary configured: a failing primary raises LLMProviderError naming it."""
    _reset_llm_gateway_singleton()
    from src.core.llm_gateway import LLMGateway, LLMProviderError
    gw = LLMGateway()

    primary = _mock_provider("Primary", raises=RuntimeError("primary down"))
    gw.provider_pool.register("primary", primary)

    with pytest.raises(LLMProviderError) as exc_info:
        gw.generate_with_fallback(
            "test prompt", "test system", provider_names=["primary"]
        )

    assert "primary" in str(exc_info.value)
    primary.generate.assert_called_once()
    _reset_llm_gateway_singleton()


def test_generate_with_fallback_no_providers_configured_raises():
    """No providers registered and none supplied explicitly -> LLMProviderError."""
    _reset_llm_gateway_singleton()
    from src.core.llm_gateway import LLMGateway, LLMProviderError
    gw = LLMGateway()
    assert gw.provider_pool.list_providers() == []

    with pytest.raises(LLMProviderError):
        gw.generate_with_fallback("test prompt", "test system")
    _reset_llm_gateway_singleton()
