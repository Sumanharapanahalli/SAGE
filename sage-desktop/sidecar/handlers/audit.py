"""Audit handler — read-only queries against compliance_audit_log.

Queries run as raw SQL against ``audit_logger.db_path`` so the handler is
independent of AuditLogger's write path. Trace IDs live inside the
metadata JSON blob (AuditLogger.log_event does not populate the dedicated
``trace_id`` column), so filtering uses SQLite's ``json_extract`` operator.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Optional

from rpc import RpcError, RPC_INVALID_PARAMS

# Injected by __main__.py at startup. Tests monkey-patch this.
_logger = None  # type: Optional[object]


def _require_logger():
    if _logger is None:
        raise RpcError(RPC_INVALID_PARAMS, "audit logger not initialized")
    return _logger


def _conn():
    lg = _require_logger()
    conn = sqlite3.connect(lg.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_event(row: sqlite3.Row) -> dict:
    """Shape a compliance_audit_log row for JSON transport.

    Extracts trace_id from metadata JSON when the dedicated column is NULL,
    and parses metadata into a dict rather than returning raw JSON text.
    """
    d = dict(row)
    metadata_raw = d.get("metadata") or "{}"
    try:
        metadata = json.loads(metadata_raw)
    except (TypeError, ValueError):
        metadata = {}
    d["metadata"] = metadata
    # Prefer dedicated column; fall back to metadata.trace_id
    if not d.get("trace_id"):
        d["trace_id"] = metadata.get("trace_id")
    return d


def _require_trace_id(params: dict) -> str:
    trace_id = params.get("trace_id")
    if not trace_id or not isinstance(trace_id, str):
        raise RpcError(RPC_INVALID_PARAMS, "missing or invalid 'trace_id'")
    return trace_id


# ---------- handlers ----------

def list_events(params: dict) -> dict:
    """List audit events newest-first with pagination + optional filters."""
    limit = int(params.get("limit", 50))
    offset = int(params.get("offset", 0))
    action_type = params.get("action_type")
    trace_id = params.get("trace_id")

    where_clauses = []
    args: list = []
    if action_type:
        where_clauses.append("action_type = ?")
        args.append(action_type)
    if trace_id:
        where_clauses.append(
            "(trace_id = ? OR json_extract(metadata, '$.trace_id') = ?)"
        )
        args.extend([trace_id, trace_id])

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    conn = _conn()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM compliance_audit_log {where_sql}",
            args,
        ).fetchone()["c"]
        rows = conn.execute(
            f"""SELECT * FROM compliance_audit_log
                {where_sql}
                ORDER BY timestamp DESC, rowid DESC
                LIMIT ? OFFSET ?""",
            args + [limit, offset],
        ).fetchall()
    finally:
        conn.close()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "events": [_row_to_event(r) for r in rows],
    }


def get_by_trace(params: dict) -> dict:
    """All events for one trace_id, chronological order (oldest first)."""
    trace_id = _require_trace_id(params)
    conn = _conn()
    try:
        rows = conn.execute(
            """SELECT * FROM compliance_audit_log
               WHERE trace_id = ? OR json_extract(metadata, '$.trace_id') = ?
               ORDER BY timestamp ASC, rowid ASC""",
            (trace_id, trace_id),
        ).fetchall()
    finally:
        conn.close()
    return {"trace_id": trace_id, "events": [_row_to_event(r) for r in rows]}


def stats(params: dict) -> dict:
    """Aggregate counts — total events, plus per-action_type breakdown."""
    conn = _conn()
    try:
        total = conn.execute(
            "SELECT COUNT(*) AS c FROM compliance_audit_log"
        ).fetchone()["c"]
        rows = conn.execute(
            """SELECT action_type, COUNT(*) AS c
               FROM compliance_audit_log
               GROUP BY action_type"""
        ).fetchall()
    finally:
        conn.close()
    by_action_type = {r["action_type"]: r["c"] for r in rows if r["action_type"]}
    return {"total": total, "by_action_type": by_action_type}
