"""
SAGE Plan Selector — Beam Search for Optimal Plans
====================================================

Instead of generating one plan and reviewing it, generates N candidate
plans in parallel, scores each with the critic, and selects the best.
Optionally applies reflection to improve the top candidate.

Pattern: Tree of Thought (Yao et al.), MCTS-inspired beam search
"""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class PlanCandidate:
    """A candidate plan with its score."""
    candidate_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    plan: Any = None
    score: float = 0.0
    feedback: str = ""
    rank: int = 0

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "score": self.score,
            "feedback": self.feedback[:200],
            "rank": self.rank,
        }


@dataclass
class SelectionResult:
    """Result of plan selection."""
    selection_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    candidates: list = field(default_factory=list)
    selected_index: int = 0
    selected_score: float = 0.0
    beam_width: int = 0
    reflected: bool = False
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict:
        return {
            "selection_id": self.selection_id,
            "beam_width": self.beam_width,
            "candidates": [c.to_dict() if hasattr(c, 'to_dict') else c
                           for c in self.candidates],
            "selected_index": self.selected_index,
            "selected_score": self.selected_score,
            "reflected": self.reflected,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class PlanSelector:
    """
    Beam search plan selection with critic scoring.

    Usage:
        selector = PlanSelector()
        result = selector.select(
            generator=lambda ctx: llm.generate(plan_prompt + ctx),
            critic=lambda plan: {score: float, feedback: str},
            beam_width=3,
        )
        best_plan = result.candidates[result.selected_index].plan
    """

    def __init__(self):
        self._results: dict[str, SelectionResult] = {}
        self._lock = threading.Lock()

    def select(
        self,
        generator: Callable[[str], Any],
        critic: Callable[[Any], dict],
        context: str = "",
        beam_width: int = 3,
        apply_reflection: bool = True,
        reflection_threshold: float = 0.7,
    ) -> SelectionResult:
        """
        Generate beam_width candidate plans, score each, select best.

        Args:
            generator: Callable(context) → plan output
            critic: Callable(plan) → {score: float, feedback: str}
            context: Planning context
            beam_width: Number of candidates to generate
            apply_reflection: If True, reflect on best candidate if below threshold
            reflection_threshold: Score threshold for reflection

        Returns:
            SelectionResult with ranked candidates
        """
        result = SelectionResult(
            beam_width=beam_width,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        self._emit("plan.candidates_generated", {
            "selection_id": result.selection_id,
            "beam_width": beam_width,
        })

        # Generate N candidates
        candidates: list[PlanCandidate] = []
        for i in range(beam_width):
            try:
                # Add variation hint to context
                varied_ctx = (
                    f"{context}\n\n"
                    f"[Generate approach variant {i + 1}/{beam_width}. "
                    f"Explore a different strategy than previous attempts.]"
                )
                plan = generator(varied_ctx)
                candidates.append(PlanCandidate(plan=plan))
            except Exception as exc:
                logger.warning("Plan generation %d failed: %s", i, exc)
                candidates.append(PlanCandidate(
                    plan=None, score=0.0, feedback=f"Generation failed: {exc}",
                ))

        # Score each candidate
        for c in candidates:
            if c.plan is None:
                continue
            try:
                critique = critic(c.plan)
                c.score = float(critique.get("score", 0.0))
                c.feedback = critique.get("feedback", "")
            except Exception as exc:
                c.score = 0.0
                c.feedback = f"Critic error: {exc}"

        # Rank by score
        candidates.sort(key=lambda c: c.score, reverse=True)
        for i, c in enumerate(candidates):
            c.rank = i + 1

        result.candidates = candidates
        result.selected_index = 0
        result.selected_score = candidates[0].score if candidates else 0.0

        # Apply reflection to best candidate if below threshold
        if (apply_reflection and candidates and
                candidates[0].score < reflection_threshold and
                candidates[0].plan is not None):
            try:
                from src.core.reflection_engine import ReflectionEngine, ReflectionConfig
                reflector = ReflectionEngine()
                ref_result = reflector.reflect(
                    generator=generator,
                    critic=critic,
                    config=ReflectionConfig(
                        max_iterations=2,
                        acceptance_threshold=reflection_threshold,
                    ),
                    context=f"{context}\n\nBest candidate feedback: {candidates[0].feedback}",
                )
                if ref_result.accepted and ref_result.final_score > candidates[0].score:
                    improved = PlanCandidate(
                        plan=ref_result.final_output,
                        score=ref_result.final_score,
                        feedback="Improved via reflection",
                        rank=0,
                    )
                    candidates.insert(0, improved)
                    result.selected_index = 0
                    result.selected_score = improved.score
                    result.reflected = True
                    # Re-rank
                    for i, c in enumerate(candidates):
                        c.rank = i + 1
            except Exception as exc:
                logger.warning("Reflection on plan failed: %s", exc)

        result.completed_at = datetime.now(timezone.utc).isoformat()

        self._emit("plan.selected", {
            "selection_id": result.selection_id,
            "selected_score": result.selected_score,
            "beam_width": beam_width,
            "reflected": result.reflected,
            "candidate_scores": [c.score for c in candidates],
        })

        with self._lock:
            self._results[result.selection_id] = result

        return result

    def get_result(self, selection_id: str) -> Optional[dict]:
        with self._lock:
            r = self._results.get(selection_id)
        return r.to_dict() if r else None

    def get_stats(self) -> dict:
        with self._lock:
            results = list(self._results.values())
        if not results:
            return {"total_selections": 0, "avg_beam_width": 0,
                    "avg_selected_score": 0, "reflection_rate": 0}
        reflected = sum(1 for r in results if r.reflected)
        return {
            "total_selections": len(results),
            "avg_beam_width": round(
                sum(r.beam_width for r in results) / len(results), 1
            ),
            "avg_selected_score": round(
                sum(r.selected_score for r in results) / len(results), 3
            ),
            "reflection_rate": round(reflected / len(results), 3),
        }

    def list_recent(self, limit: int = 20) -> list[dict]:
        with self._lock:
            items = sorted(
                self._results.values(),
                key=lambda r: r.started_at,
                reverse=True,
            )[:limit]
        return [r.to_dict() for r in items]

    @staticmethod
    def _emit(event_type: str, data: dict) -> None:
        try:
            from src.core.event_bus import get_event_bus
            get_event_bus().publish(event_type, data, source="plan_selector")
        except Exception:
            pass


# Singleton
_plan_selector: Optional[PlanSelector] = None
_ps_lock = threading.Lock()


def get_plan_selector() -> PlanSelector:
    global _plan_selector
    if _plan_selector is None:
        with _ps_lock:
            if _plan_selector is None:
                _plan_selector = PlanSelector()
    return _plan_selector
