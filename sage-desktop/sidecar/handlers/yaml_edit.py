"""Handler for reading and writing the three solution YAML files.

Phase 3b — YAML authoring. The user drives the edit themselves from the
desktop UI: this is a direct read/write (no proposal) because the user's
own explicit action is what triggers the write, not an agent. Law 1
(agents propose / humans decide) is preserved — this path never
originates from an agent.

Module vars wired at startup by ``app._wire_handlers``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml as _yaml

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError

_ALLOWED = {"project", "prompts", "tasks"}

_solution_path: Optional[Path] = None
_solution_name: Optional[str] = None


def _require_solution() -> Path:
    if _solution_path is None:
        raise RpcError(
            RPC_SIDECAR_ERROR,
            "No solution is active — pass --solution-path or switch solutions first.",
        )
    return _solution_path


def _require_file(params: Any) -> str:
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    name = params.get("file")
    if name not in _ALLOWED:
        raise RpcError(
            RPC_INVALID_PARAMS,
            f"file must be one of: {sorted(_ALLOWED)}",
        )
    return name


def read(params: Any) -> dict:
    name = _require_file(params)
    base = _require_solution()
    path = base / f"{name}.yaml"
    if not path.is_file():
        raise RpcError(
            RPC_INVALID_PARAMS,
            f"{name}.yaml not found under '{base}'",
        )
    content = path.read_text(encoding="utf-8")
    return {
        "file": name,
        "solution": _solution_name or "",
        "content": content,
        "path": str(path),
    }


def write(params: Any) -> dict:
    name = _require_file(params)
    base = _require_solution()
    content = params.get("content")  # type: ignore[union-attr]
    if not isinstance(content, str):
        raise RpcError(RPC_INVALID_PARAMS, "'content' must be a string")
    try:
        _yaml.safe_load(content)
    except _yaml.YAMLError as e:
        raise RpcError(RPC_INVALID_PARAMS, f"Invalid YAML: {e}") from e

    path = base / f"{name}.yaml"
    path.write_text(content, encoding="utf-8")
    return {
        "file": name,
        "solution": _solution_name or "",
        "path": str(path),
        "bytes": len(content.encode("utf-8")),
    }
