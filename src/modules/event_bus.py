"""
Nano-module: Event Bus
=======================
Lightweight synchronous publish/subscribe bus for decoupled agent communication.
Zero dependencies — pure Python. Thread-safe.
"""
import logging
import threading
from collections import defaultdict
from typing import Callable

logger = logging.getLogger(__name__)

_WILDCARD = "*"


class EventBus:
    """
    Simple synchronous event bus.

    Usage:
        bus = EventBus()
        bus.subscribe("my_event", handler)
        bus.publish("my_event", {"data": 42})
    """

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Register a handler for an event type. Use '*' for all events."""
        with self._lock:
            self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """Remove a previously registered handler."""
        with self._lock:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h is not handler
            ]

    def publish(self, event_type: str, data: dict) -> int:
        """
        Publish an event to all registered handlers.
        Returns the number of handlers called.
        Exceptions in handlers are logged, not re-raised.
        """
        with self._lock:
            handlers = list(self._handlers.get(event_type, []))
            handlers += [h for h in self._handlers.get(_WILDCARD, [])
                         if h not in handlers]

        called = 0
        for handler in handlers:
            try:
                handler(event_type, data)
                called += 1
            except Exception as exc:
                logger.error("EventBus handler %s raised: %s", handler, exc)
        return called

    def clear(self) -> None:
        """Remove all handlers (useful in tests)."""
        with self._lock:
            self._handlers.clear()


# Module-level singleton (optional — agents can also create their own)
event_bus = EventBus()
