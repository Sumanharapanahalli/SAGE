"""Handlers for solution listing and current-solution inspection.

The sidecar is a single-solution process. ``solutions.list`` gives the UI
the roster of switchable targets; ``solutions.get_current`` echoes the
values wired at spawn time so the UI can refresh without re-handshaking.
"""
from pathlib import Path
from typing import Any, Optional

# Wired by app._wire_handlers
_sage_root: Optional[Path] = None
_current_name: str = ""
_current_path: Optional[Path] = None
_list_fn = None  # filled by app.py with src.core.project_loader.list_solutions


def list_solutions(_params: Any):
    if _sage_root is None or _list_fn is None:
        return []
    return _list_fn(_sage_root)


def get_current(_params: Any):
    if not _current_name:
        return None
    return {
        "name": _current_name,
        "path": str(_current_path) if _current_path else "",
    }
