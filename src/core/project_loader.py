"""
SAGE Framework — Project Configuration Loader
=============================================
Loads the active project's configuration, merging the base config/config.yaml
with project-specific overrides from projects/<project>/{project,prompts,tasks}.yaml.

Project selection order (highest priority first):
  1. SAGE_PROJECT environment variable
  2. --project CLI argument  →  call ProjectConfig(project_name="...")
  3. Default: "medtech"

Usage:
    from src.core.project_loader import project_config

    # Get analyst prompts (returns (system_prompt, user_prompt_template))
    system_p, user_tmpl = project_config.get_analyst_prompts()

    # Get valid task types for this project
    types = project_config.get_task_types()

    # Get project metadata dict
    meta = project_config.metadata

    # Reload for a different project at runtime
    project_config.reload("poseengine")
"""

import logging
import os
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
_DEFAULT_PROJECT = "medtech"


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
        self.reload(project_name)

    # ------------------------------------------------------------------
    # Reload / initialisation
    # ------------------------------------------------------------------

    def reload(self, project_name: str | None = None) -> None:
        """Reload configuration for *project_name* (or env/default)."""
        self._name = (
            project_name
            or os.environ.get("SAGE_PROJECT", "")
            or _DEFAULT_PROJECT
        ).lower().strip()

        project_dir = os.path.join(_SOLUTIONS_DIR, self._name)
        self._base    = _load_yaml(os.path.join(_PROJECT_ROOT, "config", "config.yaml"))
        self._project = _load_yaml(os.path.join(project_dir, "project.yaml"))
        self._prompts = _load_yaml(os.path.join(project_dir, "prompts.yaml"))
        self._tasks   = _load_yaml(os.path.join(project_dir, "tasks.yaml"))

        logger.info("SAGE project loaded: '%s'  (%s)", self._name, project_dir)

    # ------------------------------------------------------------------
    # Project name (read-only)
    # ------------------------------------------------------------------

    @property
    def project_name(self) -> str:
        return self._name

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    @property
    def metadata(self) -> dict:
        """Rich project metadata dict (safe to serialise to JSON)."""
        return {
            "project":             self._name,
            "name":                self._project.get("name", self._name),
            "version":             self._project.get("version", "1.0.0"),
            "description":         self._project.get("description", ""),
            "domain":              self._project.get("domain", "general"),
            "active_modules":      self._project.get("active_modules", []),
            "compliance_standards":self._project.get("compliance_standards", []),
            "integrations":        self._project.get("integrations", []),
            "ui_labels":           self._project.get("ui_labels", {}),
        }

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
        """Return list of valid task_type strings for this project."""
        return self._tasks.get("task_types", list(_DEFAULT_TASK_TYPES))

    def get_task_descriptions(self) -> dict[str, str]:
        """Return task_type → human-readable description mapping."""
        return self._tasks.get("task_descriptions", {})

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
