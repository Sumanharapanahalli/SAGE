"""
swe_workflow.py — SWE agent workflow for the MedTech solution.

COMPLIANCE MODE: This solution has ISO 13485 compliance requirements.
Two interrupt_before gates are active:
  1. Before implement: human reviews the implementation plan
  2. Before create_pr: human reviews the diff before code is pushed

This is NOT the default — only regulated solutions use interrupt gates.
"""
from __future__ import annotations
import os
import logging
import re
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END

# Re-use the same node functions from starter
from solutions.starter.workflows.swe_workflow import (
    SWEState,
    _explore_repo,
    _plan_implementation,
    _implement,
    _create_pr,
)

logger = logging.getLogger(__name__)

# ─── Compliance graph (interrupt_before both action nodes) ───────────────────
graph = StateGraph(SWEState)
graph.add_node("explore_repo", _explore_repo)
graph.add_node("plan_implementation", _plan_implementation)
graph.add_node("implement", _implement)
graph.add_node("create_pr", _create_pr)

graph.set_entry_point("explore_repo")
graph.add_edge("explore_repo", "plan_implementation")
graph.add_edge("plan_implementation", "implement")
graph.add_edge("implement", "create_pr")
graph.add_edge("create_pr", END)

# Compliance: pause for human review before touching code and before creating PR
workflow = graph.compile(interrupt_before=["implement", "create_pr"])
