"""
SAGE[ai] - Universal Agent
==========================
A generic agent whose role, persona, and behaviour are defined entirely by the
solution's prompts.yaml — no hardcoded domain logic.

Inspired by oh-my-claudecode's pattern: agents are system prompts + tool
restrictions, nothing more.  Any startup function (marketing, sales, legal,
finance, product, HR, etc.) becomes an agent by adding a role definition to the
solution YAML.

Usage:
    from src.agents.universal import UniversalAgent
    agent = UniversalAgent()
    result = agent.run(role_id="marketing_strategist", task="Draft a go-to-market plan for our B2B SaaS product.")
"""

import json
import logging
from typing import Optional


class UniversalAgent:
    """
    Generic SAGE agent driven entirely by solution YAML role config.

    Role config (in solutions/<name>/prompts.yaml under 'roles:'):
        marketing_strategist:
            name: "Marketing Strategist"
            description: "Go-to-market, campaigns, growth"
            icon: "📣"
            system_prompt: |
                You are a senior marketing strategist ...
    """

    def __init__(self):
        self.logger = logging.getLogger("UniversalAgent")

    def get_roles(self) -> dict:
        """Return all roles defined in the current solution's prompts.yaml."""
        try:
            from src.core.project_loader import project_config
            return project_config.get_prompts().get("roles", {})
        except Exception as e:
            self.logger.error("Could not load roles: %s", e)
            return {}

    def run(
        self,
        role_id: str,
        task: str,
        context: str = "",
        actor: str = "web-ui",
    ) -> dict:
        """
        Run a solution-defined agent role against a task.

        Returns a structured result dict with summary, analysis,
        recommendations, next_steps, severity, confidence, and trace_id.
        """
        from src.core.llm_gateway import llm_gateway
        from src.memory.audit_logger import audit_logger
        from src.modules.trace_id import new as generate_trace_id
        from src.modules.json_extractor import extract as extract_json
        from src.modules.severity import parse as classify_severity

        roles = self.get_roles()
        role_cfg = roles.get(role_id)

        if not role_cfg:
            raise ValueError(
                f"Role '{role_id}' not found in solution config. "
                f"Available: {list(roles.keys())}"
            )

        role_name   = role_cfg.get("name", role_id)
        system_prompt = role_cfg.get("system_prompt", f"You are a {role_name} assistant.")
        icon        = role_cfg.get("icon", "🤖")

        # ── Build prompt ───────────────────────────────────────────────────
        context_block = f"\n\nAdditional context:\n{context}" if context.strip() else ""
        prompt = f"""Task: {task}{context_block}

Respond with a JSON object in this exact format:
{{
    "summary": "One-sentence summary of your response",
    "analysis": "Detailed analysis (2-5 paragraphs)",
    "recommendations": ["Specific, actionable recommendation 1", "Recommendation 2", "..."],
    "next_steps": ["Immediate next step 1", "Step 2", "..."],
    "severity": "GREEN",
    "confidence": "HIGH"
}}

severity: GREEN (no urgent issues), AMBER (attention needed), RED (critical/blocking)
confidence: HIGH, MEDIUM, or LOW based on available information
"""

        trace_id = generate_trace_id()
        self.logger.info("UniversalAgent running role=%s trace=%s", role_id, trace_id)

        # ── LLM call ───────────────────────────────────────────────────────
        raw = llm_gateway.generate(prompt, system_prompt)

        # ── Parse response ─────────────────────────────────────────────────
        parsed = extract_json(raw) or {}

        severity = classify_severity(parsed.get("severity", "GREEN"))

        result = {
            "trace_id":        trace_id,
            "role_id":         role_id,
            "role_name":       role_name,
            "icon":            icon,
            "task":            task,
            "summary":         parsed.get("summary",         raw[:200]),
            "analysis":        parsed.get("analysis",        raw),
            "recommendations": parsed.get("recommendations", []),
            "next_steps":      parsed.get("next_steps",      []),
            "severity":        severity,
            "confidence":      parsed.get("confidence",      "MEDIUM"),
            "raw_response":    raw,
            "status":          "pending_review",
        }

        # ── Audit log ──────────────────────────────────────────────────────
        try:
            audit_logger.log_event(
                actor=actor,
                action_type=f"AGENT_{role_id.upper()}",
                input_context=task[:500],
                output_content=json.dumps({
                    "trace_id":        trace_id,
                    "summary":         result["summary"],
                    "severity":        severity,
                    "confidence":      result["confidence"],
                    "recommendations": result["recommendations"],
                }),
            )
        except Exception as e:
            self.logger.warning("Audit log failed: %s", e)

        return result
