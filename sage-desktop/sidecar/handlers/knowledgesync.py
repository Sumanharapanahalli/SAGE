"""Knowledge Sync handler — bulk-import a directory into the vector store.

Wraps ``src.core.knowledge_syncer.sync_directory`` so an operator can
bootstrap or refresh the active solution's knowledge base from its own
files instead of hand-typing entries one at a time (the desktop Knowledge
page previously only exposed single-entry add).

SOLUTION SCOPING (load-bearing): ``sync_directory(root, vector_store=None)``
falls back to the framework-GLOBAL ``src.memory.vector_store.vector_memory``
singleton, which binds its collection at import time. We always pass the
sidecar's solution-scoped ``VectorMemory`` — the very instance
``handlers.knowledge`` already holds — so documents can never land in another
solution's collection. ``knowledge._vm`` is read at call time (not import
time) so wiring order in ``app._wire_handlers`` is irrelevant.

Tier: framework control, not an agent proposal. The operator pointing the
importer at their own files is the operator's own action (same rationale as
knowledge.add / yaml.write), so it executes immediately. Agent-proposed
knowledge mutations continue to flow through the proposal queue unchanged.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError

logger = logging.getLogger(__name__)

# Injected by app._wire_handlers.
_solution_name: Optional[str] = None
_solution_path: Optional[Path] = None
_logger: Optional[Any] = None  # src.memory.audit_logger.AuditLogger


def _require_vm() -> Any:
    """The solution-scoped VectorMemory owned by handlers.knowledge."""
    import handlers.knowledge as knowledge

    vm = getattr(knowledge, "_vm", None)
    if vm is None:
        raise RpcError(
            RPC_SIDECAR_ERROR,
            "knowledge sync is not wired (VectorMemory import failed or no solution active)",
        )
    return vm


def _resolve_root(params: dict) -> str:
    directory = params.get("directory")
    if directory is not None and not isinstance(directory, str):
        raise RpcError(RPC_INVALID_PARAMS, "'directory' must be a string")
    if isinstance(directory, str) and directory.strip():
        root = directory.strip()
    elif _solution_path is not None:
        root = str(_solution_path)
    else:
        raise RpcError(
            RPC_INVALID_PARAMS,
            "no 'directory' given and no active solution to default to",
        )
    root = os.path.abspath(os.path.expanduser(root))
    if not os.path.isdir(root):
        raise RpcError(RPC_INVALID_PARAMS, f"directory not found: {root}")
    return root


def _scan(root: str) -> dict:
    """Pre-walk *root* to report what the import will and will not cover.

    ``sync_directory`` only returns a chunk count, so the per-file accounting
    the operator needs (what was skipped, what failed to read) is computed here
    — reusing the syncer's own constants rather than restating its policy.
    """
    from src.core.knowledge_syncer import (
        _MAX_FILE_BYTES,
        _SKIP_DIRS,
        _TEXT_EXTENSIONS,
    )

    files_scanned = 0
    files_indexed = 0
    skipped = 0
    errors: list[dict] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")
        ]
        for fname in filenames:
            files_scanned += 1
            fpath = os.path.join(dirpath, fname)
            rel = os.path.relpath(fpath, root).replace("\\", "/")
            ext = os.path.splitext(fname)[1].lower()
            if ext not in _TEXT_EXTENSIONS:
                skipped += 1
                continue
            try:
                if os.path.getsize(fpath) > _MAX_FILE_BYTES:
                    skipped += 1
                    continue
                with open(fpath, encoding="utf-8", errors="ignore") as fh:
                    if not fh.read().strip():
                        skipped += 1
                        continue
            except OSError as exc:
                errors.append({"file": rel, "error": str(exc)})
                continue
            files_indexed += 1

    return {
        "files_scanned": files_scanned,
        "files_indexed": files_indexed,
        "skipped": skipped,
        "errors": errors,
    }


def _audit(root: str, result: dict) -> None:
    if _logger is None:
        logger.warning("knowledge.sync: no audit logger wired — sync not recorded")
        return
    try:
        _logger.log_event(
            actor="operator",
            action_type="knowledge_sync",
            input_context=f"knowledge.sync directory={root}",
            output_content=(
                f"{result['chunks_added']} chunks imported from "
                f"{result['files_indexed']} of {result['files_scanned']} files"
            ),
            metadata={
                "directory": root,
                "solution": _solution_name or "unknown",
                "files_scanned": result["files_scanned"],
                "files_indexed": result["files_indexed"],
                "chunks_added": result["chunks_added"],
                "skipped": result["skipped"],
                "error_count": len(result["errors"]),
                "source": "desktop",
            },
        )
    except Exception as e:  # noqa: BLE001 — an audit failure must not lose the import
        logger.warning("knowledge.sync: audit log failed: %s", e)


# ── RPC methods ────────────────────────────────────────────────────────────

def sync(params: Any) -> dict:
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")

    root = _resolve_root(params)
    vm = _require_vm()

    from src.core.knowledge_syncer import sync_directory

    stats = _scan(root)
    try:
        # vector_store is NOT optional here — see module docstring.
        chunks_added = int(sync_directory(root, vector_store=vm))
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"knowledge.sync failed: {e}") from e

    result = {
        "directory": root,
        "solution": _solution_name or "unknown",
        "chunks_added": chunks_added,
        **stats,
    }
    _audit(root, result)
    return result
