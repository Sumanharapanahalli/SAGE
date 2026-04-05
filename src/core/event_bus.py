"""
SAGE Event Bus — Real-Time Event Streaming
===========================================

Publish-subscribe event system with SSE (Server-Sent Events) support.
Enables real-time UI updates for orchestrator activity: task progress,
wave execution, critic scores, budget alerts, consensus votes.

Architecture:
  - In-process pub/sub via asyncio queues
  - SSE endpoint streams events to browser clients
  - Events are typed, timestamped, and JSON-serializable
  - Bounded history buffer for late-joining clients
"""

import asyncio
import json
import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# Event Types
# ──────────────────────────────────────────────────────────────────────

EVENT_TYPES = {
    # Task lifecycle
    "task.submitted", "task.started", "task.completed", "task.failed",
    "task.retried", "task.blocked",
    # Wave execution
    "wave.started", "wave.completed",
    # Build orchestrator
    "build.started", "build.phase_changed", "build.completed", "build.failed",
    # Critic / Reflection
    "critic.scored", "reflection.started", "reflection.iteration",
    "reflection.accepted", "reflection.rejected",
    # Budget
    "budget.usage", "budget.warning", "budget.exceeded",
    # Consensus
    "consensus.started", "consensus.vote", "consensus.resolved",
    # Plan selection
    "plan.candidates_generated", "plan.selected",
    # Agent spawning
    "agent.spawned", "agent.completed",
    # Generic
    "system.info", "system.error",
}


@dataclass
class Event:
    """A typed, timestamped event."""
    event_type: str
    data: dict = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    source: str = ""  # module that emitted

    def to_sse(self) -> str:
        """Format as SSE message."""
        payload = json.dumps({
            "id": self.event_id,
            "type": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp,
            "source": self.source,
        })
        return f"event: {self.event_type}\ndata: {payload}\nid: {self.event_id}\n\n"

    def to_dict(self) -> dict:
        return asdict(self)


# ──────────────────────────────────────────────────────────────────────
# EventBus
# ──────────────────────────────────────────────────────────────────────

class EventBus:
    """In-process pub/sub with SSE streaming support."""

    def __init__(self, history_size: int = 200):
        self._subscribers: list[asyncio.Queue] = []
        self._sync_callbacks: list = []  # synchronous callbacks
        self._history: deque[Event] = deque(maxlen=history_size)
        self._lock = threading.Lock()
        self._event_count = 0

    def publish(self, event_type: str, data: dict = None, source: str = "") -> Event:
        """
        Publish an event. Thread-safe. Works from sync or async context.
        Returns the created Event.
        """
        event = Event(
            event_type=event_type,
            data=data or {},
            source=source,
        )

        with self._lock:
            self._history.append(event)
            self._event_count += 1
            subs = list(self._subscribers)
            cbs = list(self._sync_callbacks)

        # Push to async subscribers (SSE clients)
        for queue in subs:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # drop oldest if client is slow

        # Call sync subscribers
        for cb in cbs:
            try:
                cb(event)
            except Exception as exc:
                logger.warning("Event callback error: %s", exc)

        return event

    def subscribe(self, max_queue: int = 100) -> asyncio.Queue:
        """
        Subscribe for events. Returns an asyncio.Queue.
        Caller should call unsubscribe() when done.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue)
        with self._lock:
            self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Remove a subscriber."""
        with self._lock:
            self._subscribers = [q for q in self._subscribers if q is not queue]

    def on_event(self, callback) -> None:
        """Register a synchronous callback for all events."""
        with self._lock:
            self._sync_callbacks.append(callback)

    def get_history(self, event_type: str = None, limit: int = 50) -> list[dict]:
        """Get recent events, optionally filtered by type."""
        with self._lock:
            events = list(self._history)
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return [e.to_dict() for e in events[-limit:]]

    def get_stats(self) -> dict:
        """Return bus statistics."""
        with self._lock:
            return {
                "total_events": self._event_count,
                "subscriber_count": len(self._subscribers),
                "callback_count": len(self._sync_callbacks),
                "history_size": len(self._history),
            }

    async def stream(self, event_types: list[str] = None) -> Any:
        """
        Async generator for SSE streaming.
        Yields SSE-formatted strings. Optionally filter by event types.
        """
        queue = self.subscribe()
        try:
            while True:
                event = await queue.get()
                if event_types and event.event_type not in event_types:
                    continue
                yield event.to_sse()
        finally:
            self.unsubscribe(queue)


# ──────────────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────────────

_event_bus: Optional[EventBus] = None
_bus_lock = threading.Lock()


def get_event_bus() -> EventBus:
    """Get or create the global EventBus instance."""
    global _event_bus
    if _event_bus is None:
        with _bus_lock:
            if _event_bus is None:
                _event_bus = EventBus()
    return _event_bus
