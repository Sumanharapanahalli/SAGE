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

Persistence: SQLite-backed (survives restarts).
Analytics: score trends, improvement rate, weakness detection.
Curriculum: auto-advance difficulty on win streaks.
Batch: train all roles in parallel waves.
Peer: cross-role review for diverse feedback.

Thread-safe. Audit every session. Non-blocking.
"""

import json
import logging
import math
import os
import sqlite3
import statistics
import threading
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
    status: str = "pending"  # pending, running, grading, critiquing, reflecting, completed, failed
    attempt_result: dict = field(default_factory=dict)
    grade: dict = field(default_factory=dict)
    critic_reviews: dict = field(default_factory=dict)  # provider_name → review
    peer_reviews: dict = field(default_factory=dict)  # peer_role → review
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
            "critic_reviews": {
                k: v.get("score", 0) if isinstance(v, dict) else 0
                for k, v in self.critic_reviews.items()
            },
            "peer_reviews": {
                k: v.get("score", 0) if isinstance(v, dict) else 0
                for k, v in self.peer_reviews.items()
            },
            "reflection": self.reflection[:300] if self.reflection else "",
            "improvement_plan": self.improvement_plan[:5],
            "elo_before": round(self.elo_before, 1),
            "elo_after": round(self.elo_after, 1),
            "duration_s": round(self.duration_s, 2),
        }


@dataclass
class SkillRating:
    """
    Glicko-2 inspired skill rating for an agent's proficiency.

    Extends basic ELO with:
      - rating_deviation (RD): confidence interval — high RD means uncertain rating
      - volatility: how erratic the agent's performance is
      - failed_exercises: exercise IDs that need spaced repetition
      - next_review_at: session count thresholds for spaced repetition
    """
    agent_role: str
    skill_name: str
    rating: float = 1000.0
    rating_deviation: float = 350.0  # Glicko-2 RD — starts high (uncertain), shrinks with data
    volatility: float = 0.06  # Glicko-2 σ — performance consistency
    sessions: int = 0
    wins: int = 0
    losses: int = 0
    streak: int = 0
    best_score: float = 0.0
    last_session_id: str = ""
    current_difficulty: str = "beginner"
    # Spaced repetition: exercise_id → next session count to retry
    failed_exercises: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "agent_role": self.agent_role,
            "skill_name": self.skill_name,
            "rating": round(self.rating, 1),
            "rating_deviation": round(self.rating_deviation, 1),
            "confidence_interval": [
                round(self.rating - 2 * self.rating_deviation, 1),
                round(self.rating + 2 * self.rating_deviation, 1),
            ],
            "volatility": round(self.volatility, 4),
            "sessions": self.sessions,
            "win_rate": round(self.wins / max(self.sessions, 1), 3),
            "streak": self.streak,
            "best_score": round(self.best_score, 1),
            "current_difficulty": self.current_difficulty,
            "pending_reviews": len([
                eid for eid, threshold in self.failed_exercises.items()
                if self.sessions >= threshold
            ]),
        }


# ---------------------------------------------------------------------------
# Difficulty levels and curriculum thresholds
# ---------------------------------------------------------------------------
DIFFICULTY_ORDER = ["beginner", "intermediate", "advanced", "expert"]

# Win rate thresholds for auto-advancing difficulty
CURRICULUM_ADVANCE_WIN_RATE = 0.70  # advance if win rate > 70%
CURRICULUM_ADVANCE_MIN_SESSIONS = 3  # minimum sessions at current level
CURRICULUM_DEMOTE_WIN_RATE = 0.25  # demote if win rate < 25%
CURRICULUM_DEMOTE_MIN_SESSIONS = 5  # minimum sessions before demotion

# Optimal learning zone — agents improve fastest when success rate is 40-70%
OPTIMAL_ZONE_LOW = 0.40
OPTIMAL_ZONE_HIGH = 0.70

# Spaced repetition intervals: session gaps for retrying failed exercises
# After failure, retry at +1, +3, +7, +15, +30 sessions
SPACED_REPETITION_INTERVALS = [1, 3, 7, 15, 30]

# Glicko-2 constants
GLICKO2_TAU = 0.5  # system constant controlling volatility change
GLICKO2_CONVERGENCE = 0.000001  # convergence tolerance for iterative algorithm
GLICKO2_RD_DECAY = 1.02  # RD increases slightly per inactive period (uncertainty grows)


# ---------------------------------------------------------------------------
# SQLite Persistence
# ---------------------------------------------------------------------------

class GymDB:
    """SQLite persistence for Agent Gym data."""

    def __init__(self, db_path: str = ""):
        if not db_path:
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                ".gym_data.db",
            )
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS training_sessions (
                        session_id TEXT PRIMARY KEY,
                        agent_role TEXT NOT NULL,
                        runner_name TEXT,
                        skill_name TEXT,
                        exercise_id TEXT,
                        difficulty TEXT,
                        status TEXT DEFAULT 'pending',
                        score REAL DEFAULT 0,
                        passed INTEGER DEFAULT 0,
                        elo_before REAL DEFAULT 1000,
                        elo_after REAL DEFAULT 1000,
                        duration_s REAL DEFAULT 0,
                        started_at REAL DEFAULT 0,
                        completed_at REAL DEFAULT 0,
                        grade_json TEXT DEFAULT '{}',
                        critic_json TEXT DEFAULT '{}',
                        peer_json TEXT DEFAULT '{}',
                        reflection TEXT DEFAULT '',
                        improvement_json TEXT DEFAULT '[]',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE TABLE IF NOT EXISTS skill_ratings (
                        rating_key TEXT PRIMARY KEY,
                        agent_role TEXT NOT NULL,
                        skill_name TEXT NOT NULL,
                        rating REAL DEFAULT 1000,
                        rating_deviation REAL DEFAULT 350.0,
                        volatility REAL DEFAULT 0.06,
                        sessions INTEGER DEFAULT 0,
                        wins INTEGER DEFAULT 0,
                        losses INTEGER DEFAULT 0,
                        streak INTEGER DEFAULT 0,
                        best_score REAL DEFAULT 0,
                        current_difficulty TEXT DEFAULT 'beginner',
                        last_session_id TEXT DEFAULT '',
                        failed_exercises_json TEXT DEFAULT '{}',
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE INDEX IF NOT EXISTS idx_sessions_role ON training_sessions(agent_role);
                    CREATE INDEX IF NOT EXISTS idx_sessions_skill ON training_sessions(skill_name);
                    CREATE INDEX IF NOT EXISTS idx_sessions_started ON training_sessions(started_at);
                    CREATE INDEX IF NOT EXISTS idx_sessions_status ON training_sessions(status);
                    CREATE INDEX IF NOT EXISTS idx_ratings_role ON skill_ratings(agent_role);
                """)
                conn.commit()
            finally:
                conn.close()

    def save_session(self, session: TrainingSession) -> None:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO training_sessions
                    (session_id, agent_role, runner_name, skill_name, exercise_id,
                     difficulty, status, score, passed, elo_before, elo_after,
                     duration_s, started_at, completed_at, grade_json, critic_json,
                     peer_json, reflection, improvement_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session.session_id, session.agent_role, session.runner_name,
                    session.skill_name, session.exercise_id, session.difficulty,
                    session.status, session.grade.get("score", 0),
                    1 if session.grade.get("passed") else 0,
                    session.elo_before, session.elo_after,
                    session.duration_s, session.started_at, session.completed_at,
                    json.dumps(session.grade),
                    json.dumps({k: v for k, v in session.critic_reviews.items() if isinstance(v, dict)}),
                    json.dumps({k: v for k, v in session.peer_reviews.items() if isinstance(v, dict)}),
                    session.reflection, json.dumps(session.improvement_plan),
                ))
                conn.commit()
            finally:
                conn.close()

    def save_rating(self, key: str, rating: SkillRating) -> None:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO skill_ratings
                    (rating_key, agent_role, skill_name, rating, rating_deviation,
                     volatility, sessions, wins, losses, streak, best_score,
                     current_difficulty, last_session_id, failed_exercises_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    key, rating.agent_role, rating.skill_name, rating.rating,
                    rating.rating_deviation, rating.volatility,
                    rating.sessions, rating.wins, rating.losses, rating.streak,
                    rating.best_score, rating.current_difficulty, rating.last_session_id,
                    json.dumps(rating.failed_exercises),
                ))
                conn.commit()
            finally:
                conn.close()

    def load_ratings(self) -> dict[str, SkillRating]:
        ratings = {}
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                # Get column names to handle schema evolution gracefully
                cursor = conn.execute("SELECT * FROM skill_ratings")
                cols = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                for row in rows:
                    row_dict = dict(zip(cols, row))
                    key = row_dict["rating_key"]
                    failed_ex = {}
                    try:
                        failed_ex = json.loads(row_dict.get("failed_exercises_json", "{}") or "{}")
                    except (json.JSONDecodeError, TypeError):
                        pass
                    ratings[key] = SkillRating(
                        agent_role=row_dict["agent_role"],
                        skill_name=row_dict["skill_name"],
                        rating=row_dict.get("rating", 1000.0),
                        rating_deviation=row_dict.get("rating_deviation", 350.0),
                        volatility=row_dict.get("volatility", 0.06),
                        sessions=row_dict.get("sessions", 0),
                        wins=row_dict.get("wins", 0),
                        losses=row_dict.get("losses", 0),
                        streak=row_dict.get("streak", 0),
                        best_score=row_dict.get("best_score", 0),
                        current_difficulty=row_dict.get("current_difficulty", "beginner"),
                        last_session_id=row_dict.get("last_session_id", ""),
                        failed_exercises=failed_ex,
                    )
            finally:
                conn.close()
        return ratings

    def load_session(self, session_id: str) -> Optional[dict]:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute(
                    "SELECT * FROM training_sessions WHERE session_id = ?",
                    (session_id,)
                ).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    def query_sessions(
        self,
        role: str = "",
        skill: str = "",
        status: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        conditions = []
        params = []
        if role:
            conditions.append("agent_role = ?")
            params.append(role)
        if skill:
            conditions.append("skill_name = ?")
            params.append(skill)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = " AND ".join(conditions) if conditions else "1=1"
        params.extend([limit, offset])

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    f"SELECT * FROM training_sessions WHERE {where} "
                    f"ORDER BY started_at DESC LIMIT ? OFFSET ?",
                    params,
                ).fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()

    # ── Analytics queries ────────────────────────────────────────────────

    def score_trend(self, role: str, skill: str = "", limit: int = 50) -> list[dict]:
        """Get score trend over time for a role (and optionally skill)."""
        conditions = ["agent_role = ?", "status = 'completed'"]
        params: list = [role]
        if skill:
            conditions.append("skill_name = ?")
            params.append(skill)

        where = " AND ".join(conditions)
        params.append(limit)

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                rows = conn.execute(
                    f"SELECT session_id, score, elo_after, difficulty, started_at "
                    f"FROM training_sessions WHERE {where} "
                    f"ORDER BY started_at ASC LIMIT ?",
                    params,
                ).fetchall()
                return [
                    {"session_id": r[0], "score": r[1], "elo": r[2],
                     "difficulty": r[3], "timestamp": r[4]}
                    for r in rows
                ]
            finally:
                conn.close()

    def weakness_analysis(self, role: str) -> list[dict]:
        """Find exercises/skills where the agent consistently scores low."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                rows = conn.execute("""
                    SELECT exercise_id, skill_name, difficulty,
                           COUNT(*) as attempts,
                           AVG(score) as avg_score,
                           SUM(passed) as passes,
                           MIN(score) as worst_score,
                           MAX(score) as best_score
                    FROM training_sessions
                    WHERE agent_role = ? AND status = 'completed'
                    GROUP BY exercise_id
                    HAVING attempts >= 2
                    ORDER BY avg_score ASC
                    LIMIT 20
                """, (role,)).fetchall()
                return [
                    {
                        "exercise_id": r[0], "skill_name": r[1], "difficulty": r[2],
                        "attempts": r[3], "avg_score": round(r[4], 1),
                        "pass_rate": round(r[5] / r[3], 3),
                        "worst_score": r[6], "best_score": r[7],
                        "is_weakness": r[4] < 50,
                    }
                    for r in rows
                ]
            finally:
                conn.close()

    def improvement_rate(self, role: str, window: int = 10) -> dict:
        """Calculate improvement rate over sliding windows."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                rows = conn.execute("""
                    SELECT score, elo_after, started_at
                    FROM training_sessions
                    WHERE agent_role = ? AND status = 'completed'
                    ORDER BY started_at ASC
                """, (role,)).fetchall()

                if len(rows) < 2:
                    return {"sessions": len(rows), "improving": False, "rate": 0.0}

                scores = [r[0] for r in rows]
                elos = [r[1] for r in rows]

                # Calculate moving averages
                early_window = scores[:min(window, len(scores))]
                late_window = scores[max(0, len(scores) - window):]
                early_avg = statistics.mean(early_window)
                late_avg = statistics.mean(late_window)

                # Score slope via linear regression approximation
                n = len(scores)
                x_mean = (n - 1) / 2
                y_mean = statistics.mean(scores)
                numerator = sum((i - x_mean) * (s - y_mean) for i, s in enumerate(scores))
                denominator = sum((i - x_mean) ** 2 for i in range(n))
                slope = numerator / denominator if denominator else 0

                return {
                    "sessions": n,
                    "improving": late_avg > early_avg,
                    "early_avg": round(early_avg, 1),
                    "late_avg": round(late_avg, 1),
                    "delta": round(late_avg - early_avg, 1),
                    "score_slope": round(slope, 3),
                    "elo_start": round(elos[0], 1),
                    "elo_current": round(elos[-1], 1),
                    "elo_delta": round(elos[-1] - elos[0], 1),
                }
            finally:
                conn.close()

    def critic_agreement_rate(self, limit: int = 100) -> dict:
        """Measure how often critics agree with each other."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                rows = conn.execute("""
                    SELECT critic_json FROM training_sessions
                    WHERE status = 'completed' AND critic_json != '{}'
                    ORDER BY started_at DESC LIMIT ?
                """, (limit,)).fetchall()

                agreements = 0
                disagreements = 0
                total_reviews = 0

                for row in rows:
                    try:
                        critics = json.loads(row[0])
                        scores = [
                            v.get("score", 0) for v in critics.values()
                            if isinstance(v, dict) and "score" in v
                        ]
                        if len(scores) >= 2:
                            total_reviews += 1
                            score_range = max(scores) - min(scores)
                            if score_range <= 20:
                                agreements += 1
                            else:
                                disagreements += 1
                    except (json.JSONDecodeError, AttributeError):
                        continue

                return {
                    "total_multi_critic_sessions": total_reviews,
                    "agreements": agreements,
                    "disagreements": disagreements,
                    "agreement_rate": round(agreements / max(total_reviews, 1), 3),
                }
            finally:
                conn.close()

    def per_difficulty_stats(self, role: str) -> dict:
        """Stats broken down by difficulty level."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                rows = conn.execute("""
                    SELECT difficulty, COUNT(*) as attempts,
                           AVG(score) as avg_score, SUM(passed) as passes
                    FROM training_sessions
                    WHERE agent_role = ? AND status = 'completed'
                    GROUP BY difficulty
                """, (role,)).fetchall()
                return {
                    r[0]: {
                        "attempts": r[1], "avg_score": round(r[2], 1),
                        "win_rate": round(r[3] / r[1], 3),
                    }
                    for r in rows
                }
            finally:
                conn.close()

    def global_stats(self) -> dict:
        """Overall gym statistics."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                total = conn.execute("SELECT COUNT(*) FROM training_sessions").fetchone()[0]
                completed = conn.execute(
                    "SELECT COUNT(*) FROM training_sessions WHERE status='completed'"
                ).fetchone()[0]
                avg_score_row = conn.execute(
                    "SELECT AVG(score) FROM training_sessions WHERE status='completed'"
                ).fetchone()
                avg_score = avg_score_row[0] if avg_score_row[0] else 0
                unique_roles = conn.execute(
                    "SELECT COUNT(DISTINCT agent_role) FROM training_sessions"
                ).fetchone()[0]
                unique_skills = conn.execute(
                    "SELECT COUNT(DISTINCT rating_key) FROM skill_ratings"
                ).fetchone()[0]
                avg_rating_row = conn.execute(
                    "SELECT AVG(rating) FROM skill_ratings"
                ).fetchone()
                avg_rating = avg_rating_row[0] if avg_rating_row[0] else 1000

                return {
                    "total_sessions": total,
                    "completed": completed,
                    "failed": total - completed,
                    "avg_score": round(avg_score, 1),
                    "unique_roles": unique_roles,
                    "unique_skills": unique_skills,
                    "avg_rating": round(avg_rating, 1),
                }
            finally:
                conn.close()


# ---------------------------------------------------------------------------
# Agent Gym
# ---------------------------------------------------------------------------

class AgentGym:
    """
    Self-play training environment for SAGE agents.

    Features:
      - 5-phase training loop (play → grade → critique → reflect → compound)
      - SQLite persistence (survives restarts)
      - ELO skill ratings with adaptive K-factor
      - Curriculum auto-progression (difficulty advances on win streaks)
      - Batch training (train all roles in parallel)
      - Peer review (cross-role critique)
      - Rich analytics (score trends, weakness detection, improvement rate)
    """

    def __init__(self, db_path: str = ""):
        self.logger = logging.getLogger("AgentGym")
        self._db = GymDB(db_path)
        self._sessions: dict[str, TrainingSession] = {}
        self._ratings: dict[str, SkillRating] = self._db.load_ratings()
        self._history: list[str] = []

        if self._ratings:
            self.logger.info("Restored %d skill ratings from SQLite", len(self._ratings))

    # ── Training loop ────────────────────────────────────────────────────

    def train(
        self,
        role: str,
        difficulty: str = "",
        skill_name: str = "",
        exercise_id: str = "",
        enable_peer_review: bool = False,
    ) -> TrainingSession:
        """
        Run a complete training session: play → grade → critique → reflect → compound.

        If difficulty is empty, uses the curriculum-recommended level.
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

        # Curriculum: auto-select difficulty if not specified
        rating_key = f"{role}:{skill_name}"
        current_rating = self._ratings.get(rating_key, SkillRating(role, skill_name))
        if not difficulty:
            difficulty = current_rating.current_difficulty

        # Get exercises
        exercises = runner.get_exercises(difficulty=difficulty)
        if not exercises:
            # Fallback to intermediate
            exercises = runner.get_exercises(difficulty="intermediate")
            difficulty = "intermediate"
        if not exercises:
            return self._failed_session(session_id, role, f"No exercises available")

        # Select exercise (prefer one not recently attempted)
        exercise = None
        if exercise_id:
            exercise = next((e for e in exercises if e.id == exercise_id), None)
        if not exercise:
            exercise = self._select_exercise(exercises, role, skill_name)

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

            # 4. CRITIQUE — N critics review
            session.status = "critiquing"
            session.critic_reviews = self._get_critic_reviews(result, exercise, role)

            # 4b. PEER REVIEW — optional cross-role critique
            if enable_peer_review:
                session.peer_reviews = self._get_peer_reviews(result, exercise, role)

            # 5. REFLECT — generate improvement plan
            session.status = "reflecting"
            session.reflection, session.improvement_plan = self._reflect(
                exercise, score, session.critic_reviews, session.peer_reviews, role
            )

            # 6. Update Glicko-2 rating
            session.elo_after = self._update_rating(
                rating_key, current_rating, score.score, score.passed,
                session_id, exercise.id,
            )

            # 7. Curriculum check — advance or demote difficulty
            self._curriculum_check(rating_key, current_rating)

            # 8. Store learnings in vector memory
            self._store_learning(session)

            # 9. Persist to SQLite
            session.status = "completed"

        except Exception as exc:
            self.logger.error("Training session failed: %s", exc)
            session.status = "failed"
            session.attempt_result["error"] = str(exc)

        session.completed_at = time.time()
        session.duration_s = time.monotonic() - start
        self._history.append(session_id)

        # Persist
        self._db.save_session(session)
        self._db.save_rating(rating_key, current_rating)

        self.logger.info(
            "Training %s: role=%s, skill=%s, score=%.1f, elo=%.1f→%.1f, diff=%s",
            session_id[:8], role, skill_name,
            session.grade.get("score", 0),
            session.elo_before, session.elo_after,
            difficulty,
        )

        return session

    # ── Batch training ───────────────────────────────────────────────────

    def train_batch(
        self,
        roles: list[str] | None = None,
        difficulty: str = "",
        enable_peer_review: bool = False,
        max_parallel: int = 4,
    ) -> list[TrainingSession]:
        """
        Train multiple roles in parallel.

        Args:
            roles: List of roles to train. If None, trains all registered roles.
            difficulty: If empty, uses curriculum-recommended for each.
            enable_peer_review: Enable cross-role review.
            max_parallel: Max concurrent training sessions.

        Returns:
            List of completed TrainingSessions.
        """
        import concurrent.futures

        if roles is None:
            from src.integrations.base_runner import get_role_to_runner_map
            roles = list(get_role_to_runner_map().keys())

        self.logger.info("Batch training %d roles (parallel=%d)", len(roles), max_parallel)

        sessions = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as executor:
            futures = {
                executor.submit(
                    self.train, role, difficulty,
                    enable_peer_review=enable_peer_review
                ): role
                for role in roles
            }
            for future in concurrent.futures.as_completed(futures):
                role = futures[future]
                try:
                    session = future.result()
                    sessions.append(session)
                except Exception as exc:
                    self.logger.error("Batch training failed for %s: %s", role, exc)

        self.logger.info(
            "Batch complete: %d/%d successful",
            sum(1 for s in sessions if s.status == "completed"),
            len(roles),
        )
        return sessions

    # ── Exercise selection ───────────────────────────────────────────────

    def _select_exercise(self, exercises, role: str, skill: str):
        """
        Smart exercise selection with three priority tiers:

        1. Spaced repetition — failed exercises due for retry (highest priority)
        2. Optimal zone — exercises where agent success rate is 40-70% (best learning)
        3. Unseen — exercises not yet attempted (exploration)

        Falls back to least-recently-attempted if all tiers are empty.
        """
        rating_key = f"{role}:{skill}"
        current_rating = self._ratings.get(rating_key)
        exercise_ids = {e.id for e in exercises}

        # Tier 1: Spaced repetition — failed exercises due for review
        if current_rating and current_rating.failed_exercises:
            due_ids = [
                eid for eid, threshold in current_rating.failed_exercises.items()
                if current_rating.sessions >= threshold and eid in exercise_ids
            ]
            if due_ids:
                match = next((e for e in exercises if e.id == due_ids[0]), None)
                if match:
                    self.logger.info("Spaced repetition: retrying %s for %s", match.id, role)
                    return match

        # Get per-exercise success rates from history
        recent_sessions = self._db.query_sessions(role=role, status="completed", limit=50)
        exercise_stats: dict[str, dict] = {}  # exercise_id → {attempts, passes}
        recent_ids = set()
        for s in recent_sessions:
            eid = s.get("exercise_id", "")
            recent_ids.add(eid)
            if eid not in exercise_stats:
                exercise_stats[eid] = {"attempts": 0, "passes": 0}
            exercise_stats[eid]["attempts"] += 1
            if s.get("passed"):
                exercise_stats[eid]["passes"] += 1

        # Tier 2: Optimal zone — exercises with 40-70% success rate (best learning)
        optimal = []
        for e in exercises:
            stats = exercise_stats.get(e.id)
            if stats and stats["attempts"] >= 2:
                rate = stats["passes"] / stats["attempts"]
                if OPTIMAL_ZONE_LOW <= rate <= OPTIMAL_ZONE_HIGH:
                    optimal.append(e)
        if optimal:
            self.logger.info("Optimal zone: selecting from %d exercises for %s", len(optimal), role)
            return optimal[0]

        # Tier 3: Unseen exercises (exploration)
        unseen = [e for e in exercises if e.id not in recent_ids]
        if unseen:
            return unseen[0]

        # Fallback: least recently attempted
        return exercises[0]

    # ── Curriculum ───────────────────────────────────────────────────────

    def _curriculum_check(self, key: str, rating: SkillRating) -> None:
        """Auto-advance or demote difficulty based on recent performance."""
        current_idx = DIFFICULTY_ORDER.index(rating.current_difficulty) \
            if rating.current_difficulty in DIFFICULTY_ORDER else 0

        # Calculate win rate at current difficulty
        recent = self._db.query_sessions(
            role=rating.agent_role, skill=rating.skill_name,
            status="completed", limit=20,
        )
        at_current = [s for s in recent if s.get("difficulty") == rating.current_difficulty]

        if len(at_current) >= CURRICULUM_ADVANCE_MIN_SESSIONS:
            wins = sum(1 for s in at_current if s.get("passed"))
            win_rate = wins / len(at_current)

            # Advance
            if win_rate >= CURRICULUM_ADVANCE_WIN_RATE and current_idx < len(DIFFICULTY_ORDER) - 1:
                old = rating.current_difficulty
                rating.current_difficulty = DIFFICULTY_ORDER[current_idx + 1]
                self.logger.info(
                    "Curriculum advance: %s %s → %s (win_rate=%.0f%%)",
                    key, old, rating.current_difficulty, win_rate * 100,
                )

        if len(at_current) >= CURRICULUM_DEMOTE_MIN_SESSIONS:
            wins = sum(1 for s in at_current if s.get("passed"))
            win_rate = wins / len(at_current)

            # Demote
            if win_rate <= CURRICULUM_DEMOTE_WIN_RATE and current_idx > 0:
                old = rating.current_difficulty
                rating.current_difficulty = DIFFICULTY_ORDER[current_idx - 1]
                self.logger.info(
                    "Curriculum demote: %s %s → %s (win_rate=%.0f%%)",
                    key, old, rating.current_difficulty, win_rate * 100,
                )

    # ── Peer review ──────────────────────────────────────────────────────

    def _get_peer_reviews(
        self, result, exercise, role: str
    ) -> dict[str, dict]:
        """Get reviews from agents in different roles (cross-discipline feedback)."""
        peer_reviews = {}

        # Map roles to review focus areas
        PEER_ROLES = {
            "firmware_engineer": {"focus": "security and memory safety", "checks": ["buffer overflow", "null pointer", "stack usage"]},
            "qa_engineer": {"focus": "test coverage and edge cases", "checks": ["error handling", "boundary conditions", "failure modes"]},
            "data_scientist": {"focus": "data handling and metrics", "checks": ["data validation", "metric correctness", "reproducibility"]},
            "technical_writer": {"focus": "documentation quality", "checks": ["comments", "API docs", "README"]},
            "ux_designer": {"focus": "user experience", "checks": ["error messages", "feedback clarity", "accessibility"]},
        }

        # Select 1-2 peer roles that differ from the current role
        peer_candidates = [r for r in PEER_ROLES if r != role][:2]

        for peer_role in peer_candidates:
            peer_info = PEER_ROLES[peer_role]
            try:
                from src.core.llm_gateway import llm_gateway
                code_output = result.output[:3000] if result.output else "No output"

                prompt = (
                    f"You are a {peer_role} reviewing work done by a {role}.\n"
                    f"Focus on: {peer_info['focus']}\n"
                    f"Check for: {peer_info['checks']}\n\n"
                    f"Exercise: {exercise.description}\n"
                    f"Output:\n{code_output}\n\n"
                    f"Return JSON: {{\"score\": 0-100, \"issues\": [...], \"suggestions\": [...]}}"
                )

                response = llm_gateway.generate(
                    prompt,
                    f"You are a {peer_role} doing a cross-discipline code review. "
                    f"Be constructive but honest. Focus only on your area of expertise.",
                    trace_name=f"agent_gym.peer.{peer_role}",
                )

                import re
                response = response.replace("```json", "").replace("```", "").strip()
                match = re.search(r'\{[\s\S]*\}', response)
                if match:
                    review = json.loads(match.group(0))
                    review["score"] = int(review.get("score", 0))
                    peer_reviews[peer_role] = review
                else:
                    peer_reviews[peer_role] = {"score": 0, "parse_error": True}

            except Exception as exc:
                self.logger.warning("Peer review by %s failed: %s", peer_role, exc)
                peer_reviews[peer_role] = {"score": 0, "error": str(exc)}

        return peer_reviews

    # ── Critic reviews ───────────────────────────────────────────────────

    def _get_critic_reviews(
        self, result, exercise, role: str
    ) -> dict[str, dict]:
        """Get reviews from all available critic providers."""
        reviews = {}
        try:
            from src.agents.critic import critic_agent
            code_output = result.output[:4000] if result.output else "No output"

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
        self, exercise, score, critic_reviews: dict, peer_reviews: dict, role: str
    ) -> tuple[str, list[str]]:
        """Generate a reflection and improvement plan from all feedback sources."""
        try:
            from src.core.llm_gateway import llm_gateway

            critic_summary = "\n".join(
                f"- {name}: score={r.get('score', '?')}, flaws={r.get('flaws', r.get('issues', []))}"
                for name, r in critic_reviews.items()
                if isinstance(r, dict)
            )

            peer_summary = "\n".join(
                f"- {name} (peer): focus={r.get('focus', 'general')}, issues={r.get('issues', [])}"
                for name, r in peer_reviews.items()
                if isinstance(r, dict) and "score" in r
            ) if peer_reviews else "No peer reviews."

            # Search vector memory for prior learnings on this exercise
            prior_context = ""
            try:
                from src.memory.vector_store import vector_memory
                prior = vector_memory.search(
                    f"training {role} {exercise.id}",
                    n_results=3,
                    metadata_filter={"type": "gym_training"},
                )
                if prior:
                    prior_context = "\nPrior training insights:\n" + "\n".join(
                        f"- {p.get('text', '')[:150]}" for p in prior
                    )
            except Exception:
                pass

            prompt = (
                f"You just attempted this exercise as a {role}:\n"
                f"Exercise: {exercise.description}\n"
                f"Your score: {score.score}/100 ({'PASSED' if score.passed else 'FAILED'})\n"
                f"Grading feedback: {score.feedback}\n"
                f"Improvement hints: {score.improvement_hints}\n\n"
                f"Critic reviews:\n{critic_summary}\n\n"
                f"Peer reviews:\n{peer_summary}\n"
                f"{prior_context}\n\n"
                f"Reflect honestly. What specific things would you do differently next time?\n"
                f"Return JSON: {{\"reflection\": \"...\", \"improvement_plan\": [\"step1\", ...]}}"
            )

            response = llm_gateway.generate(
                prompt,
                f"You are a self-aware AI agent in training for the role of {role}. "
                f"Be honest about your weaknesses. Focus on specific, actionable improvements. "
                f"Reference prior learnings if relevant.",
                trace_name="agent_gym.reflect",
            )

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

    # ── Glicko-2 Rating ─────────────────────────────────────────────────

    def _update_rating(
        self, key: str, current: SkillRating, score: float, passed: bool,
        session_id: str = "", exercise_id: str = "",
    ) -> float:
        """
        Update rating using Glicko-2 inspired algorithm.

        Glicko-2 advantages over basic ELO:
          - Rating deviation (RD) tracks confidence — high RD = uncertain skill level
          - RD shrinks with more data, grows during inactivity
          - Volatility tracks consistency — erratic agents have high volatility
          - K-factor is effectively adaptive via RD (high RD = bigger rating changes)

        Also manages spaced repetition: failed exercises are scheduled for retry
        at increasing intervals (1, 3, 7, 15, 30 sessions).
        """
        # ── Glicko-2 update ──
        # Convert to Glicko-2 scale (μ = (rating - 1500) / 173.7178)
        MU_SCALE = 173.7178
        mu = (current.rating - 1500) / MU_SCALE
        phi = current.rating_deviation / MU_SCALE
        sigma = current.volatility

        # Exercise "opponent" rating: score maps to opponent strength
        # Score 100 → opponent at 500 ELO (easy win), Score 0 → opponent at 2500 (hard loss)
        opponent_rating = 1500 + (50 - score) * 10
        mu_j = (opponent_rating - 1500) / MU_SCALE
        phi_j = 1.0  # fixed opponent RD (exercise difficulty is known)

        # g(φ) function
        def g(phi_val):
            return 1 / math.sqrt(1 + 3 * phi_val ** 2 / (math.pi ** 2))

        # E(μ, μj, φj) — expected score
        g_phi_j = g(phi_j)
        e_val = 1 / (1 + math.exp(-g_phi_j * (mu - mu_j)))

        # Variance (v)
        v = 1 / (g_phi_j ** 2 * e_val * (1 - e_val))

        # Actual outcome: 1 for pass, 0 for fail
        outcome = 1.0 if passed else 0.0
        delta = v * g_phi_j * (outcome - e_val)

        # Simplified volatility update (avoid full iterative Glicko-2 for speed)
        # If result is unexpected, volatility increases; if expected, it decreases
        surprise = abs(outcome - e_val)
        sigma_new = sigma * (1 + 0.1 * (surprise - 0.5))
        sigma_new = max(0.01, min(0.15, sigma_new))  # clamp

        # Update phi (rating deviation)
        phi_star = math.sqrt(phi ** 2 + sigma_new ** 2)
        phi_new = 1 / math.sqrt(1 / phi_star ** 2 + 1 / v)

        # Update mu (rating)
        mu_new = mu + phi_new ** 2 * g_phi_j * (outcome - e_val)

        # Convert back to ELO scale
        new_rating = mu_new * MU_SCALE + 1500
        new_rd = phi_new * MU_SCALE

        # Clamp
        new_rating = max(100, min(3000, new_rating))
        new_rd = max(30, min(350, new_rd))  # RD floor 30 (very confident), cap 350 (uncertain)

        current.rating = new_rating
        current.rating_deviation = new_rd
        current.volatility = sigma_new
        current.sessions += 1
        if passed:
            current.wins += 1
            current.streak = max(current.streak + 1, 1)
            # Clear from spaced repetition if passed
            if exercise_id and exercise_id in current.failed_exercises:
                del current.failed_exercises[exercise_id]
        else:
            current.losses += 1
            current.streak = min(current.streak - 1, -1)
            # Schedule for spaced repetition
            if exercise_id:
                fail_count = sum(1 for eid in current.failed_exercises if eid == exercise_id)
                interval_idx = min(fail_count, len(SPACED_REPETITION_INTERVALS) - 1)
                interval = SPACED_REPETITION_INTERVALS[interval_idx]
                current.failed_exercises[exercise_id] = current.sessions + interval

        current.best_score = max(current.best_score, score)
        current.last_session_id = session_id
        self._ratings[key] = current

        return new_rating

    # ── Vector memory ────────────────────────────────────────────────────

    def _store_learning(self, session: TrainingSession) -> None:
        """Store training insights in vector memory for future context."""
        try:
            from src.memory.vector_store import vector_memory

            learning = (
                f"TRAINING ({session.agent_role}, {session.skill_name}): "
                f"Exercise={session.exercise_id}, Score={session.grade.get('score', 0)}/100, "
                f"Difficulty={session.difficulty}. "
                f"Reflection: {session.reflection[:200]}. "
                f"Improvements: {session.improvement_plan[:3]}"
            )
            vector_memory.add_feedback(
                learning,
                metadata={
                    "type": "gym_training",
                    "agent_role": session.agent_role,
                    "skill_name": session.skill_name,
                    "exercise_id": session.exercise_id,
                    "score": session.grade.get("score", 0),
                    "elo": session.elo_after,
                    "difficulty": session.difficulty,
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
        self._db.save_session(session)
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

    # ── Analytics ────────────────────────────────────────────────────────

    def analytics(self, role: str = "", skill: str = "") -> dict:
        """
        Comprehensive analytics dashboard data.

        Returns everything needed for charts:
          - score_trend: scores over time (for line chart)
          - elo_curve: ELO progression (for line chart)
          - weakness_map: exercises with lowest scores (for heatmap)
          - improvement_rate: is the agent getting better? (for KPI cards)
          - difficulty_breakdown: performance per level (for bar chart)
          - critic_agreement: how often critics agree (for pie chart)
          - leaderboard: current rankings (for table)
        """
        result = {
            "global_stats": self._db.global_stats(),
            "leaderboard": self.get_leaderboard(),
            "critic_agreement": self._db.critic_agreement_rate(),
        }

        if role:
            result["score_trend"] = self._db.score_trend(role, skill)
            result["weakness_map"] = self._db.weakness_analysis(role)
            result["improvement_rate"] = self._db.improvement_rate(role)
            result["difficulty_breakdown"] = self._db.per_difficulty_stats(role)

            # Current rating
            if skill:
                rating = self.get_rating(role, skill)
                if rating:
                    result["current_rating"] = rating.to_dict()
            else:
                result["role_ratings"] = [r.to_dict() for r in self.get_ratings_for_role(role)]

        return result

    def stats(self) -> dict:
        return self._db.global_stats()


# Module-level singleton
agent_gym = AgentGym()
