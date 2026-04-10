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


# Module-level singleton (lazy to avoid circular imports)
_runner: Optional[AgentSDKRunner] = None


def get_agent_sdk_runner() -> AgentSDKRunner:
    global _runner
    if _runner is None:
        _runner = AgentSDKRunner()
    return _runner
