"""Approvals handler — wraps ProposalStore for the desktop UI.

Translates ProposalStore's generic ValueError into the domain-specific
RpcError subclasses from errors.py so the Rust side can render typed
banners ("already decided", "expired", "not found") instead of a single
opaque failure message.

Every decision is written to the audit log with a signer, mirroring
api.py's approve/reject endpoints. This is not optional decoration: the HITL
approval gate IS the product (Law 1), and a gate that leaves no record is
indistinguishable from no gate at all. Approvals.tsx tells the operator the
decision is recorded — this is what makes that true.
"""

from __future__ import annotations

import logging

import jobs
from rpc import RpcError, RPC_INVALID_PARAMS
from errors import ProposalNotFound, ProposalExpired, AlreadyDecided
from handlers import operator

logger = logging.getLogger("sidecar.approvals")

# Multi-minute LLM work — must not run inside the serial dispatch loop or every
# other RPC (including the 5s status polls) stalls behind it. Mirrors
# api.py:1396.
_BACKGROUND_TYPES = {"implementation_plan", "code_diff"}

# Injected by __main__.py at startup. Tests monkey-patch these.
_store = None  # type: Optional[object]
_logger = None  # type: Optional[object]  # AuditLogger
# Path to the DB holding feature_requests (same file as the audit log).
_feature_db_path = None  # type: Optional[str]

# Indirected so tests can substitute an identity without touching operator._path.
_operator = operator.current

# Lazily constructed so an unavailable vector store never blocks a decision.
_analyst_factory = None
_long_term_memory_factory = None

# Lazily imported: proposal_executor pulls in the coder/planner agents, and a
# desktop running in minimal mode should still be able to READ the queue.
_executor_factory = None
_revert_factory = None


def _get_executor():
    if _executor_factory is not None:
        return _executor_factory()
    from src.core.proposal_executor import execute_approved_proposal

    return execute_approved_proposal


def _get_revert():
    if _revert_factory is not None:
        return _revert_factory()
    from src.core.proposal_executor import _revert_code_diff

    return _revert_code_diff


def _advance_linked_feature_request(proposal) -> None:
    """Move the backlog item this plan came from to in_progress.

    Mirrors api.py:1407-1417. Without it, desktop's OWN backlog.plan loop
    dead-ends: the operator approves the plan and the feature request sits at
    "in_planning" forever, with no way to advance it from the desktop app.
    """
    if _feature_db_path is None:
        return
    import sqlite3
    from datetime import datetime, timezone

    try:
        conn = sqlite3.connect(_feature_db_path)
        conn.execute(
            "UPDATE feature_requests SET status='in_progress', updated_at=? "
            "WHERE plan_trace_id=?",
            (datetime.now(timezone.utc).isoformat(), proposal.trace_id),
        )
        conn.commit()
        conn.close()
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "could not advance feature request for trace_id=%s: %s",
            proposal.trace_id,
            e,
        )


def _execute(proposal) -> dict:
    """Run the approved proposal's executor.

    This is the step that was missing entirely: approving flipped a status
    column and stopped. No task was queued, no code was written — the framework's
    central vertical slice (SURFACE -> PROPOSE -> DECIDE -> EXECUTE) terminated
    one step early on desktop.

    An execution failure NEVER un-approves the proposal. The human made that
    decision; silently reverting it would be worse than a surfaced failure. The
    outcome rides back on the approve response so the UI can show it.
    """
    try:
        executor = _get_executor()
    except Exception as e:  # noqa: BLE001
        logger.error("proposal executor unavailable: %s", e)
        return {"state": "failed", "error": f"executor unavailable: {e}"}

    if proposal.action_type in _BACKGROUND_TYPES:
        job_id = jobs.submit(
            proposal.action_type,
            executor(proposal),
            label=proposal.description,
        )
        return {"state": "running", "job_id": job_id}

    return jobs.run_now(executor(proposal))


def _get_analyst():
    if _analyst_factory is not None:
        return _analyst_factory()
    from src.agents.analyst import AnalystAgent

    return AnalystAgent()


def _get_long_term_memory():
    if _long_term_memory_factory is not None:
        return _long_term_memory_factory()
    from src.memory.long_term_memory import long_term_memory

    return long_term_memory


def _compound(proposal, feedback: str) -> None:
    """Phase 5 — feed the human's correction back into the vector store.

    SOUL.md is explicit: "Never short-circuit Phase 5 (feedback ingestion).
    Every rejection is a learning opportunity." Desktop's reject was a bare SQL
    UPDATE, so an operator could correct the same wrong analysis a hundred times
    and the hundred-and-first would be just as wrong.

    Non-critical by design: compounding memory must never cost us a decision the
    human already made, so failures are logged and swallowed (mirroring
    api.py:1547).
    """
    if not feedback:
        return  # No correction was given. Do not invent a lesson from silence.

    try:
        if proposal.action_type == "analysis":
            payload = proposal.payload or {}
            # The lesson needs BOTH the AI's original guess and the human's
            # correction — a correction without the thing it corrects is noise.
            _get_analyst().learn_from_feedback(
                log_entry=payload.get("log_entry", proposal.description),
                human_comment=feedback,
                original_analysis=payload.get("analysis", {}),
            )
        else:
            _get_long_term_memory().remember(
                f"Rejected {proposal.action_type}: {feedback}",
                user_id=_operator()["name"],
                metadata={
                    "trace_id": proposal.trace_id,
                    "action_type": proposal.action_type,
                },
            )
    except Exception as e:  # noqa: BLE001
        logger.error(
            "compounding-memory write failed for %s (decision stands): %s",
            proposal.trace_id,
            e,
        )


def _require_store():
    if _store is None:
        raise RpcError(RPC_INVALID_PARAMS, "proposal store not initialized")
    return _store


def _audit(action_type: str, proposal, feedback: str = "") -> None:
    """Write the signed decision record. Mirrors api.py:1426-1436.

    Never raises: an audit failure must not lose a decision the human already
    made. It is logged loudly instead — a silent swallow here is exactly how
    the missing-audit defect went unnoticed.
    """
    if _logger is None:
        logger.error(
            "AUDIT GAP: no audit logger wired — decision on %s was NOT recorded",
            proposal.trace_id,
        )
        return
    ident = _operator()
    try:
        _logger.log_event(
            actor=ident["name"],
            action_type=action_type,
            input_context=f"trace_id={proposal.trace_id} action={proposal.action_type}",
            output_content=feedback,
            metadata={
                "trace_id": proposal.trace_id,
                "risk_class": getattr(
                    proposal.risk_class, "value", str(proposal.risk_class)
                ),
                "action_type": proposal.action_type,
            },
            approved_by=ident["name"],
            approver_role="operator",
            approver_email=ident["email"],
            approver_provider=ident["provider"],
        )
    except Exception as e:  # noqa: BLE001
        logger.error("audit log failed for %s: %s", proposal.trace_id, e)


def _require_trace_id(params: dict) -> str:
    trace_id = params.get("trace_id")
    if not trace_id or not isinstance(trace_id, str):
        raise RpcError(RPC_INVALID_PARAMS, "missing or invalid 'trace_id'")
    return trace_id


def _translate_value_error(trace_id: str, err: ValueError, store) -> RpcError:
    """Map ProposalStore.approve/reject ValueError → typed RpcError.

    Messages from proposal_store are of the form:
      "Proposal 'X' not found."
      "Proposal 'X' is already approved."   (or rejected / expired)
    """
    msg = str(err)
    if "not found" in msg:
        return ProposalNotFound(trace_id)
    # Already-decided case — inspect the current status to pick the right error.
    current = store.get(trace_id)
    if current is not None:
        if current.status == "expired":
            return ProposalExpired(trace_id)
        return AlreadyDecided(trace_id, current.status)
    return ProposalNotFound(trace_id)


# ---------- handlers ----------


def list_pending(params: dict) -> list[dict]:
    store = _require_store()
    return [p.model_dump(mode="json") for p in store.get_pending()]


def get(params: dict) -> dict:
    store = _require_store()
    trace_id = _require_trace_id(params)
    p = store.get(trace_id)
    if p is None:
        raise ProposalNotFound(trace_id)
    return p.model_dump(mode="json")


def approve(params: dict) -> dict:
    store = _require_store()
    trace_id = _require_trace_id(params)
    feedback = params.get("feedback", "")
    # The signer is resolved sidecar-side. `decided_by` is deliberately NOT
    # read from params: a renderer-supplied signer is a forgeable signature.
    decided_by = _operator()["name"]
    try:
        p = store.approve(trace_id, decided_by=decided_by, feedback=feedback)
    except ValueError as e:
        raise _translate_value_error(trace_id, e, store) from e
    _audit("PROPOSAL_APPROVED", p, feedback)
    _advance_linked_feature_request(p)

    out = p.model_dump(mode="json")
    out["execution"] = _execute(p)
    return out


def reject(params: dict) -> dict:
    store = _require_store()
    trace_id = _require_trace_id(params)
    feedback = params.get("feedback", "")
    decided_by = _operator()["name"]
    try:
        p = store.reject(trace_id, decided_by=decided_by, feedback=feedback)
    except ValueError as e:
        raise _translate_value_error(trace_id, e, store) from e
    _audit("PROPOSAL_REJECTED", p, feedback)
    _compound(p, feedback)

    # The agent already wrote its edits to disk before proposing them. Without
    # this, "reject" leaves the change in place — the exact opposite of a gate.
    if p.action_type == "code_diff":
        try:
            outcome = jobs.run_now(_get_revert()(p))
            if outcome["state"] == "failed":
                logger.error(
                    "code_diff revert FAILED for %s — the working tree may still "
                    "contain the rejected changes: %s",
                    p.trace_id,
                    outcome.get("error"),
                )
        except Exception as e:  # noqa: BLE001
            logger.error("code_diff revert unavailable for %s: %s", p.trace_id, e)

    return p.model_dump(mode="json")


def batch_approve(params: dict) -> dict:
    """Approve many proposals; per-item success/failure, never aborts.

    Phase 1 intentionally keeps this as a handler-level loop rather than a
    transaction — individual ValueErrors from the store are caught and
    reported per trace_id so a single bad id doesn't block the rest.
    """
    store = _require_store()
    trace_ids = params.get("trace_ids", [])
    if not isinstance(trace_ids, list):
        raise RpcError(RPC_INVALID_PARAMS, "'trace_ids' must be a list")
    decided_by = _operator()["name"]
    feedback = params.get("feedback", "")

    results = []
    for trace_id in trace_ids:
        if not isinstance(trace_id, str):
            results.append(
                {
                    "trace_id": trace_id,
                    "ok": False,
                    "error": {
                        "code": RPC_INVALID_PARAMS,
                        "message": "trace_id must be a string",
                    },
                }
            )
            continue
        try:
            p = store.approve(trace_id, decided_by=decided_by, feedback=feedback)
            _audit("PROPOSAL_APPROVED", p, feedback)
            results.append(
                {
                    "trace_id": trace_id,
                    "ok": True,
                    "proposal": p.model_dump(mode="json"),
                }
            )
        except ValueError as e:
            err = _translate_value_error(trace_id, e, store)
            results.append(
                {
                    "trace_id": trace_id,
                    "ok": False,
                    "error": {
                        "code": err.code,
                        "message": err.message,
                        "data": err.data,
                    },
                }
            )
    return {"results": results}
