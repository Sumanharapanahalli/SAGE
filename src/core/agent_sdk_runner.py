"""Bridge layer between SAGE agents and the Claude Agent SDK.

When the SDK is available (claude_agent_sdk installed AND provider is
claude-code), this runner translates SAGE role definitions into SDK
AgentDefinition objects, wires compliance hooks, and executes via the
SDK's built-in tool loop. Otherwise it falls back to the existing
LLMGateway.generate() path — no behavior change for non-SDK providers.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Literal

# Regulatory hooks import with graceful fallback
try:
    from src.core.regulatory import automation_bias_hook, transparency_validator_hook
    REGULATORY_AVAILABLE = True
except ImportError:
    REGULATORY_AVAILABLE = False

logger = logging.getLogger(__name__)
if not REGULATORY_AVAILABLE:
    logger.info("Regulatory hooks not available - install regulatory dependencies if needed")


# Task type → default SDK tool set (used when role has no sdk_tools field)
_TASK_TYPE_TOOLS: Dict[str, List[str]] = {
    "analysis": ["Read", "Grep", "Glob"],
    "review": ["Read", "Grep", "Glob"],
    "code_review": ["Read", "Edit", "Write", "Grep", "Glob"],
    "implementation": ["Read", "Edit", "Write", "Grep", "Glob"],
    "code_generation": ["Read", "Edit", "Write", "Bash", "Grep", "Glob"],
    "testing": ["Read", "Edit", "Write", "Bash", "Grep", "Glob"],
    "research": ["Read", "Grep", "Glob", "WebSearch", "WebFetch"],
    "investigation": ["Read", "Grep", "Glob", "WebSearch", "WebFetch"],
    "planning": ["Read", "Grep", "Glob", "Agent"],
    "decomposition": ["Read", "Grep", "Glob", "Agent"],
}


class AgentSDKRunner:
    """Singleton bridge between SAGE agents and the Agent SDK."""

    _instance: Optional["AgentSDKRunner"] = None

    def __new__(cls) -> "AgentSDKRunner":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        from src.core.llm_gateway import llm_gateway
        self._llm_gateway = llm_gateway
        self._initialized = True

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def is_sdk_available(self) -> bool:
        """True when the gateway reports SDK is available."""
        return bool(getattr(self._llm_gateway, "sdk_available", False))

    # ------------------------------------------------------------------
    # Role translation
    # ------------------------------------------------------------------

    def _resolve_tools(
        self,
        role_config: Dict[str, Any],
        task_type: Optional[str],
    ) -> List[str]:
        """Determine SDK tool set for a role.

        Resolution order:
          1. Per-role `sdk_tools` field in role_config
          2. Task-type default mapping
          3. Empty list (role has no SDK tools)
        """
        per_role = role_config.get("sdk_tools")
        if isinstance(per_role, list):
            return list(per_role)

        if task_type and task_type in _TASK_TYPE_TOOLS:
            return list(_TASK_TYPE_TOOLS[task_type])

        return []

    def _build_agent_definition(
        self,
        role_id: str,
        role_config: Dict[str, Any],
        task_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build an SDK AgentDefinition-compatible dict from a SAGE role."""
        return {
            "description": role_config.get("description", role_config.get("name", role_id)),
            "prompt": role_config.get("system_prompt", ""),
            "tools": self._resolve_tools(role_config, task_type),
        }

    def _load_role(self, role_id: str) -> Optional[Dict[str, Any]]:
        """Look up a role definition in the active project config."""
        from src.core.project_loader import project_config
        roles = project_config.get_prompts().get("roles", {})
        return roles.get(role_id)

    async def run(
        self,
        role_id: str,
        task: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a SAGE agent role. Dispatches to SDK when available, else fallback.

        Args:
            role_id: Role key in solution prompts.yaml (e.g. "security_analyst").
            task: The task text for the agent.
            context: Optional context — may include `task_type`, `trace_id`, `actor`.

        Returns:
            Dict with keys: role_id, status, result (or error), trace_id.
        """
        role_config = self._load_role(role_id)
        if role_config is None:
            return {
                "role_id": role_id,
                "status": "error",
                "error": f"Unknown role: {role_id}",
            }

        if not self.is_sdk_available():
            return await self._run_via_gateway(role_id, role_config, task, context)

        return await self._run_via_sdk(role_id, role_config, task, context)

    async def run_with_evolution(
        self,
        role_id: str,
        task: str,
        evolver_type: Literal["prompt", "code", "build"],
        config: dict,
        context: dict = None
    ) -> dict:
        """
        Execute agent role with evolutionary improvement.

        Runs evolution cycles to improve prompts/code/builds, then executes
        with the best evolved candidate. Uses two-gate HITL model:
        - Gate 1: Approve evolution goal and parameters
        - Gate 2: Approve final evolved result
        """
        from .evolution.orchestrator import EvolutionOrchestrator
        from .evolution.program_db import get_evolution_db_path, ProgramDatabase

        # Validate evolver type
        valid_types = {"prompt", "code", "build"}
        if evolver_type not in valid_types:
            raise ValueError(f"evolver_type must be one of {valid_types}, got {evolver_type}")

        # Initialize evolution infrastructure
        db_path = get_evolution_db_path()
        db = ProgramDatabase(db_path)

        # Get solution name from environment (for orchestrator)
        import os
        solution_name = os.environ.get("SAGE_PROJECT", "default")

        # Extract evolution parameters from config
        max_generations = config.get("generations", 3)
        population_size = config.get("population", 10)

        orchestrator = EvolutionOrchestrator(
            db=db,
            solution_name=solution_name,
            max_generations=max_generations,
            population_size=population_size
        )

        # Route to appropriate evolution method
        if evolver_type == "prompt":
            # For prompt evolution, evolve the system prompt for this role
            result = await orchestrator.evolve_prompt(role_id, task, context or {})
        elif evolver_type == "code":
            # For code evolution, evolve source code
            code_file = config.get("code_file", "main.py")
            code_content = (context or {}).get("code", "# Empty code file\n")
            result = await orchestrator.evolve_code(code_file, code_content, context or {})
        elif evolver_type == "build":
            # For build evolution, evolve build plans
            build_file = config.get("build_file", "build.yaml")
            build_plan = (context or {}).get("build_plan", {"steps": []})
            result = await orchestrator.evolve_build_plan(build_file, build_plan, context or {})
        else:
            raise ValueError(f"Unknown evolver_type: {evolver_type}")

        logger.info(f"Evolution completed for {role_id}: {evolver_type} evolution")
        return result

    async def _run_via_gateway(
        self,
        role_id: str,
        role_config: Dict[str, Any],
        task: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Fallback path — uses existing LLMGateway.generate() directly."""
        system_prompt = role_config.get("system_prompt", "You are a helpful assistant.")
        trace_id = context.get("trace_id", "")
        agent_name = context.get("actor", f"role:{role_id}")

        try:
            response_text = self._llm_gateway.generate(
                prompt=task,
                system_prompt=system_prompt,
                trace_name=f"agent_sdk_runner_fallback_{role_id}",
                trace_id=trace_id,
                agent_name=agent_name,
            )
            return {
                "role_id": role_id,
                "role_name": role_config.get("name", role_id),
                "status": "fallback_gateway",
                "result": response_text,
                "trace_id": trace_id,
            }
        except Exception as exc:
            logger.exception("AgentSDKRunner gateway fallback failed for role=%s", role_id)
            return {
                "role_id": role_id,
                "status": "error",
                "error": str(exc),
                "trace_id": trace_id,
            }

    async def _run_via_sdk(
        self,
        role_id: str,
        role_config: Dict[str, Any],
        task: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """SDK execution path with Gate 1 (goal alignment) gating."""
        from src.core.proposal_store import get_proposal_store, RiskClass
        import asyncio
        import uuid

        trace_id = context.get("trace_id") or str(uuid.uuid4())
        store = get_proposal_store()

        agent_def = self._build_agent_definition(
            role_id, role_config, task_type=context.get("task_type")
        )

        # ---------------- Gate 1: Goal Alignment ----------------
        goal_proposal = store.create(
            action_type="goal_alignment",
            risk_class=RiskClass.STATEFUL,
            payload={
                "role_id": role_id,
                "role_name": role_config.get("name", role_id),
                "task": task,
                "intended_approach": agent_def["prompt"][:500],
                "tools_requested": agent_def["tools"],
                "task_type": context.get("task_type"),
            },
            description=f"Goal alignment for role={role_id}",
            proposed_by=context.get("actor", "agent_sdk_runner"),
        )

        gate1_timeout = float(context.get("gate1_timeout_seconds", 1800))
        loop = asyncio.get_event_loop()
        decision = await loop.run_in_executor(
            None, store.await_decision, goal_proposal.trace_id, gate1_timeout
        )

        if decision is None:
            return {
                "role_id": role_id,
                "status": "timeout_at_goal",
                "trace_id": trace_id,
                "proposal_id": goal_proposal.trace_id,
            }
        if decision.status == "rejected":
            return {
                "role_id": role_id,
                "status": "rejected_at_goal",
                "reason": decision.feedback,
                "trace_id": trace_id,
                "proposal_id": goal_proposal.trace_id,
            }

        # ---------------- SDK execution ----------------
        try:
            result_text = await self._run_sdk_query(
                agent_def=agent_def,
                task=task,
                trace_id=trace_id,
            )
        except ImportError:
            logger.warning("claude_agent_sdk import failed at runtime; falling back")
            return await self._run_via_gateway(role_id, role_config, task, context)
        except Exception as exc:
            logger.exception("SDK query failed for role=%s", role_id)
            return {
                "role_id": role_id,
                "status": "error",
                "error": str(exc),
                "trace_id": trace_id,
            }

        # ---------------- Gate 2: Result Approval ----------------
        from src.core.sdk_change_tracker import sdk_change_tracker
        changes = sdk_change_tracker.get_session_changes(trace_id)

        result_proposal = store.create(
            action_type="result_approval",
            risk_class=RiskClass.STATEFUL,
            payload={
                "role_id": role_id,
                "task": task,
                "result_summary": (result_text or "")[:2000],
                "files_created": list(changes.created),
                "files_modified": list(changes.modified),
                "files_deleted": list(changes.deleted),
                "commands_run": list(changes.bash_commands),
            },
            description=f"Result approval for role={role_id}",
            proposed_by=context.get("actor", "agent_sdk_runner"),
        )

        gate2_timeout = float(context.get("gate2_timeout_seconds", 3600))
        result_decision = await loop.run_in_executor(
            None, store.await_decision, result_proposal.trace_id, gate2_timeout
        )

        # Clear session tracker regardless of decision
        sdk_change_tracker.clear_session(trace_id)

        if result_decision is None:
            return {
                "role_id": role_id,
                "status": "timeout_at_result",
                "trace_id": trace_id,
                "proposal_id": result_proposal.trace_id,
            }
        if result_decision.status == "rejected":
            # Feed rejection into vector memory (compounding intelligence)
            try:
                from src.memory.vector_store import vector_memory
                vector_memory.add_feedback(
                    result_decision.feedback or "rejected",
                    metadata={"phase": "result_approval", "trace_id": trace_id,
                              "role_id": role_id},
                )
            except Exception:
                logger.debug("vector_memory feedback ingest skipped")

            return {
                "role_id": role_id,
                "status": "rejected_at_result",
                "reason": result_decision.feedback,
                "trace_id": trace_id,
                "proposal_id": result_proposal.trace_id,
            }

        return {
            "role_id": role_id,
            "role_name": role_config.get("name", role_id),
            "status": "success",
            "result": result_text,
            "trace_id": trace_id,
        }

    async def _run_sdk_query(
        self,
        agent_def: Dict[str, Any],
        task: str,
        trace_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Execute the SDK query loop with regulatory hooks."""
        from claude_agent_sdk import query, ClaudeAgentOptions  # type: ignore
        from src.core.sdk_hooks import (
            destructive_op_hook,
            budget_check_hook,
            pii_filter_hook,
            audit_logger_hook,
            change_tracker_hook,
        )

        # Build hook configuration including regulatory hooks
        pre_tool_hooks = [
            destructive_op_hook,
            budget_check_hook,
            pii_filter_hook,
        ]

        post_tool_hooks = [
            audit_logger_hook,
            change_tracker_hook,
        ]

        # Add regulatory hooks when enabled and available
        if REGULATORY_AVAILABLE and self._is_regulatory_enabled(context):
            pre_tool_hooks.append(automation_bias_hook)
            post_tool_hooks.append(transparency_validator_hook)
            logger.info("Regulatory hooks enabled for this execution")

        messages_collected: List[str] = []
        options = ClaudeAgentOptions(
            system_prompt=agent_def["prompt"],
            allowed_tools=agent_def["tools"],
            permission_mode="acceptEdits",
            hooks={
                "PreToolUse": pre_tool_hooks,
                "PostToolUse": post_tool_hooks,
            },
        )
        async for message in query(prompt=task, options=options):
            if hasattr(message, "result"):
                messages_collected.append(str(message.result))
        return "\n".join(messages_collected)

    def _is_regulatory_enabled(self, context: Optional[Dict[str, Any]] = None) -> bool:
        """Check if regulatory features are enabled for this solution."""
        # Check if intended_purpose is configured in project.yaml
        from src.core.project_loader import project_config

        try:
            project_data = project_config.get_project_data()
            has_intended_purpose = "intended_purpose" in project_data
        except:
            has_intended_purpose = False

        # Also check context for explicit regulatory flag
        context_flag = False
        if context:
            context_flag = context.get("regulatory_enabled", False)

        return has_intended_purpose or context_flag


# Module-level singleton (lazy to avoid circular imports)
_runner: Optional[AgentSDKRunner] = None


def get_agent_sdk_runner() -> AgentSDKRunner:
    global _runner
    if _runner is None:
        _runner = AgentSDKRunner()
    return _runner
