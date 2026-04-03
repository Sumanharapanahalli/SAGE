"""Critic Agent endpoints — prompts, human expert reviews."""

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(tags=["critic"])


# ── Request Models ────────────────────────────────────────────────────

class PromptUpdateRequest(BaseModel):
    key: str
    prompt: str


class HumanReviewRequest(BaseModel):
    review_type: str = "code"
    artifact: str
    description: str
    context: str = ""


class HumanReviewSubmission(BaseModel):
    score: int = Field(ge=0, le=100)
    feedback: str
    flaws: Optional[List[str]] = None
    suggestions: Optional[List[str]] = None


# ── Prompt Management ─────────────────────────────────────────────────

@router.get("/critic/prompts")
async def get_critic_prompts():
    """Get all critic system prompts (defaults + custom overrides)."""
    from src.agents.critic import critic_agent
    return {"prompts": critic_agent.get_all_prompts()}


@router.put("/critic/prompts")
async def update_critic_prompt(req: PromptUpdateRequest):
    """Update a critic system prompt. Persists to config/critic_prompts.json."""
    from src.agents.critic import critic_agent
    prompts = critic_agent.update_prompt(req.key, req.prompt)
    return {"status": "updated", "key": req.key, "prompts": prompts}


@router.delete("/critic/prompts/{key}")
async def delete_critic_prompt(key: str):
    """Remove a custom prompt override (reverts to default)."""
    from src.agents.critic import critic_agent
    prompts = critic_agent.delete_prompt(key)
    return {"status": "deleted", "key": key, "prompts": prompts}


# ── Human Expert Reviews ──────────────────────────────────────────────

@router.post("/critic/human/request")
async def request_human_review(req: HumanReviewRequest):
    """Queue an artifact for human expert review."""
    from src.agents.critic import critic_agent
    result = critic_agent.request_human_review(
        review_type=req.review_type,
        artifact=req.artifact,
        description=req.description,
        context=req.context,
    )
    return result


@router.post("/critic/human/{review_id}/submit")
async def submit_human_review(review_id: str, req: HumanReviewSubmission):
    """Submit a human expert review for a pending request."""
    from src.agents.critic import critic_agent
    result = critic_agent.submit_human_review(
        review_id=review_id,
        score=req.score,
        feedback=req.feedback,
        flaws=req.flaws,
        suggestions=req.suggestions,
    )
    return result


@router.get("/critic/human/pending")
async def list_pending_human_reviews():
    """List all pending human expert reviews awaiting submission."""
    from src.agents.critic import critic_agent
    return {"pending": critic_agent.get_pending_human_reviews()}


@router.get("/critic/human/{review_id}")
async def get_human_review(review_id: str):
    """Get a completed human review by ID."""
    from src.agents.critic import critic_agent
    review = critic_agent.get_human_review(review_id)
    if review:
        return review
    return {"error": f"Review '{review_id}' not found"}
