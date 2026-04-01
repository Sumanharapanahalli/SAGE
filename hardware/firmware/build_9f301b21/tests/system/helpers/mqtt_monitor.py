"""mqtt_monitor.py — Thread-based MQTT subscriber for staging alert monitoring.

Subscribes to guardian/+/alerts and guardian/+/telemetry topics on the staging
broker and provides blocking wait_for() primitives used by system tests.

IEC 62304 traceability: STS-SYS-001 (MQTT end-to-end alert delivery)
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import paho.mqtt.client as mqtt

log = logging.getLogger(__name__)


@dataclass
class MQTTMessage:
    """Captured MQTT message with receive timestamp."""
    topic: str
    payload: Dict[str, Any]
    received_at: float = field(default_factory=time.monotonic)

    @property
    def age_ms(self) -> float:
        return (time.monotonic() - self.received_at) * 1000.0


class MQTTMonitor:
    """Thread-safe MQTT subscriber that collects messages for test assertions."""

    SUBSCRIBE_TOPICS = [
        ("guardian/+/alerts",    1),
        ("guardian/+/telemetry", 0),
        ("guardian/+/ack",       1),
        ("guardian/+/ota/status",1),
        ("guardian/+/geofence",  1),
    ]

    def __init__(
        self,
        host: str,
        port: int = 1883,
        device_id: str = "test_device_001",
        username: Optional[str] = None,
        password: Optional[str] = None,
        connect_timeout: float = 10.0,
    ) -> None:
        self._host = host
        self._port = port
        self._device_id = device_id
        self._connect_timeout = connect_timeout
        self._messages: List[MQTTMessage] = []
        self._lock = threading.Lock()
        self._connected_event = threading.Event()
        self._client = mqtt.Client(client_id=f"sage-system-test-{device_id}")
        if username:
            self._client.username_pw_set(username, password)
        self._client.on_connect    = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message    = self._on_message

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Connect and start background loop thread."""
        self._client.connect(self._host, self._port, keepalive=60)
        self._client.loop_start()
        if not self._connected_event.wait(timeout=self._connect_timeout):
            raise TimeoutError(
                f"MQTT broker {self._host}:{self._port} not reachable within "
                f"{self._connect_timeout}s"
            )
        log.info("MQTTMonitor: connected to %s:%d", self._host, self._port)

    def stop(self) -> None:
        """Disconnect and stop background loop."""
        self._client.loop_stop()
        self._client.disconnect()
        log.info("MQTTMonitor: disconnected")

    def __enter__(self) -> "MQTTMonitor":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_connect(self, client: mqtt.Client, userdata: Any,
                    flags: Dict, rc: int) -> None:
        if rc == 0:
            for topic, qos in self.SUBSCRIBE_TOPICS:
                client.subscribe(topic, qos)
                log.debug("MQTTMonitor: subscribed to %s (QoS %d)", topic, qos)
            self._connected_event.set()
        else:
            log.error("MQTTMonitor: connect failed rc=%d", rc)

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int) -> None:
        if rc != 0:
            log.warning("MQTTMonitor: unexpected disconnect rc=%d", rc)
        self._connected_event.clear()

    def _on_message(self, client: mqtt.Client, userdata: Any,
                    msg: mqtt.MQTTMessage) -> None:
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {"raw": msg.payload.decode("utf-8", errors="replace")}
        captured = MQTTMessage(topic=msg.topic, payload=payload)
        with self._lock:
            self._messages.append(captured)
        log.debug("MQTTMonitor: msg topic=%s payload=%r", msg.topic, payload)

    # ── Query helpers ─────────────────────────────────────────────────────────

    def clear(self) -> None:
        """Discard all buffered messages (call before each test scenario)."""
        with self._lock:
            self._messages.clear()

    def all_messages(self) -> List[MQTTMessage]:
        with self._lock:
            return list(self._messages)

    def wait_for(
        self,
        predicate: Callable[[MQTTMessage], bool],
        timeout: float,
        poll_interval: float = 0.1,
    ) -> Optional[MQTTMessage]:
        """Block until a matching message arrives or timeout elapses.

        Returns the first matching MQTTMessage, or None on timeout.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                for msg in self._messages:
                    if predicate(msg):
                        return msg
            time.sleep(poll_interval)
        return None

    def count_matching(
        self,
        predicate: Callable[[MQTTMessage], bool],
    ) -> int:
        """Return count of messages matching predicate in current buffer."""
        with self._lock:
            return sum(1 for m in self._messages if predicate(m))

    def wait_for_topic(
        self,
        topic_fragment: str,
        timeout: float,
    ) -> Optional[MQTTMessage]:
        return self.wait_for(
            lambda m: topic_fragment in m.topic,
            timeout=timeout,
        )

    def is_connected(self) -> bool:
        return self._connected_event.is_set()

    def wait_reconnect(self, timeout: float) -> bool:
        """Wait for reconnection after an outage. Returns True if reconnected."""
        return self._connected_event.wait(timeout=timeout)
