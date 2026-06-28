"""
Agent-to-agent communication auditing.

Closes the gap between *how agents talk* (the in-memory EventBus / direct
handoffs) and *the formal record* (compliance_audit_log). Every inter-agent
communication is written to the audit trail so the SAGE Audit Log view
(`/audit` -> trace drill-down) shows the complete chain — a regulatory control
("trace each communication between agents").

The audit DB is solution-scoped by construction (each solution gets its own
`<solution>/.sage/audit_log.db`), so these records are automatically
**per-solution** — no extra scoping needed here.

Usage
-----
Direct (e.g. from an agent handoff):
    log_agent_communication(audit_logger, from_agent="planner",
                            to_agent="openswe", message="...", trace_id="...")

Via the EventBus (so nothing escapes the record): attach the bridge once at
startup, then publish through the helper:
    attach_audit_bridge(bus, audit_logger)
    publish_agent_communication(bus, from_agent="monitor", to_agent="analyst",
                                message="anomaly detected", trace_id="...")
"""
from __future__ import annotations

from typing import Optional

# Bus event type carrying an agent-to-agent message.
AGENT_COMM_EVENT = "agent.communication"

# Audit action_type written for each such message.
AGENT_COMM_ACTION = "AGENT_COMMUNICATION"

# Keep audit rows bounded; full payloads belong in the agents' own artifacts.
_MAX_MESSAGE_CHARS = 4000


def log_agent_communication(
    audit_logger,
    *,
    from_agent: str,
    to_agent: str,
    message: str,
    trace_id: Optional[str] = None,
    kind: str = "message",
):
    """Write one AGENT_COMMUNICATION entry to the (solution-scoped) audit log.

    Returns the audit event id (or whatever ``audit_logger.log_event`` returns).
    """
    text = (message or "")
    if len(text) > _MAX_MESSAGE_CHARS:
        text = text[:_MAX_MESSAGE_CHARS] + "…[truncated]"
    return audit_logger.log_event(
        actor=from_agent,
        action_type=AGENT_COMM_ACTION,
        input_context=text,
        output_content="",
        metadata={
            "to_agent": to_agent,
            "trace_id": trace_id,
            "kind": kind,
        },
    )


def publish_agent_communication(
    bus,
    *,
    from_agent: str,
    to_agent: str,
    message: str,
    trace_id: Optional[str] = None,
    kind: str = "message",
) -> int:
    """Publish an agent-communication event on the bus.

    Returns the number of handlers the bus invoked (so callers can assert the
    audit bridge — and any other subscribers — actually ran).
    """
    return bus.publish(
        AGENT_COMM_EVENT,
        {
            "from_agent": from_agent,
            "to_agent": to_agent,
            "message": message,
            "trace_id": trace_id,
            "kind": kind,
        },
    )


def attach_audit_bridge(bus, audit_logger) -> None:
    """Subscribe an audit handler to AGENT_COMM_EVENT on *bus*.

    Only agent-communication events are mirrored to the audit log; other bus
    traffic is left untouched. Idempotent enough for startup wiring — attaching
    twice simply records twice, so attach once.
    """

    def _handler(_event_type: str, data: dict) -> None:
        log_agent_communication(
            audit_logger,
            from_agent=data.get("from_agent", "unknown"),
            to_agent=data.get("to_agent", "unknown"),
            message=data.get("message", ""),
            trace_id=data.get("trace_id"),
            kind=data.get("kind", "message"),
        )

    bus.subscribe(AGENT_COMM_EVENT, _handler)
