"""Handler for the build pipeline (``src.integrations.build_orchestrator``).

The orchestrator uses a return-dict-with-``error``-key convention instead
of exceptions. We translate those dicts to typed ``RpcError`` codes so
the UI gets the same ``DesktopError`` variants it already handles for
every other handler.

Error mapping:
    ``{"error": "... not found"}`` → ``RPC_INVALID_PARAMS``
    ``{"error": "Run is not awaiting approval..."}`` → ``RPC_INVALID_PARAMS``
    Python exception (e.g. decomposer failure) → ``RPC_SIDECAR_ERROR``
    Missing module var → ``RPC_SIDECAR_ERROR``
"""

import logging
from typing import Any, Optional

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError
from handlers import operator

logger = logging.getLogger("sidecar.builds")

# Wired at startup by app._wire_handlers
_orch: Optional[Any] = None
_logger: Optional[Any] = None  # AuditLogger

# States at which a run is sitting on a human gate. Rejecting outside one of
# these is meaningless — there is no decision pending.
_GATE_STATES = ("awaiting_plan", "awaiting_build")

# Indirected so tests can substitute an identity without touching operator._path.
_operator = operator.current

# Lazily constructed so an unavailable vector store never blocks a decision.
_long_term_memory_factory = None


def _get_long_term_memory():
    if _long_term_memory_factory is not None:
        return _long_term_memory_factory()
    from src.memory.long_term_memory import long_term_memory

    return long_term_memory


def _compound(run_id: str, state: str, feedback: str) -> None:
    """Phase 5 — feed the operator's rejection reason into the vector store.

    The orchestrator's own ``reject()`` writes a BUILD_REJECTED audit row, so
    the compliance record was never the gap. The *learning* was: nothing on the
    build path ever called into vector memory, so an operator could reject the
    same bad plan every day and the next plan would be no better. SOUL.md Law 3
    and Phase 5: "every rejection teaches."

    Non-critical by design — a vector-store failure must never cost us a
    decision the human already made (mirrors approvals._compound).
    """
    if not feedback:
        return  # No reason was given. Do not invent a lesson from silence.
    try:
        _get_long_term_memory().remember(
            f"Rejected build stage ({state}): {feedback}",
            user_id=_operator()["name"],
            metadata={"run_id": run_id, "stage": state, "action_type": "build_reject"},
        )
    except Exception as e:  # noqa: BLE001
        logger.error(
            "compounding-memory write failed for run %s (decision stands): %s",
            run_id,
            e,
        )


def _audit_rejection(run_id: str, state: str, feedback: str) -> None:
    """Sign the rejection with the operator's identity.

    The orchestrator audits as actor="BuildOrchestrator" — true, but it records
    the *system* as the decider. A HITL gate's record has to name the human who
    held it (mirrors approvals._audit). Never raises.
    """
    if _logger is None:
        logger.error(
            "AUDIT GAP: no audit logger wired — build rejection of %s was NOT signed",
            run_id,
        )
        return
    ident = _operator()
    try:
        _logger.log_event(
            actor=ident["name"],
            action_type="BUILD_STAGE_REJECTED",
            input_context=f"run_id={run_id} stage={state}",
            output_content=feedback,
            metadata={"run_id": run_id, "stage": state},
            approved_by=ident["name"],
            approver_role="operator",
            approver_email=ident["email"],
            approver_provider=ident["provider"],
        )
    except Exception as e:  # noqa: BLE001
        logger.error("audit log failed for build rejection %s: %s", run_id, e)


def _require_orch() -> Any:
    if _orch is None:
        raise RpcError(
            RPC_SIDECAR_ERROR,
            "build_orchestrator is not wired (SAGE import failed)",
        )
    return _orch


def _require_dict(params: Any) -> dict:
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    return params


def _unwrap(result: Any) -> Any:
    """Distinguish an orchestrator FAILURE from a run summary that merely has a
    non-empty ``error`` field.

    Both are dicts with an ``error`` key, which is why a plain
    ``result.get("error")`` check is wrong — and wrong in the worst direction.
    ``reject()`` sets ``run["error"] = "Rejected: <feedback>"`` on success, so a
    successful rejection was being reported to the UI as RPC error -32602, and
    the audit/compounding steps behind that check never ran. The same bug made
    ``builds.get`` unable to display any failed or rejected run at all.

    The discriminator is ``run_id``: ``_run_summary()`` always includes it
    (build_orchestrator.py:3590); a bare failure is ``{"error": "..."}`` alone.
    """
    if isinstance(result, dict) and result.get("error") and "run_id" not in result:
        raise RpcError(RPC_INVALID_PARAMS, result["error"])
    return result


def start(params: Any):
    p = _require_dict(params)
    description = p.get("product_description")
    if not isinstance(description, str) or not description.strip():
        raise RpcError(RPC_INVALID_PARAMS, "product_description is required")

    orch = _require_orch()
    try:
        result = orch.start(
            product_description=description,
            solution_name=p.get("solution_name") or "",
            repo_url=p.get("repo_url") or "",
            workspace_dir=p.get("workspace_dir") or "",
            critic_threshold=int(p.get("critic_threshold") or 70),
            hitl_level=p.get("hitl_level") or "standard",
        )
    except Exception as e:  # noqa: BLE001
        raise RpcError(
            RPC_SIDECAR_ERROR, f"build_orchestrator.start failed: {e}"
        ) from e

    if isinstance(result, dict) and result.get("error"):
        raise RpcError(RPC_SIDECAR_ERROR, result["error"])
    return result


def list_runs(_params: Any):
    orch = _require_orch()
    try:
        return orch.list_runs()
    except Exception as e:  # noqa: BLE001
        raise RpcError(
            RPC_SIDECAR_ERROR, f"build_orchestrator.list_runs failed: {e}"
        ) from e


def get(params: Any):
    p = _require_dict(params)
    run_id = p.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise RpcError(RPC_INVALID_PARAMS, "run_id is required")

    orch = _require_orch()
    try:
        result = orch.get_status(run_id)
    except Exception as e:  # noqa: BLE001
        raise RpcError(
            RPC_SIDECAR_ERROR, f"build_orchestrator.get_status failed: {e}"
        ) from e

    # NOT `result.get("error")` — a failed/rejected run is a run the operator
    # most needs to look at, and that check made the detail view refuse to show it.
    return _unwrap(result)


def _require_run_id(p: dict) -> str:
    run_id = p.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise RpcError(RPC_INVALID_PARAMS, "run_id is required")
    return run_id


def reject(params: Any):
    """Reject a build stage with operator feedback.

    The other half of the gate. ``approve_stage`` could already route
    ``approved=false`` to the orchestrator, but nothing on that path ever fed
    the operator's reasoning back into vector memory — so the build pipeline
    was the one place in SAGE where a rejection taught nothing (Law 3 /
    Phase 5). This is the single reject path; ``approve_stage`` delegates here
    so the two entry points can never diverge.

    Feedback is optional, exactly as in ``approvals.reject``: a decision is
    valid without a reason, and ``_compound`` declines to invent a lesson from
    silence.
    """
    p = _require_dict(params)
    run_id = _require_run_id(p)
    feedback = p.get("feedback") or ""

    orch = _require_orch()

    # Read state BEFORE rejecting — orch.reject() overwrites it, and both the
    # audit record and the vector-memory lesson need to say WHICH gate was
    # refused ("the plan was wrong" is a different lesson from "the build was").
    try:
        status = _unwrap(orch.get_status(run_id))
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"get_status failed: {e}") from e

    state = (status or {}).get("state", "")
    if state not in _GATE_STATES:
        raise RpcError(
            RPC_INVALID_PARAMS,
            f"Run is not awaiting approval (state: {state})",
        )

    try:
        result = orch.reject(run_id, feedback)
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"reject failed: {e}") from e
    # A successful reject sets run["error"] = "Rejected: <feedback>" — that is
    # the recorded reason, NOT an RPC failure. _unwrap knows the difference.
    result = _unwrap(result)

    _audit_rejection(run_id, state, feedback)
    _compound(run_id, state, feedback)
    return result


def approve_stage(params: Any):
    """Unified approve/reject gate — routes to approve_plan, approve_build,
    or reject based on current state and ``approved`` flag.

    Mirrors the HTTP POST /build/approve/{run_id} behavior.
    """
    p = _require_dict(params)
    run_id = _require_run_id(p)
    approved = bool(p.get("approved"))
    feedback = p.get("feedback") or ""

    if not approved:
        # Delegate — one reject path, two entry points. Duplicating the logic
        # here is how you end up with a reject that silently skips Phase 5.
        return reject(p)

    orch = _require_orch()

    # approved=True — pick the right routing from current state
    try:
        status = _unwrap(orch.get_status(run_id))
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"get_status failed: {e}") from e

    state = (status or {}).get("state", "")
    if state == "awaiting_plan":
        try:
            result = orch.approve_plan(run_id, feedback=feedback)
        except Exception as e:  # noqa: BLE001
            raise RpcError(RPC_SIDECAR_ERROR, f"approve_plan failed: {e}") from e
    elif state == "awaiting_build":
        try:
            result = orch.approve_build(run_id, feedback=feedback)
        except Exception as e:  # noqa: BLE001
            raise RpcError(RPC_SIDECAR_ERROR, f"approve_build failed: {e}") from e
    else:
        raise RpcError(
            RPC_INVALID_PARAMS,
            f"Run is not awaiting approval (state: {state})",
        )

    return _unwrap(result)
