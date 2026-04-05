"""
SAGE Memory-Augmented Planner — RAG-in-the-Loop Planning
=========================================================

Before decomposing a task, searches collective memory and past build
results for similar successful plans. Injects relevant patterns as
few-shot examples into the planning context.

Pattern: Voyager (MineDojo) skill library + Memento retrieval
"""

import logging
import threading
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class MemoryPlanner:
    """Augments planning with historical learnings and past plan structures."""

    def __init__(self, max_examples: int = 5, min_confidence: float = 0.3):
        self._max_examples = max_examples
        self._min_confidence = min_confidence
        self._plan_history: list[dict] = []  # past successful plans
        self._lock = threading.Lock()

    def augment_context(self, task_description: str, solution: str = "") -> str:
        """
        Search collective memory and plan history for relevant context.
        Returns augmented context string to prepend to planning prompt.
        """
        sections = []

        # 1. Search collective learnings
        learnings = self._search_learnings(task_description, solution)
        if learnings:
            lines = []
            for l in learnings:
                lines.append(
                    f"- [{l.get('topic', 'general')}] {l.get('title', '')}: "
                    f"{l.get('content', '')[:200]}"
                )
            sections.append(
                "## Relevant learnings from other agents\n" + "\n".join(lines)
            )

        # 2. Search past successful plans
        similar_plans = self._find_similar_plans(task_description)
        if similar_plans:
            lines = []
            for p in similar_plans:
                task_count = len(p.get("tasks", []))
                lines.append(
                    f"- Plan '{p.get('name', 'unnamed')}' ({task_count} tasks): "
                    f"{p.get('description', '')[:150]}"
                )
                # Include task type sequence as pattern
                task_types = [t.get("task_type", "") for t in p.get("tasks", [])[:5]]
                if task_types:
                    lines.append(f"  Task sequence: {' → '.join(task_types)}")
            sections.append(
                "## Similar successful plans from history\n" + "\n".join(lines)
            )

        # 3. Search vector memory for domain patterns
        domain_hits = self._search_domain_memory(task_description, solution)
        if domain_hits:
            lines = [f"- {h[:200]}" for h in domain_hits]
            sections.append(
                "## Domain knowledge from memory\n" + "\n".join(lines)
            )

        if not sections:
            return ""

        return (
            "--- Memory-Augmented Context (from past experience) ---\n"
            + "\n\n".join(sections)
            + "\n--- End of memory context ---\n"
        )

    def record_plan(self, plan: dict) -> None:
        """Record a successful plan for future reference."""
        plan_record = {
            "name": plan.get("name", ""),
            "description": plan.get("description", ""),
            "tasks": plan.get("tasks", []),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "solution": plan.get("solution", ""),
            "score": plan.get("score", 0.0),
        }
        with self._lock:
            self._plan_history.append(plan_record)
            # Keep bounded
            if len(self._plan_history) > 100:
                self._plan_history = self._plan_history[-100:]

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "recorded_plans": len(self._plan_history),
                "max_examples": self._max_examples,
                "min_confidence": self._min_confidence,
            }

    # ── Private search methods ────────────────────────────────────────

    def _search_learnings(self, query: str, solution: str = "") -> list[dict]:
        """Search collective memory for relevant learnings."""
        try:
            from src.core.collective_memory import get_collective_memory
            cm = get_collective_memory()
            results = cm.search_learnings(
                query=query, solution=solution or None,
                limit=self._max_examples,
            )
            return [r for r in results
                    if r.get("confidence", 0) >= self._min_confidence]
        except Exception:
            return []

    def _find_similar_plans(self, description: str) -> list[dict]:
        """Find similar past plans by keyword matching."""
        desc_lower = description.lower()
        keywords = set(desc_lower.split())

        scored = []
        with self._lock:
            for plan in self._plan_history:
                plan_text = f"{plan.get('name', '')} {plan.get('description', '')}".lower()
                overlap = sum(1 for kw in keywords if kw in plan_text)
                if overlap > 0:
                    scored.append((overlap, plan))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored[:self._max_examples]]

    def _search_domain_memory(self, query: str, solution: str = "") -> list[str]:
        """Search solution-specific vector memory."""
        try:
            from src.memory.vector_store import VectorMemory
            vm = VectorMemory(explicit_solution=solution) if solution else VectorMemory()
            return vm.search(query, k=3)
        except Exception:
            return []


# ──────────────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────────────

_memory_planner: Optional[MemoryPlanner] = None
_mp_lock = threading.Lock()


def get_memory_planner() -> MemoryPlanner:
    global _memory_planner
    if _memory_planner is None:
        with _mp_lock:
            if _memory_planner is None:
                _memory_planner = MemoryPlanner()
    return _memory_planner
