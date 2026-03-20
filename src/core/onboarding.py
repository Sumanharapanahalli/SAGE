"""
SAGE Framework — Onboarding Wizard
=====================================
Generates a complete solution (project.yaml, prompts.yaml, tasks.yaml) from
a plain-language description of the user's domain.

Usage:
    POST /onboarding/generate
    Body: {
        "description": "We build autonomous drones for agricultural inspection",
        "solution_name": "agri_drones",   # snake_case, becomes folder name
        "compliance_standards": ["ISO 9001"],  # optional
        "integrations": ["gitlab", "slack"]    # optional
    }

The LLM generates domain-appropriate content for all three YAML files.
The result is written to solutions/<solution_name>/ and can be immediately
loaded with POST /config/switch {"project": "<solution_name>"}.
"""

import logging
import os
import re
import yaml

logger = logging.getLogger("Onboarding")

# Lazy module-level import so tests can patch it
try:
    from src.core.llm_gateway import llm_gateway
except Exception:
    llm_gateway = None  # type: ignore

_SOLUTIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "solutions",
)

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_PROJECT_YAML_PROMPT = """
You are a SAGE framework configuration expert. Generate a project.yaml for a new SAGE solution.

Domain description: {description}
Solution name (snake_case): {solution_name}
Compliance standards: {compliance_standards}
Integrations: {integrations}
Parent solution (if any): {parent_solution}

Output VALID YAML only — no markdown fences, no explanation. Follow this exact structure.
For the "suggested_routes" field, provide 2-4 snake_case solution names this solution should route tasks to (real domain-appropriate names, not the placeholders shown).

name: "<human-friendly project name>"
version: "1.0.0"
domain: "{solution_name}"
description: >
  <2-3 sentence domain description>

active_modules:
  - dashboard
  - analyst
  - developer
  - monitor
  - audit
  - improvements
  - llm
  - settings
  - agents
  - yaml-editor

compliance_standards:
  <list the compliance standards>

integrations:
  <list the integrations>

settings:
  memory:
    collection_name: ""
  system:
    max_concurrent_tasks: 1

suggested_routes:
  - solution_a
  - solution_b

ui_labels:
  analyst_page_title: "<domain-appropriate title>"
  analyst_input_label: "<what the user pastes — log, event, signal, etc.>"
  developer_page_title: "<domain-appropriate title>"
  monitor_page_title: "<domain-appropriate title>"
  dashboard_subtitle: "<domain-appropriate subtitle>"

dashboard:
  badge_color: "bg-blue-100 text-blue-700"
  context_color: "border-blue-200 bg-blue-50"
  context_items:
    - label: "Domain"
      description: "<domain description>"
    - label: "Agents"
      description: "<what agents do in this domain>"
    - label: "Key Focus"
      description: "<primary focus areas>"
  quick_actions:
    - {{ label: "Analyze Signal", route: "/analyst",   description: "<domain-specific>" }}
    - {{ label: "Review Code",    route: "/developer", description: "<domain-specific>" }}
    - {{ label: "Run Agents",     route: "/agents",    description: "Custom agent roles" }}
    - {{ label: "Audit Trail",    route: "/audit",     description: "Decision history" }}
""".strip()

_PROMPTS_YAML_PROMPT = """
You are a SAGE framework configuration expert. Generate a prompts.yaml for this domain.

Domain description: {description}
Solution name: {solution_name}

Output VALID YAML only — no markdown fences, no explanation.

The file must contain system prompts for these roles: analyst, developer, planner, monitor.
Each role has a "system_prompt" key.
Also include a "roles" section with 3 domain-specific expert roles (each has name, description, system_prompt).

Structure:
analyst:
  system_prompt: |
    <2-4 sentence system prompt for the analyst role in this domain>

developer:
  system_prompt: |
    <2-4 sentence system prompt for the developer role in this domain>

planner:
  system_prompt: |
    <2-4 sentence system prompt for the planner role in this domain>

monitor:
  system_prompt: |
    <2-4 sentence system prompt for the monitor role in this domain>

roles:
  <role_id_1>:
    name: "<Role Name>"
    description: "<what this expert does>"
    system_prompt: |
      <domain-specific expert system prompt>
  <role_id_2>:
    name: "<Role Name>"
    description: "<what this expert does>"
    system_prompt: |
      <domain-specific expert system prompt>
  <role_id_3>:
    name: "<Role Name>"
    description: "<what this expert does>"
    system_prompt: |
      <domain-specific expert system prompt>
""".strip()

_TASKS_YAML_PROMPT = """
You are a SAGE framework configuration expert. Generate a tasks.yaml for this domain.

Domain description: {description}
Solution name: {solution_name}

Output VALID YAML only — no markdown fences, no explanation.

Define 5-7 task types relevant to this domain. Each task type has:
  agent: which agent handles it (analyst/developer/planner/monitor/universal)
  description: what the task does
  priority: integer 1-10 (1=highest)

Structure:
task_types:
  TASK_TYPE_NAME:
    agent: "analyst"
    description: "..."
    priority: 5
  ...
""".strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _try_add_to_org(org_name: str, solution_name: str) -> None:
    """
    Non-fatal: if org.yaml exists in SAGE_SOLUTIONS_DIR, add the solution under
    the given org name.  Silently logs and continues on any error.
    """
    try:
        org_yaml_path = os.path.join(_SOLUTIONS_DIR, "org.yaml")
        if not os.path.exists(org_yaml_path):
            logger.debug(
                "org.yaml not found at %s — skipping org auto-add", org_yaml_path
            )
            return
        with open(org_yaml_path, "r", encoding="utf-8") as f:
            org_data = yaml.safe_load(f) or {}

        # Validate that the org name in the file matches the requested org_name
        existing_org_name = org_data.get("org", {}).get("name", "")
        if existing_org_name and existing_org_name != org_name:
            logger.debug(
                "org.yaml name '%s' does not match requested org '%s' — skipping auto-add",
                existing_org_name,
                org_name,
            )
            return

        # Ensure org > solutions list exists
        org_block = org_data.setdefault("org", {})
        solutions_list = org_block.setdefault("solutions", [])
        if solution_name not in solutions_list:
            solutions_list.append(solution_name)
            with open(org_yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(org_data, f, default_flow_style=False, allow_unicode=True)
            logger.info(
                "Auto-added '%s' to org '%s' in org.yaml", solution_name, org_name
            )
        else:
            logger.debug(
                "Solution '%s' already listed in org.yaml — no change", solution_name
            )
    except Exception as exc:
        logger.warning(
            "Could not auto-add '%s' to org '%s': %s", solution_name, org_name, exc
        )


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def _sanitize_name(name: str) -> str:
    """Convert arbitrary string to safe snake_case folder name."""
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name)
    return name.strip("_") or "my_solution"


def _extract_yaml(text: str) -> str:
    """Strip markdown fences from LLM output if present."""
    # Remove ```yaml ... ``` or ``` ... ```
    text = re.sub(r"```(?:yaml)?\s*\n?", "", text)
    text = re.sub(r"\n?```", "", text)
    return text.strip()


def _validate_yaml(text: str, filename: str) -> dict:
    """Parse YAML and return the dict, or raise ValueError with context."""
    try:
        result = yaml.safe_load(text)
        if not isinstance(result, dict):
            raise ValueError(f"{filename}: expected a YAML mapping, got {type(result).__name__}")
        return result
    except yaml.YAMLError as e:
        raise ValueError(f"{filename}: YAML parse error — {e}")


def generate_solution(
    description: str,
    solution_name: str,
    compliance_standards: list = None,
    integrations: list = None,
    parent_solution: str = "",
    org_name: str = "",
    org_context: str = "",
) -> dict:
    """
    Generate a complete SAGE solution from a plain-language description.

    Args:
        description:          Natural language description of the domain.
        solution_name:        Desired folder name (will be sanitized).
        compliance_standards: List of compliance standards (e.g. ["ISO 9001"]).
        integrations:         List of integrations (e.g. ["gitlab", "slack"]).
        parent_solution:      If provided, inject ``parent: <value>`` into project.yaml.
        org_name:             If provided, auto-add this solution to that org in org.yaml.
        org_context:          If provided, prepended to description before LLM generation.

    Returns:
        dict with keys: solution_name, path, files (dict of filename -> content),
        status ("created" | "exists" — never overwrites an existing solution), and
        suggested_routes (list of snake_case solution names the LLM recommends routing
        tasks to — defaults to [] if the LLM does not provide them).

    Raises:
        ValueError if any generated YAML is invalid.
        RuntimeError if the LLM is unavailable.
    """
    if org_context:
        description = f"Company context:\n{org_context}\n\n---\n\n{description}"

    solution_name = _sanitize_name(solution_name)
    compliance_str = "\n  - ".join(compliance_standards or []) or "[]"
    integrations_str = "\n  - ".join(integrations or ["gitlab"]) or "- gitlab"

    template_vars = {
        "description":          description,
        "solution_name":        solution_name,
        "compliance_standards": compliance_str,
        "integrations":         integrations_str,
        "parent_solution":      parent_solution or "none",
    }

    target_dir = os.path.join(_SOLUTIONS_DIR, solution_name)
    if os.path.exists(target_dir):
        return {
            "solution_name":    solution_name,
            "path":             target_dir,
            "status":           "exists",
            "files":            {},
            "suggested_routes": [],
            "message":          f"Solution '{solution_name}' already exists. Use /config/switch to load it.",
        }

    logger.info("Generating solution '%s' from description...", solution_name)

    # Generate each YAML file from the LLM
    files = {}

    for filename, prompt_template in [
        ("project.yaml",  _PROJECT_YAML_PROMPT),
        ("prompts.yaml",  _PROMPTS_YAML_PROMPT),
        ("tasks.yaml",    _TASKS_YAML_PROMPT),
    ]:
        prompt = prompt_template.format(**template_vars)
        raw = llm_gateway.generate(
            prompt=prompt,
            system_prompt=(
                "You are a YAML generation expert. Output only valid YAML — "
                "no markdown fences, no explanations, no preamble."
            ),
            trace_name=f"onboarding_{filename.replace('.', '_')}",
        )
        cleaned = _extract_yaml(raw)
        # Validate it parses
        _validate_yaml(cleaned, filename)
        files[filename] = cleaned
        logger.debug("Generated %s (%d chars)", filename, len(cleaned))

    # --- Post-process project.yaml ---

    # Extract suggested_routes from the generated project.yaml (LLM may include them)
    proj_data = yaml.safe_load(files["project.yaml"]) or {}
    suggested_routes = proj_data.pop("suggested_routes", None)
    if not isinstance(suggested_routes, list):
        suggested_routes = []
    # Sanitize each entry to snake_case strings
    suggested_routes = [
        _sanitize_name(str(r)) for r in suggested_routes if r
    ]

    # Inject parent: field if requested
    if parent_solution:
        proj_data["parent"] = parent_solution
        logger.debug("Injected parent '%s' into project.yaml", parent_solution)

    # Re-serialize project.yaml after mutations
    files["project.yaml"] = yaml.dump(
        proj_data, default_flow_style=False, allow_unicode=True
    )

    # Write to disk
    os.makedirs(target_dir, exist_ok=True)
    for filename, content in files.items():
        path = os.path.join(target_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("Written: %s", path)

    # Also create empty workflows/ and mcp_servers/ stubs
    for subdir in ("workflows", "mcp_servers", "evals"):
        os.makedirs(os.path.join(target_dir, subdir), exist_ok=True)
        init_path = os.path.join(target_dir, subdir, ".gitkeep")
        if not os.path.exists(init_path):
            open(init_path, "w").close()

    # --- Auto-add to org.yaml if org_name provided ---
    if org_name:
        _try_add_to_org(org_name=org_name, solution_name=solution_name)

    logger.info("Solution '%s' created at %s", solution_name, target_dir)

    return {
        "solution_name":   solution_name,
        "path":            target_dir,
        "status":          "created",
        "files":           files,
        "suggested_routes": suggested_routes,
        "message":         (
            f"Solution '{solution_name}' created. "
            f"Load it with: POST /config/switch {{\"project\": \"{solution_name}\"}}"
        ),
    }
