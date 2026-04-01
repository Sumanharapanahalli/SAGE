"""
src/modules/cloud_events.py — CloudEvents Envelope (Layer 2)
=============================================================

Implements the CloudEvents v1.0 specification for standardized event routing.
Zero external dependencies — pure Python dataclass + JSON serialization.

This wraps the existing EventBus with structured envelopes, enabling:
- Standardized event format across all SAGE components
- Future integration with event-driven systems (n8n, Kafka, webhooks)
- Interoperability with any CloudEvents-compatible consumer

CloudEvents spec: https://github.com/cloudevents/spec/blob/v1.0.2/cloudevents/spec.md

Usage:
    from src.modules.cloud_events import CloudEvent, proposal_event, publish_cloud_event
    from src.modules.event_bus import event_bus

    event = proposal_event("created", "p-123", {"risk": "high"})
    publish_cloud_event(event_bus, event)
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────────────
# Core CloudEvent dataclass
# ─────────────────────────────────────────────────────────────────────

# Required attributes per spec: id, source, specversion, type
# Optional attributes: datacontenttype, dataschema, subject, time
# Extension attributes: any additional key-value pairs

_REQUIRED_ATTRS = {"id", "source", "specversion", "type"}
_KNOWN_ATTRS = _REQUIRED_ATTRS | {"datacontenttype", "dataschema", "subject", "time", "data"}


@dataclass
class CloudEvent:
    """
    CloudEvents v1.0 structured envelope.

    Required attributes (per spec):
        type: Event type (e.g., "sage.proposal.created")
        source: Event source URI-reference (e.g., "/sage/proposals")

    Auto-generated:
        id: Unique event identifier (UUID)
        specversion: Always "1.0"
        time: ISO 8601 timestamp

    Optional:
        subject: Event subject (e.g., "proposal/p-123")
        datacontenttype: MIME type of data (default: "application/json")
        data: Event payload (any JSON-serializable dict)
        extensions: Additional CloudEvents extension attributes
    """
    type: str
    source: str
    data: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=_new_id)
    specversion: str = "1.0"
    time: str = field(default_factory=_now_iso)
    subject: Optional[str] = None
    datacontenttype: str = "application/json"
    extensions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a flat dict (CloudEvents structured content mode)."""
        d: Dict[str, Any] = {
            "specversion": self.specversion,
            "id": self.id,
            "type": self.type,
            "source": self.source,
            "time": self.time,
            "datacontenttype": self.datacontenttype,
            "data": self.data,
        }
        if self.subject is not None:
            d["subject"] = self.subject
        # Extension attributes go at the top level (per spec)
        for k, v in self.extensions.items():
            d[k] = v
        return d

    def to_json(self) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CloudEvent":
        """Deserialize from a dict. Raises ValueError if required attrs missing."""
        for attr in ("type", "source"):
            if attr not in d:
                raise ValueError(f"Missing required CloudEvent attribute: {attr}")

        # Separate known attributes from extension attributes
        extensions = {k: v for k, v in d.items() if k not in _KNOWN_ATTRS}

        return cls(
            type=d["type"],
            source=d["source"],
            data=d.get("data", {}),
            id=d.get("id", _new_id()),
            specversion=d.get("specversion", "1.0"),
            time=d.get("time", _now_iso()),
            subject=d.get("subject"),
            datacontenttype=d.get("datacontenttype", "application/json"),
            extensions=extensions,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "CloudEvent":
        """Deserialize from a JSON string."""
        d = json.loads(json_str)
        return cls.from_dict(d)


# ─────────────────────────────────────────────────────────────────────
# SAGE Event Type Factories
# ─────────────────────────────────────────────────────────────────────

def proposal_event(
    action: str,
    proposal_id: str,
    data: Dict[str, Any],
    **extensions: Any,
) -> CloudEvent:
    """Create a sage.proposal.{action} event."""
    return CloudEvent(
        type=f"sage.proposal.{action}",
        source="/sage/proposals",
        subject=f"proposal/{proposal_id}",
        data=data,
        extensions=extensions,
    )


def build_event(
    action: str,
    run_id: str,
    data: Dict[str, Any],
    **extensions: Any,
) -> CloudEvent:
    """Create a sage.build.{action} event."""
    return CloudEvent(
        type=f"sage.build.{action}",
        source="/sage/build",
        subject=f"run/{run_id}",
        data=data,
        extensions=extensions,
    )


def gym_event(
    action: str,
    session_id: str,
    data: Dict[str, Any],
    **extensions: Any,
) -> CloudEvent:
    """Create a sage.gym.{action} event."""
    return CloudEvent(
        type=f"sage.gym.{action}",
        source="/sage/gym",
        subject=f"session/{session_id}",
        data=data,
        extensions=extensions,
    )


def llm_event(
    action: str,
    data: Dict[str, Any],
    **extensions: Any,
) -> CloudEvent:
    """Create a sage.llm.{action} event."""
    return CloudEvent(
        type=f"sage.llm.{action}",
        source="/sage/llm",
        data=data,
        extensions=extensions,
    )


# ─────────────────────────────────────────────────────────────────────
# EventBus Integration
# ─────────────────────────────────────────────────────────────────────

def publish_cloud_event(bus: Any, event: CloudEvent) -> int:
    """
    Publish a CloudEvent on the EventBus.

    The event type becomes the EventBus event_type, and the full
    CloudEvent envelope (as dict) is the data payload.

    Returns the number of handlers called.
    """
    return bus.publish(event.type, event.to_dict())
