"""Feature request (backlog) handlers."""

from __future__ import annotations

from typing import Any, Dict, Optional

from rpc import (
    RpcError,
    RPC_INVALID_PARAMS,
    RPC_SAGE_IMPORT_ERROR,
    RPC_FEATURE_REQUEST_NOT_FOUND,
    RPC_SIDECAR_ERROR,
)

_store = None

# Injected by app.py at startup (the SAME ProposalStore instance approvals.py
# / analyze.py use). Tests monkeypatch this.
_proposal_store = None  # type: Optional[object]

# Optional override for tests; defaults to constructing the real
# PlannerAgent (no external deps at construction time).
_planner_factory = None


def _require_store():
    if _store is None:
        raise RpcError(
            RPC_SAGE_IMPORT_ERROR,
            "feature request store unavailable",
            {"module": "src.core.feature_request_store", "detail": "not initialised"},
        )
    return _store


def _require_proposal_store():
    if _proposal_store is None:
        raise RpcError(
            RPC_SAGE_IMPORT_ERROR,
            "proposal store unavailable",
            {"module": "src.core.proposal_store", "detail": "not initialised"},
        )
    return _proposal_store


def _get_planner():
    if _planner_factory is not None:
        return _planner_factory()
    from src.agents.planner import PlannerAgent

    return PlannerAgent()


def _update_request_status(
    db_path: str, req_id: str, *, status: str, plan_trace_id: Optional[str] = None
) -> None:
    """Direct status transition for system-driven transitions (github_pr,
    in_planning) that aren't reviewer actions covered by
    FeatureRequestStore.update()'s approve/reject/complete vocabulary.
    Mirrors src/interface/api.py's raw-SQL updates for this same endpoint —
    same table, same columns.
    """
    import sqlite3
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    try:
        if plan_trace_id is not None:
            conn.execute(
                "UPDATE feature_requests SET status=?, plan_trace_id=?, updated_at=? WHERE id=?",
                (status, plan_trace_id, now, req_id),
            )
        else:
            conn.execute(
                "UPDATE feature_requests SET status=?, updated_at=? WHERE id=?",
                (status, now, req_id),
            )
        conn.commit()
    finally:
        conn.close()


def submit_feature_request(params: dict) -> dict:
    store = _require_store()
    title = params.get("title") or ""
    description = params.get("description") or ""
    kwargs: Dict[str, Any] = {
        "title": title,
        "description": description,
        "module_id": params.get("module_id", "general"),
        "module_name": params.get("module_name", "General"),
        "priority": params.get("priority", "medium"),
        "requested_by": params.get("requested_by", "anonymous"),
        "scope": params.get("scope", "solution"),
    }
    try:
        fr = store.submit(**kwargs)
    except ValueError as e:
        raise RpcError(RPC_INVALID_PARAMS, str(e)) from e
    return fr.to_dict()


def list_feature_requests(params: dict) -> list:
    store = _require_store()
    status: Optional[str] = params.get("status") or None
    scope: Optional[str] = params.get("scope") or None
    return [fr.to_dict() for fr in store.list(status=status, scope=scope)]


def update_feature_request(params: dict) -> dict:
    store = _require_store()
    fid = params.get("id")
    if not fid:
        raise RpcError(RPC_INVALID_PARAMS, "id required")
    action = params.get("action")
    if not action:
        raise RpcError(RPC_INVALID_PARAMS, "action required")
    note = params.get("reviewer_note", "")
    try:
        fr = store.update(fid, action=action, reviewer_note=note)
    except KeyError:
        raise RpcError(
            RPC_FEATURE_REQUEST_NOT_FOUND,
            f"feature request not found: {fid}",
            {"feature_id": fid},
        ) from None
    except ValueError as e:
        raise RpcError(RPC_INVALID_PARAMS, str(e)) from e
    return fr.to_dict()


def plan(params: dict) -> dict:
    """Generate an implementation plan for a feature request.

    SAGE-scope requests are contributed via GitHub, not the internal
    approval queue — no LLM/Planner call, just a status flip and a
    pre-filled issue URL. Solution-scope requests get a real ProposalStore
    proposal (action_type="implementation_plan") so the plan flows through
    the same HITL approvals inbox as everything else on desktop.
    """
    store = _require_store()
    req_id = params.get("req_id")
    if not req_id:
        raise RpcError(RPC_INVALID_PARAMS, "req_id required")

    fr = store.get(req_id)
    if fr is None:
        raise RpcError(
            RPC_FEATURE_REQUEST_NOT_FOUND,
            f"feature request not found: {req_id}",
            {"feature_id": req_id},
        )

    if fr.scope == "sage":
        import urllib.parse

        from src.core.config_loader import load_config as _load_cfg

        try:
            cfg = _load_cfg()
        except Exception:  # noqa: BLE001
            cfg = {}
        github_repo = (cfg.get("github", {}) or {}).get("repo_url", "").rstrip(
            "/"
        ) or "https://github.com/Sumanharapanahalli/SAGE"
        issue_title = urllib.parse.quote(fr.title)
        issue_body = urllib.parse.quote(
            f"## Description\n{fr.description}\n\n"
            f"**Priority:** {fr.priority}\n\n"
            f"---\n*Submitted via SAGE Improvements*"
        )
        github_url = (
            f"{github_repo}/issues/new?title={issue_title}"
            f"&body={issue_body}&labels=enhancement"
        )
        _update_request_status(store.db_path, req_id, status="github_pr")
        return {
            "request_id": req_id,
            "status": "github_pr",
            "github_issue_url": github_url,
            "message": (
                "SAGE framework improvements are contributed via GitHub. "
                "Use the link to open an issue or PR."
            ),
        }

    # Solution-scope: run the planner and create a HITL approval proposal.
    proposal_store = _require_proposal_store()
    planner = _get_planner()

    planner_task = (
        "This is a SOLUTION feature — implement in the active solution's codebase.\n"
        f"Title: {fr.title}\n"
        f"Description: {fr.description}\n"
        f"Priority: {fr.priority}"
    )

    try:
        steps = planner.create_plan(planner_task)
    except Exception as exc:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"planning failed: {exc}") from exc

    if not steps:
        raise RpcError(
            RPC_SIDECAR_ERROR,
            "LLM could not produce an executable plan. Try rephrasing the description.",
        )

    from src.core.proposal_store import RiskClass

    proposal = proposal_store.create(
        action_type="implementation_plan",
        risk_class=RiskClass.STATEFUL,
        payload={
            "description": planner_task,
            "steps": steps,
            "scope": fr.scope,
            "feature_request_id": req_id,
        },
        description=f"Implementation plan: {fr.title}",
        reversible=False,
        proposed_by="PlannerAgent",
    )

    _update_request_status(
        store.db_path, req_id, status="in_planning", plan_trace_id=proposal.trace_id
    )

    return proposal.model_dump(mode="json")
