"""Monitor handler — exposes src.agents.monitor and src.core.task_scheduler
status to the desktop.

Mirrors GET /monitor/status and GET /scheduler/status from src/interface/api.py.

Like compliance.py, ``status()`` needs no startup wiring: MonitorAgent is
already a ready-made module-level singleton, so the handler imports it
directly at call time rather than reading an injected module-level variable.

``scheduler_status()`` lazily constructs + starts a TaskScheduler on first
call and caches it here, exactly mirroring api.py's module-level
``_task_scheduler`` lazy singleton (``_get_task_scheduler()``).

Both subsystems are legitimately-often-off in the desktop sidecar (the
pollers/scheduler are not started standalone). A construction or call
failure therefore means "not active", not a wire-protocol error — neither
method ever raises; both degrade to a "not running" shape, matching the web
API's exact `{"running": False, "error": str(exc)}` graceful-degradation
behavior for /scheduler/status.
"""
from __future__ import annotations

# Cached TaskScheduler singleton, built lazily on first call.
_scheduler = None


def status(params: dict) -> dict:
    """Wraps MonitorAgent.get_status(). Never raises — on any failure,
    returns a shape indicating the monitor is unavailable so the desktop
    page can render a clean "not active" state instead of an error banner.
    """
    try:
        from src.agents.monitor import monitor_agent
        return monitor_agent.get_status()
    except Exception as e:  # noqa: BLE001
        return {"running": False, "error": str(e)}


def scheduler_status(params: dict) -> dict:
    """Wraps TaskScheduler.status(), lazily constructing + starting the
    scheduler on first call exactly like api.py's `_get_task_scheduler()`.
    Never raises — mirrors the web API's exact graceful-degradation shape
    on any construction/call failure: {"running": False, "error": str(exc)}.
    """
    global _scheduler
    try:
        if _scheduler is None:
            from src.core.task_scheduler import TaskScheduler
            from src.core.queue_manager import task_queue
            from src.core.project_loader import project_config
            sched = TaskScheduler(queue_manager=task_queue, project_config=project_config)
            sched.start()
            _scheduler = sched
        return _scheduler.status()
    except Exception as e:  # noqa: BLE001
        return {"running": False, "error": str(e)}
