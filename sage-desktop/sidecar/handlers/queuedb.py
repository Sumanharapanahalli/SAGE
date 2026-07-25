"""Durable task-queue reader — the full task list, including history.

``handlers/queue.py`` reads ``TaskQueue._tasks``, the in-memory dict. That
dict is rehydrated at startup from PENDING/IN_PROGRESS rows only
(``_restore_pending_tasks``), so it structurally cannot answer "what ran
yesterday" — completed/failed/cancelled tasks are invisible to it. This
handler queries the ``task_queue`` SQLite TABLE directly instead, which is
the only source that holds history, full payloads, and per-task errors.

Mirrors api.py's ``GET /queue/tasks`` contract (payload/result decoded from
JSON, LEFT JOIN to ``feature_requests`` for feature_title/feature_scope),
with two deliberate divergences:

1. Two DB FILES, not one. api.py joins inside a single framework-global
   ``data/audit_log.db`` that happens to hold both tables. Desktop scopes
   the queue per-solution (Phase 5l) at ``<solution>/.sage/queue.db`` while
   feature_requests lives in ``<solution>/.sage/audit_log.db``, so the join
   is done by ATTACHing the feature DB. Both paths are injected by
   ``app._wire_handlers`` — never defaulted.
2. ``subtasks`` reads the table, not ``get_all_tasks()``. api.py's
   ``/tasks/{id}/subtasks`` filters the in-memory dict, so a completed
   parent's children silently vanish from the response. Same query, durable
   source.
"""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Optional

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError

_LIMIT_DEFAULT = 100
_LIMIT_MAX = 1000

# TaskStatus values, verbatim — a key the framework never emits would make
# the UI's counter tiles read zero forever.
_STATUSES = ("pending", "in_progress", "completed", "failed", "blocked", "cancelled")

# Injected by app._wire_handlers. Tests monkey-patch these.
_db_path: Optional[str] = None  # <solution>/.sage/queue.db
_feature_db_path: Optional[str] = None  # <solution>/.sage/audit_log.db


def _require_db() -> str:
    if not _db_path:
        raise RpcError(
            RPC_SIDECAR_ERROR, "queue database is not wired (no solution active)"
        )
    return _db_path


def _require_dict(params: Any) -> dict:
    if params is None:
        return {}
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    return params


def _coerce_limit(value: Any) -> int:
    if value is None:
        return _LIMIT_DEFAULT
    if isinstance(value, bool) or not isinstance(value, int):
        raise RpcError(RPC_INVALID_PARAMS, "'limit' must be an integer")
    if value < 1 or value > _LIMIT_MAX:
        raise RpcError(
            RPC_INVALID_PARAMS, f"'limit' must be between 1 and {_LIMIT_MAX}"
        )
    return value


def _optional_str(p: dict, key: str) -> Optional[str]:
    value = p.get(key)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise RpcError(RPC_INVALID_PARAMS, f"'{key}' must be a string")
    return value


def _connect() -> tuple[sqlite3.Connection, bool]:
    """Open queue.db; ATTACH the feature DB when it really has the table.

    Returns (conn, joinable). ATTACH on a missing path would create an empty
    file, so the path is checked first — desktop must not fabricate a store.
    """
    conn = sqlite3.connect(_require_db())
    conn.row_factory = sqlite3.Row
    joinable = False
    if _feature_db_path and os.path.exists(_feature_db_path):
        try:
            conn.execute("ATTACH DATABASE ? AS fr_db", (_feature_db_path,))
            row = conn.execute(
                "SELECT name FROM fr_db.sqlite_master "
                "WHERE type='table' AND name='feature_requests'"
            ).fetchone()
            joinable = row is not None
        except sqlite3.Error:
            joinable = False
    return conn, joinable


def _decode(raw: Any, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return fallback


def _row_to_task(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["payload"] = _decode(d.get("payload"), {})
    d["result"] = _decode(d.get("result"), d.get("result"))
    d["depends_on"] = _decode(d.get("depends_on"), [])
    d["metadata"] = _decode(d.get("metadata"), {})
    return d


def _missing_table(exc: Exception) -> bool:
    # A solution whose queue has never been written has no task_queue table.
    # That is an empty queue, not an error.
    return "no such table" in str(exc)


def list_all(params: Any) -> dict:
    """Full task list from the durable table, newest first, + status counts.

    The counts are computed over the UNFILTERED table so the UI's summary
    tiles stay stable while a filter is applied — the web page instead fires
    a second full-list fetch and counts client-side, which double-polls and
    silently truncates the counts at the list's LIMIT.
    """
    p = _require_dict(params)
    limit = _coerce_limit(p.get("limit"))
    status = _optional_str(p, "status")
    source = _optional_str(p, "source")

    try:
        conn, joinable = _connect()
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"queue.list_all failed: {e}") from e

    try:
        where: list[str] = []
        args: list = []
        if status:
            where.append("t.status = ?")
            args.append(status)
        if source:
            where.append("t.source = ?")
            args.append(source)
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""

        if joinable:
            select_extra = "fr.title AS feature_title, fr.scope AS feature_scope"
            join_sql = (
                "LEFT JOIN fr_db.feature_requests fr "
                "ON fr.plan_trace_id = t.plan_trace_id "
                "AND t.plan_trace_id IS NOT NULL AND t.plan_trace_id != ''"
            )
        else:
            select_extra = "NULL AS feature_title, NULL AS feature_scope"
            join_sql = ""

        rows = conn.execute(
            f"""
            SELECT t.task_id, t.task_type, t.payload, t.priority, t.status,
                   t.created_at, t.started_at, t.completed_at, t.result, t.error,
                   t.plan_trace_id, t.source, t.depends_on, t.metadata,
                   {select_extra}
            FROM task_queue t
            {join_sql}
            {where_sql}
            ORDER BY t.created_at DESC, t.rowid DESC
            LIMIT ?
            """,
            args + [limit],
        ).fetchall()

        count_rows = conn.execute(
            "SELECT status, COUNT(*) AS c FROM task_queue GROUP BY status"
        ).fetchall()
    except sqlite3.Error as e:
        if _missing_table(e):
            return {
                "tasks": [],
                "counts": {**{s: 0 for s in _STATUSES}, "total": 0},
                "limit": limit,
            }
        raise RpcError(RPC_SIDECAR_ERROR, f"queue.list_all failed: {e}") from e
    finally:
        conn.close()

    counts = {s: 0 for s in _STATUSES}
    total = 0
    for r in count_rows:
        total += r["c"]
        if r["status"] in counts:
            counts[r["status"]] = r["c"]
    counts["total"] = total

    return {
        "tasks": [_row_to_task(r) for r in rows],
        "counts": counts,
        "limit": limit,
    }


def subtasks(params: Any) -> dict:
    """Children of a task — rows whose metadata.parent_task_id is task_id."""
    p = _require_dict(params)
    task_id = p.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        raise RpcError(RPC_INVALID_PARAMS, "'task_id' must be a non-empty string")

    conn = sqlite3.connect(_require_db())
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT task_id, task_type, status, error, created_at,
                   completed_at, depends_on, metadata
            FROM task_queue
            WHERE json_extract(metadata, '$.parent_task_id') = ?
            ORDER BY created_at ASC, rowid ASC
            """,
            (task_id,),
        ).fetchall()
    except sqlite3.Error as e:
        if _missing_table(e):
            return {"task_id": task_id, "subtasks": []}
        raise RpcError(RPC_SIDECAR_ERROR, f"queue.subtasks failed: {e}") from e
    finally:
        conn.close()

    children = []
    for r in rows:
        meta = _decode(r["metadata"], {})
        children.append(
            {
                "task_id": r["task_id"],
                "task_type": r["task_type"],
                "status": r["status"],
                "error": r["error"],
                "created_at": r["created_at"],
                "completed_at": r["completed_at"],
                "depends_on": _decode(r["depends_on"], []),
                "wave": meta.get("wave", 0) if isinstance(meta, dict) else 0,
            }
        )
    return {"task_id": task_id, "subtasks": children}
