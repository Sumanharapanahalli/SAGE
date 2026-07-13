"""Developer / GitLab handlers — ports src.agents.developer.DeveloperAgent.

Web surface being ported (src/interface/api.py):

    GET  /mr/open              -> mr.list_open
    GET  /mr/pipeline          -> mr.pipeline
    POST /mr/review            -> mr.review      (backgrounded — see below)
    POST /mr/create            -> mr.propose_create  (HITL-gated — see below)
    POST /mr/comment           -> mr.comment

Two deliberate divergences from the web behaviour:

1. LAW 1. ``POST /mr/create`` creates the merge request *immediately* — an
   agent-drafted (LLM writes the title/description), irreversible write to an
   EXTERNAL system, with no human in the loop. That is exactly the class of
   action RiskClass.EXTERNAL exists for. Desktop therefore does NOT create the
   MR; ``mr.propose_create`` files a real ProposalStore proposal
   (action_type="mr_create", risk_class=EXTERNAL, reversible=False) that
   surfaces in the existing Approvals inbox. The MR is POSTed to GitLab only
   from the approved-proposal executor, by calling
   ``DeveloperAgent.create_mr_from_issue`` verbatim.

   ``mr_create`` is not in ``proposal_executor._DISPATCH`` (nothing in the
   framework ever proposed one — the web endpoint just did it). We register the
   executor into that dict at import time rather than editing src/: _DISPATCH is
   a plain registry, and registering into it is the intended extension point.

2. ``review_merge_request`` is an LLM ReAct loop (up to 6 LLM round-trips).
   Running it inside the sidecar's serial dispatch loop would freeze every
   other RPC — including the 5s status polls — for minutes. It is submitted to
   ``jobs`` and the caller polls ``jobs.status``.

AUTH is a GitLab PAT from env/config (GITLAB_URL / GITLAB_TOKEN) — no OAuth, no
redirect, no port. ``mr.config`` reports the missing-token case as a clean state
rather than an error, so the UI can render a setup prompt.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import jobs
from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError

logger = logging.getLogger("sidecar.mr")

# Injected by app._wire_handlers (the same ProposalStore the Approvals inbox
# reads). Tests monkeypatch it.
_store = None  # type: Optional[Any]

# Test seam. Defaults to a real DeveloperAgent, constructed per call so a token
# exported after sidecar start is still picked up.
_agent_factory = None


# ── agent access ───────────────────────────────────────────────────────────

def _get_agent():
    if _agent_factory is not None:
        return _agent_factory()
    from src.agents.developer import DeveloperAgent

    return DeveloperAgent()


def _agent_config(agent) -> dict:
    return {
        "gitlab_url": getattr(agent, "gitlab_url", "") or "",
        "has_token": bool(getattr(agent, "gitlab_token", "")),
        "default_project_id": str(getattr(agent, "default_project_id", "") or ""),
    }


def _require_configured():
    """Return a DeveloperAgent, or raise if GitLab creds are absent.

    The UI gates every call below on ``mr.config``, so this is the belt-and-
    braces path: a bare RpcError rather than an opaque requests failure.
    """
    agent = _get_agent()
    cfg = _agent_config(agent)
    if not cfg["gitlab_url"] or not cfg["has_token"]:
        raise RpcError(
            RPC_SIDECAR_ERROR,
            "GitLab is not configured — set GITLAB_URL and GITLAB_TOKEN "
            "(env or config.yaml) and restart.",
            {"configured": False},
        )
    return agent


# ── param helpers ──────────────────────────────────────────────────────────

def _require_dict(params: Any) -> dict:
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    return params


def _require_int(params: dict, name: str) -> int:
    value = params.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RpcError(RPC_INVALID_PARAMS, f"'{name}' must be an integer")
    if value <= 0:
        raise RpcError(RPC_INVALID_PARAMS, f"'{name}' must be a positive integer")
    return value


def _require_store():
    if _store is None:
        raise RpcError(RPC_INVALID_PARAMS, "proposal store not initialized")
    return _store


def _raise_if_agent_error(result: Any, method: str) -> dict:
    """DeveloperAgent signals failure by RETURNING {'error': ...}, not raising."""
    if not isinstance(result, dict):
        raise RpcError(RPC_SIDECAR_ERROR, f"{method} returned an unexpected shape")
    if result.get("error"):
        raise RpcError(RPC_SIDECAR_ERROR, str(result["error"]))
    return result


# ── RPC methods ────────────────────────────────────────────────────────────

def config(params: Any) -> dict:
    """Is GitLab reachable from this host? Never an error — a state."""
    _require_dict(params if params is not None else {})
    try:
        cfg = _agent_config(_get_agent())
    except Exception as e:  # noqa: BLE001 — a missing optional dep is "not configured"
        logger.warning("DeveloperAgent unavailable: %s", e)
        return {
            "configured": False,
            "gitlab_url": "",
            "has_token": False,
            "default_project_id": "",
            "message": f"Developer agent unavailable: {e}",
        }
    configured = bool(cfg["gitlab_url"] and cfg["has_token"])
    return {
        "configured": configured,
        **cfg,
        "message": (
            "" if configured
            else "Set GITLAB_URL and GITLAB_TOKEN (env or config.yaml) to enable GitLab."
        ),
    }


def list_open(params: Any) -> dict:
    p = _require_dict(params)
    project_id = _require_int(p, "project_id")
    agent = _require_configured()
    try:
        result = agent.list_open_mrs(project_id=project_id)
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"mr.list_open failed: {e}") from e
    return _raise_if_agent_error(result, "list_open_mrs")


def pipeline(params: Any) -> dict:
    p = _require_dict(params)
    project_id = _require_int(p, "project_id")
    mr_iid = _require_int(p, "mr_iid")
    agent = _require_configured()
    try:
        result = agent.get_pipeline_status(project_id=project_id, mr_iid=mr_iid)
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"mr.pipeline failed: {e}") from e
    return _raise_if_agent_error(result, "get_pipeline_status")


def review(params: Any) -> dict:
    """Start the ReAct code review. Returns a job_id — poll jobs.status."""
    p = _require_dict(params)
    project_id = _require_int(p, "project_id")
    mr_iid = _require_int(p, "mr_iid")
    agent = _require_configured()

    async def _run() -> dict:
        # Sync + slow, but this coroutine owns a dedicated worker thread's event
        # loop (jobs.submit -> asyncio.run), so blocking here blocks nothing else.
        result = agent.review_merge_request(project_id=project_id, mr_iid=mr_iid)
        if isinstance(result, dict) and result.get("error"):
            raise RuntimeError(str(result["error"]))
        return result

    job_id = jobs.submit(
        "mr_review", _run(), label=f"Review MR !{mr_iid} (project {project_id})"
    )
    return {"job_id": job_id, "project_id": project_id, "mr_iid": mr_iid}


def propose_create(params: Any) -> dict:
    """File a HITL proposal to create an MR from an issue. Does NOT touch GitLab."""
    p = _require_dict(params)
    project_id = _require_int(p, "project_id")
    issue_iid = _require_int(p, "issue_iid")
    source_branch = p.get("source_branch")
    if source_branch is not None and not isinstance(source_branch, str):
        raise RpcError(RPC_INVALID_PARAMS, "'source_branch' must be a string")
    source_branch = (source_branch or "").strip() or None

    store = _require_store()
    agent = _require_configured()
    _ensure_executor_registered()

    # Best-effort read-only enrichment so the approver sees WHAT they are
    # approving, not just two integers. Reuses the agent's own GitLab client.
    issue_title = ""
    try:
        issue_data, err = agent._gl_get(  # noqa: SLF001 — the agent's own HTTP client
            f"/projects/{project_id}/issues/{issue_iid}"
        )
        if err:
            raise RpcError(RPC_SIDECAR_ERROR, f"could not fetch issue #{issue_iid}: {err}")
        issue_title = str((issue_data or {}).get("title", ""))
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        logger.warning("issue title lookup failed (proposing anyway): %s", e)

    from src.core.proposal_store import RiskClass

    label = issue_title or f"issue #{issue_iid}"
    proposal = store.create(
        action_type="mr_create",
        risk_class=RiskClass.EXTERNAL,
        payload={
            "project_id": project_id,
            "issue_iid": issue_iid,
            "source_branch": source_branch,
            "issue_title": issue_title,
        },
        description=f"Create GitLab MR from issue #{issue_iid}: {label}",
        # A merge request in a shared GitLab is not undoable from here.
        reversible=False,
        proposed_by="DeveloperAgent",
    )
    return proposal.model_dump(mode="json")


def comment(params: Any) -> dict:
    """Post an operator-authored note on an MR.

    Immediate, not gated: the human clicking "Post" IS the decision (Law 1 gates
    AGENT proposals, not the operator's own actions — same rationale as
    knowledge.add / constitution.update).
    """
    p = _require_dict(params)
    project_id = _require_int(p, "project_id")
    mr_iid = _require_int(p, "mr_iid")
    body = p.get("comment")
    if not isinstance(body, str) or not body.strip():
        raise RpcError(RPC_INVALID_PARAMS, "'comment' must be a non-empty string")

    agent = _require_configured()
    try:
        result = agent.add_mr_comment(project_id, mr_iid, body)
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"mr.comment failed: {e}") from e
    return _raise_if_agent_error(result, "add_mr_comment")


# ── approved-proposal executor ─────────────────────────────────────────────

async def _execute_mr_create(proposal) -> dict:
    """Executor for an APPROVED mr_create proposal — the only path that POSTs.

    Runs DeveloperAgent.create_mr_from_issue verbatim (LLM drafts the title and
    description, then the MR is created and audited).
    """
    payload = proposal.payload or {}
    agent = _get_agent()
    result = agent.create_mr_from_issue(
        project_id=int(payload["project_id"]),
        issue_iid=int(payload["issue_iid"]),
        source_branch=payload.get("source_branch") or None,
    )
    if isinstance(result, dict) and result.get("error"):
        # Must raise: execute_approved_proposal's contract is raise-on-failure,
        # and approvals surfaces the failure on the approve response.
        raise RuntimeError(str(result["error"]))
    return result


def _ensure_executor_registered() -> bool:
    """Register mr_create in the framework's executor dispatch map.

    Idempotent. Called at import (so a proposal that outlives a sidecar restart
    is still executable) and again from propose_create (so a startup-time import
    failure — e.g. minimal mode — cannot leave an unexecutable proposal behind).
    """
    try:
        from src.core.proposal_executor import _DISPATCH

        if "mr_create" not in _DISPATCH:
            _DISPATCH["mr_create"] = _execute_mr_create
        return True
    except Exception as e:  # noqa: BLE001 — minimal mode must still start
        logger.warning("mr_create executor not registered: %s", e)
        return False


_ensure_executor_registered()
