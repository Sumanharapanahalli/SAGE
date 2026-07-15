"""Handler for the SAGE_ROOT-level org.yaml.

Unlike per-solution files (constitution.yaml, project.yaml/...), org.yaml
lives above any single solution: ``<sage_root>/solutions/org.yaml`` —
mirrors ``src/interface/api.py``'s ``_get_org_yaml_path()``, which resolves
relative to the solutions dir (``_get_solutions_dir()``, default
``<repo_root>/solutions``). This handler always resolves under
``<sage_root>/solutions`` and does not honour a ``SAGE_SOLUTIONS_DIR``
override — a known gap versus the web API, acceptable for this thin slice
since the desktop sidecar has no equivalent env var wiring today.

Operator-driven edits bypass the proposal queue by the same rationale as
Phase 3b YAML authoring / Phase 5b Constitution editing: the human editing
identity fields in the desktop UI is the human's own action, not an agent
proposal. No audit logging here either, matching yaml_edit.py's precedent
(the web API's ``PUT /org`` does audit-log, but the local YAML-authoring
handlers on desktop do not).

``_sage_root`` is wired at startup by ``app._wire_handlers`` — the same
repo-root value already computed there for ``solutions._sage_root``.

Deliberately out of scope for this pass: channel/solution/route CRUD
(``POST``/``DELETE`` ``/org/channels``, ``/org/solutions``, ``/org/routes``
on the web API). This handler only supports viewing the enriched org state
(including read-only cross-team routes) and editing identity fields
(name/mission/vision/core_values), plus a reload.
"""

from __future__ import annotations

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


def _org_yaml_path() -> Path:
    return _require_sage_root() / "solutions" / "org.yaml"


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

        ol = OrgLoader(str(_require_sage_root() / "solutions"))
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
