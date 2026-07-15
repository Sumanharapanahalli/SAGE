"""Analyze handler — the desktop operator's SURFACE -> PROPOSE trigger.

The web/API's legacy ``POST /analyze`` stashes its result in an in-memory
``_pending_proposals`` dict that only its own ``/approve/{trace_id}`` branch
reads — a second, disconnected pending-item mechanism. This handler instead
wraps AnalystAgent.analyze_log() and persists the result as a REAL
ProposalStore proposal, so it flows through the already-verified
approvals.list_pending / approve / reject RPCs and the desktop Approvals
page with no new inbox to build.
"""

from __future__ import annotations


from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError

# Injected by app.py at startup (the same ProposalStore instance approvals.py
# uses). Tests monkeypatch this.
_store = None  # type: Optional[object]

# Optional override for tests; defaults to constructing the real AnalystAgent
# (no external deps at construction time, so a plain factory is enough).
_analyst_factory = None


def _require_store():
    if _store is None:
        raise RpcError(RPC_INVALID_PARAMS, "proposal store not initialized")
    return _store


def _get_analyst():
    if _analyst_factory is not None:
        return _analyst_factory()
    from src.agents.analyst import AnalystAgent

    return AnalystAgent()


def run(params: dict) -> dict:
    """Analyze a log/signal and create a pending proposal from the result."""
    log_entry = params.get("log_entry", "")
    if not isinstance(log_entry, str) or not log_entry.strip():
        raise RpcError(RPC_INVALID_PARAMS, "missing or empty 'log_entry'")

    store = _require_store()
    analyst = _get_analyst()

    try:
        analysis = analyst.analyze_log(log_entry)
    except Exception as exc:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"analysis failed: {exc}") from exc

    if isinstance(analysis, dict) and analysis.get("error"):
        raise RpcError(RPC_SIDECAR_ERROR, str(analysis["error"]))

    severity = (
        str(analysis.get("severity", "UNKNOWN"))
        if isinstance(analysis, dict)
        else "UNKNOWN"
    )
    summary = (
        (
            analysis.get("root_cause_hypothesis")
            or analysis.get("summary")
            or log_entry[:120]
        )
        if isinstance(analysis, dict)
        else log_entry[:120]
    )

    from src.core.proposal_store import RiskClass

    # Adopt the analyst's audit trace_id rather than minting a fresh one, so the
    # id the operator sees on the proposal actually resolves in
    # audit.get_by_trace. Without this the only trace_id desktop ever displayed
    # was the one that could not be audited.
    trace_id = analysis.get("trace_id") if isinstance(analysis, dict) else None

    proposal = store.create(
        action_type="analysis",
        risk_class=RiskClass.INFORMATIONAL,
        payload={"log_entry": log_entry, "analysis": analysis},
        description=f"[{severity}] {summary}",
        reversible=True,
        proposed_by="desktop-operator",
        trace_id=trace_id,
    )
    return proposal.model_dump(mode="json")
