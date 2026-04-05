"""
Orchestrator Enhancement Routes
================================
API endpoints for all SOTA orchestrator capabilities:
  - Event streaming (SSE)
  - Budget management
  - Reflection engine
  - Plan selection
  - Agent spawning
  - Tool execution
  - Backtrack planning
  - Consensus voting
  - Memory-augmented planning
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Orchestrator"])


# ─── Pydantic Models ──────────────────────────────────────────────────

class BudgetSetRequest(BaseModel):
    scope: str
    max_tokens: int = 0
    max_cost_usd: float = 0.0
    warn_threshold: float = 0.8
    hard_stop: bool = True

class UsageRecordRequest(BaseModel):
    scope: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""

class ReflectRequest(BaseModel):
    task_description: str
    context: str = ""
    max_iterations: int = 3
    acceptance_threshold: float = 0.7

class SpawnRequest(BaseModel):
    role: str
    task: str
    context: str = ""
    parent_task_id: str = ""
    depth: int = 0

class ToolCallRequest(BaseModel):
    tool_name: str
    arguments: dict = Field(default_factory=dict)

class ConsensusRequest(BaseModel):
    question: str
    voters: List[str]
    context: str = ""
    method: str = "majority"

class PlanSelectRequest(BaseModel):
    task_description: str
    context: str = ""
    beam_width: int = 3
    apply_reflection: bool = True


# ─── SSE Event Stream ─────────────────────────────────────────────────

@router.get("/orchestrator/events/stream")
async def event_stream(event_types: str = ""):
    """SSE endpoint for real-time orchestrator events."""
    from src.core.event_bus import get_event_bus
    bus = get_event_bus()
    types = [t.strip() for t in event_types.split(",") if t.strip()] or None

    async def generate():
        async for sse in bus.stream(event_types=types):
            yield sse

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/orchestrator/events/history")
async def event_history(event_type: str = "", limit: int = 50):
    """Get recent event history."""
    from src.core.event_bus import get_event_bus
    bus = get_event_bus()
    events = bus.get_history(event_type=event_type or None, limit=limit)
    return {"events": events, "count": len(events)}


# ─── Budget Management ────────────────────────────────────────────────

@router.post("/orchestrator/budget")
async def set_budget(body: BudgetSetRequest):
    """Set budget for a scope."""
    from src.core.budget_manager import get_budget_manager, BudgetConfig
    bm = get_budget_manager()
    bm.set_budget(body.scope, BudgetConfig(
        max_tokens=body.max_tokens,
        max_cost_usd=body.max_cost_usd,
        warn_threshold=body.warn_threshold,
        hard_stop=body.hard_stop,
    ))
    return {"status": "configured", "scope": body.scope}


@router.post("/orchestrator/budget/record")
async def record_budget_usage(body: UsageRecordRequest):
    """Record token usage."""
    from src.core.budget_manager import get_budget_manager
    bm = get_budget_manager()
    usage = bm.record_usage(
        scope=body.scope,
        input_tokens=body.input_tokens,
        output_tokens=body.output_tokens,
        cost_usd=body.cost_usd,
        model=body.model,
    )
    return usage


@router.get("/orchestrator/budget/{scope}")
async def check_budget(scope: str):
    """Check budget status for a scope."""
    from src.core.budget_manager import get_budget_manager
    return get_budget_manager().check_budget(scope)


@router.get("/orchestrator/budget")
async def budget_overview():
    """Get all budget usage and top consumers."""
    from src.core.budget_manager import get_budget_manager
    bm = get_budget_manager()
    return {
        "stats": bm.get_stats(),
        "top_consumers": bm.get_top_consumers(limit=10),
    }


# ─── Reflection Engine ────────────────────────────────────────────────

@router.get("/orchestrator/reflection/stats")
async def reflection_stats():
    """Get reflection engine statistics."""
    from src.core.reflection_engine import get_reflection_engine
    return get_reflection_engine().get_stats()


@router.get("/orchestrator/reflection/recent")
async def reflection_recent(limit: int = 20):
    """List recent reflection results."""
    from src.core.reflection_engine import get_reflection_engine
    return {"results": get_reflection_engine().list_recent(limit=limit)}


@router.get("/orchestrator/reflection/{reflection_id}")
async def get_reflection(reflection_id: str):
    """Get a specific reflection result."""
    from src.core.reflection_engine import get_reflection_engine
    result = get_reflection_engine().get_result(reflection_id)
    if not result:
        raise HTTPException(404, "Reflection not found")
    return result


# ─── Plan Selector ────────────────────────────────────────────────────

@router.get("/orchestrator/plans/stats")
async def plan_selector_stats():
    """Get plan selector statistics."""
    from src.core.plan_selector import get_plan_selector
    return get_plan_selector().get_stats()


@router.get("/orchestrator/plans/recent")
async def plan_selector_recent(limit: int = 20):
    """List recent plan selections."""
    from src.core.plan_selector import get_plan_selector
    return {"results": get_plan_selector().list_recent(limit=limit)}


# ─── Agent Spawner ────────────────────────────────────────────────────

@router.post("/orchestrator/spawn", status_code=201)
async def spawn_agent(body: SpawnRequest):
    """Spawn a sub-agent dynamically."""
    from src.core.agent_spawner import get_agent_spawner
    result = get_agent_spawner().spawn(
        role=body.role,
        task=body.task,
        context=body.context,
        parent_task_id=body.parent_task_id,
        depth=body.depth,
    )
    return result


@router.get("/orchestrator/spawns")
async def list_spawns(parent_task_id: str = "", limit: int = 50):
    """List spawned agents."""
    from src.core.agent_spawner import get_agent_spawner
    return {
        "spawns": get_agent_spawner().list_spawns(
            parent_task_id=parent_task_id or None, limit=limit,
        ),
    }


@router.get("/orchestrator/spawns/stats")
async def spawner_stats():
    """Get agent spawner statistics."""
    from src.core.agent_spawner import get_agent_spawner
    return get_agent_spawner().get_stats()


# ─── Tool Executor ────────────────────────────────────────────────────

@router.get("/orchestrator/tools")
async def list_tools():
    """List available tools for agents."""
    from src.core.tool_executor import get_tool_executor
    return {"tools": get_tool_executor().list_tools()}


@router.post("/orchestrator/tools/execute")
async def execute_tool(body: ToolCallRequest):
    """Execute a tool."""
    from src.core.tool_executor import get_tool_executor
    call = get_tool_executor().execute(body.tool_name, body.arguments)
    return call.to_dict()


@router.get("/orchestrator/tools/history")
async def tool_history(limit: int = 50):
    """Get tool execution history."""
    from src.core.tool_executor import get_tool_executor
    return {"history": get_tool_executor().get_history(limit=limit)}


@router.get("/orchestrator/tools/stats")
async def tool_stats():
    """Get tool executor statistics."""
    from src.core.tool_executor import get_tool_executor
    return get_tool_executor().get_stats()


# ─── Backtrack Planner ────────────────────────────────────────────────

@router.get("/orchestrator/backtrack/records")
async def backtrack_records(limit: int = 20):
    """List backtrack records."""
    from src.core.backtrack_planner import get_backtrack_planner
    return {"records": get_backtrack_planner().list_records(limit=limit)}


@router.get("/orchestrator/backtrack/stats")
async def backtrack_stats():
    """Get backtrack planner statistics."""
    from src.core.backtrack_planner import get_backtrack_planner
    return get_backtrack_planner().get_stats()


# ─── Consensus Engine ─────────────────────────────────────────────────

@router.get("/orchestrator/consensus/results")
async def consensus_results(limit: int = 20):
    """List consensus results."""
    from src.core.consensus_engine import get_consensus_engine
    return {"results": get_consensus_engine().list_results(limit=limit)}


@router.get("/orchestrator/consensus/{consensus_id}")
async def get_consensus(consensus_id: str):
    """Get a specific consensus result."""
    from src.core.consensus_engine import get_consensus_engine
    result = get_consensus_engine().get_result(consensus_id)
    if not result:
        raise HTTPException(404, "Consensus round not found")
    return result


@router.get("/orchestrator/consensus/stats")
async def consensus_stats():
    """Get consensus engine statistics."""
    from src.core.consensus_engine import get_consensus_engine
    return get_consensus_engine().get_stats()


# ─── Memory Planner ───────────────────────────────────────────────────

@router.get("/orchestrator/memory-planner/stats")
async def memory_planner_stats():
    """Get memory-augmented planner statistics."""
    from src.core.memory_planner import get_memory_planner
    return get_memory_planner().get_stats()


# ─── Combined Stats ───────────────────────────────────────────────────

@router.get("/orchestrator/stats")
async def orchestrator_stats():
    """Get combined statistics for all orchestrator modules."""
    stats = {}
    try:
        from src.core.event_bus import get_event_bus
        stats["event_bus"] = get_event_bus().get_stats()
    except Exception:
        stats["event_bus"] = {}
    try:
        from src.core.budget_manager import get_budget_manager
        stats["budget"] = get_budget_manager().get_stats()
    except Exception:
        stats["budget"] = {}
    try:
        from src.core.reflection_engine import get_reflection_engine
        stats["reflection"] = get_reflection_engine().get_stats()
    except Exception:
        stats["reflection"] = {}
    try:
        from src.core.plan_selector import get_plan_selector
        stats["plan_selector"] = get_plan_selector().get_stats()
    except Exception:
        stats["plan_selector"] = {}
    try:
        from src.core.agent_spawner import get_agent_spawner
        stats["spawner"] = get_agent_spawner().get_stats()
    except Exception:
        stats["spawner"] = {}
    try:
        from src.core.tool_executor import get_tool_executor
        stats["tools"] = get_tool_executor().get_stats()
    except Exception:
        stats["tools"] = {}
    try:
        from src.core.backtrack_planner import get_backtrack_planner
        stats["backtrack"] = get_backtrack_planner().get_stats()
    except Exception:
        stats["backtrack"] = {}
    try:
        from src.core.consensus_engine import get_consensus_engine
        stats["consensus"] = get_consensus_engine().get_stats()
    except Exception:
        stats["consensus"] = {}
    try:
        from src.core.memory_planner import get_memory_planner
        stats["memory_planner"] = get_memory_planner().get_stats()
    except Exception:
        stats["memory_planner"] = {}
    return stats
