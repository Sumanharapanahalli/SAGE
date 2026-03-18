"""
swe_workflow.py — SWE agent workflow for the Reflect solution.
Agent-first: runs autonomously. See solutions/starter/workflows/swe_workflow.py for full docs.
"""
# Reflect uses the same agent-first SWE workflow as starter.
# Import and re-export so LangGraphRunner discovers it.
from solutions.starter.workflows.swe_workflow import (  # noqa: F401
    workflow,
    SWEState,
    _explore_repo,
    _plan_implementation,
    _implement,
    _create_pr,
)
