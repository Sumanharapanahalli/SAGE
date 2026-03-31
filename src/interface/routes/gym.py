"""Gym & Exercise Catalog endpoints — /gym/*"""

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["gym"])


# ── Request Models ────────────────────────────────────────────────────

class GymTrainRequest(BaseModel):
    role: str
    difficulty: str = ""
    skill_name: str = ""
    exercise_id: str = ""
    enable_peer_review: bool = False


class GymBatchRequest(BaseModel):
    roles: Optional[List[str]] = None
    difficulty: str = ""
    enable_peer_review: bool = False
    max_parallel: int = 4


class CatalogGenerateRequest(BaseModel):
    domain: str
    count: int = 50
    difficulty: str = ""
    axis: str = ""


# ── Training Endpoints ───────────────────────────────────────────────

@router.post("/gym/train")
async def gym_train(req: GymTrainRequest):
    """Start a training session for an agent role (self-play exercise)."""
    from src.core.agent_gym import agent_gym
    session = agent_gym.train(
        role=req.role,
        difficulty=req.difficulty,
        skill_name=req.skill_name,
        exercise_id=req.exercise_id,
        enable_peer_review=req.enable_peer_review,
    )
    return session.to_dict()


@router.post("/gym/train/batch")
async def gym_train_batch(req: GymBatchRequest):
    """Train multiple roles in parallel. If roles is empty, trains all registered roles."""
    from src.core.agent_gym import agent_gym
    sessions = agent_gym.train_batch(
        roles=req.roles,
        difficulty=req.difficulty,
        enable_peer_review=req.enable_peer_review,
        max_parallel=req.max_parallel,
    )
    completed = sum(1 for s in sessions if s.status == "completed")
    return {
        "total": len(sessions),
        "completed": completed,
        "failed": len(sessions) - completed,
        "sessions": [s.to_dict() for s in sessions],
    }


# ── Session & Ratings ────────────────────────────────────────────────

@router.get("/gym/session/{session_id}")
async def gym_session(session_id: str):
    """Get details of a training session."""
    from src.core.agent_gym import agent_gym
    session = agent_gym.get_session(session_id)
    if not session:
        db_session = agent_gym._db.load_session(session_id)
        if db_session:
            return db_session
        return {"error": f"Session '{session_id}' not found"}
    return session.to_dict()


@router.get("/gym/ratings")
async def gym_ratings():
    """Get all agent skill ratings (leaderboard)."""
    from src.core.agent_gym import agent_gym
    return {
        "leaderboard": agent_gym.get_leaderboard(),
        "stats": agent_gym.stats(),
    }


@router.get("/gym/ratings/{role}")
async def gym_role_ratings(role: str):
    """Get skill ratings for a specific agent role."""
    from src.core.agent_gym import agent_gym
    ratings = agent_gym.get_ratings_for_role(role)
    return {"role": role, "ratings": [r.to_dict() for r in ratings]}


@router.get("/gym/history")
async def gym_history(limit: int = 20):
    """Get recent training session history."""
    from src.core.agent_gym import agent_gym
    return {"sessions": agent_gym.get_history(limit=limit)}


@router.get("/gym/analytics")
async def gym_analytics(role: str = "", skill: str = ""):
    """Comprehensive gym analytics dashboard data."""
    from src.core.agent_gym import agent_gym
    return agent_gym.analytics(role=role, skill=skill)


@router.get("/gym/curriculum/{role}")
async def gym_curriculum(role: str):
    """Get curriculum status for a role — current difficulty and progression data."""
    from src.core.agent_gym import agent_gym
    ratings = agent_gym.get_ratings_for_role(role)
    if not ratings:
        return {"role": role, "skills": [], "message": "No training data yet"}
    return {
        "role": role,
        "skills": [
            {
                "skill": r.skill_name,
                "current_difficulty": r.current_difficulty,
                "sessions": r.sessions,
                "win_rate": round(r.wins / max(r.sessions, 1), 3),
                "rating": round(r.rating, 1),
            }
            for r in ratings
        ],
    }


# ── Exercise Catalog ─────────────────────────────────────────────────

@router.get("/gym/catalog")
async def gym_catalog_stats():
    """Get exercise catalog statistics — total exercises per domain and difficulty."""
    from src.core.exercise_catalog import exercise_catalog
    return exercise_catalog.stats()


@router.get("/gym/catalog/{domain}")
async def gym_catalog_domain(domain: str, difficulty: str = ""):
    """Get exercises for a specific domain, optionally filtered by difficulty."""
    from src.core.exercise_catalog import exercise_catalog
    exercises = exercise_catalog.get_for_domain(domain, difficulty)
    return {
        "domain": domain,
        "difficulty": difficulty or "all",
        "count": len(exercises),
        "exercises": [e.to_dict() for e in exercises[:100]],
    }


@router.post("/gym/catalog/generate")
async def gym_catalog_generate(req: CatalogGenerateRequest):
    """Generate exercise variants from seed exercises using LLM."""
    from src.core.exercise_catalog import exercise_catalog
    generated = exercise_catalog.generate_variants(
        domain=req.domain,
        count=req.count,
        difficulty=req.difficulty,
        axis=req.axis,
    )
    return {
        "generated": len(generated),
        "domain": req.domain,
        "exercises": [e.to_dict() for e in generated],
        "catalog_stats": exercise_catalog.stats(),
    }
