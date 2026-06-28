"""Handler for Collective Intelligence (Phase 5a).

Proxies ``src.core.collective_memory.CollectiveMemory`` — the
git-backed cross-solution knowledge-sharing surface. Twelve RPC
methods cover learnings (list/get/search/publish/validate), help
requests (list/create/claim/respond/close), and maintenance
(sync/stats).

Law 1: operator-driven actions bypass the proposal queue; agent
``publish_learning`` still flows through ``collective_publish``
proposals when the framework is configured with
``require_approval=True`` (default).

Module-level ``_cm`` is wired at startup by ``app._wire_handlers``;
if the import or singleton construction fails, every handler
returns ``SidecarError`` with a typed message so the UI can render
a single disabled state.
"""
from __future__ import annotations

from typing import Any, Optional

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError

_LIMIT_MAX = 500
_LIMIT_DEFAULT = 50
_SEARCH_LIMIT_MAX = 50
_SEARCH_LIMIT_DEFAULT = 10

_URGENCIES = {"low", "medium", "high", "critical"}
_STATUSES = {"open", "closed"}

_cm: Optional[Any] = None


def _require_cm() -> Any:
    if _cm is None:
        raise RpcError(
            RPC_SIDECAR_ERROR,
            "collective handlers are not wired (CollectiveMemory import or construction failed)",
        )
    return _cm


def _require_dict(params: Any) -> dict:
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    return params


def _coerce_int(value: Any, name: str, default: int, lo: int, hi: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise RpcError(RPC_INVALID_PARAMS, f"'{name}' must be an integer")
    if value < lo or value > hi:
        raise RpcError(RPC_INVALID_PARAMS, f"'{name}' must be between {lo} and {hi}")
    return value


def _require_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RpcError(RPC_INVALID_PARAMS, f"'{name}' must be a non-empty string")
    return value


def _optional_str_list(value: Any, name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise RpcError(RPC_INVALID_PARAMS, f"'{name}' must be a list of strings")
    return value


# ── RPC methods ──────────────────────────────────────────────────


def list_learnings(params: Any) -> dict:
    p = _require_dict(params)
    solution = p.get("solution")
    topic = p.get("topic")
    if solution is not None and not isinstance(solution, str):
        raise RpcError(RPC_INVALID_PARAMS, "'solution' must be a string")
    if topic is not None and not isinstance(topic, str):
        raise RpcError(RPC_INVALID_PARAMS, "'topic' must be a string")
    limit = _coerce_int(p.get("limit"), "limit", _LIMIT_DEFAULT, 1, _LIMIT_MAX)
    offset = _coerce_int(p.get("offset"), "offset", 0, 0, 10_000_000)

    cm = _require_cm()
    try:
        full = cm.list_learnings(
            solution=solution or None, topic=topic or None, limit=10_000_000, offset=0
        )
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"list_learnings failed: {e}") from e

    total = len(full)
    entries = full[offset: offset + limit]
    return {
        "entries": entries,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_learning(params: Any) -> dict:
    p = _require_dict(params)
    learning_id = _require_str(p.get("id"), "id")

    cm = _require_cm()
    try:
        result = cm.get_learning(learning_id)
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"get_learning failed: {e}") from e

    return {"learning": result}


def search_learnings(params: Any) -> dict:
    p = _require_dict(params)
    query = p.get("query", "")
    if not isinstance(query, str):
        raise RpcError(RPC_INVALID_PARAMS, "'query' must be a string")
    tags = _optional_str_list(p.get("tags"), "tags")
    solution = p.get("solution")
    if solution is not None and not isinstance(solution, str):
        raise RpcError(RPC_INVALID_PARAMS, "'solution' must be a string")
    limit = _coerce_int(
        p.get("limit"), "limit", _SEARCH_LIMIT_DEFAULT, 1, _SEARCH_LIMIT_MAX
    )

    cm = _require_cm()
    try:
        raw = cm.search_learnings(
            query=query, tags=tags or None, solution=solution or None, limit=limit
        )
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"search_learnings failed: {e}") from e

    results = list(raw or [])
    return {"query": query, "results": results, "count": len(results)}


def publish_learning(params: Any) -> dict:
    p = _require_dict(params)
    author_agent = _require_str(p.get("author_agent"), "author_agent")
    author_solution = _require_str(p.get("author_solution"), "author_solution")
    topic = _require_str(p.get("topic"), "topic")
    title = _require_str(p.get("title"), "title")
    content = _require_str(p.get("content"), "content")
    tags = _optional_str_list(p.get("tags"), "tags")
    confidence = p.get("confidence", 0.5)
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise RpcError(RPC_INVALID_PARAMS, "'confidence' must be a number")
    if not 0.0 <= float(confidence) <= 1.0:
        raise RpcError(RPC_INVALID_PARAMS, "'confidence' must be between 0.0 and 1.0")
    source_task_id = p.get("source_task_id", "")
    if not isinstance(source_task_id, str):
        raise RpcError(RPC_INVALID_PARAMS, "'source_task_id' must be a string")
    proposed_by = p.get("proposed_by", "operator@desktop")
    if not isinstance(proposed_by, str) or not proposed_by.strip():
        raise RpcError(RPC_INVALID_PARAMS, "'proposed_by' must be a non-empty string")

    payload = {
        "author_agent": author_agent,
        "author_solution": author_solution,
        "topic": topic,
        "title": title,
        "content": content,
        "tags": tags,
        "confidence": float(confidence),
        "source_task_id": source_task_id,
    }

    cm = _require_cm()
    try:
        result = cm.publish_learning(payload, proposed_by=proposed_by)
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"publish_learning failed: {e}") from e

    if getattr(cm, "require_approval", False):
        return {"id": None, "gated": True, "trace_id": str(result)}
    return {"id": str(result), "gated": False}


def validate_learning(params: Any) -> dict:
    p = _require_dict(params)
    learning_id = _require_str(p.get("id"), "id")
    validated_by = _require_str(p.get("validated_by"), "validated_by")

    cm = _require_cm()
    try:
        updated = cm.validate_learning(learning_id, validated_by)
    except ValueError as e:
        raise RpcError(RPC_SIDECAR_ERROR, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"validate_learning failed: {e}") from e

    return {"learning": updated}


def list_help_requests(params: Any) -> dict:
    p = _require_dict(params)
    status = p.get("status", "open")
    if status not in _STATUSES:
        raise RpcError(
            RPC_INVALID_PARAMS, f"'status' must be one of {sorted(_STATUSES)}"
        )
    expertise = _optional_str_list(p.get("expertise"), "expertise")

    cm = _require_cm()
    try:
        entries = cm.list_help_requests(status=status, expertise=expertise or None)
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"list_help_requests failed: {e}") from e

    entries = list(entries or [])
    return {"entries": entries, "count": len(entries)}


def create_help_request(params: Any) -> dict:
    p = _require_dict(params)
    title = _require_str(p.get("title"), "title")
    requester_agent = _require_str(p.get("requester_agent"), "requester_agent")
    requester_solution = _require_str(p.get("requester_solution"), "requester_solution")
    urgency = p.get("urgency", "medium")
    if urgency not in _URGENCIES:
        raise RpcError(
            RPC_INVALID_PARAMS, f"'urgency' must be one of {sorted(_URGENCIES)}"
        )
    required_expertise = _optional_str_list(
        p.get("required_expertise"), "required_expertise"
    )
    context = p.get("context", "")
    if not isinstance(context, str):
        raise RpcError(RPC_INVALID_PARAMS, "'context' must be a string")

    payload = {
        "title": title,
        "requester_agent": requester_agent,
        "requester_solution": requester_solution,
        "urgency": urgency,
        "required_expertise": required_expertise,
        "context": context,
    }

    cm = _require_cm()
    try:
        req_id = cm.create_help_request(payload)
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"create_help_request failed: {e}") from e

    return {"id": str(req_id)}


def claim_help_request(params: Any) -> dict:
    p = _require_dict(params)
    request_id = _require_str(p.get("id"), "id")
    agent = _require_str(p.get("agent"), "agent")
    solution = _require_str(p.get("solution"), "solution")

    cm = _require_cm()
    try:
        updated = cm.claim_help_request(request_id, agent, solution)
    except ValueError as e:
        raise RpcError(RPC_SIDECAR_ERROR, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"claim_help_request failed: {e}") from e

    return {"request": updated}


def respond_to_help_request(params: Any) -> dict:
    p = _require_dict(params)
    request_id = _require_str(p.get("id"), "id")
    responder_agent = _require_str(p.get("responder_agent"), "responder_agent")
    responder_solution = _require_str(p.get("responder_solution"), "responder_solution")
    content = _require_str(p.get("content"), "content")

    cm = _require_cm()
    try:
        updated = cm.respond_to_help_request(
            request_id,
            {
                "responder_agent": responder_agent,
                "responder_solution": responder_solution,
                "content": content,
            },
        )
    except ValueError as e:
        raise RpcError(RPC_SIDECAR_ERROR, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise RpcError(
            RPC_SIDECAR_ERROR, f"respond_to_help_request failed: {e}"
        ) from e

    return {"request": updated}


def close_help_request(params: Any) -> dict:
    p = _require_dict(params)
    request_id = _require_str(p.get("id"), "id")

    cm = _require_cm()
    try:
        updated = cm.close_help_request(request_id)
    except ValueError as e:
        raise RpcError(RPC_SIDECAR_ERROR, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"close_help_request failed: {e}") from e

    return {"request": updated}


def sync(params: Any) -> dict:
    if params is not None and not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    cm = _require_cm()
    try:
        result = cm.sync()
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"sync failed: {e}") from e
    pulled = bool(result.get("pulled", False))
    indexed = int(result.get("indexed", 0))
    return {"pulled": pulled, "indexed": indexed}


def stats(params: Any) -> dict:
    if params is not None and not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    cm = _require_cm()
    try:
        base = cm.get_stats()
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"get_stats failed: {e}") from e
    return {
        "learning_count": int(base.get("learning_count", 0)),
        "help_request_count": int(base.get("help_request_count", 0)),
        "help_requests_closed": int(base.get("help_requests_closed", 0)),
        "topics": dict(base.get("topics") or {}),
        "contributors": dict(base.get("contributors") or {}),
        "git_available": bool(getattr(cm, "_git_available", False)),
        "repo_path": str(getattr(cm, "repo_path", "")),
    }
