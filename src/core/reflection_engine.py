"""
SAGE Reflection Engine — Self-Correcting Agent Loop
=====================================================

Implements bounded self-correction: when a critic scores output below
threshold, re-generate with critic feedback injected as context.
Max iterations configurable (default 3). Each iteration is logged
as an event for full transparency.

Pattern: Reflexion (Shinn et al.) + LATS (Language Agent Tree Search)
"""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ReflectionResult:
    """Result of a reflection loop."""
    reflection_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    iterations: int = 0
    final_score: float = 0.0
    accepted: bool = False
    history: list = field(default_factory=list)
    final_output: Any = None
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict:
        return {
            "reflection_id": self.reflection_id,
            "iterations": self.iterations,
            "final_score": self.final_score,
            "accepted": self.accepted,
            "history": self.history,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class ReflectionConfig:
    """Configuration for reflection loop."""
    max_iterations: int = 3
    acceptance_threshold: float = 0.7
    improvement_threshold: float = 0.05  # min improvement per iteration to continue
    include_history: bool = True         # inject prior attempts in prompt


class ReflectionEngine:
    """
    Bounded self-correction loop.

    Usage:
        engine = ReflectionEngine()
        result = engine.reflect(
            generator=lambda ctx: llm.generate(prompt + ctx),
            critic=lambda output: score_output(output),
            config=ReflectionConfig(max_iterations=3, acceptance_threshold=0.7),
        )
    """

    def __init__(self):
        self._results: dict[str, ReflectionResult] = {}
        self._lock = threading.Lock()

    def reflect(
        self,
        generator: Callable[[str], Any],
        critic: Callable[[Any], dict],
        config: ReflectionConfig = None,
        context: str = "",
        task_id: str = "",
    ) -> ReflectionResult:
        """
        Run reflection loop.

        Args:
            generator: Callable(context_str) → output. Generates candidate output.
            critic: Callable(output) → {score: float, feedback: str}.
                    Evaluates output quality.
            config: Loop configuration.
            context: Initial context to pass to generator.
            task_id: Optional task ID for event correlation.

        Returns:
            ReflectionResult with final output, score, and iteration history.
        """
        config = config or ReflectionConfig()
        result = ReflectionResult(
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        self._emit("reflection.started", {
            "reflection_id": result.reflection_id,
            "task_id": task_id,
            "max_iterations": config.max_iterations,
            "threshold": config.acceptance_threshold,
        })

        augmented_context = context
        prev_score = 0.0

        for i in range(config.max_iterations):
            result.iterations = i + 1

            # Generate
            try:
                output = generator(augmented_context)
            except Exception as exc:
                result.history.append({
                    "iteration": i + 1,
                    "error": str(exc),
                    "score": 0.0,
                })
                logger.warning("Reflection generator error at iteration %d: %s", i + 1, exc)
                break

            # Critique
            try:
                critique = critic(output)
                score = float(critique.get("score", 0.0))
                feedback = critique.get("feedback", "")
            except Exception as exc:
                score = 0.0
                feedback = f"Critic error: {exc}"
                logger.warning("Reflection critic error at iteration %d: %s", i + 1, exc)

            result.history.append({
                "iteration": i + 1,
                "score": score,
                "feedback": feedback,
            })
            result.final_output = output
            result.final_score = score

            self._emit("reflection.iteration", {
                "reflection_id": result.reflection_id,
                "iteration": i + 1,
                "score": score,
                "accepted": score >= config.acceptance_threshold,
                "task_id": task_id,
            })

            # Accept if above threshold
            if score >= config.acceptance_threshold:
                result.accepted = True
                break

            # Stop if no improvement
            if i > 0 and (score - prev_score) < config.improvement_threshold:
                logger.info(
                    "Reflection stopping: no improvement (%.3f → %.3f)",
                    prev_score, score,
                )
                break

            prev_score = score

            # Build feedback context for next iteration
            if config.include_history:
                history_block = "\n".join(
                    f"Attempt {h['iteration']}: score={h['score']:.2f} — {h.get('feedback', '')}"
                    for h in result.history
                )
                augmented_context = (
                    f"{context}\n\n"
                    f"--- Previous attempts (improve on these) ---\n"
                    f"{history_block}\n"
                    f"--- Critic feedback on last attempt ---\n"
                    f"{feedback}\n"
                    f"Generate an improved version addressing the feedback above."
                )
            else:
                augmented_context = (
                    f"{context}\n\n"
                    f"Critic feedback (score {score:.2f}): {feedback}\n"
                    f"Improve your output to address this feedback."
                )

        result.completed_at = datetime.now(timezone.utc).isoformat()

        event_type = "reflection.accepted" if result.accepted else "reflection.rejected"
        self._emit(event_type, {
            "reflection_id": result.reflection_id,
            "iterations": result.iterations,
            "final_score": result.final_score,
            "task_id": task_id,
        })

        with self._lock:
            self._results[result.reflection_id] = result

        return result

    def get_result(self, reflection_id: str) -> Optional[dict]:
        """Get a reflection result by ID."""
        with self._lock:
            r = self._results.get(reflection_id)
        return r.to_dict() if r else None

    def get_stats(self) -> dict:
        """Return reflection engine statistics."""
        with self._lock:
            results = list(self._results.values())
        if not results:
            return {
                "total_reflections": 0,
                "accepted_count": 0,
                "rejected_count": 0,
                "avg_iterations": 0,
                "avg_final_score": 0,
            }
        accepted = sum(1 for r in results if r.accepted)
        return {
            "total_reflections": len(results),
            "accepted_count": accepted,
            "rejected_count": len(results) - accepted,
            "acceptance_rate": round(accepted / len(results), 3) if results else 0,
            "avg_iterations": round(sum(r.iterations for r in results) / len(results), 2),
            "avg_final_score": round(sum(r.final_score for r in results) / len(results), 3),
        }

    def list_recent(self, limit: int = 20) -> list[dict]:
        """List recent reflection results."""
        with self._lock:
            items = sorted(
                self._results.values(),
                key=lambda r: r.started_at,
                reverse=True,
            )[:limit]
        return [r.to_dict() for r in items]

    @staticmethod
    def _emit(event_type: str, data: dict) -> None:
        """Emit event via EventBus (non-blocking)."""
        try:
            from src.core.event_bus import get_event_bus
            get_event_bus().publish(event_type, data, source="reflection_engine")
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────────────

_reflection_engine: Optional[ReflectionEngine] = None
_re_lock = threading.Lock()


def get_reflection_engine() -> ReflectionEngine:
    global _reflection_engine
    if _reflection_engine is None:
        with _re_lock:
            if _reflection_engine is None:
                _reflection_engine = ReflectionEngine()
    return _reflection_engine
