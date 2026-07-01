"""Tests for the costs handler.

Ports /costs/summary, /costs/daily, /costs/budget (api.py:4501-4579).

Like compliance.py, cost_tracker's get_summary/get_daily are pure query
functions over the llm_costs SQLite table — no store to wire, so tests
monkeypatch cost_tracker's own ``_get_db_path`` (mirroring test_audit.py's
temp-SQLite-DB fixture) so no test ever touches a real audit_log.db.

set_budget tests monkeypatch ``handlers.costs._config_path`` directly
(mirroring test_yaml_edit.py's ``_solution_path`` injection) so no test
ever touches the real repo's config/config.yaml.
"""
from __future__ import annotations

import pytest
import yaml as _yaml

from handlers import costs
from rpc import RpcError


# ---------------------------------------------------------------------------
# summary / daily
# ---------------------------------------------------------------------------

@pytest.fixture
def cost_db(tmp_path, monkeypatch):
    """Fresh llm_costs SQLite DB, injected via cost_tracker._get_db_path."""
    from src.core import cost_tracker

    db_path = str(tmp_path / "costs.db")
    monkeypatch.setattr(cost_tracker, "_get_db_path", lambda: db_path)
    return cost_tracker


def _seed(cost_tracker_mod, n=3, model="claude-sonnet-4-6", solution="demo", tenant="acme"):
    for i in range(n):
        cost_tracker_mod.record_usage(
            tenant=tenant,
            solution=solution,
            model=model,
            input_tokens=1000,
            output_tokens=500,
            trace_id=f"t-{i}",
        )


def test_summary_returns_zeroed_defaults_when_no_calls_recorded(cost_db):
    out = costs.summary({})
    assert out["total_cost_usd"] == 0.0
    assert out["total_calls"] == 0
    assert out["period_days"] == 30


def test_summary_aggregates_recorded_calls(cost_db):
    _seed(cost_db, n=3)
    out = costs.summary({})
    assert out["total_calls"] == 3
    assert out["total_cost_usd"] > 0
    assert out["by_model"][0]["model"] == "claude-sonnet-4-6"


def test_summary_filters_by_solution(cost_db):
    _seed(cost_db, n=2, solution="demo")
    _seed(cost_db, n=1, solution="other")
    out = costs.summary({"solution": "demo"})
    assert out["total_calls"] == 2


def test_summary_filters_by_tenant(cost_db):
    _seed(cost_db, n=2, tenant="acme")
    _seed(cost_db, n=1, tenant="other-tenant")
    out = costs.summary({"tenant": "acme"})
    assert out["total_calls"] == 2


def test_summary_defaults_period_days_to_30_when_missing(cost_db):
    out = costs.summary({})
    assert out["period_days"] == 30


def test_summary_defaults_period_days_to_30_when_none(cost_db):
    out = costs.summary({"period_days": None})
    assert out["period_days"] == 30


def test_summary_honours_custom_period_days(cost_db):
    out = costs.summary({"period_days": 7})
    assert out["period_days"] == 7


def test_summary_rejects_invalid_period_days_type(cost_db):
    with pytest.raises(RpcError) as e:
        costs.summary({"period_days": "not-a-number"})
    assert e.value.code == -32602


def test_summary_rejects_non_string_tenant(cost_db):
    with pytest.raises(RpcError) as e:
        costs.summary({"tenant": 123})
    assert e.value.code == -32602


def test_summary_wraps_unexpected_errors(cost_db, monkeypatch):
    from src.core import cost_tracker

    def _boom(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(cost_tracker, "get_summary", _boom)
    with pytest.raises(RpcError) as e:
        costs.summary({})
    assert e.value.code == -32000


def test_daily_returns_empty_list_when_no_calls(cost_db):
    out = costs.daily({})
    assert out == {"daily": [], "count": 0, "period_days": 30}


def test_daily_returns_rows_for_recorded_calls(cost_db):
    _seed(cost_db, n=2)
    out = costs.daily({})
    assert out["count"] == 1  # both calls land on the same UTC day
    assert out["daily"][0]["calls"] == 2


def test_daily_defaults_period_days_to_30_when_missing(cost_db):
    out = costs.daily({})
    assert out["period_days"] == 30


def test_daily_honours_custom_period_days(cost_db):
    out = costs.daily({"period_days": 7})
    assert out["period_days"] == 7


def test_daily_rejects_invalid_period_days_type(cost_db):
    with pytest.raises(RpcError) as e:
        costs.daily({"period_days": "soon"})
    assert e.value.code == -32602


def test_daily_wraps_unexpected_errors(cost_db, monkeypatch):
    from src.core import cost_tracker

    def _boom(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(cost_tracker, "get_daily", _boom)
    with pytest.raises(RpcError) as e:
        costs.daily({})
    assert e.value.code == -32000


# ---------------------------------------------------------------------------
# set_budget
# ---------------------------------------------------------------------------

@pytest.fixture
def wired_config(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.yaml"
    monkeypatch.setattr(costs, "_config_path", cfg_path)
    return cfg_path


def test_set_budget_creates_config_when_missing(wired_config):
    out = costs.set_budget({"solution": "demo", "monthly_usd": 50})
    assert out == {"saved": True, "key": "demo", "monthly_usd": 50.0}
    assert wired_config.exists()

    cfg = _yaml.safe_load(wired_config.read_text(encoding="utf-8"))
    assert cfg["llm"]["budgets"]["per_solution"]["demo"] == 50.0


def test_set_budget_prefers_solution_over_tenant(wired_config):
    out = costs.set_budget({"tenant": "acme", "solution": "demo", "monthly_usd": 10})
    assert out["key"] == "demo"


def test_set_budget_falls_back_to_tenant_when_no_solution(wired_config):
    out = costs.set_budget({"tenant": "acme", "monthly_usd": 10})
    assert out["key"] == "acme"


def test_set_budget_falls_back_to_default_when_neither_given(wired_config):
    out = costs.set_budget({"monthly_usd": 10})
    assert out["key"] == "default"


def test_set_budget_merges_into_existing_config(wired_config):
    wired_config.write_text(
        "llm:\n  provider: gemini\nother_section:\n  key: value\n",
        encoding="utf-8",
    )
    costs.set_budget({"solution": "demo", "monthly_usd": 25})

    cfg = _yaml.safe_load(wired_config.read_text(encoding="utf-8"))
    assert cfg["llm"]["provider"] == "gemini"
    assert cfg["llm"]["budgets"]["per_solution"]["demo"] == 25.0
    assert cfg["other_section"]["key"] == "value"


def test_set_budget_overwrites_existing_key_for_same_solution(wired_config):
    costs.set_budget({"solution": "demo", "monthly_usd": 10})
    costs.set_budget({"solution": "demo", "monthly_usd": 99})

    cfg = _yaml.safe_load(wired_config.read_text(encoding="utf-8"))
    assert cfg["llm"]["budgets"]["per_solution"]["demo"] == 99.0


def test_set_budget_requires_monthly_usd(wired_config):
    with pytest.raises(RpcError) as e:
        costs.set_budget({"solution": "demo"})
    assert e.value.code == -32602


def test_set_budget_rejects_non_numeric_monthly_usd(wired_config):
    with pytest.raises(RpcError) as e:
        costs.set_budget({"solution": "demo", "monthly_usd": "fifty"})
    assert e.value.code == -32602


def test_set_budget_rejects_non_string_solution(wired_config):
    with pytest.raises(RpcError) as e:
        costs.set_budget({"solution": 123, "monthly_usd": 10})
    assert e.value.code == -32602


def test_set_budget_wraps_unexpected_write_errors(wired_config, monkeypatch):
    def _boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(_yaml, "dump", _boom)
    with pytest.raises(RpcError) as e:
        costs.set_budget({"solution": "demo", "monthly_usd": 10})
    assert e.value.code == -32000
