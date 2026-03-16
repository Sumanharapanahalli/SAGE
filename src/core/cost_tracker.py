"""
Per-tenant token and cost tracking backed by SQLite.

Records every LLM call with estimated token counts and USD cost.
Supports budget controls per tenant/solution.

SQLite table: llm_costs in data/audit_log.db
"""

import logging
import os
import sqlite3
import time
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cost table (USD per 1K tokens) — input and output rates
# ---------------------------------------------------------------------------
COST_PER_1K_TOKENS: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6":          {"input": 0.003,    "output": 0.015},
    "claude-opus-4-6":            {"input": 0.015,    "output": 0.075},
    "claude-sonnet-4-5":          {"input": 0.003,    "output": 0.015},
    "claude-opus-4-5":            {"input": 0.015,    "output": 0.075},
    "claude-haiku-4-5":           {"input": 0.00025,  "output": 0.00125},
    "gemini-2.5-flash":           {"input": 0.000075, "output": 0.0003},
    "gemini-2.5-pro":             {"input": 0.00125,  "output": 0.005},
    "gemini-2.0-flash":           {"input": 0.000075, "output": 0.0003},
    "gpt-4o":                     {"input": 0.0025,   "output": 0.010},
    "ollama":                     {"input": 0.0,      "output": 0.0},
    "local":                      {"input": 0.0,      "output": 0.0},
    "default":                    {"input": 0.002,    "output": 0.008},
}


def _get_db_path() -> str:
    """Resolve audit_log.db path from config or default."""
    try:
        import yaml
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "config", "config.yaml",
        )
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                cfg = yaml.safe_load(f) or {}
            return cfg.get("memory", {}).get("audit_db_path", "./data/audit_log.db")
    except Exception:
        pass
    return "./data/audit_log.db"


def _ensure_table(conn: sqlite3.Connection) -> None:
    """Create llm_costs table if it does not exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_costs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant          TEXT    NOT NULL DEFAULT '',
            solution        TEXT    NOT NULL DEFAULT '',
            model           TEXT    NOT NULL DEFAULT '',
            input_tokens    INTEGER NOT NULL DEFAULT 0,
            output_tokens   INTEGER NOT NULL DEFAULT 0,
            estimated_cost_usd REAL NOT NULL DEFAULT 0.0,
            trace_id        TEXT    NOT NULL DEFAULT '',
            recorded_at     TEXT    NOT NULL
        )
    """)
    conn.commit()


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate estimated USD cost for a given model and token counts."""
    # Normalise model key: strip provider prefix if present (e.g. "ollama/llama3.2")
    model_key = model.split("/")[-1] if "/" in model else model

    rates = COST_PER_1K_TOKENS.get(model_key)
    if rates is None:
        # Try prefix match (e.g. "claude-sonnet" matches "claude-sonnet-4-6")
        for key in COST_PER_1K_TOKENS:
            if model_key.startswith(key) or key.startswith(model_key):
                rates = COST_PER_1K_TOKENS[key]
                break
    if rates is None:
        rates = COST_PER_1K_TOKENS["default"]

    cost = (input_tokens / 1000.0) * rates["input"] + (output_tokens / 1000.0) * rates["output"]
    return round(cost, 8)


def record_usage(
    tenant: str,
    solution: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    trace_id: str = "",
) -> None:
    """
    Record a single LLM call's token usage and estimated cost.
    Silently logs errors rather than raising — cost tracking must never
    block inference.
    """
    try:
        db_path = _get_db_path()
        cost = _estimate_cost(model, input_tokens, output_tokens)
        recorded_at = datetime.now(timezone.utc).isoformat()

        conn = sqlite3.connect(db_path)
        _ensure_table(conn)
        conn.execute(
            """
            INSERT INTO llm_costs
                (tenant, solution, model, input_tokens, output_tokens,
                 estimated_cost_usd, trace_id, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (tenant, solution, model, input_tokens, output_tokens, cost, trace_id, recorded_at),
        )
        conn.commit()
        conn.close()
        logger.debug(
            "Cost recorded: tenant=%s solution=%s model=%s in=%d out=%d cost=$%.6f",
            tenant, solution, model, input_tokens, output_tokens, cost,
        )
    except Exception as exc:
        logger.warning("Cost tracking record_usage failed (non-fatal): %s", exc)


def get_summary(
    tenant: str = None,
    solution: str = None,
    period_days: int = 30,
) -> dict:
    """
    Return aggregated cost summary for the given tenant/solution over period_days.

    Returns a dict with keys:
        total_cost_usd, total_calls, total_input_tokens, total_output_tokens,
        avg_cost_per_call, by_model, by_solution, period_days
    """
    try:
        db_path = _get_db_path()
        conn = sqlite3.connect(db_path)
        _ensure_table(conn)
        conn.row_factory = sqlite3.Row

        since = (datetime.now(timezone.utc) - timedelta(days=period_days)).isoformat()

        conditions = ["recorded_at >= ?"]
        params: list = [since]
        if tenant:
            conditions.append("tenant = ?")
            params.append(tenant)
        if solution:
            conditions.append("solution = ?")
            params.append(solution)

        where = " AND ".join(conditions)

        row = conn.execute(
            f"""
            SELECT
                COALESCE(SUM(estimated_cost_usd), 0) AS total_cost,
                COUNT(*) AS total_calls,
                COALESCE(SUM(input_tokens), 0) AS total_input,
                COALESCE(SUM(output_tokens), 0) AS total_output
            FROM llm_costs WHERE {where}
            """,
            params,
        ).fetchone()

        total_cost = float(row["total_cost"])
        total_calls = int(row["total_calls"])
        total_input = int(row["total_input"])
        total_output = int(row["total_output"])
        avg_cost = round(total_cost / total_calls, 8) if total_calls > 0 else 0.0

        # By model breakdown
        model_rows = conn.execute(
            f"""
            SELECT model,
                   COUNT(*) AS calls,
                   COALESCE(SUM(estimated_cost_usd), 0) AS cost
            FROM llm_costs WHERE {where}
            GROUP BY model ORDER BY cost DESC
            """,
            params,
        ).fetchall()

        # By solution breakdown
        solution_rows = conn.execute(
            f"""
            SELECT solution,
                   COUNT(*) AS calls,
                   COALESCE(SUM(estimated_cost_usd), 0) AS cost
            FROM llm_costs WHERE {where}
            GROUP BY solution ORDER BY cost DESC
            """,
            params,
        ).fetchall()

        conn.close()

        return {
            "total_cost_usd":      round(total_cost, 6),
            "total_calls":         total_calls,
            "total_input_tokens":  total_input,
            "total_output_tokens": total_output,
            "avg_cost_per_call":   avg_cost,
            "by_model":            [dict(r) for r in model_rows],
            "by_solution":         [dict(r) for r in solution_rows],
            "period_days":         period_days,
            "tenant":              tenant,
            "solution":            solution,
        }

    except Exception as exc:
        logger.warning("get_summary failed (non-fatal): %s", exc)
        return {
            "total_cost_usd": 0.0, "total_calls": 0,
            "total_input_tokens": 0, "total_output_tokens": 0,
            "avg_cost_per_call": 0.0, "by_model": [], "by_solution": [],
            "period_days": period_days, "tenant": tenant, "solution": solution,
        }


def get_daily(
    tenant: str = None,
    solution: str = None,
    period_days: int = 30,
) -> list[dict]:
    """
    Return daily cost breakdown for charting.

    Returns list of {date, calls, cost_usd} dicts ordered by date ascending.
    """
    try:
        db_path = _get_db_path()
        conn = sqlite3.connect(db_path)
        _ensure_table(conn)

        since = (datetime.now(timezone.utc) - timedelta(days=period_days)).isoformat()

        conditions = ["recorded_at >= ?"]
        params: list = [since]
        if tenant:
            conditions.append("tenant = ?")
            params.append(tenant)
        if solution:
            conditions.append("solution = ?")
            params.append(solution)

        where = " AND ".join(conditions)

        rows = conn.execute(
            f"""
            SELECT
                DATE(recorded_at) AS day,
                COUNT(*) AS calls,
                COALESCE(SUM(estimated_cost_usd), 0) AS cost_usd
            FROM llm_costs WHERE {where}
            GROUP BY day ORDER BY day ASC
            """,
            params,
        ).fetchall()
        conn.close()

        return [{"date": r[0], "calls": r[1], "cost_usd": round(r[2], 6)} for r in rows]

    except Exception as exc:
        logger.warning("get_daily failed (non-fatal): %s", exc)
        return []


def check_budget(tenant: str, solution: str) -> tuple[bool, float]:
    """
    Check whether the tenant/solution is within its configured monthly budget.

    Returns:
        (is_within_budget, current_month_spend_usd)

    When budgets.enabled=false, always returns (True, 0.0).
    Raises ValueError if hard_cutoff=true and budget is exceeded.
    """
    try:
        import yaml
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "config", "config.yaml",
        )
        if not os.path.exists(config_path):
            return True, 0.0
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception:
        return True, 0.0

    budget_cfg = cfg.get("llm", {}).get("budgets", {})
    if not budget_cfg.get("enabled", False):
        return True, 0.0

    # Get the limit for this solution (fall back to default)
    per_solution: dict = budget_cfg.get("per_solution", {})
    limit_usd: float = per_solution.get(solution, budget_cfg.get("default_monthly_usd", 50.0))

    # Current month spend
    try:
        now = datetime.now(timezone.utc)
        month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc).isoformat()

        db_path = _get_db_path()
        conn = sqlite3.connect(db_path)
        _ensure_table(conn)

        conditions = ["recorded_at >= ?"]
        params: list = [month_start]
        if tenant:
            conditions.append("tenant = ?")
            params.append(tenant)
        if solution:
            conditions.append("solution = ?")
            params.append(solution)

        where = " AND ".join(conditions)
        row = conn.execute(
            f"SELECT COALESCE(SUM(estimated_cost_usd), 0) FROM llm_costs WHERE {where}",
            params,
        ).fetchone()
        conn.close()

        current_spend = float(row[0])
    except Exception as exc:
        logger.warning("check_budget spend query failed (non-fatal): %s", exc)
        return True, 0.0

    within_budget = current_spend < limit_usd
    hard_cutoff = budget_cfg.get("hard_cutoff", False)

    if not within_budget and hard_cutoff:
        raise ValueError(
            f"Monthly budget of ${limit_usd:.2f} exceeded for {solution} "
            f"(spent ${current_spend:.4f}). Hard cutoff is enabled."
        )

    return within_budget, round(current_spend, 6)
