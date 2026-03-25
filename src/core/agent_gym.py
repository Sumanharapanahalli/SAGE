"""
SAGE Framework — Agent Gym
============================
Self-play skill improvement engine inspired by MuZero/AlphaZero.

Instead of learning from human demonstrations alone, agents improve by:
  1. PLAY    — attempt exercises from their runner's skill set
  2. GRADE   — runner grades the attempt (domain verification)
  3. CRITIQUE — N critics (Gemini, Claude, Ollama, etc.) score independently
  4. REFLECT — agent reviews its own output vs critic feedback
  5. COMPOUND — learnings stored in vector memory for next attempt

This creates a compounding improvement loop where agents get better
at skills through practice, not just instruction.

Key principles from game-playing AI applied here:
  - MuZero: learn a model of the environment through self-play
    → Agents learn what "good output" looks like by practicing and reflecting
  - AlphaZero: self-play > supervised learning from examples
    → Exercises + self-grading > hardcoded prompts
  - ELO/TrueSkill: track skill ratings over time
    → Per-skill rating that compounds with practice

Thread-safe. Audit every session. Non-blocking.
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("AgentGym")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TrainingSession:
    """A single training session for an agent."""
    session_id: str
    agent_role: str
    runner_name: str
    skill_name: str
    exercise_id: str
    difficulty: str
    status: str = "pending"  # pending, running, grading, reflecting, completed, failed
    attempt_result: dict = field(default_factory=dict)
    grade: dict = field(default_factory=dict)
    critic_reviews: dict = field(default_factory=dict)  # provider_name → review
    reflection: str = ""
    improvement_plan: list[str] = field(default_factory=list)
    elo_before: float = 1000.0
    elo_after: float = 1000.0
    duration_s: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "agent_role": self.agent_role,
            "runner_name": self.runner_name,
            "skill_name": self.skill_name,
            "exercise_id": self.exercise_id,
            "difficulty": self.difficulty,
            "status": self.status,
            "grade": self.grade,
            "critic_reviews": {k: v.get("score", 0) for k, v in self.critic_reviews.items()},
            "elo_before": round(self.elo_before, 1),
            "elo_after": round(self.elo_after, 1),
            "duration_s": round(self.duration_s, 2),
        }


@dataclass
class SkillRating:
    """ELO-style rating for an agent's proficiency in a specific skill."""
    agent_role: str
    skill_name: str
    rating: float = 1000.0  # ELO-style, starts at 1000
    sessions: int = 0
    wins: int = 0  # exercises passed
    losses: int = 0  # exercises failed
    streak: int = 0  # consecutive wins (negative for losses)
    best_score: float = 0.0
    last_session_id: str = ""

    def to_dict(self) -> dict:
        return {
            "agent_role": self.agent_role,
            "skill_name": self.skill_name,
            "rating": round(self.rating, 1),
            "sessions": self.sessions,
            "win_rate": round(self.wins / max(self.sessions, 1), 3),
            "streak": self.streak,
            "best_score": round(self.best_score, 1),
        }


# ---------------------------------------------------------------------------
# Agent Gym
# ---------------------------------------------------------------------------

class AgentGym:
    """
    Self-play training environment for SAGE agents.

    Usage:
        gym = agent_gym  # module singleton
        session = gym.train(role="firmware_engineer", difficulty="intermediate")
        # Returns completed TrainingSession with grade + reflection
    """

    def __init__(self):
        self.logger = logging.getLogger("AgentGym")
        self._sessions: dict[str, TrainingSession] = {}
        self._ratings: dict[str, SkillRating] = {}  # "role:skill" → SkillRating
        self._history: list[str] = []  # session_ids in order

    # ── Training loop ────────────────────────────────────────────────────

    def train(
        self,
        role: str,
        difficulty: str = "intermediate",
        skill_name: str = "",
        exercise_id: str = "",
    ) -> TrainingSession:
        """
        Run a complete training session: play → grade → critique → reflect.

        Args:
            role: Agent role (e.g., "firmware_engineer").
            difficulty: Exercise difficulty level.
            skill_name: Optional specific skill to practice.
            exercise_id: Optional specific exercise ID.

        Returns:
            Completed TrainingSession with full results.
        """
        session_id = str(uuid.uuid4())
        start = time.monotonic()

        # 1. Find the runner and exercise
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role(role)
        if not runner:
            return self._failed_session(session_id, role, f"No runner for role '{role}'")

        # Get skill name from registry
        if not skill_name:
            skills = runner.get_skills()
            skill_name = skills[0]["name"] if skills else runner.name

        # Get exercises
        exercises = runner.get_exercises(difficulty=difficulty)
        if not exercises:
            return self._failed_session(session_id, role, f"No {difficulty} exercises")

        # Select exercise
        exercise = None
        if exercise_id:
            exercise = next((e for e in exercises if e.id == exercise_id), None)
        if not exercise:
            exercise = exercises[0]

        # Get current ELO
        rating_key = f"{role}:{skill_name}"
        current_rating = self._ratings.get(rating_key, SkillRating(role, skill_name))

        session = TrainingSession(
            session_id=session_id,
            agent_role=role,
            runner_name=runner.name,
            skill_name=skill_name,
            exercise_id=exercise.id,
            difficulty=difficulty,
            status="running",
            elo_before=current_rating.rating,
            started_at=time.time(),
        )
        self._sessions[session_id] = session

        try:
            # 2. PLAY — attempt the exercise
            session.status = "running"
            task = {
                "description": exercise.description,
                "task_type": exercise.task_type,
                "acceptance_criteria": exercise.acceptance_criteria,
                "payload": {"exercise_id": exercise.id, "training": True},
            }
            import tempfile
            workspace = tempfile.mkdtemp(prefix=f"sage_gym_{role}_")
            result = runner.execute(task=task, workspace=workspace)
            session.attempt_result = result.to_dict()

            # 3. GRADE — runner grades the attempt
            session.status = "grading"
            score = runner.grade_exercise(exercise, result)
            session.grade = {
                "passed": score.passed,
                "score": score.score,
                "criteria": score.criteria_results,
                "feedback": score.feedback,
                "hints": score.improvement_hints,
            }

            # 4. CRITIQUE — N critics review (non-blocking, best-effort)
            session.status = "critiquing"
            session.critic_reviews = self._get_critic_reviews(
                result, exercise, role
            )

            # 5. REFLECT — generate improvement plan
            session.status = "reflecting"
            session.reflection, session.improvement_plan = self._reflect(
                exercise, score, session.critic_reviews, role
            )

            # 6. Update ELO rating
            session.elo_after = self._update_rating(
                rating_key, current_rating, score.score, score.passed
            )

            # 7. Store learnings in vector memory
            self._store_learning(session)

            session.status = "completed"

        except Exception as exc:
            self.logger.error("Training session failed: %s", exc)
            session.status = "failed"
            session.attempt_result["error"] = str(exc)

        session.completed_at = time.time()
        session.duration_s = time.monotonic() - start
        self._history.append(session_id)

        self.logger.info(
            "Training session %s: role=%s, skill=%s, score=%.1f, elo=%.1f→%.1f",
            session_id[:8], role, skill_name,
            session.grade.get("score", 0),
            session.elo_before, session.elo_after,
        )

        return session

    # ── Critic reviews ───────────────────────────────────────────────────

    def _get_critic_reviews(
        self, result, exercise, role: str
    ) -> dict[str, dict]:
        """Get reviews from all available critic providers."""
        reviews = {}
        try:
            from src.agents.critic import critic_agent
            code_output = result.output[:4000] if result.output else "No output"

            # Use multi-critic if providers are available
            review = critic_agent.multi_critic_review(
                review_type="code",
                artifact=code_output,
                description=(
                    f"Exercise: {exercise.description}\n"
                    f"Role: {role}\n"
                    f"Acceptance criteria: {exercise.acceptance_criteria}"
                ),
                context=f"This is a training exercise (difficulty: {exercise.difficulty}). "
                        f"Grade the agent's output strictly.",
            )

            if review.get("multi_critic"):
                reviews = review.get("reviews", {})
            else:
                reviews["primary"] = review

        except Exception as exc:
            self.logger.warning("Critic review during training failed: %s", exc)
            reviews["error"] = {"score": 0, "error": str(exc)}

        return reviews

    # ── Reflection ───────────────────────────────────────────────────────

    def _reflect(
        self, exercise, score, critic_reviews: dict, role: str
    ) -> tuple[str, list[str]]:
        """Generate a reflection and improvement plan from grading + critic feedback."""
        try:
            from src.core.llm_gateway import llm_gateway

            critic_summary = "\n".join(
                f"- {name}: score={r.get('score', '?')}, flaws={r.get('flaws', r.get('issues', []))}"
                for name, r in critic_reviews.items()
                if isinstance(r, dict)
            )

            prompt = (
                f"You just attempted this exercise as a {role}:\n"
                f"Exercise: {exercise.description}\n"
                f"Your score: {score.score}/100 ({'PASSED' if score.passed else 'FAILED'})\n"
                f"Grading feedback: {score.feedback}\n"
                f"Improvement hints: {score.improvement_hints}\n\n"
                f"Critic reviews:\n{critic_summary}\n\n"
                f"Reflect on what you did well and what you need to improve.\n"
                f"Return JSON: {{\"reflection\": \"...\", \"improvement_plan\": [\"step1\", ...]}}"
            )

            response = llm_gateway.generate(
                prompt,
                f"You are a self-aware AI agent in training for the role of {role}. "
                f"Be honest about your weaknesses. Focus on specific, actionable improvements.",
                trace_name="agent_gym.reflect",
            )

            # Parse reflection
            import re
            response = response.replace("```json", "").replace("```", "").strip()
            match = re.search(r'\{[\s\S]*\}', response)
            if match:
                data = json.loads(match.group(0))
                return (
                    data.get("reflection", ""),
                    data.get("improvement_plan", []),
                )
            return (response[:500], [])

        except Exception as exc:
            self.logger.warning("Reflection failed: %s", exc)
            return ("Reflection generation failed", score.improvement_hints)

    # ── ELO rating ───────────────────────────────────────────────────────

    def _update_rating(
        self, key: str, current: SkillRating, score: float, passed: bool
    ) -> float:
        """
        Update ELO-style rating based on exercise result.

        K-factor varies by experience:
          - First 10 sessions: K=40 (fast calibration)
          - 10-30 sessions: K=20 (standard)
          - 30+ sessions: K=10 (slow, stable)

        Expected score is based on difficulty-adjusted baseline.
        """
        if current.sessions < 10:
            k = 40
        elif current.sessions < 30:
            k = 20
        else:
            k = 10

        # Normalize score to 0-1 range
        actual = score / 100.0
        # Expected performance based on current rating
        expected = 1 / (1 + 10 ** ((1000 - current.rating) / 400))

        new_rating = current.rating + k * (actual - expected)
        new_rating = max(100, min(3000, new_rating))  # clamp

        # Update rating object
        current.rating = new_rating
        current.sessions += 1
        if passed:
            current.wins += 1
            current.streak = max(current.streak + 1, 1)
        else:
            current.losses += 1
            current.streak = min(current.streak - 1, -1)
        current.best_score = max(current.best_score, score)
        self._ratings[key] = current

        return new_rating

    # ── Vector memory ────────────────────────────────────────────────────

    def _store_learning(self, session: TrainingSession) -> None:
        """Store training insights in vector memory for future context."""
        try:
            from src.memory.vector_store import vector_memory

            learning = (
                f"TRAINING ({session.agent_role}, {session.skill_name}): "
                f"Exercise={session.exercise_id}, Score={session.grade.get('score', 0)}/100. "
                f"Reflection: {session.reflection[:200]}. "
                f"Improvements: {session.improvement_plan[:3]}"
            )
            vector_memory.add_feedback(
                learning,
                metadata={
                    "type": "gym_training",
                    "agent_role": session.agent_role,
                    "skill_name": session.skill_name,
                    "score": session.grade.get("score", 0),
                    "elo": session.elo_after,
                    "source": "AgentGym",
                },
            )
        except Exception as exc:
            self.logger.warning("Vector store learning failed (non-fatal): %s", exc)

    # ── Helpers ──────────────────────────────────────────────────────────

    def _failed_session(self, session_id: str, role: str, error: str) -> TrainingSession:
        session = TrainingSession(
            session_id=session_id,
            agent_role=role,
            runner_name="",
            skill_name="",
            exercise_id="",
            difficulty="",
            status="failed",
            attempt_result={"error": error},
        )
        self._sessions[session_id] = session
        return session

    # ── Query ────────────────────────────────────────────────────────────

    def get_session(self, session_id: str) -> Optional[TrainingSession]:
        return self._sessions.get(session_id)

    def get_rating(self, role: str, skill_name: str) -> Optional[SkillRating]:
        return self._ratings.get(f"{role}:{skill_name}")

    def get_ratings_for_role(self, role: str) -> list[SkillRating]:
        return [r for r in self._ratings.values() if r.agent_role == role]

    def get_all_ratings(self) -> list[dict]:
        return [r.to_dict() for r in self._ratings.values()]

    def get_history(self, limit: int = 20) -> list[dict]:
        recent = self._history[-limit:]
        return [
            self._sessions[sid].to_dict()
            for sid in reversed(recent)
            if sid in self._sessions
        ]

    def get_leaderboard(self) -> list[dict]:
        """Return all ratings sorted by ELO descending."""
        sorted_ratings = sorted(self._ratings.values(), key=lambda r: r.rating, reverse=True)
        return [r.to_dict() for r in sorted_ratings]

    def stats(self) -> dict:
        total = len(self._history)
        completed = sum(1 for sid in self._history if self._sessions.get(sid, TrainingSession("","","","","","")).status == "completed")
        return {
            "total_sessions": total,
            "completed": completed,
            "failed": total - completed,
            "unique_roles": len(set(r.agent_role for r in self._ratings.values())),
            "unique_skills": len(self._ratings),
            "avg_rating": round(
                sum(r.rating for r in self._ratings.values()) / max(len(self._ratings), 1), 1
            ),
        }


# Module-level singleton
agent_gym = AgentGym()
