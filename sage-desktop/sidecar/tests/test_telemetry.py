"""Tests for the opt-in telemetry allowlist filter."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_H = Path(__file__).resolve().parents[1]
if str(_H) not in sys.path:
    sys.path.insert(0, str(_H))

import handlers.telemetry as tel  # noqa: E402


@pytest.fixture
def cfg(tmp_path: Path) -> tel.TelemetryConfig:
    return tel.TelemetryConfig(tmp_path)


def test_default_state_is_disabled(cfg: tel.TelemetryConfig) -> None:
    assert cfg.enabled is False
    assert cfg.anon_id is None


def test_opt_in_generates_anon_id(cfg: tel.TelemetryConfig) -> None:
    cfg.set_enabled(True)
    assert cfg.enabled is True
    assert cfg.anon_id is not None
    assert len(cfg.anon_id) == 36  # UUID4 canonical form


def test_opt_in_persists_across_instances(tmp_path: Path) -> None:
    a = tel.TelemetryConfig(tmp_path)
    a.set_enabled(True)
    anon = a.anon_id

    b = tel.TelemetryConfig(tmp_path)
    assert b.enabled is True
    assert b.anon_id == anon


def test_opt_out_keeps_anon_id_but_disables(tmp_path: Path) -> None:
    cfg = tel.TelemetryConfig(tmp_path)
    cfg.set_enabled(True)
    anon = cfg.anon_id
    cfg.set_enabled(False)
    assert cfg.enabled is False
    # anon_id is retained so re-opt-in doesn't look like a new user
    assert cfg.anon_id == anon


def test_record_noop_when_disabled(cfg: tel.TelemetryConfig) -> None:
    assert tel.record(cfg, "approval.decided", {"status": "approved"}) is False
    assert not cfg.buffer_path.exists()


def test_record_drops_disallowed_events(cfg: tel.TelemetryConfig) -> None:
    cfg.set_enabled(True)
    assert tel.record(cfg, "not.an.event", {"status": "approved"}) is False
    assert not cfg.buffer_path.exists()


def test_record_strips_unapproved_fields(cfg: tel.TelemetryConfig) -> None:
    cfg.set_enabled(True)
    ok = tel.record(
        cfg,
        "approval.decided",
        {
            "status": "approved",
            "action_type": "yaml_edit",
            # The following MUST NOT survive the filter:
            "user_email": "leak@example.com",
            "trace_id": "proposal-42",
            "raw_prompt": "secret plaintext",
        },
    )
    assert ok is True

    lines = cfg.buffer_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])

    assert event["event"] == "approval.decided"
    assert event["status"] == "approved"
    assert event["action_type"] == "yaml_edit"
    assert event["anon_id"] == cfg.anon_id
    assert "ts" in event

    # Privacy guarantee — assert leaks are absent
    for banned in ("user_email", "trace_id", "raw_prompt"):
        assert banned not in event, f"{banned} leaked into telemetry payload"


def test_filter_payload_returns_none_for_banned_event() -> None:
    assert tel.filter_payload("evil.event", {"status": "x"}) is None


def test_filter_payload_keeps_only_allowed_keys() -> None:
    clean = tel.filter_payload(
        "build.started",
        {"kind": "build", "solution_name": "medtech", "duration_ms": 120},
    )
    assert clean == {"event": "build.started", "kind": "build", "duration_ms": 120}


def test_get_status_rpc_reports_disabled_by_default(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SAGE_DESKTOP_CONFIG_DIR", str(tmp_path))
    # Reset the module-level singleton so it re-reads the env var
    tel._config = None
    resp = tel.get_status({})
    assert resp["enabled"] is False
    assert resp["anon_id"] is None
    assert "approval.decided" in resp["allowed_events"]
    assert "user_email" not in resp["allowed_fields"]


def test_set_enabled_rpc_round_trips(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SAGE_DESKTOP_CONFIG_DIR", str(tmp_path))
    tel._config = None
    resp = tel.set_enabled({"enabled": True})
    assert resp["enabled"] is True
    assert resp["anon_id"] is not None

    resp2 = tel.set_enabled({"enabled": False})
    assert resp2["enabled"] is False
    # Opt-in anon_id is retained per contract
    assert resp2["anon_id"] == resp["anon_id"]


def test_record_stamps_session_id(cfg: tel.TelemetryConfig) -> None:
    cfg.set_enabled(True)
    assert tel.record(cfg, "build.started", {"kind": "build"}) is True
    event = json.loads(cfg.buffer_path.read_text(encoding="utf-8").strip())
    assert "session_id" in event
    assert len(event["session_id"]) == 36  # UUID4 canonical form


def test_session_id_is_stable_within_process(cfg: tel.TelemetryConfig) -> None:
    """Per-launch session id — same value for every record() call in this process."""
    cfg.set_enabled(True)
    tel.record(cfg, "build.started", {"kind": "build"})
    tel.record(cfg, "build.completed", {"status": "completed"})
    lines = cfg.buffer_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    e1, e2 = json.loads(lines[0]), json.loads(lines[1])
    assert e1["session_id"] == e2["session_id"]


def test_session_id_not_persisted_to_disk(cfg: tel.TelemetryConfig) -> None:
    """session_id only lives in the event buffer, never in config.json."""
    cfg.set_enabled(True)
    tel.record(cfg, "build.started", {"kind": "build"})
    saved_config = json.loads(cfg.config_path.read_text(encoding="utf-8"))
    assert "session_id" not in saved_config


def test_opt_out_clears_event_buffer(cfg: tel.TelemetryConfig) -> None:
    """Opting out wipes any buffered events on disk (PRIVACY.md §5.1 contract)."""
    cfg.set_enabled(True)
    tel.record(cfg, "approval.decided", {"status": "approved"})
    assert cfg.buffer_path.exists()
    assert cfg.buffer_path.stat().st_size > 0

    cfg.set_enabled(False)
    # Buffer is cleared — file may not exist, or exists and is empty
    if cfg.buffer_path.exists():
        assert cfg.buffer_path.read_text(encoding="utf-8") == ""
