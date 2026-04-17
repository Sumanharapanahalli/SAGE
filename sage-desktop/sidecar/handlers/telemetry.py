"""Opt-in telemetry with a strict PII allowlist.

Disabled by default. The frontend Settings page toggles it on; until
that happens, `record` is a no-op. Even when enabled we *never* send
raw event payloads — every field is filtered through ``_ALLOWED_FIELDS``
so only non-identifying values reach the local JSONL buffer.

The buffer lives at ``<config_dir>/telemetry.jsonl`` and is consumed by
a future uploader (not yet implemented — Phase 4.8 only ships the
collection side; shipping the uploader without the consent UI would
violate the opt-in guarantee).
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Optional

LOGGER = logging.getLogger(__name__)

# Per-launch session id. Generated once at import; never persisted.
# Rebinds per process, so two runs of the same user see two values.
_SESSION_ID = str(uuid.uuid4())

# Fields that may appear in event payloads. Anything else is dropped.
# Keep this list conservative — adding a key here is a privacy decision.
_ALLOWED_FIELDS = frozenset(
    {
        "event",        # event name itself (e.g. "approval.decided")
        "kind",         # high-level category
        "status",       # e.g. "approved" / "rejected"
        "action_type",  # proposal action_type
        "route",        # UI route name (no query string)
        "duration_ms",  # timings
        "count",        # aggregate counts
        "ok",           # bool success flag
        "error_kind",   # DesktopError kind (no detail)
    }
)

# Event names we actually care about. Any other event name is dropped
# before it hits the allowlist — belt-and-suspenders.
_ALLOWED_EVENTS = frozenset(
    {
        "approval.decided",
        "build.started",
        "build.completed",
        "solution.switched",
        "onboarding.generated",
        "update.checked",
        "update.installed",
        "llm.switched",
    }
)


class TelemetryConfig:
    """Persisted opt-in state. Writes to ``<dir>/telemetry.json``."""

    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir
        self.config_path = config_dir / "telemetry.json"
        self.buffer_path = config_dir / "telemetry.jsonl"
        self._enabled = False
        self._anon_id: Optional[str] = None
        self._load()

    def _load(self) -> None:
        if not self.config_path.exists():
            return
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
            self._enabled = bool(data.get("enabled", False))
            self._anon_id = data.get("anon_id")
        except Exception as e:  # noqa: BLE001
            LOGGER.warning("telemetry config unreadable: %s", e)

    def _save(self) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(
                {"enabled": self._enabled, "anon_id": self._anon_id},
                indent=2,
            ),
            encoding="utf-8",
        )

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def anon_id(self) -> Optional[str]:
        return self._anon_id

    def set_enabled(self, enabled: bool) -> None:
        if enabled and self._anon_id is None:
            # Generate a random UUID4 — not derived from anything
            # machine-identifying, so it cannot be correlated back.
            self._anon_id = str(uuid.uuid4())
        self._enabled = bool(enabled)
        self._save()
        # Opt-out wipes any buffered events immediately (PRIVACY.md §5.1)
        if not self._enabled and self.buffer_path.exists():
            try:
                self.buffer_path.write_text("", encoding="utf-8")
            except Exception as e:  # noqa: BLE001
                LOGGER.warning("telemetry buffer wipe failed: %s", e)


def filter_payload(event: str, payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Return a sanitised payload, or None if the event itself is disallowed.

    The returned dict contains only keys from ``_ALLOWED_FIELDS``. All
    other keys are silently dropped — callers should not rely on them
    round-tripping.
    """
    if event not in _ALLOWED_EVENTS:
        return None
    clean = {"event": event}
    for k, v in (payload or {}).items():
        if k in _ALLOWED_FIELDS:
            clean[k] = v
    return clean


def record(config: TelemetryConfig, event: str, payload: dict[str, Any]) -> bool:
    """Append a filtered event to the local buffer. Returns True if written."""
    if not config.enabled:
        return False
    clean = filter_payload(event, payload)
    if clean is None:
        return False
    clean["ts"] = int(time.time())
    clean["session_id"] = _SESSION_ID
    if config.anon_id:
        clean["anon_id"] = config.anon_id
    try:
        config.config_dir.mkdir(parents=True, exist_ok=True)
        with config.buffer_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(clean) + "\n")
        return True
    except Exception as e:  # noqa: BLE001
        LOGGER.warning("telemetry write failed: %s", e)
        return False


# ── RPC handlers ──────────────────────────────────────────────────────────

_config: Optional[TelemetryConfig] = None


def _default_config_dir() -> Path:
    """Platform-appropriate per-user config dir. Avoids per-solution scoping
    so the opt-in follows the user across solutions."""
    base = os.environ.get("SAGE_DESKTOP_CONFIG_DIR")
    if base:
        return Path(base)
    if os.name == "nt":
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(appdata) / "sage-desktop"
    return Path.home() / ".config" / "sage-desktop"


def _cfg() -> TelemetryConfig:
    global _config
    if _config is None:
        _config = TelemetryConfig(_default_config_dir())
    return _config


def get_status(params: dict) -> dict:
    cfg = _cfg()
    return {
        "enabled": cfg.enabled,
        "anon_id": cfg.anon_id,
        "allowed_events": sorted(_ALLOWED_EVENTS),
        "allowed_fields": sorted(_ALLOWED_FIELDS),
    }


def set_enabled(params: dict) -> dict:
    enabled = bool(params.get("enabled", False))
    cfg = _cfg()
    cfg.set_enabled(enabled)
    return {"enabled": cfg.enabled, "anon_id": cfg.anon_id}
