"""
Collective Intelligence Routes
===============================
API endpoints for Git-backed agent knowledge sharing:
  - Learnings: publish, search, validate shared knowledge
  - Help Requests: create, claim, respond, close cross-agent help
  - Sync: pull latest from remote, re-index
  - Stats: contribution metrics and trending topics
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Collective Intelligence"])


# ─── Dependency ────────────────────────────────────────────────────────

def _get_cm():
    """Lazy-load CollectiveMemory singleton."""
    from src.core.collective_memory import get_collective_memory
    return get_collective_memory()


# ─── Pydantic Models ──────────────────────────────────────────────────

class LearningCreate(BaseModel):
    author_agent: str
    author_solution: str
    topic: str
    title: str
    content: str
    tags: List[str] = Field(default_factory=list)
    confidence: float = 0.5
    source_task_id: str = ""


class ValidateRequest(BaseModel):
    validated_by: str


class HelpRequestCreate(BaseModel):
    title: str
    requester_agent: str
    requester_solution: str
    urgency: str = "medium"
    required_expertise: List[str] = Field(default_factory=list)
    context: str = ""


class ClaimRequest(BaseModel):
    agent: str
    solution: str


class ResponseCreate(BaseModel):
    responder_agent: str
    responder_solution: str
    content: str


# ─── Learning Endpoints ───────────────────────────────────────────────

@router.post("/collective/learnings", status_code=201)
async def publish_learning(body: LearningCreate, cm=Depends(_get_cm)):
    """Publish a learning to the collective knowledge base."""
    learning_id = cm.publish_learning(body.model_dump())
    return {"id": learning_id, "status": "published"}


@router.get("/collective/learnings")
async def list_learnings(
    query: str = "",
    tags: str = "",
    solution: str = "",
    limit: int = 20,
    offset: int = 0,
    cm=Depends(_get_cm),
):
    """List or search collective learnings."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None

    if query:
        results = cm.search_learnings(
            query=query, tags=tag_list, solution=solution or None, limit=limit,
        )
    else:
        results = cm.list_learnings(
            solution=solution or None, limit=limit, offset=offset,
        )
        if tag_list:
            results = [r for r in results if any(t in r.get("tags", []) for t in tag_list)]

    return {"learnings": results, "count": len(results)}


@router.get("/collective/learnings/{learning_id}")
async def get_learning(learning_id: str, cm=Depends(_get_cm)):
    """Get a specific learning by ID."""
    result = cm.get_learning(learning_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Learning {learning_id} not found")
    return result


@router.post("/collective/learnings/{learning_id}/validate")
async def validate_learning(
    learning_id: str, body: ValidateRequest, cm=Depends(_get_cm),
):
    """Mark a learning as validated, boosting its confidence."""
    try:
        result = cm.validate_learning(learning_id, validated_by=body.validated_by)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ─── Help Request Endpoints ───────────────────────────────────────────

@router.post("/collective/help-requests", status_code=201)
async def create_help_request(body: HelpRequestCreate, cm=Depends(_get_cm)):
    """Create a help request for cross-agent collaboration."""
    req_id = cm.create_help_request(body.model_dump())
    return {"id": req_id, "status": "open"}


@router.get("/collective/help-requests")
async def list_help_requests(
    status: str = "open",
    expertise: str = "",
    cm=Depends(_get_cm),
):
    """List help requests filtered by status and expertise."""
    exp_list = [e.strip() for e in expertise.split(",") if e.strip()] if expertise else None
    results = cm.list_help_requests(status=status, expertise=exp_list)
    return {"requests": results, "count": len(results)}


@router.put("/collective/help-requests/{request_id}/claim")
async def claim_help_request(
    request_id: str, body: ClaimRequest, cm=Depends(_get_cm),
):
    """Claim a help request."""
    try:
        result = cm.claim_help_request(request_id, agent=body.agent, solution=body.solution)
        return result
    except ValueError as exc:
        msg = str(exc)
        if "already claimed" in msg:
            raise HTTPException(status_code=409, detail=msg)
        raise HTTPException(status_code=404, detail=msg)


@router.put("/collective/help-requests/{request_id}/respond")
async def respond_to_help_request(
    request_id: str, body: ResponseCreate, cm=Depends(_get_cm),
):
    """Add a response to a help request."""
    try:
        result = cm.respond_to_help_request(request_id, body.model_dump())
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.put("/collective/help-requests/{request_id}/close")
async def close_help_request(request_id: str, cm=Depends(_get_cm)):
    """Close a help request."""
    try:
        result = cm.close_help_request(request_id)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ─── Sync & Stats ─────────────────────────────────────────────────────

@router.post("/collective/sync")
async def trigger_sync(cm=Depends(_get_cm)):
    """Pull latest from remote and re-index all learnings."""
    result = cm.sync()
    return result


@router.get("/collective/stats")
async def get_stats(cm=Depends(_get_cm)):
    """Get collective intelligence statistics."""
    return cm.get_stats()
