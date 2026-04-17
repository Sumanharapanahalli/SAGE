"""Status handler — combined health/LLM/project snapshot for the Status page.

The handler never raises for peripheral failures (LLM provider down,
project not loaded) so the Status page always renders something. Errors
are surfaced inline in the payload instead.
"""
from __future__ import annotations

from typing import Optional

SIDECAR_VERSION = "0.1.0"

# Injected by __main__.py at startup. Tests monkey-patch these.
_project = None  # type: Optional[object]
_store = None  # type: Optional[object]
_llm = None  # type: Optional[object]


def _project_info() -> Optional[dict]:
    if _project is None:
        return None
    try:
        name = getattr(_project, "project_name", None)
        path = getattr(_project, "project_path", None)
        return {"name": name, "path": path}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def _llm_info() -> Optional[dict]:
    if _llm is None:
        return None
    try:
        info = _llm.get_model_info()
        return {
            "provider": info.get("provider"),
            "model": info.get("model"),
        }
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def _pending_count() -> int:
    if _store is None:
        return 0
    try:
        return len(_store.get_pending())
    except Exception:  # noqa: BLE001
        return 0


def get_status(params: dict) -> dict:
    return {
        "health": "ok",
        "sidecar_version": SIDECAR_VERSION,
        "project": _project_info(),
        "llm": _llm_info(),
        "pending_approvals": _pending_count(),
    }
