"""Tests for the monitor handler.

Mirrors GET /monitor/status and GET /scheduler/status from src/interface/api.py:

- monitor.status wraps MonitorAgent.get_status() — MonitorAgent is already a
  ready-made module-level singleton (like compliance_flags.py, no wiring
  needed), so the handler imports it directly at call time. Never raises: on
  any failure it degrades to a "not running" shape instead of propagating an
  RpcError.
- monitor.scheduler_status lazily constructs + starts a TaskScheduler exactly
  like api.py's `_get_task_scheduler()`, caches it at module scope, then
  forwards `.status()`. Never raises: mirrors the web endpoint's exact
  graceful-degradation shape `{"running": False, "error": str(exc)}`.

Both subsystems are legitimately-often-off (pollers usually aren't started
standalone in the desktop sidecar), so a construction/call failure means
"not active", not a wire-protocol error.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from handlers import monitor


@pytest.fixture(autouse=True)
def _reset_scheduler_cache():
    """Every test starts with a clean lazy-singleton cache."""
    monitor._scheduler = None
    yield
    monitor._scheduler = None


# ---------- status (MonitorAgent) ----------


def test_status_returns_monitor_agent_get_status_happy_path(monkeypatch):
    fake_monitor = SimpleNamespace(
        get_status=lambda: {
            "running": True,
            "active_threads": ["MonitorAgent-Teams"],
            "thread_count": 1,
            "seen_messages": 3,
            "seen_issues": 0,
            "teams_configured": True,
            "metabase_configured": False,
            "gitlab_configured": False,
        }
    )
    monkeypatch.setattr("src.agents.monitor.monitor_agent", fake_monitor)
    out = monitor.status({})
    assert out["running"] is True
    assert out["thread_count"] == 1
    assert out["active_threads"] == ["MonitorAgent-Teams"]
    assert out["teams_configured"] is True


def test_status_degrades_gracefully_when_get_status_raises(monkeypatch):
    def boom():
        raise RuntimeError("monitor thread crashed")

    fake_monitor = SimpleNamespace(get_status=boom)
    monkeypatch.setattr("src.agents.monitor.monitor_agent", fake_monitor)

    out = monitor.status({})
    assert out["running"] is False
    assert "monitor thread crashed" in out["error"]


def test_status_degrades_gracefully_when_import_fails(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "src.agents.monitor":
            raise ImportError("no module named src.agents.monitor")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    out = monitor.status({})
    assert out["running"] is False
    assert "error" in out


# ---------- scheduler_status (TaskScheduler) ----------


def test_scheduler_status_returns_cached_scheduler_status_happy_path(monkeypatch):
    fake_sched = SimpleNamespace(
        status=lambda: {
            "running": True,
            "scheduled_count": 2,
            "next_check_in_seconds": 30,
        }
    )
    monkeypatch.setattr(monitor, "_scheduler", fake_sched)

    out = monitor.scheduler_status({})
    assert out["running"] is True
    assert out["scheduled_count"] == 2
    assert out["next_check_in_seconds"] == 30


def test_scheduler_status_lazily_constructs_and_starts_on_first_call(monkeypatch):
    started = []

    class FakeScheduler:
        def __init__(self, queue_manager=None, project_config=None):
            self.queue_manager = queue_manager
            self.project_config = project_config

        def start(self):
            started.append(True)

        def status(self):
            return {"running": True, "scheduled_count": 0, "next_check_in_seconds": 30}

    monkeypatch.setattr("src.core.task_scheduler.TaskScheduler", FakeScheduler)
    monkeypatch.setattr(
        "src.core.queue_manager.task_queue", SimpleNamespace(), raising=False
    )
    monkeypatch.setattr(
        "src.core.project_loader.project_config", SimpleNamespace(), raising=False
    )

    assert monitor._scheduler is None
    out = monitor.scheduler_status({})
    assert out["running"] is True
    assert started == [True]
    assert monitor._scheduler is not None  # now cached

    # Second call reuses the cached instance — no second construction/start.
    monitor.scheduler_status({})
    assert started == [True]


def test_scheduler_status_degrades_gracefully_when_construction_raises(monkeypatch):
    class BoomScheduler:
        def __init__(self, **_kw):
            raise RuntimeError("no project loaded")

    monkeypatch.setattr("src.core.task_scheduler.TaskScheduler", BoomScheduler)
    monkeypatch.setattr(
        "src.core.queue_manager.task_queue", SimpleNamespace(), raising=False
    )
    monkeypatch.setattr(
        "src.core.project_loader.project_config", SimpleNamespace(), raising=False
    )

    out = monitor.scheduler_status({})
    assert out["running"] is False
    assert "no project loaded" in out["error"]
    assert monitor._scheduler is None  # not cached — safe to retry on next call


def test_scheduler_status_degrades_gracefully_when_status_call_raises(monkeypatch):
    def boom():
        raise RuntimeError("scheduler thread died")

    fake_sched = SimpleNamespace(status=boom)
    monkeypatch.setattr(monitor, "_scheduler", fake_sched)

    out = monitor.scheduler_status({})
    assert out["running"] is False
    assert "scheduler thread died" in out["error"]


def test_scheduler_status_requires_no_params():
    """params dict is accepted but unused — must not raise on empty dict."""
    monkeypatch_target = SimpleNamespace(
        status=lambda: {
            "running": False,
            "scheduled_count": 0,
            "next_check_in_seconds": 30,
        }
    )
    monitor._scheduler = monkeypatch_target
    out = monitor.scheduler_status({})
    assert isinstance(out, dict)
