# Task 18: LLM provider fallback test

**Category:** testing  
**Score:** 9.0/10  
**Converged:** True  
**Iterations:** 1  
**Elapsed:** 310s  

---

## Task

Add tests in tests/test_llm_gateway.py for provider fallback: (1) when the primary provider raises an exception, the gateway falls back to the secondary provider if configured; (2) when all providers fail, the gateway raises LLMProviderError with a message listing all failed providers. Mock all provider generate() calls.

## Criteria

Fallback test uses mocked providers; all-fail test verifies LLMProviderError with provider list; no real LLM calls; tests pass with pytest.

## Proposal (submit to HITL approval gate)

=== FILE: src/core/llm_gateway.py (ADDITIONS) ===
```python
# ---------------------------------------------------------------------------
# Fallback error (place at module level, e.g. just above `class ProviderPool`)
# ---------------------------------------------------------------------------
class LLMProviderError(Exception):
    """Raised when every provider in a fallback chain has failed.

    Carries the per-provider failures so callers can inspect them, and renders
    a message that names every failed provider (and its error) for logging.
    """

    def __init__(self, failures):
        # failures: iterable of (provider_name, error_message) tuples
        self.failures = list(failures)
        providers = ", ".join(name for name, _ in self.failures) or "<none>"
        details = "; ".join(f"{name}: {err}" for name, err in self.failures)
        message = f"All LLM providers failed [{providers}]"
        if details:
            message += f" — {details}"
        super().__init__(message)


# ---------------------------------------------------------------------------
# Add the following method to class LLMGateway
# ---------------------------------------------------------------------------
    def generate_with_fallback(self, prompt,
                               system_prompt="You are a helpful AI assistant.",
                               *, provider_names=None):
        """Try registered providers in order; return the first success.

        Falls back to the next provider whenever one *raises*. Honours the
        single-lane inference guarantee (held across the whole chain). If every
        provider fails, raises LLMProviderError naming all failed providers.

        Args:
            prompt:         User/task prompt.
            system_prompt:  Role/instruction context.
            provider_names: Explicit ordered list of pool provider keys to try.
                            Defaults to every provider registered in the pool.

        Raises:
            LLMProviderError: when no provider yields a successful response.
        """
        names = provider_names or self.provider_pool.list_providers()
        if not names:
            raise LLMProviderError([("<none>", "no providers configured")])

        failures = []
        with self._inference_semaphore:
            for name in names:
                provider = self.provider_pool.get(name)
                if provider is None:
                    failures.append((name, "provider not registered"))
                    continue
                try:
                    self.logger.debug("Fallback attempt via provider '%s'", name)
                    return provider.generate(prompt, system_prompt)
                except Exception as exc:  # noqa: BLE001 — provider may raise anything
                    self.logger.warning("Provider '%s' failed: %s", name, exc)
                    failures.append((name, str(exc)))

        raise LLMProviderError(failures)
```

=== FILE: tests/test_llm_gateway.py (ADDITIONS — append) ===
```python
# ---------------------------------------------------------------------------
# Provider fallback tests
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
    # Both providers must have been attempted before giving up.
    primary.generate.assert_called_once_with("test prompt", "test system")
    secondary.generate.assert_called_once_with("test prompt", "test system")
    # Structured failures are preserved for programmatic inspection.
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
```

---

## Iteration History

**Iter 1** — score 9.0 pass=True  
Feedback:   

