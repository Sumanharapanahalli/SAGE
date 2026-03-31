"""AutoResearch & Meta-Optimizer endpoints — /research/*, /meta/*"""

from fastapi import APIRouter, BackgroundTasks, Request

router = APIRouter(tags=["research"])


# ── Meta-Optimizer ───────────────────────────────────────────────────

@router.post("/meta/optimize")
async def meta_optimize(request: Request):
    """Run a meta-optimization iteration for a runner."""
    body = await request.json()
    runner_name = body.get("runner_name", "openswe")
    from src.core.meta_optimizer import MetaOptimizer
    optimizer = MetaOptimizer()
    result = optimizer.run_iteration(runner_name=runner_name)
    return result


@router.get("/meta/history")
async def meta_history(runner_name: str = ""):
    """Get meta-optimization iteration history."""
    from src.core.meta_optimizer import MetaOptimizer
    optimizer = MetaOptimizer()
    return {"history": optimizer.get_history(runner_name=runner_name)}


@router.get("/meta/stats")
async def meta_stats(runner_name: str = ""):
    """Get meta-optimizer statistics."""
    from src.core.meta_optimizer import MetaOptimizer
    optimizer = MetaOptimizer()
    return optimizer.stats(runner_name=runner_name)


@router.get("/meta/best")
async def meta_best(runner_name: str = ""):
    """Get the best optimization iteration for a runner."""
    from src.core.meta_optimizer import MetaOptimizer
    optimizer = MetaOptimizer()
    best = optimizer.get_best_iteration(runner_name=runner_name)
    return best or {"message": "No iterations found"}


# ── AutoResearch ─────────────────────────────────────────────────────

@router.post("/research/experiment")
async def research_experiment(request: Request):
    """Run a single autonomous experiment."""
    body = await request.json()
    workspace = body.get("workspace", ".")
    metric_name = body.get("metric_name", "val_loss")
    run_command = body.get("run_command", "")
    budget_s = body.get("budget_s")
    direction = body.get("direction", "lower")
    from src.core.auto_research import AutoResearchEngine
    engine = AutoResearchEngine()
    result = engine.run_experiment(
        workspace=workspace,
        metric_name=metric_name,
        run_command=run_command,
        budget_s=budget_s,
        direction=direction,
    )
    return result


@router.post("/research/session")
async def research_session(request: Request, background_tasks: BackgroundTasks):
    """Start a research session (N experiments in a loop)."""
    body = await request.json()
    workspace = body.get("workspace", ".")
    metric_name = body.get("metric_name", "val_loss")
    run_command = body.get("run_command", "")
    max_experiments = body.get("max_experiments", 10)
    budget_s = body.get("budget_s")
    direction = body.get("direction", "lower")
    from src.core.auto_research import AutoResearchEngine
    engine = AutoResearchEngine()
    result = engine.run_session(
        workspace=workspace,
        metric_name=metric_name,
        run_command=run_command,
        max_experiments=max_experiments,
        budget_s=budget_s,
        direction=direction,
    )
    return result


@router.get("/research/results")
async def research_results(limit: int = 100):
    """Get experiment results."""
    from src.core.auto_research import AutoResearchEngine
    engine = AutoResearchEngine()
    return {"results": engine.get_results(limit=limit)}


@router.get("/research/best")
async def research_best(direction: str = "lower"):
    """Get the best experiment result."""
    from src.core.auto_research import AutoResearchEngine
    engine = AutoResearchEngine()
    best = engine.get_best_result(direction=direction)
    return best or {"message": "No experiments found"}


@router.get("/research/stats")
async def research_stats():
    """Get experiment analytics."""
    from src.core.auto_research import AutoResearchEngine
    engine = AutoResearchEngine()
    return engine.stats()


@router.get("/research/program")
async def research_load_program(path: str = "program.md"):
    """Load a research program (Markdown-as-skill) to guide experiment hypotheses."""
    try:
        from src.core.auto_research import AutoResearchEngine
        engine = AutoResearchEngine()
        program = engine.load_program(path)
        return {"path": path, "program": program, "loaded": bool(program)}
    except FileNotFoundError:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Research program not found: {path}")
    except Exception as exc:
        return {"error": str(exc)}
