"""
Unit tests for src/modules/event_bus.py
"""
import threading
import time

import pytest

pytestmark = pytest.mark.unit

from src.modules.event_bus import EventBus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_recorder():
    """Return a list and a handler that appends (event_type, data) to it."""
    calls = []

    def handler(event_type, data):
        calls.append((event_type, data))

    return calls, handler


# ---------------------------------------------------------------------------
# subscribe() + publish()
# ---------------------------------------------------------------------------

class TestSubscribePublish:
    def test_handler_called_on_publish(self):
        bus = EventBus()
        calls, handler = make_recorder()
        bus.subscribe("task.created", handler)
        bus.publish("task.created", {"id": 1})
        assert calls == [("task.created", {"id": 1})]

    def test_handler_receives_correct_event_type_and_data(self):
        bus = EventBus()
        calls, handler = make_recorder()
        bus.subscribe("alert", handler)
        bus.publish("alert", {"severity": "HIGH"})
        event_type, data = calls[0]
        assert event_type == "alert"
        assert data == {"severity": "HIGH"}

    def test_multiple_handlers_for_same_event(self):
        bus = EventBus()
        calls1, h1 = make_recorder()
        calls2, h2 = make_recorder()
        bus.subscribe("ping", h1)
        bus.subscribe("ping", h2)
        bus.publish("ping", {})
        assert len(calls1) == 1
        assert len(calls2) == 1

    def test_publish_returns_handler_count(self):
        bus = EventBus()
        _, h1 = make_recorder()
        _, h2 = make_recorder()
        bus.subscribe("evt", h1)
        bus.subscribe("evt", h2)
        count = bus.publish("evt", {})
        assert count == 2

    def test_publish_with_no_handlers_returns_zero(self):
        bus = EventBus()
        assert bus.publish("nothing_subscribed", {}) == 0

    def test_handler_not_called_for_different_event(self):
        bus = EventBus()
        calls, handler = make_recorder()
        bus.subscribe("event_a", handler)
        bus.publish("event_b", {})
        assert calls == []


# ---------------------------------------------------------------------------
# Wildcard '*' handler
# ---------------------------------------------------------------------------

class TestWildcard:
    def test_wildcard_receives_any_event(self):
        bus = EventBus()
        calls, handler = make_recorder()
        bus.subscribe("*", handler)
        bus.publish("task.created", {"id": 1})
        bus.publish("alert", {"severity": "RED"})
        assert len(calls) == 2

    def test_wildcard_receives_correct_event_types(self):
        bus = EventBus()
        calls, handler = make_recorder()
        bus.subscribe("*", handler)
        bus.publish("alpha", {})
        bus.publish("beta", {})
        event_types = [c[0] for c in calls]
        assert "alpha" in event_types
        assert "beta" in event_types

    def test_wildcard_handler_not_called_twice_when_also_subscribed_specifically(self):
        bus = EventBus()
        calls, handler = make_recorder()
        bus.subscribe("my_event", handler)
        bus.subscribe("*", handler)
        count = bus.publish("my_event", {})
        # handler is already in specific list; wildcard dedup prevents double-call
        assert count == 1

    def test_wildcard_and_specific_handler_both_called(self):
        bus = EventBus()
        calls_specific, h_specific = make_recorder()
        calls_wild, h_wild = make_recorder()
        bus.subscribe("evt", h_specific)
        bus.subscribe("*", h_wild)
        bus.publish("evt", {"x": 1})
        assert len(calls_specific) == 1
        assert len(calls_wild) == 1


# ---------------------------------------------------------------------------
# unsubscribe()
# ---------------------------------------------------------------------------

class TestUnsubscribe:
    def test_handler_not_called_after_unsubscribe(self):
        bus = EventBus()
        calls, handler = make_recorder()
        bus.subscribe("evt", handler)
        bus.unsubscribe("evt", handler)
        bus.publish("evt", {})
        assert calls == []

    def test_other_handlers_still_called_after_one_unsubscribed(self):
        bus = EventBus()
        calls1, h1 = make_recorder()
        calls2, h2 = make_recorder()
        bus.subscribe("evt", h1)
        bus.subscribe("evt", h2)
        bus.unsubscribe("evt", h1)
        bus.publish("evt", {})
        assert calls1 == []
        assert len(calls2) == 1

    def test_unsubscribe_nonexistent_handler_does_not_raise(self):
        bus = EventBus()
        _, handler = make_recorder()
        bus.unsubscribe("evt", handler)  # never subscribed — should not raise


# ---------------------------------------------------------------------------
# Exception handling
# ---------------------------------------------------------------------------

class TestExceptionHandling:
    def test_exception_in_handler_does_not_propagate(self):
        bus = EventBus()

        def bad_handler(event_type, data):
            raise RuntimeError("handler failure")

        calls, good_handler = make_recorder()
        bus.subscribe("evt", bad_handler)
        bus.subscribe("evt", good_handler)

        # Should not raise
        count = bus.publish("evt", {})
        # bad_handler raised but good_handler still ran
        assert len(calls) == 1
        # bad_handler is counted — it was called (even though it raised)
        # Actually per implementation, only successful calls increment count
        # Let's verify: bad_handler raised, so it was NOT counted
        # good_handler succeeded, so count == 1
        assert count == 1

    def test_all_handlers_called_despite_earlier_exception(self):
        bus = EventBus()
        order = []

        def h_bad(event_type, data):
            order.append("bad")
            raise ValueError("oops")

        def h_good1(event_type, data):
            order.append("good1")

        def h_good2(event_type, data):
            order.append("good2")

        bus.subscribe("evt", h_bad)
        bus.subscribe("evt", h_good1)
        bus.subscribe("evt", h_good2)
        bus.publish("evt", {})
        assert "good1" in order
        assert "good2" in order


# ---------------------------------------------------------------------------
# clear()
# ---------------------------------------------------------------------------

class TestClear:
    def test_clear_removes_all_handlers(self):
        bus = EventBus()
        calls, handler = make_recorder()
        bus.subscribe("a", handler)
        bus.subscribe("b", handler)
        bus.subscribe("*", handler)
        bus.clear()
        bus.publish("a", {})
        bus.publish("b", {})
        assert calls == []

    def test_clear_returns_zero_count_after(self):
        bus = EventBus()
        _, handler = make_recorder()
        bus.subscribe("evt", handler)
        bus.clear()
        assert bus.publish("evt", {}) == 0


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_publish_does_not_corrupt_state(self):
        bus = EventBus()
        results = []
        lock = threading.Lock()

        def handler(event_type, data):
            with lock:
                results.append(data["n"])

        bus.subscribe("work", handler)

        threads = [
            threading.Thread(target=bus.publish, args=("work", {"n": i}))
            for i in range(50)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 50
        assert sorted(results) == list(range(50))

    def test_concurrent_subscribe_and_publish(self):
        """Ensure subscribe/publish interleaving does not raise."""
        bus = EventBus()
        errors = []

        def subscriber():
            try:
                _, handler = make_recorder()
                bus.subscribe("evt", handler)
            except Exception as e:
                errors.append(e)

        def publisher():
            try:
                bus.publish("evt", {"x": 1})
            except Exception as e:
                errors.append(e)

        threads = (
            [threading.Thread(target=subscriber) for _ in range(20)]
            + [threading.Thread(target=publisher) for _ in range(20)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"
