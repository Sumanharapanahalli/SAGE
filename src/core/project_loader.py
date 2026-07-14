"""
SAGE Framework — Project Configuration Loader
=============================================
Loads the active project's configuration, merging the base config/config.yaml
with project-specific overrides from solutions/<project>/{project,prompts,tasks}.yaml.

Project selection order (highest priority first):
  1. SAGE_PROJECT environment variable
  2. --project CLI argument  →  call ProjectConfig(project_name="...")
  3. SAGE_DEFAULT_PROJECT environment variable
  4. Auto-discover: first alphabetical solution in SAGE_SOLUTIONS_DIR

The framework has no hardcoded solution name. Solutions live in SAGE_SOLUTIONS_DIR
(default: ./solutions/) or any external directory set via that env var.

Validation
----------
When a solution's project.yaml / prompts.yaml / tasks.yaml (or the equivalent
sections of a SKILL.md frontmatter) are loaded, they are checked against the
minimal JSON Schemas defined below. Missing required fields or wrong types raise
a clear :class:`ConfigValidationError` naming the file and the offending field —
instead of a KeyError surfacing deep inside agent code at runtime.

Boundary cases (intentional, covered by tests/test_project_loader_validation.py):

* **Absent or present-but-empty files are skipped.** A missing file, or a file
  that parses to an empty mapping / ``null`` (e.g. a `project.yaml` containing
  only comments), yields ``{}``. ``_validate_config`` treats ``{}`` as "nothing
  declared" and performs NO checks, so the framework's defaults and the org-level
  task inheritance continue to work. Consequently a present-but-empty
  ``project.yaml`` does NOT trip the ``name`` requirement — that is by design,
  not a missed check.

* **``tasks.yaml`` does not require ``task_types``.** A child solution may
  legitimately omit it and inherit task types from a parent via the org
  parent-chain merge (see :meth:`ProjectConfig.get_task_types`), and the loader
  falls back to ``_DEFAULT_TASK_TYPES`` when no org is active. Marking it required
  would turn that supported case into a spurious load-time error.

Usage:
    from src.core.project_loader import project_config

    # Get analyst prompts (returns (system_prompt, user_prompt_template))
    system_p, user_tmpl = project_config.get_analyst_prompts()

    # Get valid task types for this project
    types = project_config.get_task_types()

    # Get project metadata dict
    meta = project_config.metadata

    # Reload for a different project at runtime
    project_config.reload("my_solution")
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
    os.path.join(_PROJECT_ROOT, "solutions")
)


# ---------------------------------------------------------------------------
# Config validation — minimal JSON Schemas + a tiny dependency-free validator
# ---------------------------------------------------------------------------

class ConfigValidationError(ValueError):
    """Raised when a solution's YAML config fails schema validation.

    Carries the originating file path and the dotted field path so the error
    is actionable for solution authors rather than an opaque KeyError raised
    later from inside an agent.
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
#   required    — list of keys that must be present on an object
#   properties  — per-key sub-schemas (only validated when the key is present)
#   items       — sub-schema applied to every element of an array
# Only fields that are present are type-checked; ``required`` enforces presence.

PROJECT_SCHEMA: dict = {
    "type": "object",
    # `name` is the single mandatory project field. The SKILL.md loader always
    # supplies it (defaulting to ""), so this only constrains the legacy
    # project.yaml layout — where a missing name is a genuine authoring error.
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
            # If an analyst section is declared at all, it must carry a system
            # prompt — otherwise the agent silently runs on framework defaults
            # while appearing configured.
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
    # NOTE: `task_types` is intentionally NOT in `required`.
    # A child solution may legitimately omit it and inherit task types from a
    # parent via the org parent-chain merge (see ProjectConfig.get_task_types),
    # and the loader falls back to _DEFAULT_TASK_TYPES when no org is active.
    # Marking it required would convert that valid, supported case into a
    # load-time ConfigValidationError (a regression). We still type-check it
    # whenever it IS present: it must be an array of strings.
    "properties": {
        "task_types":            {"type": "array", "items": {"type": "string"}},
        "task_descriptions":     {"type": "object"},
        "task_hooks":            {"type": "object"},
        "task_sandbox_policies": {"type": "object"},
        "scheduled":             {"type": "array"},
    },
}

_JSON_TYPES: dict = {
    "object":  dict,
    "array":   list,
    "string":  str,
    "integer": int,
    "boolean": bool,
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
    """Validate *instance* against *schema*, raising ConfigValidationError.

    A minimal JSON-Schema interpreter supporting type/required/properties/items.
    """
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
                _validate(
                    instance[key], sub_schema, source,
                    f"{path}.{key}".lstrip("."),
                )

    if expected_type == "array" and isinstance(instance, list):
        item_schema = schema.get("items")
        if item_schema:
            for idx, item in enumerate(instance):
                _validate(item, item_schema, source, f"{path}[{idx}]")


def _validate_config(data: dict, schema: dict, source: str) -> dict:
    """Validate a loaded config section, skipping empty (absent-file) dicts.

    A falsy *data* (``{}`` / ``None``) means the file was missing, blank, or
    comment-only — the loader intentionally falls back to framework defaults and
    org inheritance in that case, so there is nothing to validate and required
    fields are NOT enforced. This is a deliberate boundary (see module docstring)
    and is exercised by tests/test_project_loader_validation.py. Returns *data*
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

    Format:
        ---
        <YAML frontmatter>
        ---
        <markdown body>

    The frontmatter must contain all structured config (project metadata,
    agent_roles, tasks).  The markdown body is stored as skill_content and
    injected into every agent system prompt as domain context.
    """
    if not os.path.exists(path):
        return {}, {}, {}, ""

    with open(path, "r", encoding="utf-8") as fh:
        raw = fh.read()

    # Split on the frontmatter delimiters --- \n
    parts = raw.split("---\n", 2)
    if len(parts) < 3:
        # Malformed — try splitting with \r\n
        parts = raw.split("---\r\n", 2)
    if len(parts) < 3:
        logger.warning("SKILL.md at %s has no valid frontmatter — treating entire file as body.", path)
        return {}, {}, {}, raw.strip()

    _, frontmatter_raw, body = parts
    skill_content = body.strip()

    try:
        fm = yaml.safe_load(frontmatter_raw) or {}
    except yaml.YAMLError as exc:
        logger.error("SKILL.md frontmatter YAML parse error at %s: %s", path, exc)
        return {}, {}, {}, skill_content

    # ── Build project dict from frontmatter top-level keys ────────────────
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
    # Copy through any extra top-level keys (e.g. source_repo, tenants)
    skip = {
        "name", "version", "domain", "description", "modules", "active_modules",
        "compliance_standards", "integrations", "ui_labels", "dashboard",
        "settings", "tasks", "agent_roles",
    }
    for k, v in fm.items():
        if k not in skip:
            project_dict[k] = v

    # ── Build prompts dict from agent_roles ───────────────────────────────
    prompts_dict: dict = {}
    agent_roles = fm.get("agent_roles", {})
    # Standard named agents — map to the keys project_loader already knows
    for role_key in ("analyst", "developer", "planner", "monitor"):
        if role_key in agent_roles:
            role_cfg = agent_roles[role_key]
            if role_key == "analyst":
                prompts_dict["analyst"] = {
                    "system_prompt":       role_cfg.get("system_prompt", ""),
                    "user_prompt_template": role_cfg.get(
                        "user_prompt_template",
                        "INPUT:\n{input}\n\nPAST CONTEXT:\n{context}\n\nGenerate Analysis JSON:",
                    ),
                    "output_schema":       role_cfg.get("output_schema", {}),
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

    # Any extra roles go into prompts_dict["roles"] for UniversalAgent
    universal_roles = {
        k: v for k, v in agent_roles.items()
        if k not in ("analyst", "developer", "planner", "monitor")
    }
    if universal_roles:
        prompts_dict["roles"] = universal_roles

    # ── Build tasks dict ──────────────────────────────────────────────────
    tasks_raw = fm.get("tasks", {})
    if isinstance(tasks_raw, list):
        # Simple list of task type strings
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
    """
    Central configuration manager for the active SAGE project.

    Every agent and component should import the module-level singleton
    ``project_config`` rather than instantiating this class directly.

    Layered config (lower index = lower priority):
        1. Framework defaults  (hardcoded in this file)
        2. config/config.yaml  (base LLM / memory / integration settings)
        3. solutions/<name>/project.yaml   (project metadata + overrides)
        4. solutions/<name>/prompts.yaml   (agent prompts)
        5. solutions/<name>/tasks.yaml     (task types + descriptions)
    """

    def __init__(self, project_name: str | None = None):
        self._name: str = ""
        self._base: dict = {}
        self._project: dict = {}
        self._prompts: dict = {}
        self._tasks: dict = {}
        self._skill_content: str = ""
        self._skill_md_path: str = ""
        self.reload(project_name)

    # ------------------------------------------------------------------
    # Reload / initialisation
    # ------------------------------------------------------------------

    def reload(self, project_name: str | None = None) -> None:
        """Reload configuration for *project_name* (or env/default).

        Each loaded config section is validated against its minimal schema.
        A failure raises :class:`ConfigValidationError` here — at load time —
        rather than letting a missing key surface as a KeyError inside an agent.
        """
        self._name = (
            project_name
            or os.environ.get("SAGE_PROJECT", "")
            or _auto_discover_project()
        ).lower().strip()

        project_dir = os.path.join(_SOLUTIONS_DIR, self._name)
        self._base    = _load_yaml(os.path.join(_PROJECT_ROOT, "config", "config.yaml"))

        skill_path = os.path.join(project_dir, "SKILL.md")
        if os.path.isfile(skill_path):
            # SKILL.md takes priority — parse frontmatter + body
            self._project, self._prompts, self._tasks, self._skill_content = (
                _parse_skill_md(skill_path)
            )
            self._skill_md_path = skill_path
            _validate_config(self._project, PROJECT_SCHEMA, skill_path)
            _validate_config(self._prompts, PROMPTS_SCHEMA, skill_path)
            _validate_config(self._tasks,   TASKS_SCHEMA,   skill_path)
            logger.info(
                "SAGE project loaded from SKILL.md: '%s'  (%s)",
                self._name, skill_path,
            )
        else:
            # Fall back to legacy 3-file layout
            project_path = os.path.join(project_dir, "project.yaml")
            prompts_path = os.path.join(project_dir, "prompts.yaml")
            tasks_path   = os.path.join(project_dir, "tasks.yaml")
            self._project = _validate_config(_load_yaml(project_path), PROJECT_SCHEMA, project_path)
            self._prompts = _validate_config(_load_yaml(prompts_path), PROMPTS_SCHEMA, prompts_path)
            self._tasks   = _validate_config(_load_yaml(tasks_path),   TASKS_SCHEMA,   tasks_path)
            self._skill_content = ""
            self._skill_md_path = ""
            logger.info("SAGE project loaded: '%s'  (%s)", self._name, project_dir)

    # ------------------------------------------------------------------
    # Project name (read-only)
    # ------------------------------------------------------------------

    @property
    def project_name(self) -> str:
        return self._name

    # ------------------------------------------------------------------
    # .sage/ data directory — one per solution, never inside the framework
    # ------------------------------------------------------------------

    @property
    def sage_data_dir(self) -> str:
        """
        Return (and create) the .sage/ directory for the active solution.

        This is the single source of truth for all runtime data paths:
          <solution_dir>/.sage/audit_log.db   — compliance audit trail + proposals
          <solution_dir>/.sage/chroma_db/     — vector knowledge store

        When no solution is loaded (framework fallback), returns a .sage/
        directory at the project root so the framework itself never pollutes
        a solution's data directory.

        The .sage/ folder should be gitignored in every solution repo.
        It is never committed — it is runtime state, not configuration.
        """
        if self._name:
            sage_dir = os.path.join(_SOLUTIONS_DIR, self._name, ".sage")
        else:
            sage_dir = os.path.join(_PROJECT_ROOT, ".sage")
        os.makedirs(sage_dir, exist_ok=True)
        return sage_dir

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    @property
    def metadata(self) -> dict:
        """Rich project metadata dict (safe to serialise to JSON)."""
        return {
            "project":             self._name,
            # `or`, not get(..., default): dict.get only falls back when the key is ABSENT,
            # so a present-but-empty `name: ""` returned "" — and that empty string then
            # became the solution's display name and flowed into derived identifiers. An
            # empty name is as unusable as a missing one; fall back to the directory name.
            "name":                self._project.get("name") or self._name,
            "version":             self._project.get("version", "1.0.0"),
            "description":         self._project.get("description", ""),
            "domain":              self._project.get("domain", "general"),
            "active_modules":      self._project.get("active_modules", []),
            "compliance_standards":self._project.get("compliance_standards", []),
            "integrations":        self._project.get("integrations", []),
            "ui_labels":           self._project.get("ui_labels", {}),
            "dashboard":           self._project.get("dashboard", {}),
            "theme":               self._project.get("theme", {}),
        }

    # ------------------------------------------------------------------
    # SKILL.md access
    # ------------------------------------------------------------------

    @property
    def skill_content(self) -> str:
        """
        Markdown body from SKILL.md.  Non-empty only when the solution uses
        SKILL.md format.  Agents inject this into their system prompts to
        provide rich domain knowledge.
        """
        return self._skill_content

    @property
    def skill_md_path(self) -> str:
        """Absolute path to the active SKILL.md, or empty string if not in use."""
        return self._skill_md_path

    @property
    def solution_context(self) -> str:
        """
        Contents of <solution_dir>/solution_context.md, if it exists.

        Analogous to CLAUDE.md in Claude Code — injected as a prefix to every
        agent system prompt so domain-specific standing instructions are always
        in context without being embedded in the solution's YAML files.

        Returns empty string when the file is absent (no-op for agents).
        """
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

    # ------------------------------------------------------------------
    # Prompt accessors — return project prompts or framework defaults
    # ------------------------------------------------------------------

    def get_analyst_prompts(self) -> Tuple[str, str]:
        """Return (system_prompt, user_prompt_template) for AnalystAgent."""
        cfg = self._prompts.get("analyst", {})
        return (
            cfg.get("system_prompt",        _DEFAULT_ANALYST_SYSTEM),
            cfg.get("user_prompt_template",  _DEFAULT_ANALYST_USER),
        )

    def get_developer_review_prompt(self) -> str:
        """Return system prompt for DeveloperAgent code review."""
        return self._prompts.get("developer", {}).get(
            "review_system_prompt", _DEFAULT_DEV_REVIEW_SYSTEM
        )

    def get_planner_prompt(self) -> str:
        """Return system prompt for PlannerAgent."""
        return self._prompts.get("planner", {}).get(
            "system_prompt", _DEFAULT_PLANNER_SYSTEM
        )

    def get_monitor_prompt(self) -> str:
        """Return system prompt for MonitorAgent event classification."""
        return self._prompts.get("monitor", {}).get(
            "system_prompt", _DEFAULT_MONITOR_SYSTEM
        )

    def get_analyst_output_schema(self) -> dict:
        """Return expected JSON output schema for AnalystAgent."""
        return (
            self._prompts.get("analyst", {})
                         .get("output_schema", _DEFAULT_ANALYST_SCHEMA)
        )

    # ------------------------------------------------------------------
    # Task types
    # ------------------------------------------------------------------

    def get_task_types(self) -> list[str]:
        """Return list of valid task_type strings for this project.

        When an org is configured and the active solution has a parent chain,
        returns the merged task types from the full parent chain (root → child),
        so child solutions inherit task types declared in parent solutions.
        Falls back to the solution's own tasks.yaml when no org is active.

        Because inheritance / framework defaults legitimately cover a tasks.yaml
        that omits ``task_types``, TASKS_SCHEMA does NOT mark it required.
        """
        ol = _get_org_loader()
        if ol.org_name and self._name:
            merged = ol.get_merged_tasks(self._name)
            return merged.get("task_types", self._tasks.get("task_types", list(_DEFAULT_TASK_TYPES)))
        return self._tasks.get("task_types", list(_DEFAULT_TASK_TYPES))

    def get_task_descriptions(self) -> dict[str, str]:
        """Return task_type → human-readable description mapping.

        When an org is configured, returns merged descriptions from the full
        parent chain (root → child), with child entries overriding parent on conflict.
        Falls back to the solution's own tasks.yaml when no org is active.
        """
        ol = _get_org_loader()
        if ol.org_name and self._name:
            merged = ol.get_merged_tasks(self._name)
            return merged.get("task_descriptions", self._tasks.get("task_descriptions", {}))
        return self._tasks.get("task_descriptions", {})

    def get_task_hooks(self, task_type: str) -> dict:
        """Return {'pre': [...], 'post': [...]} shell commands for task_type, or empty lists."""
        hooks_map = self._tasks.get("task_hooks", {})
        entry = hooks_map.get(task_type, {})
        return {
            "pre":  entry.get("pre", []),
            "post": entry.get("post", []),
        }

    def get_scheduled_tasks(self) -> list:
        """Return scheduled task definitions from tasks.yaml."""
        return self._tasks.get("scheduled", [])

    def get_task_sandbox_policy(self, task_type: str) -> dict | None:
        """Return OpenShell sandbox policy config for task_type, or None if not declared."""
        policies = self._tasks.get("task_sandbox_policies", {})
        return policies.get(task_type)

    # ------------------------------------------------------------------
    # Base config passthrough (for integrations: gitlab, teams, etc.)
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Read a top-level key from config/config.yaml."""
        return self._base.get(key, default)

    def get_project_setting(self, key: str, default: Any = None) -> Any:
        """Read a top-level key from the project's project.yaml."""
        return self._project.get(key, default)

    def get_prompts(self) -> dict:
        """Return the full parsed prompts.yaml dict for the active solution."""
        return self._prompts

    def set_active_modules(self, modules: list) -> None:
        """Override active_modules at runtime (not persisted to disk)."""
        self._project["active_modules"] = list(modules)
        logger.info("Active modules updated: %s", modules)

    def get_agent_budget(self, agent_name: str) -> dict | None:
        """Return budget config for agent_name from project.yaml agent_budgets, or None."""
        budgets = self._project.get("agent_budgets", {})
        return budgets.get(agent_name)


# ---------------------------------------------------------------------------
# Framework-level defaults  (used when project config omits a section)
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
    """Return sorted SolutionRef dicts for each valid solution in the active
    solutions directory.

    Honors ``SAGE_SOLUTIONS_DIR`` when set — the same env var this module's
    own ``_SOLUTIONS_DIR`` (and every ``ProjectConfig``) resolves the active
    solution against — so solutions mounted outside the framework checkout
    (SOUL.md: "solutions are tenants, not children") are discoverable, not
    just ones under ``<sage_root>/solutions``. Falls back to
    ``<sage_root>/solutions`` when unset, unchanged from prior behaviour.

    A valid solution is a non-dotfile directory that contains either
    ``project.yaml`` or ``SKILL.md``.
    """
    override = os.environ.get("SAGE_SOLUTIONS_DIR", "")
    root = Path(override) if override else Path(sage_root) / "solutions"
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
        out.append(
            {
                "name": entry.name,
                "path": str(entry.resolve()),
                "has_sage_dir": (entry / ".sage").is_dir(),
            }
        )
    return out
