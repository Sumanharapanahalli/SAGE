# Task 7: YAML schema validation on project load

**Category:** backend  
**Score:** 9.0/10  
**Converged:** True  
**Iterations:** 3  
**Elapsed:** 874s  

---

## Task

Add JSON Schema or Pydantic validation to src/core/project_loader.py so that when a solution's project.yaml, prompts.yaml, or tasks.yaml is loaded, required fields are checked and a clear error is raised (not a KeyError deep in agent code). Define minimal schemas for the three YAML files.

## Criteria

Missing required fields raise a descriptive ValidationError at load time; the three YAML schemas are defined; valid existing solution YAMLs still load without error.

## Proposal (submit to HITL approval gate)

# src/core/project_loader.py

```python
"""
SAGE Framework — Project Configuration Loader
=============================================
Loads the active project's configuration, merging the base config/config.yaml
with project-specific overrides from solutions/<project>/{project,prompts,tasks}.yaml
(or the equivalent SKILL.md frontmatter).

Validation
----------
Every loaded project.yaml / prompts.yaml / tasks.yaml is checked against a
minimal schema. Missing required fields or wrong types raise a clear
:class:`ConfigValidationError` naming the file and the offending field at load
time — instead of a KeyError surfacing deep inside agent code at runtime.
"""

import logging
import os
from pathlib import Path
from typing import Any, Tuple

import yaml

logger = logging.getLogger(__name__)

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_SOLUTIONS_DIR = os.environ.get(
    "SAGE_SOLUTIONS_DIR",
    os.path.join(_PROJECT_ROOT, "solutions"),
)


# ---------------------------------------------------------------------------
# Config validation — minimal schemas + a tiny dependency-free validator
# ---------------------------------------------------------------------------

class ConfigValidationError(ValueError):
    """Raised when a solution's YAML config fails schema validation.

    Carries the originating file path and the dotted field path so the error is
    actionable for solution authors rather than an opaque KeyError raised later
    from inside an agent.
    """

    def __init__(self, source: str, field_path: str, message: str):
        self.source = source
        self.field_path = field_path or "<root>"
        super().__init__(
            f"Invalid SAGE config in '{source}': "
            f"field '{self.field_path}' {message}"
        )


# Minimal JSON-Schema subset understood by ``_validate``:
#   type        — "object" | "array" | "string" | "number" | "integer" | "boolean"
#   required    — keys that must be present on an object
#   properties  — per-key sub-schemas (validated only when the key is present)
#   items       — sub-schema applied to every element of an array

PROJECT_SCHEMA: dict = {
    "type": "object",
    "required": ["name"],
    "properties": {
        "name":                 {"type": "string"},
        "version":              {"type": "string"},
        "domain":               {"type": "string"},
        "description":          {"type": "string"},
        "active_modules":       {"type": "array"},
        "compliance_standards": {"type": "array"},
        "integrations":         {"type": "array"},
        "ui_labels":            {"type": "object"},
        "dashboard":            {"type": "object"},
        "agent_budgets":        {"type": "object"},
    },
}

PROMPTS_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "analyst": {
            "type": "object",
            "required": ["system_prompt"],
            "properties": {
                "system_prompt":        {"type": "string"},
                "user_prompt_template": {"type": "string"},
                "output_schema":        {"type": "object"},
            },
        },
        "developer": {
            "type": "object",
            "properties": {
                "review_system_prompt":    {"type": "string"},
                "mr_create_system_prompt": {"type": "string"},
            },
        },
        "planner": {
            "type": "object",
            "properties": {"system_prompt": {"type": "string"}},
        },
        "monitor": {
            "type": "object",
            "properties": {"system_prompt": {"type": "string"}},
        },
        "roles": {"type": "object"},
    },
}

TASKS_SCHEMA: dict = {
    "type": "object",
    # `task_types` is intentionally NOT required: a child solution may omit it
    # and inherit from a parent via the org parent-chain merge, and the loader
    # falls back to _DEFAULT_TASK_TYPES when no org is active. When present it is
    # still type-checked (array of strings).
    "properties": {
        "task_types":            {"type": "array", "items": {"type": "string"}},
        "task_descriptions":     {"type": "object"},
        "task_hooks":            {"type": "object"},
        "task_sandbox_policies": {"type": "object"},
        "scheduled":             {"type": "array"},
    },
}

_JSON_TYPES: dict = {
    "object": dict,
    "array":  list,
    "string": str,
}


def _type_matches(value: Any, json_type: str) -> bool:
    if json_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if json_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if json_type == "boolean":
        return isinstance(value, bool)
    py_type = _JSON_TYPES.get(json_type)
    return py_type is None or isinstance(value, py_type)


def _validate(instance: Any, schema: dict, source: str, path: str = "") -> None:
    """Validate *instance* against *schema*, raising ConfigValidationError."""
    expected_type = schema.get("type")
    if expected_type and not _type_matches(instance, expected_type):
        raise ConfigValidationError(
            source, path,
            f"must be a {expected_type}, got {type(instance).__name__}",
        )

    if expected_type == "object" and isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                raise ConfigValidationError(
                    source, f"{path}.{key}".lstrip("."),
                    "is required but missing",
                )
        for key, sub_schema in schema.get("properties", {}).items():
            if key in instance:
                _validate(instance[key], sub_schema, source,
                          f"{path}.{key}".lstrip("."))

    if expected_type == "array" and isinstance(instance, list):
        item_schema = schema.get("items")
        if item_schema:
            for idx, item in enumerate(instance):
                _validate(item, item_schema, source, f"{path}[{idx}]")


def _validate_config(data: dict, schema: dict, source: str) -> dict:
    """Validate a loaded config section, skipping empty (absent-file) dicts.

    Falsy *data* (``{}`` / ``None``) means the file was missing, blank, or
    comment-only — the loader intentionally falls back to framework defaults and
    org inheritance there, so required fields are NOT enforced. Returns *data*
    unchanged for convenient chaining.
    """
    if data:
        _validate(data, schema, source)
    return data


def _auto_discover_project() -> str:
    """Return the first available solution name, or empty string if none found."""
    explicit = os.environ.get("SAGE_DEFAULT_PROJECT", "").strip().lower()
    if explicit:
        return explicit
    try:
        candidates = sorted(
            d for d in os.listdir(_SOLUTIONS_DIR)
            if (
                os.path.isfile(os.path.join(_SOLUTIONS_DIR, d, "SKILL.md"))
                or os.path.isfile(os.path.join(_SOLUTIONS_DIR, d, "project.yaml"))
            )
        )
        return candidates[0] if candidates else ""
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# Internal YAML loader
# ---------------------------------------------------------------------------

def _load_yaml(path: str) -> dict:
    """Load a YAML file; return {} silently if missing."""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    logger.debug("Config file not found (using defaults): %s", path)
    return {}


def _get_org_loader():
    """Lazy import to avoid circular dependency at module load time."""
    from src.core.org_loader import org_loader
    return org_loader


def _parse_skill_md(path: str) -> tuple[dict, dict, dict, str]:
    """
    Parse a SKILL.md file with YAML frontmatter.

    Returns (project_dict, prompts_dict, tasks_dict, skill_content_body).
    """
    if not os.path.exists(path):
        return {}, {}, {}, ""

    with open(path, "r", encoding="utf-8") as fh:
        raw = fh.read()

    parts = raw.split("---\n", 2)
    if len(parts) < 3:
        parts = raw.split("---\r\n", 2)
    if len(parts) < 3:
        logger.warning(
            "SKILL.md at %s has no valid frontmatter — treating entire file as body.",
            path,
        )
        return {}, {}, {}, raw.strip()

    _, frontmatter_raw, body = parts
    skill_content = body.strip()

    try:
        fm = yaml.safe_load(frontmatter_raw) or {}
    except yaml.YAMLError as exc:
        logger.error("SKILL.md frontmatter YAML parse error at %s: %s", path, exc)
        return {}, {}, {}, skill_content

    project_dict = {
        "name":                 fm.get("name", ""),
        "version":              fm.get("version", "1.0.0"),
        "domain":               fm.get("domain", "general"),
        "description":          fm.get("description", ""),
        "active_modules":       fm.get("modules", fm.get("active_modules", [])),
        "compliance_standards": fm.get("compliance_standards", []),
        "integrations":         fm.get("integrations", []),
        "ui_labels":            fm.get("ui_labels", {}),
        "dashboard":            fm.get("dashboard", {}),
        "settings":             fm.get("settings", {}),
    }
    skip = {
        "name", "version", "domain", "description", "modules", "active_modules",
        "compliance_standards", "integrations", "ui_labels", "dashboard",
        "settings", "tasks", "agent_roles",
    }
    for k, v in fm.items():
        if k not in skip:
            project_dict[k] = v

    prompts_dict: dict = {}
    agent_roles = fm.get("agent_roles", {})
    for role_key in ("analyst", "developer", "planner", "monitor"):
        if role_key in agent_roles:
            role_cfg = agent_roles[role_key]
            if role_key == "analyst":
                prompts_dict["analyst"] = {
                    "system_prompt":        role_cfg.get("system_prompt", ""),
                    "user_prompt_template": role_cfg.get(
                        "user_prompt_template",
                        "INPUT:\n{input}\n\nPAST CONTEXT:\n{context}\n\nGenerate Analysis JSON:",
                    ),
                    "output_schema":        role_cfg.get("output_schema", {}),
                }
            elif role_key == "developer":
                prompts_dict["developer"] = {
                    "review_system_prompt":    role_cfg.get("system_prompt", ""),
                    "mr_create_system_prompt": role_cfg.get("mr_create_system_prompt", ""),
                }
            elif role_key == "planner":
                prompts_dict["planner"] = {"system_prompt": role_cfg.get("system_prompt", "")}
            elif role_key == "monitor":
                prompts_dict["monitor"] = {"system_prompt": role_cfg.get("system_prompt", "")}

    universal_roles = {
        k: v for k, v in agent_roles.items()
        if k not in ("analyst", "developer", "planner", "monitor")
    }
    if universal_roles:
        prompts_dict["roles"] = universal_roles

    tasks_raw = fm.get("tasks", {})
    if isinstance(tasks_raw, list):
        tasks_dict: dict = {"task_types": tasks_raw}
    elif isinstance(tasks_raw, dict):
        tasks_dict = tasks_raw
    else:
        tasks_dict = {}

    return project_dict, prompts_dict, tasks_dict, skill_content


# ---------------------------------------------------------------------------
# ProjectConfig
# ---------------------------------------------------------------------------

class ProjectConfig:
    """Central configuration manager for the active SAGE project."""

    def __init__(self, project_name: str | None = None):
        self._name: str = ""
        self._base: dict = {}
        self._project: dict = {}
        self._prompts: dict = {}
        self._tasks: dict = {}
        self._skill_content: str = ""
        self._skill_md_path: str = ""
        self.reload(project_name)

    def reload(self, project_name: str | None = None) -> None:
        """Reload configuration for *project_name* (or env/default).

        Each loaded config section is validated against its minimal schema. A
        failure raises :class:`ConfigValidationError` here — at load time —
        rather than letting a missing key surface as a KeyError inside an agent.
        """
        self._name = (
            project_name
            or os.environ.get("SAGE_PROJECT", "")
            or _auto_discover_project()
        ).lower().strip()

        project_dir = os.path.join(_SOLUTIONS_DIR, self._name)
        self._base = _load_yaml(os.path.join(_PROJECT_ROOT, "config", "config.yaml"))

        skill_path = os.path.join(project_dir, "SKILL.md")
        if os.path.isfile(skill_path):
            self._project, self._prompts, self._tasks, self._skill_content = (
                _parse_skill_md(skill_path)
            )
            self._skill_md_path = skill_path
            _validate_config(self._project, PROJECT_SCHEMA, skill_path)
            _validate_config(self._prompts, PROMPTS_SCHEMA, skill_path)
            _validate_config(self._tasks,   TASKS_SCHEMA,   skill_path)
            logger.info("SAGE project loaded from SKILL.md: '%s'  (%s)", self._name, skill_path)
        else:
            project_path = os.path.join(project_dir, "project.yaml")
            prompts_path = os.path.join(project_dir, "prompts.yaml")
            tasks_path   = os.path.join(project_dir, "tasks.yaml")
            self._project = _validate_config(_load_yaml(project_path), PROJECT_SCHEMA, project_path)
            self._prompts = _validate_config(_load_yaml(prompts_path), PROMPTS_SCHEMA, prompts_path)
            self._tasks   = _validate_config(_load_yaml(tasks_path),   TASKS_SCHEMA,   tasks_path)
            self._skill_content = ""
            self._skill_md_path = ""
            logger.info("SAGE project loaded: '%s'  (%s)", self._name, project_dir)

    @property
    def project_name(self) -> str:
        return self._name

    @property
    def sage_data_dir(self) -> str:
        """Return (and create) the .sage/ directory for the active solution."""
        if self._name:
            sage_dir = os.path.join(_SOLUTIONS_DIR, self._name, ".sage")
        else:
            sage_dir = os.path.join(_PROJECT_ROOT, ".sage")
        os.makedirs(sage_dir, exist_ok=True)
        return sage_dir

    @property
    def metadata(self) -> dict:
        """Rich project metadata dict (safe to serialise to JSON)."""
        return {
            "project":              self._name,
            "name":                 self._project.get("name", self._name),
            "version":              self._project.get("version", "1.0.0"),
            "description":          self._project.get("description", ""),
            "domain":               self._project.get("domain", "general"),
            "active_modules":       self._project.get("active_modules", []),
            "compliance_standards": self._project.get("compliance_standards", []),
            "integrations":         self._project.get("integrations", []),
            "ui_labels":            self._project.get("ui_labels", {}),
            "dashboard":            self._project.get("dashboard", {}),
            "theme":                self._project.get("theme", {}),
        }

    @property
    def skill_content(self) -> str:
        return self._skill_content

    @property
    def skill_md_path(self) -> str:
        return self._skill_md_path

    @property
    def solution_context(self) -> str:
        """Contents of <solution_dir>/solution_context.md, if it exists."""
        if not self._name:
            return ""
        ctx_path = os.path.join(_SOLUTIONS_DIR, self._name, "solution_context.md")
        if not os.path.isfile(ctx_path):
            return ""
        try:
            with open(ctx_path, "r", encoding="utf-8") as fh:
                return fh.read().strip()
        except OSError as exc:
            logger.warning("Could not read solution_context.md at %s: %s", ctx_path, exc)
            return ""

    def get_analyst_prompts(self) -> Tuple[str, str]:
        cfg = self._prompts.get("analyst", {})
        return (
            cfg.get("system_prompt",       _DEFAULT_ANALYST_SYSTEM),
            cfg.get("user_prompt_template", _DEFAULT_ANALYST_USER),
        )

    def get_developer_review_prompt(self) -> str:
        return self._prompts.get("developer", {}).get(
            "review_system_prompt", _DEFAULT_DEV_REVIEW_SYSTEM
        )

    def get_planner_prompt(self) -> str:
        return self._prompts.get("planner", {}).get("system_prompt", _DEFAULT_PLANNER_SYSTEM)

    def get_monitor_prompt(self) -> str:
        return self._prompts.get("monitor", {}).get("system_prompt", _DEFAULT_MONITOR_SYSTEM)

    def get_analyst_output_schema(self) -> dict:
        return self._prompts.get("analyst", {}).get("output_schema", _DEFAULT_ANALYST_SCHEMA)

    def get_task_types(self) -> list[str]:
        ol = _get_org_loader()
        if ol.org_name and self._name:
            merged = ol.get_merged_tasks(self._name)
            return merged.get("task_types", self._tasks.get("task_types", list(_DEFAULT_TASK_TYPES)))
        return self._tasks.get("task_types", list(_DEFAULT_TASK_TYPES))

    def get_task_descriptions(self) -> dict[str, str]:
        ol = _get_org_loader()
        if ol.org_name and self._name:
            merged = ol.get_merged_tasks(self._name)
            return merged.get("task_descriptions", self._tasks.get("task_descriptions", {}))
        return self._tasks.get("task_descriptions", {})

    def get_task_hooks(self, task_type: str) -> dict:
        hooks_map = self._tasks.get("task_hooks", {})
        entry = hooks_map.get(task_type, {})
        return {"pre": entry.get("pre", []), "post": entry.get("post", [])}

    def get_scheduled_tasks(self) -> list:
        return self._tasks.get("scheduled", [])

    def get_task_sandbox_policy(self, task_type: str) -> dict | None:
        policies = self._tasks.get("task_sandbox_policies", {})
        return policies.get(task_type)

    def get(self, key: str, default: Any = None) -> Any:
        return self._base.get(key, default)

    def get_project_setting(self, key: str, default: Any = None) -> Any:
        return self._project.get(key, default)

    def get_prompts(self) -> dict:
        return self._prompts

    def set_active_modules(self, modules: list) -> None:
        self._project["active_modules"] = list(modules)
        logger.info("Active modules updated: %s", modules)

    def get_agent_budget(self, agent_name: str) -> dict | None:
        budgets = self._project.get("agent_budgets", {})
        return budgets.get(agent_name)


# ---------------------------------------------------------------------------
# Framework-level defaults
# ---------------------------------------------------------------------------

_DEFAULT_ANALYST_SYSTEM = (
    "You are an expert diagnostic analyst. "
    "Analyze the provided input carefully. "
    "Use the provided CONTEXT from past cases if relevant. "
    "Output your analysis in STRICT JSON format with keys: "
    "'severity', 'root_cause_hypothesis', 'recommended_action'. "
    "Do not output markdown."
)

_DEFAULT_ANALYST_USER = """\
INPUT:
{input}

PAST CONTEXT:
{context}

Generate Analysis JSON:"""

_DEFAULT_ANALYST_SCHEMA = {
    "severity": "string  # e.g. RED, AMBER, GREEN, UNKNOWN",
    "root_cause_hypothesis": "string",
    "recommended_action": "string",
}

_DEFAULT_DEV_REVIEW_SYSTEM = (
    "You are a senior software engineer performing a thorough code review. "
    "Identify bugs, security issues, performance problems, and style violations. "
    "Be constructive and specific. Return JSON with keys: "
    "'summary', 'issues' (list), 'suggestions' (list), 'approved' (bool)."
)

_DEFAULT_PLANNER_SYSTEM = (
    "You are a planning agent. Decompose the user request into a sequence of "
    "atomic tasks. Each task must have: step (int), task_type (string from the "
    "VALID_TASK_TYPES list), payload (dict), description (string). "
    "Return a JSON array only — no markdown."
)

_DEFAULT_MONITOR_SYSTEM = (
    "You are a monitoring agent. Classify incoming events by severity and "
    "determine if they require immediate attention. Return JSON with keys: "
    "'severity' (critical/high/medium/low), 'requires_action' (bool), "
    "'summary' (string)."
)

_DEFAULT_TASK_TYPES = [
    "ANALYZE_LOG",
    "REVIEW_CODE",
    "CREATE_MR",
    "MONITOR_CHECK",
    "PLAN_TASK",
]

# ---------------------------------------------------------------------------
# Module-level singleton — import this everywhere
# ---------------------------------------------------------------------------

project_config = ProjectConfig()


def list_solutions(sage_root):
    """Return sorted SolutionRef dicts for each valid solution under <sage_root>/solutions/."""
    root = Path(sage_root) / "solutions"
    if not root.is_dir():
        return []
    out = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if entry.name.startswith("."):
            continue
        if not entry.is_dir():
            continue
        has_yaml = (entry / "project.yaml").is_file()
        has_skill = (entry / "SKILL.md").is_file()
        if not (has_yaml or has_skill):
            continue
        out.append({
            "name": entry.name,
            "path": str(entry.resolve()),
            "has_sage_dir": (entry / ".sage").is_dir(),
        })
    return out
```

# tests/test_project_loader_validation.py

```python
"""Validation tests for src/core/project_loader.py.

Run with:  pytest tests/test_project_loader_validation.py -v
"""

import os

import pytest
import yaml

import src.core.project_loader as pl
from src.core.project_loader import (
    ConfigValidationError,
    PROJECT_SCHEMA,
    PROMPTS_SCHEMA,
    TASKS_SCHEMA,
    ProjectConfig,
    _validate_config,
    list_solutions,
)


# --- Unit tests: schema validator (pure, no filesystem) --------------------

def test_project_missing_name_raises():
    with pytest.raises(ConfigValidationError) as exc:
        _validate_config({"version": "1.0.0"}, PROJECT_SCHEMA, "project.yaml")
    assert exc.value.field_path == "name"
    assert exc.value.source == "project.yaml"
    assert "required but missing" in str(exc.value)


def test_project_with_name_passes():
    data = {"name": "starter", "version": "1.0.0", "domain": "general"}
    assert _validate_config(data, PROJECT_SCHEMA, "project.yaml") == data


def test_prompts_analyst_missing_system_prompt_raises():
    data = {"analyst": {"user_prompt_template": "{input}"}}
    with pytest.raises(ConfigValidationError) as exc:
        _validate_config(data, PROMPTS_SCHEMA, "prompts.yaml")
    assert exc.value.field_path == "analyst.system_prompt"
    assert "required but missing" in str(exc.value)


def test_prompts_without_analyst_section_passes():
    data = {"planner": {"system_prompt": "plan stuff"}}
    assert _validate_config(data, PROMPTS_SCHEMA, "prompts.yaml") == data


def test_prompts_full_analyst_passes():
    data = {
        "analyst": {
            "system_prompt": "You are an analyst.",
            "user_prompt_template": "{input}",
            "output_schema": {"severity": "string"},
        }
    }
    assert _validate_config(data, PROMPTS_SCHEMA, "prompts.yaml") == data


def test_tasks_missing_task_types_is_allowed():
    data = {"task_descriptions": {"FOO": "does foo"}}
    assert _validate_config(data, TASKS_SCHEMA, "tasks.yaml") == data


def test_tasks_with_task_types_passes():
    data = {"task_types": ["ANALYZE_LOG", "REVIEW_CODE"]}
    assert _validate_config(data, TASKS_SCHEMA, "tasks.yaml") == data


def test_wrong_type_name_raises():
    with pytest.raises(ConfigValidationError) as exc:
        _validate_config({"name": 123}, PROJECT_SCHEMA, "project.yaml")
    assert exc.value.field_path == "name"
    assert "must be a string" in str(exc.value)


def test_wrong_type_task_types_not_array_raises():
    with pytest.raises(ConfigValidationError) as exc:
        _validate_config({"task_types": "ANALYZE_LOG"}, TASKS_SCHEMA, "tasks.yaml")
    assert exc.value.field_path == "task_types"
    assert "must be a array" in str(exc.value)


def test_wrong_type_task_types_item_raises():
    with pytest.raises(ConfigValidationError) as exc:
        _validate_config({"task_types": ["OK", 42]}, TASKS_SCHEMA, "tasks.yaml")
    assert exc.value.field_path == "task_types[1]"
    assert "must be a string" in str(exc.value)


def test_empty_config_bypasses_required_check():
    assert _validate_config({}, PROJECT_SCHEMA, "project.yaml") == {}
    assert _validate_config(None, PROJECT_SCHEMA, "project.yaml") is None


# --- Integration tests: full ProjectConfig load against a temp dir ---------

def _write_solution(sol_dir, project=None, prompts=None, tasks=None):
    os.makedirs(sol_dir, exist_ok=True)
    if project is not None:
        with open(os.path.join(sol_dir, "project.yaml"), "w", encoding="utf-8") as fh:
            yaml.safe_dump(project, fh)
    if prompts is not None:
        with open(os.path.join(sol_dir, "prompts.yaml"), "w", encoding="utf-8") as fh:
            yaml.safe_dump(prompts, fh)
    if tasks is not None:
        with open(os.path.join(sol_dir, "tasks.yaml"), "w", encoding="utf-8") as fh:
            yaml.safe_dump(tasks, fh)


@pytest.fixture
def temp_solutions(tmp_path, monkeypatch):
    sols = tmp_path / "solutions"
    sols.mkdir()
    monkeypatch.setattr(pl, "_SOLUTIONS_DIR", str(sols))
    monkeypatch.delenv("SAGE_PROJECT", raising=False)
    monkeypatch.delenv("SAGE_DEFAULT_PROJECT", raising=False)
    return sols


def test_valid_solution_loads_cleanly(temp_solutions):
    _write_solution(
        temp_solutions / "demo",
        project={"name": "demo", "version": "1.0.0", "domain": "general"},
        prompts={"analyst": {"system_prompt": "You are an analyst."}},
        tasks={"task_types": ["ANALYZE_LOG"]},
    )
    cfg = ProjectConfig("demo")
    assert cfg.project_name == "demo"
    assert cfg.metadata["name"] == "demo"
    assert cfg.get_task_types() == ["ANALYZE_LOG"]


def test_loader_raises_on_missing_name(temp_solutions):
    _write_solution(temp_solutions / "bad", project={"version": "1.0.0"})
    with pytest.raises(ConfigValidationError) as exc:
        ProjectConfig("bad")
    assert exc.value.field_path == "name"


def test_loader_raises_on_missing_analyst_system_prompt(temp_solutions):
    _write_solution(
        temp_solutions / "bad",
        project={"name": "bad"},
        prompts={"analyst": {"user_prompt_template": "{input}"}},
    )
    with pytest.raises(ConfigValidationError) as exc:
        ProjectConfig("bad")
    assert exc.value.field_path == "analyst.system_prompt"


def test_loader_allows_tasks_without_task_types(temp_solutions):
    _write_solution(
        temp_solutions / "child",
        project={"name": "child"},
        tasks={"task_descriptions": {"ANALYZE_LOG": "analyse a log"}},
    )
    cfg = ProjectConfig("child")
    assert cfg.get_task_types() == list(pl._DEFAULT_TASK_TYPES)


def test_loader_raises_on_wrong_type(temp_solutions):
    _write_solution(
        temp_solutions / "bad",
        project={"name": "bad"},
        tasks={"task_types": "ANALYZE_LOG"},
    )
    with pytest.raises(ConfigValidationError) as exc:
        ProjectConfig("bad")
    assert exc.value.field_path == "task_types"


def test_present_but_empty_project_yaml_does_not_raise(temp_solutions):
    sol = temp_solutions / "empty"
    sol.mkdir()
    (sol / "project.yaml").write_text("# nothing yet\n", encoding="utf-8")
    cfg = ProjectConfig("empty")
    assert cfg.metadata["name"] == "empty"


# --- Smoke test: every real solution shipped in the repo loads -------------

def _repo_solution_names():
    return [s["name"] for s in list_solutions(pl._PROJECT_ROOT)]


@pytest.mark.parametrize("solution_name", _repo_solution_names())
def test_real_solution_loads_without_error(solution_name, monkeypatch):
    monkeypatch.delenv("SAGE_PROJECT", raising=False)
    monkeypatch.delenv("SAGE_DEFAULT_PROJECT", raising=False)
    cfg = ProjectConfig(solution_name)
    assert cfg.project_name == solution_name.lower().strip()
    assert isinstance(cfg.get_task_types(), list)
    assert isinstance(cfg.metadata, dict)


def test_repo_has_at_least_one_loadable_solution():
    names = _repo_solution_names()
    if not names:
        pytest.skip("no solutions/ shipped in this checkout")
    for name in names:
        ProjectConfig(name)
```

---

## Iteration History

**Iter 1** — score 6.0 pass=False  
Feedback: Strong, well-structured validation core, but the deliverable is incomplete against the rubric. (1) Criterion 14 FAILS: no new tests are included. You must add tests that assert each missing-required-f  

**Iter 2** — score 0.0 pass=False  
Feedback: (no parseable feedback)  

**Iter 3** — score 9.0 pass=True  
Feedback:   

