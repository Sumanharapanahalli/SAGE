"""
SAGE Starter — Analysis Workflow (LangGraph)
=============================================
A minimal two-node workflow that demonstrates the SAGE approval gate pattern:

  [analyze] → (interrupt) → [finalize] → END

The graph pauses after "analyze" so a human can review the AI's analysis
before the result is finalised. This mirrors the SAGE Lean Loop:
  SURFACE → CONTEXTUALIZE → PROPOSE → *DECIDE* → COMPOUND

Usage:
  POST /workflow/run  {"workflow_name": "analysis_workflow", "state": {"task": "..."}}
  # Returns {"status": "awaiting_approval", "run_id": "..."}
  POST /workflow/resume  {"run_id": "...", "feedback": {"approved": true, "comment": "LGTM"}}
  # Returns {"status": "completed", "result": {...}}

Replace analyze_node / finalize_node with your domain logic.
This file is intentionally simple — duplicate and customise per solution.
"""

from __future__ import annotations

import logging
from typing import TypedDict

logger = logging.getLogger("analysis_workflow")

# ---------------------------------------------------------------------------
# State definition
# ---------------------------------------------------------------------------

class AnalysisState(TypedDict, total=False):
    task: str           # Input: description of what to analyse
    analysis: str       # Output of analyze_node
    approved: bool      # Set by human via /workflow/resume
    comment: str        # Optional human comment
    final_output: str   # Produced by finalize_node after approval


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def analyze_node(state: AnalysisState) -> AnalysisState:
    """
    Run the SAGE analyst agent on the incoming task.
    Falls back to a stub if no LLM is configured.
    """
    task = state.get("task", "")
    analysis = ""
    try:
        from src.core.llm_gateway import llm_gateway
        analysis = llm_gateway.generate(
            prompt=f"Analyse the following and produce a concise structured summary:\n\n{task}",
            system_prompt="You are a precise analyst. Respond with a bullet-point summary.",
            trace_name="analysis_workflow.analyze",
        )
    except Exception as exc:
        logger.warning("LLM unavailable in analyze_node: %s", exc)
        analysis = f"[stub] Analysis of: {task}"

    return {**state, "analysis": analysis}


def finalize_node(state: AnalysisState) -> AnalysisState:
    """
    Produce the final output after human approval.
    If rejected (approved=False), records the rejection reason.
    """
    if not state.get("approved", False):
        final_output = f"[rejected] Human rejected the analysis. Comment: {state.get('comment', '')}"
    else:
        analysis = state.get("analysis", "")
        comment  = state.get("comment", "")
        final_output = analysis
        if comment:
            final_output = f"{analysis}\n\n[Human note] {comment}"

    try:
        from src.memory.vector_store import vector_memory
        vector_memory.add_feedback(
            original_analysis=state.get("analysis", ""),
            human_feedback=state.get("comment", "approved" if state.get("approved") else "rejected"),
            context=state.get("task", ""),
        )
    except Exception:
        pass

    return {**state, "final_output": final_output}


# ---------------------------------------------------------------------------
# Graph definition
# ---------------------------------------------------------------------------

try:
    from langgraph.graph import StateGraph, END

    _graph = StateGraph(AnalysisState)
    _graph.add_node("analyze", analyze_node)
    _graph.add_node("finalize", finalize_node)
    _graph.set_entry_point("analyze")
    _graph.add_edge("analyze", "finalize")
    _graph.add_edge("finalize", END)

    # Interrupt BEFORE finalize so the human can review analysis first
    workflow = _graph.compile(interrupt_before=["finalize"])

except ImportError:
    # langgraph not installed — expose a no-op stub so the module still loads
    class _StubWorkflow:
        def invoke(self, state, config=None):
            return {**state, "error": "langgraph not installed"}
        def get_state(self, config):
            return None

    workflow = _StubWorkflow()
    logger.debug("langgraph not installed — analysis_workflow using stub")
