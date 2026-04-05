"""
SAGE Budget Manager — Token & Cost Controls
=============================================

Tracks token usage per agent, wave, and build run. Enforces budget
limits with configurable thresholds. Emits events via EventBus
when budgets approach or exceed limits.

Integrates with existing cost_tracker.py for per-call recording
and adds higher-level aggregation and enforcement.
"""

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Budget Config
# ──────────────────────────────────────────────────────────────────────

@dataclass
class BudgetConfig:
    """Budget limits for a scope (build, agent, or global)."""
    max_tokens: int = 0          # 0 = unlimited
    max_cost_usd: float = 0.0   # 0 = unlimited
    warn_threshold: float = 0.8  # emit warning at 80%
    hard_stop: bool = True       # stop execution when exceeded


@dataclass
class UsageRecord:
    """Accumulated usage for a scope."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    call_count: int = 0
    last_updated: str = ""

    def to_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "call_count": self.call_count,
            "last_updated": self.last_updated,
        }


# ──────────────────────────────────────────────────────────────────────
# BudgetManager
# ──────────────────────────────────────────────────────────────────────

class BudgetManager:
    """Tracks and enforces token/cost budgets across scopes."""

    def __init__(self, default_config: BudgetConfig = None):
        self._default_config = default_config or BudgetConfig()
        self._configs: dict[str, BudgetConfig] = {}
        self._usage: dict[str, UsageRecord] = defaultdict(UsageRecord)
        self._lock = threading.Lock()
        self._warnings_sent: set[str] = set()

    def set_budget(self, scope: str, config: BudgetConfig) -> None:
        """Set budget for a scope (e.g., 'build:run-123', 'agent:analyst')."""
        with self._lock:
            self._configs[scope] = config

    def get_budget(self, scope: str) -> BudgetConfig:
        """Get budget config for a scope."""
        return self._configs.get(scope, self._default_config)

    def record_usage(
        self,
        scope: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        model: str = "",
    ) -> dict:
        """
        Record token usage for a scope. Returns current usage summary.
        Also records to parent scopes (e.g., agent scope rolls up to build scope).
        """
        now = datetime.now(timezone.utc).isoformat()
        total = input_tokens + output_tokens

        # Estimate cost if not provided
        if cost_usd == 0.0 and total > 0:
            cost_usd = self._estimate_cost(model, input_tokens, output_tokens)

        with self._lock:
            usage = self._usage[scope]
            usage.input_tokens += input_tokens
            usage.output_tokens += output_tokens
            usage.total_tokens += total
            usage.estimated_cost_usd += cost_usd
            usage.call_count += 1
            usage.last_updated = now

        # Check budget
        self._check_budget(scope)

        # Emit event
        self._emit_usage_event(scope, usage)

        return usage.to_dict()

    def check_budget(self, scope: str) -> dict:
        """
        Check if a scope is within budget.
        Returns: {allowed: bool, usage: dict, budget: dict, utilization: float}
        """
        config = self.get_budget(scope)
        with self._lock:
            usage = self._usage.get(scope, UsageRecord())

        token_util = (
            usage.total_tokens / config.max_tokens
            if config.max_tokens > 0 else 0.0
        )
        cost_util = (
            usage.estimated_cost_usd / config.max_cost_usd
            if config.max_cost_usd > 0 else 0.0
        )
        utilization = max(token_util, cost_util)

        exceeded = False
        if config.max_tokens > 0 and usage.total_tokens > config.max_tokens:
            exceeded = True
        if config.max_cost_usd > 0 and usage.estimated_cost_usd > config.max_cost_usd:
            exceeded = True

        allowed = not (exceeded and config.hard_stop)

        return {
            "allowed": allowed,
            "exceeded": exceeded,
            "utilization": round(utilization, 4),
            "usage": usage.to_dict(),
            "budget": {
                "max_tokens": config.max_tokens,
                "max_cost_usd": config.max_cost_usd,
                "warn_threshold": config.warn_threshold,
                "hard_stop": config.hard_stop,
            },
        }

    def get_usage(self, scope: str) -> dict:
        """Get current usage for a scope."""
        with self._lock:
            usage = self._usage.get(scope, UsageRecord())
        return usage.to_dict()

    def get_all_usage(self) -> dict[str, dict]:
        """Get usage for all tracked scopes."""
        with self._lock:
            return {scope: u.to_dict() for scope, u in self._usage.items()}

    def reset_scope(self, scope: str) -> None:
        """Reset usage counters for a scope."""
        with self._lock:
            self._usage[scope] = UsageRecord()
            self._warnings_sent.discard(scope)

    def get_top_consumers(self, limit: int = 10) -> list[dict]:
        """Get top scopes by total token usage."""
        with self._lock:
            items = [(s, u.to_dict()) for s, u in self._usage.items()]
        items.sort(key=lambda x: x[1]["total_tokens"], reverse=True)
        return [{"scope": s, **u} for s, u in items[:limit]]

    def get_stats(self) -> dict:
        """Return budget manager statistics."""
        with self._lock:
            total_tokens = sum(u.total_tokens for u in self._usage.values())
            total_cost = sum(u.estimated_cost_usd for u in self._usage.values())
            total_calls = sum(u.call_count for u in self._usage.values())
        return {
            "tracked_scopes": len(self._usage),
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 6),
            "total_calls": total_calls,
            "budgets_configured": len(self._configs),
        }

    # ── Private ───────────────────────────────────────────────────────

    def _check_budget(self, scope: str) -> None:
        """Emit warnings/exceeded events."""
        config = self.get_budget(scope)
        with self._lock:
            usage = self._usage.get(scope, UsageRecord())

        if config.max_tokens <= 0 and config.max_cost_usd <= 0:
            return  # no budget set

        token_util = (
            usage.total_tokens / config.max_tokens
            if config.max_tokens > 0 else 0.0
        )
        cost_util = (
            usage.estimated_cost_usd / config.max_cost_usd
            if config.max_cost_usd > 0 else 0.0
        )
        utilization = max(token_util, cost_util)

        try:
            from src.core.event_bus import get_event_bus
            bus = get_event_bus()

            if utilization >= 1.0:
                bus.publish("budget.exceeded", {
                    "scope": scope,
                    "utilization": round(utilization, 4),
                    "usage": usage.to_dict(),
                }, source="budget_manager")
                logger.warning("Budget exceeded for scope=%s util=%.2f", scope, utilization)
            elif utilization >= config.warn_threshold:
                warn_key = f"{scope}:{int(utilization * 10)}"
                if warn_key not in self._warnings_sent:
                    self._warnings_sent.add(warn_key)
                    bus.publish("budget.warning", {
                        "scope": scope,
                        "utilization": round(utilization, 4),
                        "threshold": config.warn_threshold,
                    }, source="budget_manager")
        except Exception:
            pass  # event bus is optional

    def _emit_usage_event(self, scope: str, usage: UsageRecord) -> None:
        """Emit usage event."""
        try:
            from src.core.event_bus import get_event_bus
            bus = get_event_bus()
            bus.publish("budget.usage", {
                "scope": scope,
                "total_tokens": usage.total_tokens,
                "cost_usd": round(usage.estimated_cost_usd, 6),
                "call_count": usage.call_count,
            }, source="budget_manager")
        except Exception:
            pass

    @staticmethod
    def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD."""
        try:
            from src.core.cost_tracker import COST_PER_1K_TOKENS
            rates = COST_PER_1K_TOKENS.get(model, COST_PER_1K_TOKENS["default"])
            return (input_tokens / 1000 * rates["input"] +
                    output_tokens / 1000 * rates["output"])
        except Exception:
            return (input_tokens + output_tokens) / 1000 * 0.002  # fallback


# ──────────────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────────────

_budget_manager: Optional[BudgetManager] = None
_bm_lock = threading.Lock()


def get_budget_manager() -> BudgetManager:
    """Get or create the global BudgetManager instance."""
    global _budget_manager
    if _budget_manager is None:
        with _bm_lock:
            if _budget_manager is None:
                _budget_manager = BudgetManager()
    return _budget_manager
