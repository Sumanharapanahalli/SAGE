"""Activity handler — the live triage feed over compliance_audit_log.

Distinct from ``audit.py`` (the paginated evidence table, filtered by an
exact ``action_type`` match). This is the *triage* view: it answers "show me
everything that FAILED", which an exact-match dropdown structurally cannot
express — an error can surface in ``event_type``, in ``action_type``, in the
``status`` column, or only in the free text of ``output_content``.

Classification is computed SERVER-side (SQL predicates + a mirrored Python
classifier) so pagination and totals stay correct: filtering client-side
after a LIMIT would silently drop matches beyond the first page.

Reads via raw SQL against ``audit_logger.db_path`` (same pattern as
audit.py) so the handler is independent of AuditLogger's write path.
"""

from __future__ import annotations

import json
import sqlite3

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError

# Injected by app.py::_wire_handlers at startup. Tests monkey-patch this.
_logger = None  # type: Optional[object]

# --- classification vocabulary -------------------------------------------
# Ported from web/src/pages/Activity.tsx::classifyEvent. The precedence of
# these buckets is load-bearing: errors are checked first, so an event whose
# type says "proposal" but whose output says "error" triages as an error.
_ERROR_KW = ("error", "failed")
_PROPOSAL_KW = ("proposal", "approved", "rejected", "pending")
_TASK_KW = ("task", "completed", "submit", "queue")
_LLM_KW = ("llm", "generate", "model")

CATEGORIES = ("tasks", "proposals", "llm", "errors")

# The web client collapses the DB's event_type and action_type into one field
# before classifying, and so loses whichever it dropped. Desktop has both
# columns, so match against the pair.
_TYPE_SQL = "LOWER(COALESCE(event_type,'') || ' ' || COALESCE(action_type,''))"
_TEXT_SQL = "LOWER(COALESCE(output_content,''))"

MAX_LIMIT = 500


def _require_logger():
    if _logger is None:
        raise RpcError(RPC_INVALID_PARAMS, "audit logger not initialized")
    return _logger


def _conn():
    lg = _require_logger()
    conn = sqlite3.connect(lg.db_path)
    conn.row_factory = sqlite3.Row
    return conn


# --- predicate builders (SQL and Python kept in lockstep) -----------------


def _like_any(exprs: tuple, keywords: tuple) -> tuple:
    """(sql, args) matching any keyword in any of the given SQL expressions."""
    clauses, args = [], []
    for expr in exprs:
        for kw in keywords:
            clauses.append(f"{expr} LIKE ?")
            args.append(f"%{kw}%")
    return "(" + " OR ".join(clauses) + ")", args


def _sql_error() -> tuple:
    # status='ERROR' is a first-class failure signal the web feed never read
    # (it only ever saw type + output text). Include it.
    sql, args = _like_any((_TYPE_SQL, _TEXT_SQL), _ERROR_KW)
    return f"({sql} OR UPPER(COALESCE(status,'')) = 'ERROR')", args


def _sql_proposal() -> tuple:
    return _like_any((_TYPE_SQL,), _PROPOSAL_KW)


def _sql_task_kw() -> tuple:
    return _like_any((_TYPE_SQL,), _TASK_KW)


def _sql_llm() -> tuple:
    return _like_any((_TYPE_SQL,), _LLM_KW)


def _category_predicate(category: str) -> tuple:
    """SQL for one category, replicating classifyEvent's if-chain precedence.

    The chain is: errors → proposals → task-keywords → llm → fallback(tasks).
    So 'llm' means "llm-ish AND none of the earlier buckets matched", and
    'tasks' absorbs the fallback (anything left over).
    """
    e_sql, e_args = _sql_error()
    p_sql, p_args = _sql_proposal()
    t_sql, t_args = _sql_task_kw()
    l_sql, l_args = _sql_llm()

    if category == "errors":
        return e_sql, e_args
    if category == "proposals":
        return f"(NOT {e_sql} AND {p_sql})", e_args + p_args
    if category == "llm":
        return (
            f"(NOT {e_sql} AND NOT {p_sql} AND NOT {t_sql} AND {l_sql})",
            e_args + p_args + t_args + l_args,
        )
    if category == "tasks":
        # everything not error / proposal / llm — includes the fallback bucket
        return (
            f"(NOT {e_sql} AND NOT {p_sql} AND ({t_sql} OR NOT {l_sql}))",
            e_args + p_args + t_args + l_args,
        )
    raise RpcError(
        RPC_INVALID_PARAMS,
        f"unknown category '{category}'. Valid categories: {list(CATEGORIES)}",
    )


def classify(row: dict) -> str:
    """Python mirror of _category_predicate — same precedence, same keywords."""
    t = f"{(row.get('event_type') or '')} {(row.get('action_type') or '')}".lower()
    d = (row.get("output_content") or "").lower()
    status = (row.get("status") or "").upper()

    if status == "ERROR" or any(k in t or k in d for k in _ERROR_KW):
        return "errors"
    if any(k in t for k in _PROPOSAL_KW):
        return "proposals"
    if any(k in t for k in _TASK_KW):
        return "tasks"
    if any(k in t for k in _LLM_KW):
        return "llm"
    return "tasks"


def _row_to_event(row: sqlite3.Row) -> dict:
    """Full event row for JSON transport, annotated with its category.

    Trace IDs live inside the metadata JSON blob when AuditLogger.log_event
    didn't populate the dedicated column, so fall back to it. (The web feed
    read ``verification_signature`` for the trace id — a column that is a
    documented placeholder and is always NULL. That is a bug, not a contract.)
    """
    d = dict(row)
    try:
        metadata = json.loads(d.get("metadata") or "{}")
    except (TypeError, ValueError):
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    d["metadata"] = metadata
    if not d.get("trace_id"):
        d["trace_id"] = metadata.get("trace_id")
    d["category"] = classify(d)
    return d


def _clamp_limit(params: dict) -> int:
    try:
        limit = int(params.get("limit", 50))
    except (TypeError, ValueError):
        raise RpcError(RPC_INVALID_PARAMS, "'limit' must be an integer")
    return max(1, min(limit, MAX_LIMIT))


def _clamp_offset(params: dict) -> int:
    try:
        offset = int(params.get("offset", 0))
    except (TypeError, ValueError):
        raise RpcError(RPC_INVALID_PARAMS, "'offset' must be an integer")
    return max(0, offset)


# ---------- handlers ----------


def list_events(params: dict) -> dict:
    """Triage feed: full rows, newest-first, category + free-text filtered."""
    limit = _clamp_limit(params)
    offset = _clamp_offset(params)
    category = params.get("category") or None
    query = (params.get("query") or "").strip()

    where, args = [], []

    if category and category != "all":
        if not isinstance(category, str):
            raise RpcError(RPC_INVALID_PARAMS, "'category' must be a string")
        sql, cat_args = _category_predicate(category)
        where.append(sql)
        args.extend(cat_args)

    if query:
        like = f"%{query.lower()}%"
        where.append(
            "(LOWER(COALESCE(actor,'')) LIKE ?"
            " OR LOWER(COALESCE(action_type,'')) LIKE ?"
            " OR LOWER(COALESCE(event_type,'')) LIKE ?"
            " OR LOWER(COALESCE(output_content,'')) LIKE ?)"
        )
        args.extend([like, like, like, like])

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    try:
        conn = _conn()
    except RpcError:
        raise
    try:
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM compliance_audit_log {where_sql}", args
        ).fetchone()["c"]
        rows = conn.execute(
            f"""SELECT * FROM compliance_audit_log
                {where_sql}
                ORDER BY timestamp DESC, rowid DESC
                LIMIT ? OFFSET ?""",
            args + [limit, offset],
        ).fetchall()
    except sqlite3.Error as e:
        raise RpcError(RPC_SIDECAR_ERROR, f"activity.list failed: {e}") from e
    finally:
        conn.close()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "category": category or "all",
        "query": query,
        "events": [_row_to_event(r) for r in rows],
    }
