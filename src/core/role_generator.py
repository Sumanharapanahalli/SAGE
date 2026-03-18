"""
role_generator.py — LLM-powered agent role generation and YAML persistence.
Called by POST /agent/hire to create new agent roles from plain-English job descriptions.

Philosophy: 1 person running a billion-dollar company. Hiring an agent should be
as easy as describing a job role in plain English.
"""
import os
import re
import logging
import yaml
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_SOLUTIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "solutions",
)

DEPARTMENT_ICONS = {
    "engineering": "⚙️",
    "marketing": "📣",
    "legal": "⚖️",
    "finance": "💰",
    "product": "🎯",
    "operations": "📋",
    "hr": "👥",
    "custom": "🤖",
}

TECHNICAL_DEPARTMENTS = {"engineering"}


def _make_role_id(job_title: str) -> str:
    """Convert 'VP of Marketing' → 'vp_of_marketing'"""
    slug = job_title.lower()
    slug = re.sub(r"[^a-z0-9\s]", "", slug)
    slug = re.sub(r"\s+", "_", slug.strip())
    return slug or "custom_role"


def _prompts_yaml_path(solution_name: str) -> str:
    return os.path.join(_SOLUTIONS_DIR, solution_name, "prompts.yaml")


class RoleGenerator:
    def generate_system_prompt(
        self,
        job_title: str,
        department: str,
        responsibilities: list,
        domain_context: str = "",
    ) -> str:
        """Use LLM to generate a system_prompt for a new agent role."""
        from src.core.llm_gateway import llm_gateway

        is_technical = department.lower() in TECHNICAL_DEPARTMENTS
        severity_labels = "RED | AMBER | GREEN" if is_technical else "CRITICAL | HIGH | MEDIUM | LOW"

        resp_text = "\n".join(f"- {r}" for r in responsibilities) if responsibilities else "- Execute responsibilities for this role with high quality"

        prompt = f"""Generate a concise system prompt for an AI agent with this job role:

Job Title: {job_title}
Department: {department}
{f"Domain Context: {domain_context}" if domain_context else ""}

Key Responsibilities:
{resp_text}

The system prompt must:
1. Start with "You are the {job_title}..."
2. Describe domain expertise and working style (2-3 sentences)
3. State the primary optimization goal (1 sentence)
4. List 3-4 operating principles as bullets
5. End with: "Always output JSON with: summary, analysis, recommendations, next_steps, severity ({severity_labels}), confidence (HIGH|MEDIUM|LOW)"

Return ONLY the system prompt text. Under 400 words."""

        try:
            result = llm_gateway.generate(prompt, max_tokens=600)
            return result.strip()
        except Exception as e:
            logger.warning("LLM role generation failed, using template: %s", e)
            return self._template_system_prompt(job_title, department, responsibilities, severity_labels)

    def _template_system_prompt(self, job_title, department, responsibilities, severity_labels):
        resp_text = "\n".join(f"- {r}" for r in responsibilities) if responsibilities else "- Execute tasks within your domain with high quality"
        return f"""You are the {job_title}, a senior expert in {department}.

Your primary goal is to deliver high-quality work and provide clear, actionable insights.

Key responsibilities:
{resp_text}

Operating principles:
- Prioritize accuracy and quality
- Flag risks and blockers early to the founder
- Be concise and direct
- Escalate only decisions requiring human judgment

Always output JSON with: summary, analysis, recommendations, next_steps, severity ({severity_labels}), confidence (HIGH|MEDIUM|LOW)"""

    def add_role_to_yaml(self, solution_name: str, role_id: str, role_data: dict) -> str:
        """Add a new role to solutions/<solution_name>/prompts.yaml."""
        path = _prompts_yaml_path(solution_name)
        if not os.path.exists(path):
            raise FileNotFoundError(f"prompts.yaml not found for solution: {solution_name}")

        with open(path, "r") as f:
            content = yaml.safe_load(f) or {}

        roles = content.get("roles") or {}
        if role_id in roles:
            raise ValueError(f"Role '{role_id}' already exists in {solution_name}")

        roles[role_id] = role_data
        content["roles"] = roles

        with open(path, "w") as f:
            yaml.dump(content, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        return yaml.dump({role_id: role_data}, default_flow_style=False, allow_unicode=True)

    def remove_role_from_yaml(self, solution_name: str, role_id: str) -> bool:
        """Remove a role. Returns True if removed."""
        path = _prompts_yaml_path(solution_name)
        if not os.path.exists(path):
            return False

        with open(path, "r") as f:
            content = yaml.safe_load(f) or {}

        roles = content.get("roles") or {}
        if role_id not in roles:
            return False

        del roles[role_id]
        content["roles"] = roles

        with open(path, "w") as f:
            yaml.dump(content, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return True

    def update_role_in_yaml(self, solution_name: str, role_id: str, updates: dict) -> bool:
        """Update fields of an existing role."""
        path = _prompts_yaml_path(solution_name)
        if not os.path.exists(path):
            return False

        with open(path, "r") as f:
            content = yaml.safe_load(f) or {}

        roles = content.get("roles") or {}
        if role_id not in roles:
            return False

        roles[role_id].update({k: v for k, v in updates.items() if v is not None})
        content["roles"] = roles

        with open(path, "w") as f:
            yaml.dump(content, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return True

    def get_org_chart(self, solution_name: str) -> dict:
        """Return role hierarchy tree based on reports_to fields."""
        path = _prompts_yaml_path(solution_name)
        if not os.path.exists(path):
            return {"root_roles": [], "tree": {}}

        with open(path, "r") as f:
            content = yaml.safe_load(f) or {}

        roles = content.get("roles") or {}
        tree = {}
        root_roles = []

        for role_id, role in roles.items():
            if not isinstance(role, dict):
                continue
            reports_to = role.get("reports_to")
            tree[role_id] = {
                "name": role.get("name", role_id),
                "department": role.get("department", "custom"),
                "domain_type": role.get("domain_type", "technical"),
                "reports_to": reports_to,
                "manages": [],
                "icon": role.get("icon", "🤖"),
                "description": role.get("description", ""),
                "hired_at": role.get("hired_at"),
                "responsibilities": role.get("responsibilities", []),
            }
            if not reports_to:
                root_roles.append(role_id)

        # Build manages lists
        for role_id, node in tree.items():
            mgr = node["reports_to"]
            if mgr and mgr in tree:
                tree[mgr]["manages"].append(role_id)

        return {"root_roles": root_roles, "tree": tree, "total": len(tree)}


role_generator = RoleGenerator()
