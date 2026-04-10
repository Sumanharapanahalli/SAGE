"""Bridge from sync agent code to the async AgentSDKRunner."""

from __future__ import annotations

import asyncio

from src.core.agent_sdk_runner import get_agent_sdk_runner


def run_agent(
    role_id: str,
    task: str,
    context: str = "",
    *,
    task_type: str | None = None,
) -> str:
    runner = get_agent_sdk_runner()
    result = asyncio.run(
        runner.run(
            role_id=role_id,
            task=task,
            context=context,
            task_type=task_type,
        )
    )
    return result.get("raw_response", "") or result.get("summary", "") or ""
