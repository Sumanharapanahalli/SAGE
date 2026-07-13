"""Handlers for solution listing, inspection, and removal.

The sidecar is a single-solution process. ``solutions.list`` gives the UI
the roster of switchable targets; ``solutions.get_current`` echoes the
values wired at spawn time so the UI can refresh without re-handshaking.

``solutions.remove`` deregisters a solution. Solutions are *tenants*
(SOUL.md) — a tenant's directory holds the operator's own YAML, tests and
tools, so the default mode never deletes anything: it moves the directory
into ``<solutions_dir>/.archive/<name>-<utc>``, which ``list_solutions``
skips (dotdir) and a human can restore with a single ``mv``. An actual
on-disk delete is opt-in (``mode="delete"``) and requires the caller to
echo the solution name back in ``confirm``; the UI gates it behind a typed
confirmation. Both modes refuse anything that is not a direct child of the
resolved solutions dir, and refuse the currently-active solution (unload
it first — the running process holds its ``.sage/`` SQLite files open).

Removal is framework control, not an agent proposal: it is the operator's
own action and executes immediately (SOUL.md Law 1).
"""
from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError

logger = logging.getLogger(__name__)

# Wired by app._wire_handlers
_sage_root: Optional[Path] = None
_current_name: str = ""
_current_path: Optional[Path] = None
_list_fn = None  # filled by app.py with src.core.project_loader.list_solutions

_ARCHIVE_DIRNAME = ".archive"


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


def _solutions_root() -> Path:
    """Resolve the solutions dir exactly as ``project_loader.list_solutions``
    does: ``SAGE_SOLUTIONS_DIR`` when set, else ``<sage_root>/solutions``."""
    override = os.environ.get("SAGE_SOLUTIONS_DIR", "")
    if override:
        root = Path(override)
    elif _sage_root is not None:
        root = _sage_root / "solutions"
    else:
        raise RpcError(RPC_SIDECAR_ERROR, "solutions dir is not resolvable")
    if not root.is_dir():
        raise RpcError(RPC_SIDECAR_ERROR, f"solutions dir does not exist: {root}")
    return root.resolve()


def _is_solution_dir(p: Path) -> bool:
    # Same validity rule as project_loader.list_solutions.
    return (p / "project.yaml").is_file() or (p / "SKILL.md").is_file()


def _resolve_target(name: str) -> Path:
    """Validate ``name`` and resolve it to a directory that is provably a
    direct child of the solutions dir and provably a solution."""
    if not isinstance(name, str) or not name.strip():
        raise RpcError(RPC_INVALID_PARAMS, "'name' must be a non-empty string")
    # A solution name is a single path component. Anything with a separator,
    # a parent ref, a drive letter, or a leading dot is rejected outright —
    # before any filesystem call.
    if name != Path(name).name or name in (".", "..") or name.startswith("."):
        raise RpcError(RPC_INVALID_PARAMS, f"invalid solution name: {name!r}")
    if os.sep in name or (os.altsep and os.altsep in name) or "/" in name or "\\" in name:
        raise RpcError(RPC_INVALID_PARAMS, f"invalid solution name: {name!r}")

    root = _solutions_root()
    target = (root / name).resolve()
    # Containment: the resolved target must sit directly inside the resolved
    # solutions root. Defeats symlinks and any traversal that slipped through.
    if target.parent != root:
        raise RpcError(
            RPC_INVALID_PARAMS,
            f"refusing to touch a path outside the solutions dir: {target}",
        )
    if not target.is_dir():
        raise RpcError(RPC_INVALID_PARAMS, f"no such solution: {name}")
    if not _is_solution_dir(target):
        raise RpcError(
            RPC_INVALID_PARAMS,
            f"not a solution directory (no project.yaml or SKILL.md): {name}",
        )
    if _current_name and name == _current_name:
        raise RpcError(
            RPC_INVALID_PARAMS,
            f"'{name}' is the active solution — unload it first",
        )
    return target


def remove(params: Any) -> dict:
    """Deregister a solution.

    params:
      name    (str, required)  solution name, a single path component
      mode    (str, optional)  "archive" (default) | "delete"
      confirm (str, required for mode="delete") must equal ``name``
    """
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")

    name = params.get("name")
    mode = params.get("mode", "archive")
    if mode not in ("archive", "delete"):
        raise RpcError(RPC_INVALID_PARAMS, "'mode' must be 'archive' or 'delete'")

    target = _resolve_target(name)

    if mode == "delete":
        confirm = params.get("confirm")
        if confirm != name:
            raise RpcError(
                RPC_INVALID_PARAMS,
                "'confirm' must exactly equal the solution name to delete it",
            )
        try:
            shutil.rmtree(target)
        except Exception as e:  # noqa: BLE001
            raise RpcError(RPC_SIDECAR_ERROR, f"delete failed: {e}") from e
        logger.warning("solution deleted from disk: %s", target)
        return {"name": name, "mode": "delete", "path": str(target)}

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_dir = target.parent / _ARCHIVE_DIRNAME
    dest = archive_dir / f"{name}-{stamp}"
    try:
        archive_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(target), str(dest))
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"archive failed: {e}") from e
    logger.info("solution archived: %s -> %s", target, dest)
    return {
        "name": name,
        "mode": "archive",
        "path": str(target),
        "archived_to": str(dest),
    }
