"""
fall_classifier.py — FallClassifierAgent

Classifies incoming device events by severity and determines grace period duration.
No external I/O: pure deterministic logic on sensor payload → fast enough for 3s SLA.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class FallSeverity(str, Enum):
    CONFIRMED_FALL = "CONFIRMED_FALL"
    SOS_BUTTON = "SOS_BUTTON"
    POSSIBLE_FALL = "POSSIBLE_FALL"
    FALSE_ALARM = "FALSE_ALARM"


@dataclass
class FallEventInput:
    event_id: str
    device_id: str
    user_id: str
    event_type: str                          # fall_detected | sos_button | impact
    accelerometer_data: Optional[dict] = None
    gyroscope_data: Optional[dict] = None
    impact_force_g: Optional[float] = None
    button_pressed: bool = False
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


@dataclass
class AlertClassification:
    event_id: str
    device_id: str
    user_id: str
    severity: FallSeverity
    confidence: float                        # 0.0–1.0
    requires_immediate_dispatch: bool
    grace_period_seconds: int
    reasoning: str
    classified_at: float = field(default_factory=time.time)


class FallClassifierAgent:
    """
    Rule-based fall classifier.

    Severity ladder:
      SOS_BUTTON     → explicit user distress signal (30 s grace)
      CONFIRMED_FALL → high-impact + no post-fall recovery (60 s grace)
      POSSIBLE_FALL  → moderate impact or ambiguous recovery (90 s grace)
      FALSE_ALARM    → low impact / quick recovery → no notification
    """

    # g-force thresholds
    IMPACT_HIGH: float = 3.0       # hard fall
    IMPACT_MODERATE: float = 1.8   # possible fall
    IMPACT_LOW: float = 1.0        # likely noise

    def classify(self, event: FallEventInput) -> AlertClassification:
        logger.info(
            "FallClassifier: classifying event=%s type=%s device=%s impact=%.2fg",
            event.event_id,
            event.event_type,
            event.device_id,
            event.impact_force_g or 0.0,
        )

        if event.button_pressed or event.event_type == "sos_button":
            return self._classify_sos(event)
        return self._classify_fall(event)

    # ── private helpers ─────────────────────────────────────────────────────

    def _classify_sos(self, event: FallEventInput) -> AlertClassification:
        return AlertClassification(
            event_id=event.event_id,
            device_id=event.device_id,
            user_id=event.user_id,
            severity=FallSeverity.SOS_BUTTON,
            confidence=1.0,
            requires_immediate_dispatch=True,
            grace_period_seconds=30,
            reasoning="SOS button explicitly pressed by user.",
        )

    def _classify_fall(self, event: FallEventInput) -> AlertClassification:
        impact = event.impact_force_g or 0.0
        recovered = self._check_recovery(event)

        if impact >= self.IMPACT_HIGH and not recovered:
            confidence = min(0.97, 0.70 + (impact - self.IMPACT_HIGH) * 0.05)
            return AlertClassification(
                event_id=event.event_id,
                device_id=event.device_id,
                user_id=event.user_id,
                severity=FallSeverity.CONFIRMED_FALL,
                confidence=round(confidence, 3),
                requires_immediate_dispatch=True,
                grace_period_seconds=60,
                reasoning=(
                    f"High-impact fall ({impact:.1f}g) with no post-fall recovery detected."
                ),
            )

        if impact >= self.IMPACT_MODERATE:
            return AlertClassification(
                event_id=event.event_id,
                device_id=event.device_id,
                user_id=event.user_id,
                severity=FallSeverity.POSSIBLE_FALL,
                confidence=0.55,
                requires_immediate_dispatch=False,
                grace_period_seconds=90,
                reasoning=(
                    f"Moderate-impact event ({impact:.1f}g). Recovery status ambiguous."
                ),
            )

        return AlertClassification(
            event_id=event.event_id,
            device_id=event.device_id,
            user_id=event.user_id,
            severity=FallSeverity.FALSE_ALARM,
            confidence=0.85,
            requires_immediate_dispatch=False,
            grace_period_seconds=0,
            reasoning=f"Low-impact event ({impact:.1f}g) — classified as false alarm.",
        )

    def _check_recovery(self, event: FallEventInput) -> bool:
        """
        Inspect the post-fall accelerometer window for upright-recovery motion.
        post_fall_window_rms > 0.3 → user moved after impact (possible self-recovery).
        """
        if not event.accelerometer_data:
            return False
        post_rms = event.accelerometer_data.get("post_fall_window_rms", 0.0)
        return float(post_rms) > 0.3
