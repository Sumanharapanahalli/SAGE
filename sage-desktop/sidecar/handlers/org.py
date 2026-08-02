"""Handler for the SAGE_ROOT-level org.yaml.

Unlike per-solution files (constitution.yaml, project.yaml/...), org.yaml
lives above any single solution: ``<solutions_dir>/org.yaml`` — mirroring
``src/interface/api.py``'s ``_get_org_yaml_path()``, which resolves relative
to the solutions dir.

``_solutions_dir()`` honours ``SAGE_SOLUTIONS_DIR`` (exported by
``app._bootstrap_env`` before any ``src.`` import, and settable directly),
falling back to ``<sage_root>/solutions``. That matters beyond org.yaml:
routes and parents are written into each solution's OWN project.yaml, so
without the override a solution mounted outside the framework checkout would
have its edits written to a different path than the rest of the app reads.

Operator-driven edits bypass the proposal queue by the same rationale as
Phase 3b YAML authoring / Phase 5b Constitution editing: the human editing
identity fields in the desktop UI is the human's own action, not an agent
proposal. No audit logging here either, matching yaml_edit.py's precedent
(the web API's ``PUT /org`` does audit-log, but the local YAML-authoring
handlers on desktop do not).

``_sage_root`` is wired at startup by ``app._wire_handlers`` — the same
repo-root value already computed there for ``solutions._sage_root``.

Supports viewing the enriched org state, editing identity fields
(name/mission/vision/core_values), reload, and CRUD over knowledge channels,
cross-team routes and solution parents.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, List, Optional

import yaml as _yaml

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError

# Wired by app._wire_handlers to the same repo root as solutions._sage_root.
_sage_root: Optional[Path] = None


def _require_sage_root() -> Path:
    if _sage_root is None:
        raise RpcError(
            RPC_SIDECAR_ERROR,
            "org handlers are not wired (SAGE_ROOT unresolved) — "
            "set SAGE_ROOT or launch the sidecar from a SAGE checkout.",
        )
    return _sage_root


def _solutions_dir() -> Path:
    """Where solutions live: ``SAGE_SOLUTIONS_DIR`` when set, else
    ``<sage_root>/solutions``.

    Either/or, not additive — the framework's own resolution semantics.
    Checked before ``_require_sage_root()`` so an externally-mounted solutions
    dir works even when the repo root is unresolved.
    """
    env = os.environ.get("SAGE_SOLUTIONS_DIR")
    if env:
        return Path(env)
    return _require_sage_root() / "solutions"


def _org_yaml_path() -> Path:
    return _solutions_dir() / "org.yaml"


def _write_org_yaml(data: dict) -> None:
    path = _org_yaml_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            _yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    except OSError as e:
        raise RpcError(RPC_SIDECAR_ERROR, f"failed to write org.yaml: {e}") from e


def _require_name(params: Any, key: str) -> str:
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RpcError(RPC_INVALID_PARAMS, f"'{key}' is required")
    return value.strip()


def _project_yaml_path(solution: str) -> Path:
    """Resolve <solutions_dir>/<solution>/project.yaml, refusing escapes.

    ``solution`` arrives from the UI and becomes a path segment, so a name
    like ``../../etc`` would otherwise write outside the solutions tree.
    """
    root = _solutions_dir().resolve()
    target = (root / solution).resolve()
    if target != root and root not in target.parents:
        raise RpcError(RPC_INVALID_PARAMS, f"invalid solution name: {solution}")
    path = target / "project.yaml"
    if not path.is_file():
        raise RpcError(RPC_INVALID_PARAMS, f"solution '{solution}' not found")
    return path


def _read_project_yaml(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as f:
            return _yaml.safe_load(f) or {}
    except _yaml.YAMLError as e:
        raise RpcError(RPC_INVALID_PARAMS, f"{path.name} is not valid YAML: {e}") from e
    except OSError as e:
        raise RpcError(RPC_SIDECAR_ERROR, f"could not read {path.name}: {e}") from e


def _write_project_yaml(path: Path, data: dict) -> None:
    try:
        with path.open("w", encoding="utf-8") as f:
            _yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    except OSError as e:
        raise RpcError(RPC_SIDECAR_ERROR, f"could not write {path.name}: {e}") from e


def _reload_org_loader() -> None:
    """Best-effort: the cached org graph is stale after any of these writes."""
    try:
        from src.core.org_loader import reload_org_loader

        reload_org_loader()
    except Exception:  # noqa: BLE001 — a stale cache must not fail the write
        pass


def _read_org_yaml() -> dict:
    path = _org_yaml_path()
    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return _yaml.safe_load(f) or {}
    except _yaml.YAMLError as e:
        raise RpcError(RPC_SIDECAR_ERROR, f"failed to parse org.yaml: {e}") from e


def get(params: Any) -> dict:
    if params is not None and not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")

    data = _read_org_yaml()
    org_section = data.get("org") if isinstance(data.get("org"), dict) else {}

    routes: List[dict] = []
    try:
        from src.core.org_loader import OrgLoader

        ol = OrgLoader(str(_solutions_dir()))
        routes = ol.get_all_routes()
    except Exception:  # noqa: BLE001 — routes are best-effort enrichment
        routes = []

    return {"org": org_section, "routes": routes}


def update(params: Any) -> dict:
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")

    name = params.get("name")
    mission = params.get("mission")
    vision = params.get("vision")
    core_values = params.get("core_values")

    for field, value in (("name", name), ("mission", mission), ("vision", vision)):
        if value is not None and not isinstance(value, str):
            raise RpcError(RPC_INVALID_PARAMS, f"'{field}' must be a string")
    if core_values is not None:
        if not isinstance(core_values, list) or not all(
            isinstance(v, str) for v in core_values
        ):
            raise RpcError(
                RPC_INVALID_PARAMS, "'core_values' must be a list of strings"
            )

    path = _org_yaml_path()
    existing = _read_org_yaml()
    if not isinstance(existing.get("org"), dict):
        existing["org"] = {}
    org_section = existing["org"]

    if name is not None:
        org_section["name"] = name
    if mission is not None:
        org_section["mission"] = mission
    if vision is not None:
        org_section["vision"] = vision
    if core_values is not None:
        org_section["core_values"] = core_values

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            _yaml.dump(existing, f, default_flow_style=False, allow_unicode=True)
    except OSError as e:
        raise RpcError(RPC_SIDECAR_ERROR, f"failed to write org.yaml: {e}") from e

    return {"status": "saved", "org": org_section}


def reload(params: Any) -> dict:
    if params is not None and not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    try:
        from src.core.org_loader import reload_org_loader

        reload_org_loader()
    except Exception:  # noqa: BLE001 — reload is best-effort; get() always re-reads disk
        pass
    return {"status": "reloaded"}


# ---------- knowledge channels (org.yaml) ----------


def _require_str_list(params: dict, key: str) -> list:
    value = params.get(key) or []
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        raise RpcError(RPC_INVALID_PARAMS, f"'{key}' must be a list of strings")
    return value


def channel_create(params: Any) -> dict:
    """Create or replace a knowledge channel."""
    name = _require_name(params, "name")
    producers = _require_str_list(params, "producers")
    consumers = _require_str_list(params, "consumers")

    data = _read_org_yaml()
    if not isinstance(data.get("org"), dict):
        data["org"] = {}
    channels = data["org"].setdefault("knowledge_channels", {})
    if not isinstance(channels, dict):
        channels = {}
        data["org"]["knowledge_channels"] = channels
    channels[name] = {"producers": producers, "consumers": consumers}

    _write_org_yaml(data)
    _reload_org_loader()
    return {"status": "created", "channel": name}


def channel_delete(params: Any) -> dict:
    name = _require_name(params, "name")

    data = _read_org_yaml()
    channels = data.get("org", {}).get("knowledge_channels", {})
    if not isinstance(channels, dict) or name not in channels:
        raise RpcError(RPC_INVALID_PARAMS, f"channel '{name}' not found")
    del channels[name]

    _write_org_yaml(data)
    _reload_org_loader()
    return {"status": "deleted", "channel": name}


# ---------- cross-team routes (per-solution project.yaml) ----------


def route_add(params: Any) -> dict:
    """Route tasks from one solution to another. Idempotent."""
    solution = _require_name(params, "solution")
    target = _require_name(params, "target")

    path = _project_yaml_path(solution)
    project = _read_project_yaml(path)
    routes = project.get("cross_team_routes") or []
    if not isinstance(routes, list):
        routes = []
    # Re-adding an existing target is a no-op rather than a duplicate entry.
    if not any(isinstance(r, dict) and r.get("target") == target for r in routes):
        routes.append({"target": target})
    project["cross_team_routes"] = routes

    _write_project_yaml(path, project)
    _reload_org_loader()
    return {"status": "added", "solution": solution, "target": target}


def route_delete(params: Any) -> dict:
    solution = _require_name(params, "solution")
    target = _require_name(params, "target")

    path = _project_yaml_path(solution)
    project = _read_project_yaml(path)
    routes = project.get("cross_team_routes") or []
    project["cross_team_routes"] = [
        r
        for r in routes
        if not (isinstance(r, dict) and r.get("target") == target)
    ]

    _write_project_yaml(path, project)
    _reload_org_loader()
    return {"status": "removed", "solution": solution, "target": target}


# ---------- solution parent (per-solution project.yaml) ----------


def solution_set_parent(params: Any) -> dict:
    """Place a solution under a parent in the org tree."""
    solution = _require_name(params, "solution")
    parent = _require_name(params, "parent")

    path = _project_yaml_path(solution)
    project = _read_project_yaml(path)
    project["parent"] = parent

    _write_project_yaml(path, project)
    _reload_org_loader()
    return {"status": "added", "solution": solution, "parent": parent}


def solution_clear_parent(params: Any) -> dict:
    """Detach a solution from its parent. A no-op when it has none."""
    solution = _require_name(params, "solution")

    path = _project_yaml_path(solution)
    project = _read_project_yaml(path)
    project.pop("parent", None)

    _write_project_yaml(path, project)
    _reload_org_loader()
    return {"status": "removed", "solution": solution}
