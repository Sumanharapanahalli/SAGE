"""Costs handler — exposes src.core.cost_tracker to the desktop.

Ports /costs/summary, /costs/daily, /costs/budget (api.py:4501-4579) so an
operator can review LLM spend and set monthly budgets without leaving the
desktop app. Like compliance.py, cost_tracker's get_summary/get_daily are
pure query functions over the llm_costs SQLite table — no store/instance
to wire at startup, so these handlers import cost_tracker directly at
call time rather than reading an injected module-level variable.

set_budget writes straight to config.yaml (mirroring api.py's
costs_set_budget: read -> merge into llm.budgets.per_solution -> write),
bypassing the proposal queue for the same reason yaml_edit.py does — the
desktop operator's own explicit action is what triggers the write, not an
agent proposal. ``_config_path`` is a test seam only: production code
always infers the real repo-root config/config.yaml (same SAGE_ROOT-then-
infer strategy app.py uses); tests monkeypatch it directly (mirroring
yaml_edit.py's ``_solution_path`` injection) so a test run never touches
the real repo's config/config.yaml.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import yaml as _yaml

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError

# Test seam — see module docstring. None in production; _resolve_config_path()
# then infers the real repo-root config/config.yaml.
_config_path: Optional[Path] = None


def _resolve_config_path() -> Path:
    if _config_path is not None:
        return Path(_config_path)
    env = os.environ.get("SAGE_ROOT")
    if env and os.path.isdir(env):
        root = env
    else:
        root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..")
        )
    return Path(root) / "config" / "config.yaml"


def _optional_str(params: dict, key: str) -> Optional[str]:
    value = params.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise RpcError(RPC_INVALID_PARAMS, f"'{key}' must be a string")
    return value


def _period_days(params: dict) -> int:
    value = params.get("period_days")
    if value is None:
        return 30
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RpcError(RPC_INVALID_PARAMS, "'period_days' must be a number")
    return int(value)


def summary(params: dict) -> dict:
    try:
        from src.core import cost_tracker

        tenant = _optional_str(params, "tenant")
        solution = _optional_str(params, "solution")
        period_days = _period_days(params)
        return cost_tracker.get_summary(
            tenant=tenant, solution=solution, period_days=period_days
        )
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"costs.summary failed: {e}") from e


def daily(params: dict) -> dict:
    try:
        from src.core import cost_tracker

        tenant = _optional_str(params, "tenant")
        solution = _optional_str(params, "solution")
        period_days = _period_days(params)
        rows = cost_tracker.get_daily(
            tenant=tenant, solution=solution, period_days=period_days
        )
        return {"daily": rows, "count": len(rows), "period_days": period_days}
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"costs.daily failed: {e}") from e


def set_budget(params: dict) -> dict:
    try:
        monthly_usd = params.get("monthly_usd")
        if (
            monthly_usd is None
            or isinstance(monthly_usd, bool)
            or not isinstance(monthly_usd, (int, float))
        ):
            raise RpcError(RPC_INVALID_PARAMS, "missing or invalid 'monthly_usd'")

        tenant = _optional_str(params, "tenant")
        solution = _optional_str(params, "solution")
        key = solution or tenant or "default"

        config_path = _resolve_config_path()
        if config_path.exists():
            with open(config_path, "r") as f:
                cfg = _yaml.safe_load(f) or {}
        else:
            cfg = {}

        llm_section = cfg.setdefault("llm", {})
        budget_section = llm_section.setdefault("budgets", {})
        per_solution = budget_section.setdefault("per_solution", {})
        per_solution[key] = float(monthly_usd)

        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            _yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)

        return {
            "saved": True,
            "key": key,
            "monthly_usd": float(monthly_usd),
        }
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"costs.set_budget failed: {e}") from e
