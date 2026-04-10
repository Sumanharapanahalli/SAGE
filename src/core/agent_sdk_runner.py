"""Bridge layer between SAGE agents and the Claude Agent SDK.

When the SDK is available (claude_agent_sdk installed AND provider is
claude-code), this runner translates SAGE role definitions into SDK
AgentDefinition objects, wires compliance hooks, and executes via the
SDK's built-in tool loop. Otherwise it falls back to the existing
LLMGateway.generate() path — no behavior change for non-SDK providers.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


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
        """SDK execution path — stub in Task 7, Gate 1/2 wiring lands in Task 8."""
        # Lazy import so the module loads without claude_agent_sdk installed
        try:
            from claude_agent_sdk import query, ClaudeAgentOptions  # type: ignore
        except ImportError:
            logger.warning("claude_agent_sdk import failed at runtime; falling back")
            return await self._run_via_gateway(role_id, role_config, task, context)

        agent_def = self._build_agent_definition(
            role_id, role_config, task_type=context.get("task_type")
        )

        trace_id = context.get("trace_id", "")
        messages_collected: List[str] = []

        try:
            options = ClaudeAgentOptions(
                system_prompt=agent_def["prompt"],
                allowed_tools=agent_def["tools"],
                permission_mode="acceptEdits",
            )
            async for message in query(prompt=task, options=options):
                if hasattr(message, "result"):
                    messages_collected.append(str(message.result))

            return {
                "role_id": role_id,
                "role_name": role_config.get("name", role_id),
                "status": "success",
                "result": "\n".join(messages_collected) if messages_collected else "",
                "trace_id": trace_id,
            }
        except Exception as exc:
            logger.exception("AgentSDKRunner SDK path failed for role=%s", role_id)
            return {
                "role_id": role_id,
                "status": "error",
                "error": str(exc),
                "trace_id": trace_id,
            }


# Module-level singleton (lazy to avoid circular imports)
_runner: Optional[AgentSDKRunner] = None


def get_agent_sdk_runner() -> AgentSDKRunner:
    global _runner
    if _runner is None:
        _runner = AgentSDKRunner()
    return _runner
