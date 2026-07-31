"""Handler for solution onboarding via the SAGE onboarding wizard.

Thin wrapper over ``src.core.onboarding.generate_solution``. The framework
function does the heavy lifting (LLM generation, YAML validation, disk
write); we validate inputs, forward kwargs, and map framework exceptions
to JSON-RPC error codes the UI already understands.

Error mapping:
    RuntimeError (LLM unavailable) → ``RPC_SIDECAR_ERROR``  (-32000)
    ValueError   (bad YAML / name) → ``RPC_INVALID_PARAMS`` (-32602)
"""

import json
import logging
import os
import re
from typing import Any, Optional

import yaml as _yaml

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError

logger = logging.getLogger("sidecar.onboarding")

# Wired at startup by app._wire_handlers (None when the framework import fails)
_generate_fn: Optional[Any] = None
_llm: Optional[Any] = None
_logger: Optional[Any] = None

# Tests point this at a tmp dir. None -> resolve from src.core.onboarding, which
# already honors SAGE_SOLUTIONS_DIR (set by app._bootstrap_env before any src.
# import), so there is exactly one place that decides where solutions live.
_solutions_dir_override: Optional[str] = None

# Loaded once from config/org_templates.yaml. None = not yet loaded.
_org_templates_cache: Optional[list] = None

# Mirrors api.py's _SAFE_SOLUTION_NAME.
_SAFE_SOLUTION_NAME = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

# The LLM picks these key names, so treat them as a whitelist rather than
# trusting them as paths.
_TRIAD = ("project.yaml", "prompts.yaml", "tasks.yaml")


def generate(params: Any):
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")

    description = params.get("description")
    solution_name = params.get("solution_name")
    if not isinstance(description, str) or not description.strip():
        raise RpcError(RPC_INVALID_PARAMS, "description is required")
    if not isinstance(solution_name, str) or not solution_name.strip():
        raise RpcError(RPC_INVALID_PARAMS, "solution_name is required")

    org_context = params.get("org_context") or ""
    if not isinstance(org_context, str):
        raise RpcError(RPC_INVALID_PARAMS, "'org_context' must be a string")

    if _generate_fn is None:
        raise RpcError(
            RPC_SIDECAR_ERROR,
            "onboarding.generate is not wired (SAGE import failed)",
        )

    try:
        return _generate_fn(
            description=description,
            solution_name=solution_name,
            compliance_standards=params.get("compliance_standards") or [],
            integrations=params.get("integrations") or [],
            parent_solution=params.get("parent_solution") or "",
            # How a chosen org template reaches generation: the framework
            # documents org_context as "prepended to description before LLM
            # generation", so the template's role brief steers the drafted
            # prompts.yaml without any framework change.
            org_context=org_context,
        )
    except ValueError as e:
        raise RpcError(RPC_INVALID_PARAMS, f"invalid onboarding input: {e}") from e
    except RuntimeError as e:
        raise RpcError(RPC_SIDECAR_ERROR, f"LLM unavailable: {e}") from e


# ---------- import an existing codebase ----------


def _require_str(params: Any, key: str) -> str:
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RpcError(RPC_INVALID_PARAMS, f"missing or empty '{key}'")
    return value


def _solutions_dir() -> str:
    if _solutions_dir_override is not None:
        return _solutions_dir_override
    from src.core import onboarding as _framework_onboarding

    return _framework_onboarding._SOLUTIONS_DIR


def _org_context() -> str:
    """Mission/vision/values from org.yaml, injected so a generated solution
    inherits the operator's company context. Best-effort — never fatal."""
    try:
        from handlers import org as _org

        data = _org._read_org_yaml()
        section = data.get("org", {}) if isinstance(data, dict) else {}
        if not section.get("mission"):
            return ""
        parts = [f"Mission: {section['mission']}"]
        if section.get("vision"):
            parts.append(f"Vision: {section['vision']}")
        if section.get("core_values"):
            values = "\n  - ".join(section["core_values"])
            parts.append(f"Core values:\n  - {values}")
        return "\n".join(parts)
    except Exception:  # noqa: BLE001
        logger.debug("org.yaml context unavailable", exc_info=True)
        return ""


def _parse_generated_files(raw: str) -> tuple[dict, dict]:
    """Parse the LLM's JSON reply into the YAML triad plus a summary.

    Mirrors api.py's _parse_generated_files: strip a ``` fence if present, and
    fall back to treating the whole reply as project.yaml rather than failing —
    a half-usable draft the operator can edit beats a hard error.
    """
    text = raw.strip()
    fence = re.search(r"```(?:\w+)?\n([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()

    fallback = {
        "project.yaml": text,
        "prompts.yaml": "roles: {}",
        "tasks.yaml": "task_types: []",
    }
    try:
        files = json.loads(text)
        if not isinstance(files, dict):
            files = fallback
    except (ValueError, TypeError):
        files = fallback

    summary: dict = {
        "name": "",
        "description": "",
        "task_types": [],
        "compliance_standards": [],
        "integrations": [],
    }
    try:
        project = _yaml.safe_load(files.get("project.yaml", "")) or {}
        if isinstance(project, dict):
            summary["name"] = project.get("name", "")
            summary["description"] = project.get("description", "")
            summary["compliance_standards"] = project.get("compliance_standards", [])
            summary["integrations"] = project.get("integrations", [])
        tasks = _yaml.safe_load(files.get("tasks.yaml", "")) or {}
        if isinstance(tasks, dict):
            for task_type in tasks.get("task_types", []) or []:
                if isinstance(task_type, dict):
                    summary["task_types"].append(
                        {
                            "name": task_type.get("name", ""),
                            "description": task_type.get("description", ""),
                        }
                    )
    except _yaml.YAMLError:
        # A draft with unparseable YAML is still worth returning — the review
        # step is where the operator sees and fixes it.
        logger.debug("generated YAML did not parse for the summary", exc_info=True)

    return files, summary


def _audit(action_type: str, **kw) -> None:
    if _logger is None:
        return
    try:
        _logger.log_event(actor="human_via_onboarding", action_type=action_type, **kw)
    except Exception:  # noqa: BLE001
        logger.warning("could not write %s audit event", action_type, exc_info=True)


def scan_folder(params: Any) -> dict:
    """Scan an existing codebase and draft a solution from it.

    Deliberately writes nothing: the drafts come back for review and
    ``save_solution`` performs the write, so the operator decides.
    """
    folder_path = _require_str(params, "folder_path")
    solution_name = _require_str(params, "solution_name")
    intent = params.get("intent") or ""
    if not isinstance(intent, str):
        raise RpcError(RPC_INVALID_PARAMS, "'intent' must be a string")

    try:
        from src.core.folder_scanner import FolderScanner
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"FolderScanner unavailable: {e}") from e

    try:
        content = FolderScanner().scan(folder_path)
    except FileNotFoundError as e:
        raise RpcError(RPC_INVALID_PARAMS, f"folder not found: {folder_path}") from e
    except OSError as e:
        raise RpcError(RPC_INVALID_PARAMS, f"could not read folder: {e}") from e

    if not content.strip():
        raise RpcError(
            RPC_INVALID_PARAMS, "no readable files found in this folder"
        )

    if _llm is None:
        raise RpcError(RPC_SIDECAR_ERROR, "LLM gateway is not wired")

    system_prompt = (
        "You are a SAGE solution architect. Generate three YAML files for a SAGE "
        "solution: project.yaml, prompts.yaml, and tasks.yaml. Return ONLY a JSON "
        "object with keys 'project.yaml', 'prompts.yaml', 'tasks.yaml' — each value "
        "is the full YAML content as a string. No other text."
    )
    parts = []
    org = _org_context()
    if org:
        parts.append(f"Company context:\n{org}\n")
    parts.append(f"Solution name: {solution_name}")
    if intent:
        parts.append(f"Intent: {intent}")
    parts.append(f"Codebase:\n{content}")

    try:
        # `prompt=`, NOT `user_prompt=`. LLMGateway.generate takes no
        # `user_prompt` parameter and no **kwargs, so the web endpoints this
        # ports (api.py:4081, api.py:4125) raise TypeError on every call and
        # surface it as a misleading 503 "Could not reach the LLM".
        raw = _llm.generate(prompt="\n\n".join(parts), system_prompt=system_prompt)
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"LLM unavailable: {e}") from e

    files, summary = _parse_generated_files(raw or "")

    _audit(
        "ONBOARDING_SCAN",
        input_context=intent,
        output_content=str(files.get("project.yaml", ""))[:2000],
        metadata={"solution_name": solution_name, "folder_path": folder_path},
    )
    return {"solution_name": solution_name, "files": files, "summary": summary}


def save_solution(params: Any) -> dict:
    """Write reviewed YAML drafts to <solutions_dir>/<solution_name>/."""
    solution_name = _require_str(params, "solution_name")
    if not _SAFE_SOLUTION_NAME.match(solution_name):
        raise RpcError(
            RPC_INVALID_PARAMS,
            "solution_name must be 1-64 characters: letters, digits, '_' or '-'",
        )

    files = params.get("files")
    if not isinstance(files, dict) or not files:
        raise RpcError(RPC_INVALID_PARAMS, "'files' must be a non-empty object")

    writable = {
        name: content
        for name, content in files.items()
        if name in _TRIAD and isinstance(content, str)
    }
    if not writable:
        raise RpcError(
            RPC_INVALID_PARAMS,
            f"'files' must contain at least one of: {', '.join(_TRIAD)}",
        )

    root = os.path.realpath(_solutions_dir())
    target = os.path.join(root, solution_name)
    # Defence in depth: the regex already forbids separators and dots, but a
    # symlinked solutions dir could still resolve outside it.
    if not os.path.realpath(target).startswith(root + os.sep):
        raise RpcError(
            RPC_INVALID_PARAMS, "resolved path escapes the solutions directory"
        )

    try:
        os.makedirs(target, exist_ok=True)
        for name, content in writable.items():
            with open(os.path.join(target, name), "w", encoding="utf-8") as f:
                f.write(content)
    except OSError as e:
        raise RpcError(RPC_SIDECAR_ERROR, f"could not write solution: {e}") from e

    _audit(
        "ONBOARDING_COMPLETE",
        input_context=solution_name,
        output_content=str(writable.get("project.yaml", ""))[:2000],
        metadata={"solution_name": solution_name, "path": target},
    )
    return {
        "status": "saved",
        "solution_name": solution_name,
        "path": target,
        "files_written": sorted(writable),
    }


# ---------- org templates ----------


def _org_templates_path() -> str:
    """config/org_templates.yaml at the framework root.

    From sidecar/handlers/onboarding.py that is four levels up:
    handlers -> sidecar -> sage-desktop -> <sage root>.
    """
    root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    return os.path.join(root, "config", "org_templates.yaml")


def org_templates(params: Any = None) -> dict:
    """Pre-built team structures the wizard can start from.

    The templates are DATA in config/org_templates.yaml, outside src/ so the
    framework stays domain-blind (SOUL.md) — adding one is a YAML edit.

    Returns [] rather than raising if the file is missing or unreadable: the
    wizard works fine without a template, so a packaging slip must not take
    onboarding down with it.
    """
    global _org_templates_cache
    if _org_templates_cache is None:
        path = _org_templates_path()
        try:
            with open(path, encoding="utf-8") as f:
                data = _yaml.safe_load(f) or {}
            templates = data.get("templates", [])
            _org_templates_cache = templates if isinstance(templates, list) else []
        except (OSError, _yaml.YAMLError):
            logger.warning("could not load org templates from %s", path, exc_info=True)
            _org_templates_cache = []
    return {"templates": _org_templates_cache}
