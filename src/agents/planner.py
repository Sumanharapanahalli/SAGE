"""
SAGE[ai] - Planner Agent
==========================
Orchestrates complex multi-step tasks using the Plan-and-Execute pattern.

The Planner Agent receives a high-level task description (e.g. "fix issue #45"),
uses the LLM to decompose it into an ordered list of subtasks, then submits each
subtask to the TaskQueue for serialised execution.

Pattern: Plan-and-Execute
  1. LLM generates a structured plan (list of subtasks with task_type + payload)
  2. Planner submits subtasks to TaskQueue in dependency order
  3. Planner tracks completion and reports back

ISO 13485 Compliance: Every planning decision is audited. No subtask executes
without an audit trail entry. Human-in-the-loop gates are enforced by each
downstream agent.
"""

import json
import logging
import os
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# Task types are loaded dynamically from the active project config
# (falls back to framework defaults if project config omits tasks.yaml)
def _get_valid_task_types() -> set[str]:
    from src.core.project_loader import project_config
    return set(project_config.get_task_types())


class PlannerAgent:
    """
    Orchestrator that decomposes complex requests into executable subtasks.

    Usage:
        from src.agents.planner import planner_agent
        result = planner_agent.plan_and_execute("Investigate and fix issue #42 in project 7")
    """

    def __init__(self):
        self.logger = logging.getLogger("PlannerAgent")
        self._llm_gateway = None
        self._audit_logger = None

    @property
    def llm(self):
        if self._llm_gateway is None:
            from src.core.llm_gateway import llm_gateway
            self._llm_gateway = llm_gateway
        return self._llm_gateway

    @property
    def audit(self):
        if self._audit_logger is None:
            from src.memory.audit_logger import audit_logger
            self._audit_logger = audit_logger
        return self._audit_logger

    # -----------------------------------------------------------------------
    # Core Planning
    # -----------------------------------------------------------------------

    # SAGE framework task types — used when planning framework improvements (scope=sage)
    FRAMEWORK_TASK_TYPES = {
        "ANALYZE":  "Analyse existing code, architecture, or requirements",
        "DEVELOP":  "Write or modify code files in the SAGE codebase",
        "REVIEW":   "Review code quality, security, or correctness",
        "TEST":     "Write or run tests to verify correctness",
        "PLAN":     "Decompose a sub-goal into further steps",
        "DOCUMENT": "Update documentation or comments",
    }

    def create_plan(self, description: str, override_task_types: dict | None = None) -> list[dict]:
        """
        Uses the LLM to decompose a complex task into ordered subtasks.

        Args:
            description:         High-level task description in natural language.
            override_task_types: Optional dict of {TYPE: description} to use instead of
                                 the active solution's task types. Pass
                                 PlannerAgent.FRAMEWORK_TASK_TYPES for sage-scope items.

        Returns:
            List of subtask dicts, each with 'task_type', 'payload', and
            'description' keys. Returns empty list on failure.
        """
        self.logger.info("Creating plan for: %s", description[:120])

        if override_task_types:
            valid_types = set(override_task_types.keys())
            descs_str = "\n".join(f"  {k}: {v}" for k, v in override_task_types.items())
            system_prompt_base = (
                "You are a software engineering planner. Decompose the task into ordered "
                "implementation steps using ONLY the valid task types listed. "
                "Output a JSON array. Each element must have: "
                "'step' (int), 'task_type' (string), 'description' (string), 'payload' (object). "
                "VALID_TASK_TYPES: " + ", ".join(sorted(valid_types))
            )
        else:
            from src.core.project_loader import project_config
            valid_types = _get_valid_task_types()
            task_descs = project_config.get_task_descriptions()
            descs_str = "\n".join(
                f"  {k}: {v}" for k, v in task_descs.items()
                if k in valid_types
            ) or "  " + "\n  ".join(sorted(valid_types))
            system_prompt_base = project_config.get_planner_prompt().replace(
                "VALID_TASK_TYPES", ", ".join(sorted(valid_types))
            )
            # Inject solution_context.md standing instructions (if present)
            _sol_ctx = project_config.solution_context
            if _sol_ctx:
                system_prompt_base = _sol_ctx + "\n\n" + system_prompt_base
            # Inject SKILL.md domain knowledge when available
            _skill = project_config.skill_content
            if _skill:
                system_prompt_base = system_prompt_base + "\n\n## Domain Skills\n" + _skill

        system_prompt = system_prompt_base + (
            f"\n\nTask type descriptions:\n{descs_str}\n\n"
            "Rules:\n"
            "  - Only include steps that are directly necessary.\n"
            "  - Preserve dependency order.\n"
            "  - Do not include markdown fences in output.\n"
            "  - If the task cannot be mapped to supported types, return []."
        )

        user_prompt = f"Task: {description}\n\nGenerate the execution plan as a JSON array:"

        response_text = self.llm.generate(user_prompt, system_prompt)

        try:
            response_text = response_text.replace("```json", "").replace("```", "").strip()
            # Extract JSON array even when the LLM adds prose before/after it
            import re as _re
            arr_match = _re.search(r'\[[\s\S]*\]', response_text)
            if arr_match:
                response_text = arr_match.group(0)
            plan = json.loads(response_text)
            if not isinstance(plan, list):
                raise ValueError("Expected a JSON array.")
        except (json.JSONDecodeError, ValueError) as exc:
            self.logger.error("Plan parsing failed: %s | Raw: %s", exc, response_text[:300])
            return []

        # Validate and filter steps — use override_task_types when provided
        effective_valid_types = valid_types  # already set above from override or project config
        validated = []
        for step in plan:
            task_type = step.get("task_type", "").upper()
            if task_type not in effective_valid_types:
                self.logger.warning("Planner emitted unknown task_type '%s' — skipping.", task_type)
                continue
            if not isinstance(step.get("payload"), dict):
                step["payload"] = {}  # default to empty payload rather than skipping
            step["task_type"] = task_type
            validated.append(step)

        self.logger.info("Plan created: %d step(s).", len(validated))
        return validated

    def plan_and_execute(self, description: str, priority: int = 5) -> dict:
        """
        Decomposes a task into a plan and submits all subtasks to the TaskQueue.

        Args:
            description: High-level task description.
            priority:    Queue priority for all submitted subtasks (default 5).

        Returns:
            dict with 'plan' (list), 'task_ids' (list), 'trace_id', and 'status'.
        """
        from src.core.queue_manager import task_queue

        # Audit the planning request
        trace_id = self.audit.log_event(
            actor="PlannerAgent",
            action_type="PLAN_CREATED",
            input_context=description,
            output_content="",  # Updated below
            metadata={"description": description[:500]},
        )

        plan = self.create_plan(description)
        if not plan:
            self.audit.log_event(
                actor="PlannerAgent",
                action_type="PLAN_FAILED",
                input_context=description,
                output_content="No executable steps produced.",
                metadata={"trace_id": trace_id},
            )
            return {
                "status": "failed",
                "reason": "LLM could not produce an executable plan for this task.",
                "description": description,
                "trace_id": trace_id,
            }

        # Submit subtasks in order
        task_ids = []
        for step in sorted(plan, key=lambda s: s.get("step", 999)):
            task_id = task_queue.submit(
                task_type=step["task_type"],
                payload=step["payload"],
                priority=priority,
            )
            task_ids.append({
                "step": step.get("step"),
                "task_type": step["task_type"],
                "description": step.get("description", ""),
                "task_id": task_id,
            })
            self.logger.info(
                "Submitted step %s: %s (task_id=%s)",
                step.get("step"), step["task_type"], task_id,
            )

        # Update audit entry with the full plan
        self.audit.log_event(
            actor="PlannerAgent",
            action_type="PLAN_SUBMITTED",
            input_context=description,
            output_content=json.dumps(task_ids),
            metadata={"trace_id": trace_id, "step_count": len(task_ids)},
        )

        self.logger.info(
            "Plan-and-Execute complete: %d subtask(s) queued (trace: %s).",
            len(task_ids), trace_id,
        )
        return {
            "status": "queued",
            "description": description,
            "plan": plan,
            "task_ids": task_ids,
            "step_count": len(task_ids),
            "trace_id": trace_id,
        }

    def get_plan_status(self, task_ids: list[str]) -> list[dict]:
        """
        Returns current status of each task in a previously submitted plan.

        Args:
            task_ids: List of task_id strings.

        Returns:
            List of status dicts from the TaskQueue.
        """
        from src.core.queue_manager import task_queue
        return [
            task_queue.get_status(tid) or {"task_id": tid, "status": "not_found"}
            for tid in task_ids
        ]


# ---------------------------------------------------------------------------
# Global access point
# ---------------------------------------------------------------------------
planner_agent = PlannerAgent()
