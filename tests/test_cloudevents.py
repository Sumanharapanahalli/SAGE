"""
CloudEvents Envelope Tests — Layer 2 Communication
====================================================

Tests cover:
  1. CloudEvent dataclass structure and required fields
  2. CloudEvents spec v1.0 compliance (required attributes)
  3. JSON serialization / deserialization roundtrip
  4. Factory helpers for SAGE-specific event types
  5. EventBus integration (publish/subscribe with envelopes)
  6. Validation and error handling
"""

import json
import time
import uuid
from datetime import datetime, timezone

import pytest


# ─── 1. CloudEvent Structure ───────────────────────────────────────


class TestCloudEventStructure:
    """Verify CloudEvent dataclass has correct fields."""

    def test_create_event_with_required_fields(self):
        """CloudEvent can be created with the 4 required attributes."""
        from src.modules.cloud_events import CloudEvent
        event = CloudEvent(
            type="sage.test.created",
            source="/test",
            data={"key": "value"},
        )
        assert event.type == "sage.test.created"
        assert event.source == "/test"
        assert event.data == {"key": "value"}
        assert event.specversion == "1.0"

    def test_auto_generated_id(self):
        """CloudEvent auto-generates a UUID id if not provided."""
        from src.modules.cloud_events import CloudEvent
        e1 = CloudEvent(type="test", source="/test", data={})
        e2 = CloudEvent(type="test", source="/test", data={})
        assert e1.id != e2.id
        # Verify it's a valid UUID
        uuid.UUID(e1.id)

    def test_auto_generated_time(self):
        """CloudEvent auto-generates an ISO 8601 timestamp."""
        from src.modules.cloud_events import CloudEvent
        before = datetime.now(timezone.utc).isoformat()
        event = CloudEvent(type="test", source="/test", data={})
        after = datetime.now(timezone.utc).isoformat()
        assert event.time is not None
        assert before <= event.time <= after

    def test_custom_id_and_time(self):
        """CloudEvent accepts custom id and time."""
        from src.modules.cloud_events import CloudEvent
        event = CloudEvent(
            type="test",
            source="/test",
            data={},
            id="custom-123",
            time="2026-03-31T12:00:00Z",
        )
        assert event.id == "custom-123"
        assert event.time == "2026-03-31T12:00:00Z"

    def test_optional_subject(self):
        """CloudEvent supports optional subject attribute."""
        from src.modules.cloud_events import CloudEvent
        event = CloudEvent(
            type="sage.proposal.created",
            source="/proposals",
            data={"proposal_id": "p-1"},
            subject="proposal/p-1",
        )
        assert event.subject == "proposal/p-1"

    def test_datacontenttype_defaults_json(self):
        """CloudEvent defaults datacontenttype to application/json."""
        from src.modules.cloud_events import CloudEvent
        event = CloudEvent(type="test", source="/test", data={})
        assert event.datacontenttype == "application/json"


# ─── 2. CloudEvents Spec v1.0 Compliance ──────────────────────────


class TestSpecCompliance:
    """Verify compliance with CloudEvents spec v1.0 required attributes."""

    def test_required_attributes_present(self):
        """All 4 required attributes (id, source, specversion, type) are present."""
        from src.modules.cloud_events import CloudEvent
        event = CloudEvent(type="test.event", source="/sage", data={})
        assert hasattr(event, "id")
        assert hasattr(event, "source")
        assert hasattr(event, "specversion")
        assert hasattr(event, "type")

    def test_specversion_is_1_0(self):
        """specversion must be '1.0'."""
        from src.modules.cloud_events import CloudEvent
        event = CloudEvent(type="test", source="/test", data={})
        assert event.specversion == "1.0"

    def test_type_is_non_empty_string(self):
        """type must be a non-empty string."""
        from src.modules.cloud_events import CloudEvent
        event = CloudEvent(type="sage.build.completed", source="/build", data={})
        assert isinstance(event.type, str)
        assert len(event.type) > 0

    def test_source_is_non_empty_string(self):
        """source must be a non-empty string (URI-reference)."""
        from src.modules.cloud_events import CloudEvent
        event = CloudEvent(type="test", source="/sage/gym", data={})
        assert isinstance(event.source, str)
        assert len(event.source) > 0


# ─── 3. JSON Serialization / Deserialization ───────────────────────


class TestSerialization:
    """Verify JSON roundtrip fidelity."""

    def test_to_json_produces_valid_json(self):
        """to_json() returns a valid JSON string."""
        from src.modules.cloud_events import CloudEvent
        event = CloudEvent(
            type="sage.test",
            source="/test",
            data={"nested": {"key": [1, 2, 3]}},
        )
        json_str = event.to_json()
        parsed = json.loads(json_str)
        assert parsed["type"] == "sage.test"
        assert parsed["data"]["nested"]["key"] == [1, 2, 3]

    def test_to_dict_returns_dict(self):
        """to_dict() returns a plain dict with all attributes."""
        from src.modules.cloud_events import CloudEvent
        event = CloudEvent(type="test", source="/test", data={"a": 1})
        d = event.to_dict()
        assert isinstance(d, dict)
        assert d["specversion"] == "1.0"
        assert d["data"] == {"a": 1}

    def test_from_json_roundtrip(self):
        """from_json(event.to_json()) produces an equivalent event."""
        from src.modules.cloud_events import CloudEvent
        original = CloudEvent(
            type="sage.roundtrip",
            source="/test",
            data={"x": 42},
            subject="test/subject",
        )
        json_str = original.to_json()
        restored = CloudEvent.from_json(json_str)
        assert restored.id == original.id
        assert restored.type == original.type
        assert restored.source == original.source
        assert restored.data == original.data
        assert restored.subject == original.subject
        assert restored.specversion == original.specversion

    def test_from_dict_roundtrip(self):
        """from_dict(event.to_dict()) produces an equivalent event."""
        from src.modules.cloud_events import CloudEvent
        original = CloudEvent(type="sage.dict", source="/test", data={"y": 99})
        d = original.to_dict()
        restored = CloudEvent.from_dict(d)
        assert restored.id == original.id
        assert restored.type == original.type
        assert restored.data == original.data

    def test_from_json_invalid_raises(self):
        """from_json with invalid JSON raises ValueError."""
        from src.modules.cloud_events import CloudEvent
        with pytest.raises((ValueError, json.JSONDecodeError)):
            CloudEvent.from_json("not valid json{{{")

    def test_from_dict_missing_required_raises(self):
        """from_dict without required 'type' raises ValueError."""
        from src.modules.cloud_events import CloudEvent
        with pytest.raises((ValueError, KeyError)):
            CloudEvent.from_dict({"source": "/test", "data": {}})


# ─── 4. SAGE Event Type Factories ─────────────────────────────────


class TestEventFactories:
    """Verify factory functions for common SAGE event types."""

    def test_proposal_event(self):
        """proposal_event() creates a properly typed CloudEvent."""
        from src.modules.cloud_events import proposal_event
        event = proposal_event(
            action="created",
            proposal_id="p-123",
            data={"risk": "medium", "action_type": "yaml_edit"},
        )
        assert event.type == "sage.proposal.created"
        assert event.source == "/sage/proposals"
        assert event.subject == "proposal/p-123"
        assert event.data["risk"] == "medium"

    def test_build_event(self):
        """build_event() creates a properly typed CloudEvent."""
        from src.modules.cloud_events import build_event
        event = build_event(
            action="task_completed",
            run_id="run-456",
            data={"task_type": "implementation", "agent": "developer"},
        )
        assert event.type == "sage.build.task_completed"
        assert event.source == "/sage/build"
        assert event.subject == "run/run-456"

    def test_gym_event(self):
        """gym_event() creates a properly typed CloudEvent."""
        from src.modules.cloud_events import gym_event
        event = gym_event(
            action="session_completed",
            session_id="sess-789",
            data={"role": "firmware_engineer", "score": 0.85},
        )
        assert event.type == "sage.gym.session_completed"
        assert event.source == "/sage/gym"
        assert event.subject == "session/sess-789"

    def test_llm_event(self):
        """llm_event() creates a properly typed CloudEvent."""
        from src.modules.cloud_events import llm_event
        event = llm_event(
            action="generate",
            data={"provider": "gemini", "model": "flash", "tokens": 500},
        )
        assert event.type == "sage.llm.generate"
        assert event.source == "/sage/llm"


# ─── 5. EventBus Integration ──────────────────────────────────────


class TestEventBusIntegration:
    """Verify CloudEvents work with the existing EventBus."""

    def test_publish_cloudevent_via_bus(self):
        """CloudEvent can be published on EventBus as a dict."""
        from src.modules.cloud_events import CloudEvent, publish_cloud_event
        from src.modules.event_bus import EventBus

        bus = EventBus()
        received = []
        bus.subscribe("sage.test.published", lambda t, d: received.append(d))

        event = CloudEvent(
            type="sage.test.published",
            source="/test",
            data={"msg": "hello"},
        )
        publish_cloud_event(bus, event)

        assert len(received) == 1
        assert received[0]["specversion"] == "1.0"
        assert received[0]["data"]["msg"] == "hello"

    def test_subscribe_filter_by_event_type(self):
        """Only matching event types are received."""
        from src.modules.cloud_events import CloudEvent, publish_cloud_event
        from src.modules.event_bus import EventBus

        bus = EventBus()
        proposals = []
        builds = []
        bus.subscribe("sage.proposal.created", lambda t, d: proposals.append(d))
        bus.subscribe("sage.build.started", lambda t, d: builds.append(d))

        publish_cloud_event(bus, CloudEvent(
            type="sage.proposal.created", source="/proposals", data={"id": "p1"}
        ))
        publish_cloud_event(bus, CloudEvent(
            type="sage.build.started", source="/build", data={"id": "b1"}
        ))

        assert len(proposals) == 1
        assert len(builds) == 1
        assert proposals[0]["data"]["id"] == "p1"
        assert builds[0]["data"]["id"] == "b1"

    def test_wildcard_receives_all_cloud_events(self):
        """Wildcard subscriber receives all CloudEvent types."""
        from src.modules.cloud_events import CloudEvent, publish_cloud_event
        from src.modules.event_bus import EventBus

        bus = EventBus()
        all_events = []
        bus.subscribe("*", lambda t, d: all_events.append(d))

        publish_cloud_event(bus, CloudEvent(type="sage.a", source="/a", data={}))
        publish_cloud_event(bus, CloudEvent(type="sage.b", source="/b", data={}))

        assert len(all_events) == 2


# ─── 6. Extension Attributes ──────────────────────────────────────


class TestExtensionAttributes:
    """Verify CloudEvents extension attributes for SAGE-specific metadata."""

    def test_sage_extensions_in_dict(self):
        """SAGE-specific extensions are included in to_dict()."""
        from src.modules.cloud_events import CloudEvent
        event = CloudEvent(
            type="sage.test",
            source="/test",
            data={},
            extensions={"sagetenant": "team-alpha", "sagetraceid": "trace-001"},
        )
        d = event.to_dict()
        assert d["sagetenant"] == "team-alpha"
        assert d["sagetraceid"] == "trace-001"

    def test_extensions_survive_roundtrip(self):
        """Extension attributes survive JSON roundtrip."""
        from src.modules.cloud_events import CloudEvent
        original = CloudEvent(
            type="sage.ext",
            source="/test",
            data={"x": 1},
            extensions={"sagetenant": "t1"},
        )
        restored = CloudEvent.from_json(original.to_json())
        assert restored.extensions.get("sagetenant") == "t1"
