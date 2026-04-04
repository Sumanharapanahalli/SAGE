"""
SAGE Framework — Agent MessageBus
===================================
Structured inter-agent messaging for build orchestrator waves.

Agents in different waves communicate through topics (broadcast) or
point-to-point messages (direct). The bus produces a markdown digest
injectable into any agent's context window.

Inspired by open-multi-agent's MessageBus pattern, adapted for
SAGE's wave-based execution model.

Thread-safe. In-memory per build run (not persistent).
"""

import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("MessageBus")


class MessageBus:
    """Lightweight pub/sub + point-to-point message bus for agent coordination.

    Usage in build orchestrator:
        bus = MessageBus()
        # Agent A publishes to topic
        bus.publish("arch_agent", "architecture", {"stack": "Python+FastAPI"})
        # Agent B reads topic
        messages = bus.read("architecture")
        # Agent A sends direct message to Agent B
        bus.send("arch_agent", "fw_agent", {"interface": "SPI"})
        # Agent B checks inbox
        inbox = bus.inbox("fw_agent")
        # Inject summary into next wave context
        summary = bus.get_summary()
    """

    def __init__(self):
        self._topics: Dict[str, List[Dict]] = {}
        self._inboxes: Dict[str, List[Dict]] = {}
        self._lock = threading.Lock()

    def publish(self, sender: str, topic: str, data: Any) -> None:
        """Broadcast a message to a topic."""
        msg = {
            "sender": sender,
            "topic": topic,
            "data": data,
            "timestamp": time.time(),
        }
        with self._lock:
            self._topics.setdefault(topic, []).append(msg)

    def read(self, topic: str) -> List[Dict]:
        """Read all messages on a topic."""
        with self._lock:
            return list(self._topics.get(topic, []))

    def send(self, sender: str, recipient: str, data: Any) -> None:
        """Send a point-to-point message to a specific agent."""
        msg = {
            "sender": sender,
            "recipient": recipient,
            "data": data,
            "timestamp": time.time(),
        }
        with self._lock:
            self._inboxes.setdefault(recipient, []).append(msg)

    def inbox(self, agent_id: str) -> List[Dict]:
        """Read all direct messages for an agent."""
        with self._lock:
            return list(self._inboxes.get(agent_id, []))

    def get_summary(self) -> str:
        """Produce a markdown digest of all messages for context injection.

        Returns a compact summary grouped by topic, suitable for injecting
        into an agent's context window.
        """
        with self._lock:
            if not self._topics:
                return ""

            lines = ["## Agent Communication Summary\n"]
            for topic, messages in self._topics.items():
                lines.append(f"### {topic}")
                for msg in messages:
                    sender = msg["sender"]
                    data = msg["data"]
                    if isinstance(data, dict):
                        data_str = ", ".join(f"{k}={v}" for k, v in data.items())
                    else:
                        data_str = str(data)
                    lines.append(f"- **{sender}**: {data_str}")
                lines.append("")

            return "\n".join(lines)

    def clear(self) -> None:
        """Clear all messages (used between build runs)."""
        with self._lock:
            self._topics.clear()
            self._inboxes.clear()

    def topic_count(self) -> int:
        """Return number of active topics."""
        with self._lock:
            return len(self._topics)

    def message_count(self) -> int:
        """Return total number of messages across all topics and inboxes."""
        with self._lock:
            topic_msgs = sum(len(msgs) for msgs in self._topics.values())
            inbox_msgs = sum(len(msgs) for msgs in self._inboxes.values())
            return topic_msgs + inbox_msgs
