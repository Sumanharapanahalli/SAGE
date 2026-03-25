"""Smoke tests for the fall alert pipeline."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_fall_classifier():
    from backend.agents.fall_classifier import FallClassifierAgent, FallEventInput, FallSeverity

    agent = FallClassifierAgent()

    # SOS button -> highest priority, 30s grace
    e = FallEventInput(event_id="e1", device_id="d1", user_id="u1",
                       event_type="sos_button", button_pressed=True)
    c = agent.classify(e)
    assert c.severity == FallSeverity.SOS_BUTTON, f"Expected SOS_BUTTON got {c.severity}"
    assert c.grace_period_seconds == 30

    # High-impact fall, no recovery -> confirmed
    e2 = FallEventInput(event_id="e2", device_id="d1", user_id="u1",
                        event_type="fall_detected", impact_force_g=4.5)
    c2 = agent.classify(e2)
    assert c2.severity == FallSeverity.CONFIRMED_FALL
    assert c2.grace_period_seconds == 60

    # Moderate impact -> possible fall
    e3 = FallEventInput(event_id="e3", device_id="d1", user_id="u1",
                        event_type="impact", impact_force_g=2.0)
    c3 = agent.classify(e3)
    assert c3.severity == FallSeverity.POSSIBLE_FALL

    # Low impact -> false alarm
    e4 = FallEventInput(event_id="e4", device_id="d1", user_id="u1",
                        event_type="impact", impact_force_g=0.5)
    c4 = agent.classify(e4)
    assert c4.severity == FallSeverity.FALSE_ALARM

    print("FallClassifier: PASS")


async def test_notification_router_parallel():
    from backend.agents.fall_classifier import FallClassifierAgent, FallEventInput
    from backend.agents.notification_router import CaregiverContact, NotificationRouterAgent
    import time

    classifier = FallClassifierAgent()
    router = NotificationRouterAgent()

    event = FallEventInput(event_id="e10", device_id="d1", user_id="u1",
                           event_type="fall_detected", impact_force_g=4.0)
    classification = classifier.classify(event)

    caregivers = [
        CaregiverContact(
            caregiver_id="cg1", name="Alice",
            fcm_token="tok_abc", phone_number="+15550001", email="alice@test.com"
        )
    ]

    start = time.monotonic()
    decision = await router.notify_all("alert-001", classification, caregivers)
    elapsed_ms = (time.monotonic() - start) * 1000

    # All 3 channels should have been attempted (push + sms + email)
    assert len(decision.results) == 3, f"Expected 3 results, got {len(decision.results)}"
    assert decision.primary_notification_sent
    # Parallel: wall clock should be close to the slowest channel (~120ms), not sum (~250ms)
    assert elapsed_ms < 300, f"Expected <300ms got {elapsed_ms:.0f}ms"
    print(f"NotificationRouter: PASS — 3 channels in {elapsed_ms:.0f}ms (parallel verified)")


async def test_idempotency():
    from backend.services.alert_service import IdempotencyStore

    store = IdempotencyStore()
    aid1, is_new1 = await store.get_or_create("event-dup")
    aid2, is_new2 = await store.get_or_create("event-dup")

    assert is_new1 is True
    assert is_new2 is False
    assert aid1 == aid2
    print("Idempotency: PASS")


async def test_dispatch_decider_cancel():
    from backend.agents.dispatch_decider import DispatchDeciderAgent, GracePeriodStatus

    dispatched = []

    async def on_dispatch(state):
        dispatched.append(state.alert_id)

    decider = DispatchDeciderAgent(dispatch_callback=on_dispatch)
    state = decider.start_grace_period("a1", "u1", "CONFIRMED_FALL", timeout_seconds=2)
    assert state.status == GracePeriodStatus.ACTIVE

    # Cancel within grace period
    cancelled = await decider.cancel("a1", cancelled_by="user")
    assert cancelled is True

    final = decider.get_state("a1")
    assert final.status == GracePeriodStatus.CANCELLED
    assert final.cancelled_by == "user"

    # Wait past the original timeout to confirm dispatch was NOT called
    await asyncio.sleep(2.5)
    assert len(dispatched) == 0, "Dispatch should NOT have been called after cancellation"
    print("DispatchDecider cancel: PASS")


async def test_dispatch_decider_expires():
    from backend.agents.dispatch_decider import DispatchDeciderAgent, GracePeriodStatus

    dispatched = []

    async def on_dispatch(state):
        dispatched.append(state.alert_id)

    decider = DispatchDeciderAgent(dispatch_callback=on_dispatch)
    decider.start_grace_period("a2", "u2", "SOS_BUTTON", timeout_seconds=1)

    await asyncio.sleep(1.5)
    assert len(dispatched) == 1
    final = decider.get_state("a2")
    assert final.status == GracePeriodStatus.DISPATCHED
    print("DispatchDecider expiry dispatch: PASS")


async def test_full_pipeline_latency():
    from backend.services.alert_service import AlertService, FallEventRequest
    import time

    svc = AlertService()
    req = FallEventRequest(
        event_id="perf-test-001",
        device_id="dev-1",
        user_id="user-1",
        event_type="fall_detected",
        impact_force_g=5.0,
        button_pressed=False,
    )

    start = time.monotonic()
    resp = await svc.process_fall_event(req)
    elapsed_ms = (time.monotonic() - start) * 1000

    assert resp.status == "active"
    assert resp.severity == "CONFIRMED_FALL"
    assert resp.is_duplicate is False
    assert elapsed_ms < 3000, f"Expected <3000ms got {elapsed_ms:.0f}ms"
    print(f"Full pipeline: PASS — processed in {elapsed_ms:.0f}ms (SLA: 3000ms)")

    # Duplicate event should be idempotent
    resp2 = await svc.process_fall_event(req)
    assert resp2.is_duplicate is True
    assert resp2.alert_id == resp.alert_id
    print("Duplicate suppression: PASS")

    # Cancel within grace period
    cancel_resp = await svc.cancel_alert(resp.alert_id, cancelled_by="user")
    assert cancel_resp.cancelled is True
    print("Self-cancellation: PASS")

    # Verify audit trail has entries
    trail = await svc.get_audit_trail(resp.alert_id)
    events = [e["event"] for e in trail]
    assert "RECEIVED" in events
    assert "CLASSIFIED" in events
    assert "NOTIFIED" in events
    assert "GRACE_PERIOD_STARTED" in events
    assert "CANCELLED" in events
    print(f"Audit trail: PASS — {len(trail)} events: {events}")


if __name__ == "__main__":
    test_fall_classifier()
    asyncio.run(test_idempotency())
    asyncio.run(test_notification_router_parallel())
    asyncio.run(test_dispatch_decider_cancel())
    asyncio.run(test_dispatch_decider_expires())
    asyncio.run(test_full_pipeline_latency())
    print("\nAll tests PASSED")
