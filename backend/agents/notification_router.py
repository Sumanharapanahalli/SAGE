"""
notification_router.py — NotificationRouterAgent

Routes an alert to ALL three channels (push/SMS/email) concurrently via asyncio.gather().
Partial failures are tolerated: one successful channel satisfies the 3-second SLA.

Swap stub clients for real SDKs:
  FCMClient   → firebase-admin   (pip install firebase-admin)
  TwilioClient → twilio          (pip install twilio)
  SendGridClient → sendgrid      (pip install sendgrid)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from backend.agents.fall_classifier import AlertClassification, FallSeverity

logger = logging.getLogger(__name__)


# ── Contact model ────────────────────────────────────────────────────────────

@dataclass
class CaregiverContact:
    caregiver_id: str
    name: str
    fcm_token: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    priority: int = 1  # 1 = primary caregiver


# ── Result models ────────────────────────────────────────────────────────────

@dataclass
class NotificationResult:
    channel: str           # "push" | "sms" | "email"
    caregiver_id: str
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    sent_at: float = field(default_factory=time.time)


@dataclass
class RoutingDecision:
    alert_id: str
    event_id: str
    channels_used: list[str]
    results: list[NotificationResult]
    primary_notification_sent: bool
    notification_latency_ms: float
    routed_at: float = field(default_factory=time.time)


# ── Notification client stubs ────────────────────────────────────────────────

class FCMClient:
    """
    Firebase Cloud Messaging client.
    Replace body with: firebase_admin.messaging.send(Message(...))
    """

    async def send(
        self, token: str, title: str, body: str, data: dict
    ) -> str:
        logger.info(
            "FCM → token=%.8s… title=%r data_keys=%s",
            token,
            title,
            list(data.keys()),
        )
        await asyncio.sleep(0.05)  # simulate ~50 ms network
        return f"fcm_{int(time.time() * 1000)}"


class TwilioClient:
    """
    Twilio SMS client.
    Replace body with: client.messages.create(to=to, from_=FROM_NUMBER, body=body)
    """

    async def send_sms(self, to: str, body: str) -> str:
        logger.info("SMS → %s: %.60r", to, body)
        await asyncio.sleep(0.08)  # simulate ~80 ms
        return f"SM{int(time.time() * 1000)}"


class SendGridClient:
    """
    SendGrid email client.
    Replace body with: sg.send(Mail(from_email=..., to_emails=to, ...))
    """

    async def send_email(self, to: str, subject: str, html_body: str) -> str:
        logger.info("Email → %s subject=%r", to, subject)
        await asyncio.sleep(0.12)  # simulate ~120 ms
        return f"sg_{int(time.time() * 1000)}"


# ── Agent ────────────────────────────────────────────────────────────────────

class NotificationRouterAgent:
    """
    Sends alert to push + SMS + email channels in parallel.
    All tasks are launched with asyncio.gather(return_exceptions=True) so a
    single channel failure never blocks or delays the other channels.
    """

    def __init__(
        self,
        fcm: Optional[FCMClient] = None,
        twilio: Optional[TwilioClient] = None,
        sendgrid: Optional[SendGridClient] = None,
    ) -> None:
        self.fcm = fcm or FCMClient()
        self.twilio = twilio or TwilioClient()
        self.sendgrid = sendgrid or SendGridClient()

    async def notify_all(
        self,
        alert_id: str,
        classification: AlertClassification,
        caregivers: list[CaregiverContact],
    ) -> RoutingDecision:
        start = time.monotonic()
        logger.info(
            "NotificationRouter: routing alert=%s severity=%s to %d caregiver(s)",
            alert_id,
            classification.severity,
            len(caregivers),
        )

        title, body = self._build_message(classification)
        data_payload = {
            "alert_id": alert_id,
            "event_id": classification.event_id,
            "severity": classification.severity,
            "user_id": classification.user_id,
        }

        # Build one coroutine per channel per caregiver
        tasks: list[asyncio.coroutine] = []
        for cg in caregivers:
            if cg.fcm_token:
                tasks.append(self._send_push(cg, title, body, data_payload))
            if cg.phone_number:
                tasks.append(self._send_sms(cg, title, body, classification))
            if cg.email:
                tasks.append(self._send_email(cg, title, body, classification))

        if not tasks:
            logger.warning("NotificationRouter: no channels available for alert %s", alert_id)

        raw = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[NotificationResult] = []
        for item in raw:
            if isinstance(item, Exception):
                logger.error("NotificationRouter: channel error — %s", item)
                results.append(
                    NotificationResult(
                        channel="unknown",
                        caregiver_id="unknown",
                        success=False,
                        error=str(item),
                    )
                )
            else:
                results.append(item)

        latency_ms = (time.monotonic() - start) * 1000
        primary_sent = any(r.success for r in results)
        successes = sum(1 for r in results if r.success)

        logger.info(
            "NotificationRouter: alert=%s — %d/%d channels succeeded in %.0f ms",
            alert_id,
            successes,
            len(results),
            latency_ms,
        )

        return RoutingDecision(
            alert_id=alert_id,
            event_id=classification.event_id,
            channels_used=[r.channel for r in results],
            results=results,
            primary_notification_sent=primary_sent,
            notification_latency_ms=latency_ms,
        )

    # ── message builders ─────────────────────────────────────────────────────

    def _build_message(
        self, classification: AlertClassification
    ) -> tuple[str, str]:
        sev = classification.severity
        grace = classification.grace_period_seconds
        if sev == FallSeverity.SOS_BUTTON:
            return (
                "SOS Emergency Activated",
                (
                    f"Your loved one pressed the SOS button. "
                    f"Emergency services will be called in {grace}s unless cancelled."
                ),
            )
        if sev == FallSeverity.CONFIRMED_FALL:
            return (
                "Fall Detected",
                (
                    f"A fall has been confirmed ({classification.confidence:.0%} confidence). "
                    f"Emergency services in {grace}s unless user cancels."
                ),
            )
        return (
            "Possible Fall Alert",
            "A possible fall was detected. Please check on your loved one.",
        )

    # ── per-channel send helpers ─────────────────────────────────────────────

    async def _send_push(
        self,
        cg: CaregiverContact,
        title: str,
        body: str,
        data: dict,
    ) -> NotificationResult:
        try:
            msg_id = await self.fcm.send(cg.fcm_token, title, body, data)
            return NotificationResult(
                channel="push", caregiver_id=cg.caregiver_id,
                success=True, message_id=msg_id,
            )
        except Exception as exc:
            logger.error("FCM failed caregiver=%s: %s", cg.caregiver_id, exc)
            return NotificationResult(
                channel="push", caregiver_id=cg.caregiver_id,
                success=False, error=str(exc),
            )

    async def _send_sms(
        self,
        cg: CaregiverContact,
        title: str,
        body: str,
        classification: AlertClassification,
    ) -> NotificationResult:
        try:
            sms_body = f"{title}: {body}"
            msg_id = await self.twilio.send_sms(cg.phone_number, sms_body)
            return NotificationResult(
                channel="sms", caregiver_id=cg.caregiver_id,
                success=True, message_id=msg_id,
            )
        except Exception as exc:
            logger.error("SMS failed caregiver=%s: %s", cg.caregiver_id, exc)
            return NotificationResult(
                channel="sms", caregiver_id=cg.caregiver_id,
                success=False, error=str(exc),
            )

    async def _send_email(
        self,
        cg: CaregiverContact,
        title: str,
        body: str,
        classification: AlertClassification,
    ) -> NotificationResult:
        try:
            html = (
                f"<h2>{title}</h2>"
                f"<p>{body}</p>"
                f"<hr>"
                f"<p><strong>Alert ID:</strong> {classification.event_id}</p>"
                f"<p><strong>Severity:</strong> {classification.severity}</p>"
                f"<p><strong>Confidence:</strong> {classification.confidence:.0%}</p>"
                f"<p><em>{classification.reasoning}</em></p>"
            )
            msg_id = await self.sendgrid.send_email(cg.email, title, html)
            return NotificationResult(
                channel="email", caregiver_id=cg.caregiver_id,
                success=True, message_id=msg_id,
            )
        except Exception as exc:
            logger.error("Email failed caregiver=%s: %s", cg.caregiver_id, exc)
            return NotificationResult(
                channel="email", caregiver_id=cg.caregiver_id,
                success=False, error=str(exc),
            )
