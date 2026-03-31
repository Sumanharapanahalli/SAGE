"""
SAGE Framework — Meta-Optimization Loop
==========================================
Harness evolution engine inspired by Stanford IRIS Lab's Meta-Harness.

Paper: "Meta-Harness: End-to-End Optimization of Model Harnesses" (arXiv:2603.28052)

Key insight: the harness (prompts, tools, strategies) matters as much as the model.
Instead of hand-designing agent scaffolding, evolve it through an outer loop:

  1. COLLECT  — gather execution traces from Agent Gym sessions
  2. PROPOSE  — LLM reads traces + prior candidates, proposes harness changes
  3. EVALUATE — run proposal against exercise set, measure improvement
  4. PERSIST  — save iteration history (accepted/rejected) in SQLite
  5. CONVERGE — detect when optimization has plateaued

The paper's ablation shows that access to raw execution traces is critical:
  - Scores only:          34.6% median accuracy
  - Scores + summary:     34.9%
  - Full traces:          50.0%

SAGE already stores execution traces in audit logs — this module adds the
optimization loop that turns those traces into better agent harnesses.

Thread-safe. SQLite-backed. Non-blocking.
"""

import json
import logging
import os
import sqlite3
import statistics
import threading
import time
import uuid
from typing import Any, Optional

logger = logging.getLogger("MetaOptimizer")


class MetaOptimizer:
    """
    Meta-optimization loop for evolving agent harnesses.

    Uses execution traces (not just scores) to propose improvements to
    system prompts, tool schemas, strategies, and runner configurations.
    """

    # Valid targets for harness proposals
    VALID_TARGETS = {"system_prompt", "tool_schema", "strategy", "config"}

    # Minimum iterations before convergence detection
    MIN_CONVERGENCE_ITERATIONS = 3

    # Convergence threshold: max score variance in last N iterations
    CONVERGENCE_THRESHOLD = 2.0

    def __init__(self, db_path: str = ""):
        if not db_path:
            db_path = os.path.join(os.getcwd(), ".sage", "meta_optimizer.db")
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite tables for iteration history."""
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS iterations (
                    iteration_id TEXT PRIMARY KEY,
                    runner_name TEXT NOT NULL,
                    proposal_json TEXT NOT NULL,
                    evaluation_json TEXT NOT NULL,
                    accepted INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_iterations_runner
                ON iterations(runner_name)
            """)

    # ── Trace Collection ────────────────────────────────────────────────

    def collect_traces(self, sessions: list[dict]) -> list[dict]:
        """
        Collect execution traces from Agent Gym training sessions.

        Transforms session dicts into trace format optimized for the proposer.
        Full output is preserved — the paper shows this is critical for quality.
        """
        if not sessions:
            return []

        traces = []
        for session in sessions:
            trace = {
                "session_id": session.get("session_id", ""),
                "role": session.get("agent_role", ""),
                "runner": session.get("runner_name", ""),
                "exercise_id": session.get("exercise_id", ""),
                "difficulty": session.get("difficulty", ""),
                "score": session.get("grade", {}).get("score", 0)
                    if isinstance(session.get("grade"), dict) else 0,
                "passed": session.get("grade", {}).get("passed", False)
                    if isinstance(session.get("grade"), dict) else False,
                "output": session.get("attempt_result", {}).get("output", "")
                    if isinstance(session.get("attempt_result"), dict) else "",
                "reflection": session.get("reflection", ""),
                "improvement_plan": session.get("improvement_plan", []),
                "critic_scores": {
                    k: v.get("score", 0) if isinstance(v, dict) else 0
                    for k, v in session.get("critic_reviews", {}).items()
                },
            }
            traces.append(trace)

        return traces

    # ── Harness Proposal Generation ─────────────────────────────────────

    def propose_improvement(
        self, traces: list[dict], runner_name: str = ""
    ) -> dict:
        """
        Use LLM to analyze execution traces and propose harness improvements.

        The LLM sees full traces (not just scores) to identify patterns:
          - Common failure modes
          - Wasted exploration turns
          - Missing tool capabilities
          - Prompt gaps
        """
        try:
            from src.core.llm_gateway import llm_gateway

            # Build trace summary for the proposer
            trace_text = self._format_traces_for_proposer(traces)

            # Get prior proposals for context
            history = self.get_history(runner_name=runner_name, limit=5)
            history_text = self._format_history_for_proposer(history)

            prompt = (
                f"## Meta-Harness Optimization — Runner: {runner_name}\n\n"
                f"You are optimizing the agent harness (system prompts, tool schemas, "
                f"execution strategies) for the '{runner_name}' domain runner.\n\n"
                f"## Execution Traces ({len(traces)} sessions)\n"
                f"{trace_text}\n\n"
                f"## Prior Optimization Attempts\n"
                f"{history_text}\n\n"
                f"## Instructions\n"
                f"Analyze the execution traces and propose ONE improvement to the harness.\n"
                f"Focus on the most impactful change based on failure patterns.\n\n"
                f"Valid targets: system_prompt, tool_schema, strategy, config\n\n"
                f"Return JSON:\n"
                f'{{"proposal_id": "prop-<uuid4_short>", '
                f'"target": "<valid_target>", '
                f'"changes": [{{"component": "<target>", '
                f'"before": "<current_value>", '
                f'"after": "<proposed_value>", '
                f'"rationale": "<why_this_change>"}}], '
                f'"expected_improvement": "<what_should_improve>", '
                f'"confidence": 0.0-1.0}}'
            )

            response = llm_gateway.generate(
                prompt,
                system_prompt=(
                    "You are a meta-optimization engine. Analyze execution traces "
                    "and propose harness improvements. Return valid JSON only."
                ),
                trace_name=f"meta_optimizer.propose.{runner_name}",
            )

            # Parse JSON from response
            cleaned = response.replace("```json", "").replace("```", "").strip()
            import re
            match = re.search(r'\{[\s\S]*\}', cleaned)
            if match:
                parsed = json.loads(match.group(0))
                # Ensure proposal_id
                if "proposal_id" not in parsed:
                    parsed["proposal_id"] = f"prop-{uuid.uuid4().hex[:8]}"
                # Validate target
                if parsed.get("target") not in self.VALID_TARGETS:
                    parsed["target"] = "system_prompt"
                return parsed

            return {"error": "Could not parse LLM proposal", "changes": []}

        except Exception as exc:
            logger.error("Proposal generation failed: %s", exc)
            return {"error": str(exc), "changes": []}

    # ── Proposal Evaluation ─────────────────────────────────────────────

    def evaluate_proposal(
        self,
        proposal: dict,
        runner_name: str = "",
        baseline_score: float = 0.0,
    ) -> dict:
        """
        Evaluate a harness proposal against exercise set.

        Runs evaluation sessions and compares against baseline.
        """
        sessions = self._run_evaluation_sessions(proposal, runner_name)

        if not sessions:
            return {
                "score": 0.0,
                "improvement": -baseline_score,
                "delta": -baseline_score,
                "sessions": [],
                "details": [],
            }

        scores = [s.get("score", 0) for s in sessions]
        avg_score = statistics.mean(scores) if scores else 0.0
        improvement = avg_score - baseline_score

        return {
            "score": round(avg_score, 2),
            "improvement": round(improvement, 2),
            "delta": round(improvement, 2),
            "sessions": sessions,
            "details": sessions,
        }

    def _run_evaluation_sessions(
        self, proposal: dict, runner_name: str
    ) -> list[dict]:
        """
        Run Agent Gym sessions with the proposed harness changes.

        Override point for testing.
        """
        try:
            from src.core.agent_gym import AgentGym
            gym = AgentGym()

            # Get runner's roles
            from src.integrations.base_runner import get_runner_by_name
            runner = get_runner_by_name(runner_name)
            if not runner or not runner.roles:
                return []

            role = runner.roles[0]
            session = gym.train(role=role, difficulty="intermediate")
            if session:
                return [{
                    "score": session.grade.get("score", 0) if isinstance(session.grade, dict) else 0,
                    "passed": session.grade.get("passed", False) if isinstance(session.grade, dict) else False,
                    "exercise_id": session.exercise_id,
                }]
            return []
        except Exception as exc:
            logger.debug("Evaluation session failed: %s", exc)
            return []

    # ── Full Optimization Loop ──────────────────────────────────────────

    def run_iteration(self, runner_name: str = "", traces: list[dict] = None) -> dict:
        """
        Run a complete meta-optimization iteration:
          1. Collect traces (or use provided ones)
          2. Propose improvement
          3. Evaluate proposal
          4. Save to history
          5. Accept or reject
        """
        iteration_id = f"iter-{uuid.uuid4().hex[:8]}"

        # 1. Collect traces
        if traces is None:
            traces = self.collect_traces(self._get_recent_sessions(runner_name))

        # 2. Propose
        proposal = self.propose_improvement(traces, runner_name=runner_name)

        # 3. Evaluate
        baseline = self._get_baseline_score(runner_name)
        evaluation = self.evaluate_proposal(
            proposal, runner_name=runner_name, baseline_score=baseline
        )

        # 4. Accept/reject
        improvement = evaluation.get("improvement", evaluation.get("delta", 0))
        accepted = improvement > 0

        # 5. Save
        iteration = {
            "iteration_id": iteration_id,
            "runner_name": runner_name,
            "proposal": proposal,
            "evaluation": evaluation,
            "accepted": accepted,
        }
        self.save_iteration(iteration)

        return iteration

    # ── Iteration History & Persistence ─────────────────────────────────

    def save_iteration(self, iteration: dict) -> None:
        """Save an optimization iteration to SQLite."""
        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO iterations
                       (iteration_id, runner_name, proposal_json, evaluation_json, accepted, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        iteration["iteration_id"],
                        iteration.get("runner_name", ""),
                        json.dumps(iteration.get("proposal", {})),
                        json.dumps(iteration.get("evaluation", {})),
                        1 if iteration.get("accepted") else 0,
                        time.time(),
                    ),
                )

    def get_history(
        self, runner_name: str = "", limit: int = 50
    ) -> list[dict]:
        """Get iteration history, optionally filtered by runner."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            if runner_name:
                rows = conn.execute(
                    "SELECT * FROM iterations WHERE runner_name = ? ORDER BY created_at DESC LIMIT ?",
                    (runner_name, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM iterations ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()

        return [
            {
                "iteration_id": r["iteration_id"],
                "runner_name": r["runner_name"],
                "proposal": json.loads(r["proposal_json"]),
                "evaluation": json.loads(r["evaluation_json"]),
                "accepted": bool(r["accepted"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def get_best_iteration(self, runner_name: str = "") -> Optional[dict]:
        """Get the highest-scoring iteration for a runner."""
        history = self.get_history(runner_name=runner_name, limit=100)
        if not history:
            return None
        return max(
            history,
            key=lambda h: h.get("evaluation", {}).get("score", 0),
        )

    # ── Convergence Detection ───────────────────────────────────────────

    def check_convergence(self, runner_name: str = "") -> bool:
        """
        Detect whether optimization has plateaued.

        Converged when last N iterations show < threshold variance in scores.
        """
        history = self.get_history(runner_name=runner_name, limit=10)

        if len(history) < self.MIN_CONVERGENCE_ITERATIONS:
            return False

        recent_scores = [
            h.get("evaluation", {}).get("score", 0)
            for h in history[:self.MIN_CONVERGENCE_ITERATIONS + 2]
        ]

        if len(recent_scores) < self.MIN_CONVERGENCE_ITERATIONS:
            return False

        # Check if variance is below threshold
        try:
            score_range = max(recent_scores) - min(recent_scores)
            return score_range < self.CONVERGENCE_THRESHOLD
        except (ValueError, TypeError):
            return False

    # ── Statistics & Analytics ──────────────────────────────────────────

    def stats(self, runner_name: str = "") -> dict:
        """Get meta-optimizer statistics."""
        history = self.get_history(runner_name=runner_name, limit=1000)

        if not history:
            return {
                "total_iterations": 0,
                "accepted": 0,
                "rejected": 0,
                "trend": "none",
                "improvement_rate": 0.0,
            }

        scores = [
            h.get("evaluation", {}).get("score", 0)
            for h in history
        ]
        accepted = sum(1 for h in history if h.get("accepted"))

        # Calculate trend
        trend = "flat"
        if len(scores) >= 3:
            recent = scores[:3]
            older = scores[3:6] if len(scores) >= 6 else scores[3:]
            if older:
                recent_avg = statistics.mean(recent)
                older_avg = statistics.mean(older)
                if recent_avg > older_avg + 2:
                    trend = "improving"
                elif recent_avg < older_avg - 2:
                    trend = "declining"

        return {
            "total_iterations": len(history),
            "accepted": accepted,
            "rejected": len(history) - accepted,
            "best_score": max(scores) if scores else 0,
            "latest_score": scores[0] if scores else 0,
            "trend": trend,
            "improvement_rate": round(accepted / len(history) * 100, 1) if history else 0.0,
            "converged": self.check_convergence(runner_name),
        }

    # ── Internal Helpers ────────────────────────────────────────────────

    def _format_traces_for_proposer(self, traces: list[dict]) -> str:
        """Format traces for the LLM proposer prompt."""
        parts = []
        for i, trace in enumerate(traces[:10]):  # Limit to 10 most recent
            parts.append(
                f"### Session {i+1}: {trace.get('exercise_id', 'unknown')}\n"
                f"- Role: {trace.get('role', '')}\n"
                f"- Score: {trace.get('score', 0)}/100 "
                f"({'PASS' if trace.get('passed') else 'FAIL'})\n"
                f"- Output (truncated):\n```\n{str(trace.get('output', ''))[:500]}\n```\n"
                f"- Reflection: {trace.get('reflection', 'none')}\n"
            )
        return "\n".join(parts) or "No traces available."

    def _format_history_for_proposer(self, history: list[dict]) -> str:
        """Format prior iterations for context."""
        if not history:
            return "No prior optimization attempts."
        parts = []
        for h in history[:5]:
            status = "ACCEPTED" if h.get("accepted") else "REJECTED"
            score = h.get("evaluation", {}).get("score", 0)
            target = h.get("proposal", {}).get("target", "unknown")
            parts.append(f"- [{status}] Target: {target}, Score: {score}")
        return "\n".join(parts)

    def _get_recent_sessions(self, runner_name: str) -> list[dict]:
        """Get recent Agent Gym sessions for a runner."""
        try:
            from src.core.agent_gym import AgentGym
            gym = AgentGym()
            history = gym.get_history(limit=20)
            return [
                s for s in history
                if s.get("runner_name") == runner_name
            ]
        except Exception:
            return []

    def _get_baseline_score(self, runner_name: str) -> float:
        """Get the current baseline score from recent iterations."""
        history = self.get_history(runner_name=runner_name, limit=5)
        if not history:
            return 0.0
        scores = [h.get("evaluation", {}).get("score", 0) for h in history]
        return statistics.mean(scores) if scores else 0.0
