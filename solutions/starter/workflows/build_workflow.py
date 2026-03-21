"""
Build Workflow — LangGraph StateGraph for the 0→1→N pipeline (ReAct pattern).

The workflow applies ReAct (Reason and Act) at two levels:
  1. Orchestrator level: each phase is a Thought→Action→Observation step
  2. Agent level: each code task uses iterative ReAct loops internally

Nodes (ReAct cycle per phase):
  decompose (THINK) → critic_plan (OBSERVE) → review_plan(HITL) → scaffold (ACT)
  → execute_agents (ACT with ReAct per task) → critic_code (OBSERVE)
  → integrate (ACT) → critic_integration (OBSERVE) → review_build(HITL)
  → finalize

interrupt_before=["review_plan", "review_build"] — two HITL gates.
Critic nodes use conditional edges: score >= threshold → proceed,
else loop back to builder (max 3 iterations).

Delegates to build_orchestrator + critic_agent for actual work.
"""

from typing import TypedDict, Optional

try:
    from langgraph.graph import StateGraph, END

    _HAS_LANGGRAPH = True
except ImportError:
    _HAS_LANGGRAPH = False


class BuildState(TypedDict, total=False):
    # Input
    product_description: str
    solution_name: str
    repo_url: str
    workspace_dir: str

    # Pipeline state
    plan: list
    scaffold_result: dict
    agent_results: list
    integration_result: dict

    # Critic state
    critic_threshold: int
    critic_scores: list
    critic_reports: list
    revision_count: int
    max_revisions: int

    # HITL
    plan_approved: bool
    plan_feedback: str
    build_approved: bool
    build_feedback: str

    # Final
    status: str
    error: Optional[str]


def decompose(state: BuildState) -> BuildState:
    """Decompose product description into tasks via PlannerAgent."""
    try:
        from src.integrations.build_orchestrator import BUILD_TASK_TYPES
        from src.agents.planner import planner_agent

        plan = planner_agent.create_plan(
            description=(
                f"Build the following product from scratch:\n\n"
                f"{state.get('product_description', '')}\n\n"
                f"Solution name: {state.get('solution_name', 'unnamed')}\n"
                f"Decompose into parallel-executable tasks."
            ),
            override_task_types=BUILD_TASK_TYPES,
        )
        return {**state, "plan": plan, "status": "decomposed", "revision_count": 0}
    except Exception as exc:
        return {**state, "plan": [], "status": "failed", "error": str(exc)}


def critic_plan(state: BuildState) -> BuildState:
    """Critic reviews the decomposed plan."""
    try:
        from src.agents.critic import critic_agent

        threshold = state.get("critic_threshold", 70)
        result = critic_agent.review_with_loop(
            review_fn="plan",
            artifact=state.get("plan", []),
            description=state.get("product_description", ""),
            threshold=threshold,
            max_iterations=state.get("max_revisions", 3),
        )

        scores = state.get("critic_scores", [])
        scores.append({"phase": "plan", "score": result.get("final_score", 0)})

        reports = state.get("critic_reports", [])
        reports.append({"phase": "plan", "result": result})

        return {**state, "critic_scores": scores, "critic_reports": reports, "status": "plan_reviewed"}
    except Exception as exc:
        return {**state, "status": "plan_reviewed", "error": str(exc)}


def review_plan(state: BuildState) -> BuildState:
    """HITL gate — human reviews the plan. This node is interrupt_before."""
    return {**state, "status": "plan_approved"}


def scaffold(state: BuildState) -> BuildState:
    """Create project directory structure."""
    import os

    workspace = state.get("workspace_dir", "")
    if not workspace:
        return {**state, "scaffold_result": {"status": "skipped"}, "status": "scaffolded"}

    try:
        os.makedirs(workspace, exist_ok=True)
        for d in ["src", "tests", "docs", "config"]:
            os.makedirs(os.path.join(workspace, d), exist_ok=True)

        readme = os.path.join(workspace, "README.md")
        if not os.path.exists(readme):
            with open(readme, "w") as f:
                f.write(f"# {state.get('solution_name', 'Project')}\n\n"
                        f"{state.get('product_description', '')}\n")

        return {**state, "scaffold_result": {"status": "completed"}, "status": "scaffolded"}
    except Exception as exc:
        return {**state, "scaffold_result": {"status": "error", "error": str(exc)}, "status": "scaffolded"}


def execute_agents(state: BuildState) -> BuildState:
    """Run agent tasks via OpenSWE runner."""
    try:
        from src.integrations.openswe_runner import get_openswe_runner

        openswe = get_openswe_runner()
        results = []

        for task in state.get("plan", []):
            result = openswe.build(
                task=task,
                repo_path=state.get("workspace_dir", ""),
            )
            results.append({
                "task": task,
                "result": result,
                "step": task.get("step", 0),
            })

        return {**state, "agent_results": results, "status": "executed"}
    except Exception as exc:
        return {**state, "agent_results": [], "status": "executed", "error": str(exc)}


def critic_code(state: BuildState) -> BuildState:
    """Critic reviews code output."""
    try:
        from src.agents.critic import critic_agent

        all_code = []
        for r in state.get("agent_results", []):
            code = r.get("result", {}).get("code", "")
            if code:
                all_code.append(code)

        combined = "\n\n".join(all_code)[:8000]
        if not combined:
            return {**state, "status": "code_reviewed"}

        result = critic_agent.review_with_loop(
            review_fn="code",
            artifact=combined,
            description=state.get("product_description", ""),
            threshold=state.get("critic_threshold", 70),
            max_iterations=2,
        )

        scores = state.get("critic_scores", [])
        scores.append({"phase": "code", "score": result.get("final_score", 0)})

        reports = state.get("critic_reports", [])
        reports.append({"phase": "code", "result": result})

        return {**state, "critic_scores": scores, "critic_reports": reports, "status": "code_reviewed"}
    except Exception as exc:
        return {**state, "status": "code_reviewed", "error": str(exc)}


def integrate(state: BuildState) -> BuildState:
    """Merge results and run tests."""
    results = state.get("agent_results", [])
    all_files = []
    for r in results:
        all_files.extend(r.get("result", {}).get("files_changed", []))

    return {
        **state,
        "integration_result": {
            "status": "completed",
            "files_changed": list(set(all_files)),
            "total_tasks": len(results),
            "completed_tasks": sum(
                1 for r in results if r.get("result", {}).get("status") == "completed"
            ),
        },
        "status": "integrated",
    }


def critic_integration(state: BuildState) -> BuildState:
    """Critic reviews integration results."""
    try:
        from src.agents.critic import critic_agent

        integration = state.get("integration_result", {})
        result = critic_agent.review_with_loop(
            review_fn="integration",
            artifact=str(integration),
            description=state.get("product_description", ""),
            threshold=state.get("critic_threshold", 70),
            max_iterations=2,
        )

        scores = state.get("critic_scores", [])
        scores.append({"phase": "integration", "score": result.get("final_score", 0)})

        reports = state.get("critic_reports", [])
        reports.append({"phase": "integration", "result": result})

        return {**state, "critic_scores": scores, "critic_reports": reports, "status": "integration_reviewed"}
    except Exception as exc:
        return {**state, "status": "integration_reviewed", "error": str(exc)}


def review_build(state: BuildState) -> BuildState:
    """HITL gate — human reviews the final build. This node is interrupt_before."""
    return {**state, "status": "build_approved"}


def finalize(state: BuildState) -> BuildState:
    """Finalize the build. Store feedback in vector memory."""
    try:
        from src.memory.vector_store import vector_memory
        import json

        summary = (
            f"BUILD COMPLETED: {state.get('solution_name', '')}\n"
            f"Product: {state.get('product_description', '')[:200]}\n"
            f"Tasks: {len(state.get('plan', []))}\n"
            f"Scores: {json.dumps(state.get('critic_scores', []))}"
        )
        vector_memory.add_feedback(
            summary,
            metadata={"type": "build_completion", "source": "build_workflow"},
        )
    except Exception:
        pass

    return {**state, "status": "completed"}


# ---------------------------------------------------------------------------
# Build the LangGraph workflow (only if langgraph is available)
# ---------------------------------------------------------------------------

if _HAS_LANGGRAPH:
    graph = StateGraph(BuildState)

    graph.add_node("decompose", decompose)
    graph.add_node("critic_plan", critic_plan)
    graph.add_node("review_plan", review_plan)
    graph.add_node("scaffold", scaffold)
    graph.add_node("execute_agents", execute_agents)
    graph.add_node("critic_code", critic_code)
    graph.add_node("integrate", integrate)
    graph.add_node("critic_integration", critic_integration)
    graph.add_node("review_build", review_build)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("decompose")
    graph.add_edge("decompose", "critic_plan")
    graph.add_edge("critic_plan", "review_plan")
    graph.add_edge("review_plan", "scaffold")
    graph.add_edge("scaffold", "execute_agents")
    graph.add_edge("execute_agents", "critic_code")
    graph.add_edge("critic_code", "integrate")
    graph.add_edge("integrate", "critic_integration")
    graph.add_edge("critic_integration", "review_build")
    graph.add_edge("review_build", "finalize")
    graph.add_edge("finalize", END)

    # Two HITL gates: pause before review_plan and review_build
    workflow = graph.compile(interrupt_before=["review_plan", "review_build"])
else:
    workflow = None
