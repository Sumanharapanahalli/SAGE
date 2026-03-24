"""
SAGE[ai] - Multi-LLM Provider Pool Tests
==========================================
Tests for parallel multi-provider generation with strategies:
  - voting (majority consensus)
  - fastest (first response wins)
  - fallback (try next on failure)
  - quality (critic-scored best response)
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Mock providers for testing
# ---------------------------------------------------------------------------

class MockProvider:
    """Configurable mock LLM provider."""
    def __init__(self, name, response="mock response", delay=0, fail=False):
        self._name = name
        self._response = response
        self._delay = delay
        self._fail = fail

    def provider_name(self):
        return self._name

    def generate(self, prompt, system_prompt):
        if self._delay:
            time.sleep(self._delay)
        if self._fail:
            raise ConnectionError(f"{self._name} unavailable")
        return self._response


# ===========================================================================
# Provider Pool Tests
# ===========================================================================


class TestProviderPool:
    """Tests for the multi-provider registry."""

    def test_register_provider(self):
        from src.core.llm_gateway import ProviderPool
        pool = ProviderPool()
        p = MockProvider("test-gemini")
        pool.register("gemini", p)
        assert pool.get("gemini") is p

    def test_get_unknown_returns_none(self):
        from src.core.llm_gateway import ProviderPool
        pool = ProviderPool()
        assert pool.get("nonexistent") is None

    def test_list_providers(self):
        from src.core.llm_gateway import ProviderPool
        pool = ProviderPool()
        pool.register("gemini", MockProvider("gemini"))
        pool.register("claude", MockProvider("claude"))
        names = pool.list_providers()
        assert "gemini" in names
        assert "claude" in names

    def test_set_default(self):
        from src.core.llm_gateway import ProviderPool
        pool = ProviderPool()
        pool.register("gemini", MockProvider("gemini"))
        pool.register("claude", MockProvider("claude"))
        pool.set_default("claude")
        assert pool.default_name == "claude"

    def test_default_is_first_registered(self):
        from src.core.llm_gateway import ProviderPool
        pool = ProviderPool()
        pool.register("gemini", MockProvider("gemini"))
        pool.register("claude", MockProvider("claude"))
        assert pool.default_name == "gemini"

    def test_get_default(self):
        from src.core.llm_gateway import ProviderPool
        pool = ProviderPool()
        p = MockProvider("gemini")
        pool.register("gemini", p)
        assert pool.get_default() is p

    def test_remove_provider(self):
        from src.core.llm_gateway import ProviderPool
        pool = ProviderPool()
        pool.register("gemini", MockProvider("gemini"))
        pool.remove("gemini")
        assert pool.get("gemini") is None

    def test_pool_status(self):
        from src.core.llm_gateway import ProviderPool
        pool = ProviderPool()
        pool.register("gemini", MockProvider("gemini"))
        pool.register("claude", MockProvider("claude"))
        pool.set_default("claude")
        status = pool.status()
        assert status["default"] == "claude"
        assert len(status["providers"]) == 2


# ===========================================================================
# Parallel Generation Tests
# ===========================================================================


class TestParallelGeneration:
    """Tests for generate_parallel with different strategies."""

    def _make_pool(self, providers: dict):
        from src.core.llm_gateway import ProviderPool
        pool = ProviderPool()
        for name, p in providers.items():
            pool.register(name, p)
        return pool

    def test_voting_strategy_majority_wins(self):
        """Majority response should win in voting strategy."""
        from src.core.llm_gateway import generate_parallel
        pool = self._make_pool({
            "a": MockProvider("a", response="answer A"),
            "b": MockProvider("b", response="answer A"),
            "c": MockProvider("c", response="answer B"),
        })
        result = generate_parallel(
            pool, "test prompt", "system",
            strategy="voting", provider_names=["a", "b", "c"],
        )
        assert result["response"] == "answer A"
        assert result["strategy"] == "voting"
        assert result["votes"]["answer A"] >= 2

    def test_voting_with_all_different(self):
        """When no majority, first response should be returned."""
        from src.core.llm_gateway import generate_parallel
        pool = self._make_pool({
            "a": MockProvider("a", response="X"),
            "b": MockProvider("b", response="Y"),
            "c": MockProvider("c", response="Z"),
        })
        result = generate_parallel(
            pool, "test", "sys",
            strategy="voting", provider_names=["a", "b", "c"],
        )
        assert result["response"] in ("X", "Y", "Z")

    def test_fastest_strategy(self):
        """Fastest provider's response should be returned."""
        from src.core.llm_gateway import generate_parallel
        pool = self._make_pool({
            "slow": MockProvider("slow", response="slow answer", delay=2),
            "fast": MockProvider("fast", response="fast answer", delay=0),
        })
        result = generate_parallel(
            pool, "test", "sys",
            strategy="fastest", provider_names=["slow", "fast"],
        )
        assert result["response"] == "fast answer"
        assert result["provider"] == "fast"

    def test_fallback_strategy_first_succeeds(self):
        """Fallback should use first provider if it succeeds."""
        from src.core.llm_gateway import generate_parallel
        pool = self._make_pool({
            "primary": MockProvider("primary", response="primary answer"),
            "backup": MockProvider("backup", response="backup answer"),
        })
        result = generate_parallel(
            pool, "test", "sys",
            strategy="fallback", provider_names=["primary", "backup"],
        )
        assert result["response"] == "primary answer"
        assert result["provider"] == "primary"

    def test_fallback_strategy_failover(self):
        """Fallback should try next provider when first fails."""
        from src.core.llm_gateway import generate_parallel
        pool = self._make_pool({
            "broken": MockProvider("broken", fail=True),
            "backup": MockProvider("backup", response="backup works"),
        })
        result = generate_parallel(
            pool, "test", "sys",
            strategy="fallback", provider_names=["broken", "backup"],
        )
        assert result["response"] == "backup works"
        assert result["provider"] == "backup"

    def test_fallback_all_fail(self):
        """When all providers fail, return error."""
        from src.core.llm_gateway import generate_parallel
        pool = self._make_pool({
            "a": MockProvider("a", fail=True),
            "b": MockProvider("b", fail=True),
        })
        result = generate_parallel(
            pool, "test", "sys",
            strategy="fallback", provider_names=["a", "b"],
        )
        assert "error" in result

    def test_quality_strategy(self):
        """Quality strategy should return the longest/best response."""
        from src.core.llm_gateway import generate_parallel
        pool = self._make_pool({
            "short": MockProvider("short", response="ok"),
            "detailed": MockProvider("detailed", response="This is a very detailed and thorough analysis of the problem."),
        })
        result = generate_parallel(
            pool, "test", "sys",
            strategy="quality", provider_names=["short", "detailed"],
        )
        assert result["provider"] == "detailed"

    def test_parallel_uses_default_when_no_names(self):
        """When no provider_names given, use all registered providers."""
        from src.core.llm_gateway import generate_parallel
        pool = self._make_pool({
            "a": MockProvider("a", response="response A"),
            "b": MockProvider("b", response="response A"),
        })
        result = generate_parallel(pool, "test", "sys", strategy="voting")
        assert result["response"] == "response A"

    def test_parallel_with_one_provider(self):
        """Single provider should work for any strategy."""
        from src.core.llm_gateway import generate_parallel
        pool = self._make_pool({
            "solo": MockProvider("solo", response="only answer"),
        })
        for strategy in ("voting", "fastest", "fallback", "quality"):
            result = generate_parallel(
                pool, "test", "sys",
                strategy=strategy, provider_names=["solo"],
            )
            assert result["response"] == "only answer"

    def test_parallel_ignores_failed_in_voting(self):
        """Failed providers should be excluded from voting."""
        from src.core.llm_gateway import generate_parallel
        pool = self._make_pool({
            "good1": MockProvider("good1", response="consensus"),
            "good2": MockProvider("good2", response="consensus"),
            "broken": MockProvider("broken", fail=True),
        })
        result = generate_parallel(
            pool, "test", "sys",
            strategy="voting", provider_names=["good1", "good2", "broken"],
        )
        assert result["response"] == "consensus"

    def test_parallel_returns_metadata(self):
        """Result should include timing and provider info."""
        from src.core.llm_gateway import generate_parallel
        pool = self._make_pool({
            "a": MockProvider("a", response="test"),
        })
        result = generate_parallel(pool, "test", "sys", strategy="fastest")
        assert "elapsed_ms" in result
        assert "strategy" in result


# ===========================================================================
# Gateway Integration Tests
# ===========================================================================


class TestGatewayMultiLLM:
    """Tests for LLMGateway integration with ProviderPool."""

    def test_gateway_has_provider_pool(self):
        """LLMGateway should have a provider_pool attribute."""
        from src.core.llm_gateway import LLMGateway
        gw = LLMGateway()
        assert hasattr(gw, "provider_pool")

    def test_gateway_generate_multi(self):
        """LLMGateway.generate_multi should delegate to generate_parallel."""
        from src.core.llm_gateway import LLMGateway
        gw = LLMGateway()

        # Register mock providers
        gw.provider_pool.register("mock1", MockProvider("mock1", response="r1"))
        gw.provider_pool.register("mock2", MockProvider("mock2", response="r1"))

        result = gw.generate_multi(
            "test prompt", "system",
            strategy="voting",
            provider_names=["mock1", "mock2"],
        )
        assert result["response"] == "r1"
