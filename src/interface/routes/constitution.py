"""
SAGE — Constitution API Routes
===============================
CRUD endpoints for per-solution constitution (blue book).
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/constitution", tags=["constitution"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class PrincipleCreate(BaseModel):
    id: str
    text: str
    weight: float = Field(0.5, ge=0.0, le=1.0)

class PrincipleUpdate(BaseModel):
    text: Optional[str] = None
    weight: Optional[float] = Field(None, ge=0.0, le=1.0)

class ConstraintBody(BaseModel):
    constraint: str

class VoiceUpdate(BaseModel):
    tone: Optional[str] = None
    avoid: Optional[list[str]] = None

class DecisionsUpdate(BaseModel):
    default_approval_tier: Optional[str] = None
    auto_approve_categories: Optional[list[str]] = None
    escalation_keywords: Optional[list[str]] = None

class ActionCheck(BaseModel):
    action: str

class SaveBody(BaseModel):
    changed_by: str = "web-ui"

class ConstitutionImport(BaseModel):
    data: dict


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

def _get_constitution():
    from src.core.constitution import get_constitution
    return get_constitution()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
def get_constitution():
    """Return the full constitution."""
    c = _get_constitution()
    return c.to_dict()

@router.get("/stats")
def get_stats():
    c = _get_constitution()
    return c.get_stats()

@router.get("/validate")
def validate():
    c = _get_constitution()
    errors = c.validate()
    return {"valid": len(errors) == 0, "errors": errors}

@router.get("/preamble")
def get_preamble():
    """Return the prompt preamble that gets injected into agent prompts."""
    c = _get_constitution()
    return {"preamble": c.build_prompt_preamble()}

@router.get("/history")
def get_history():
    c = _get_constitution()
    return {"history": c.get_version_history()}


# ── Principles ────────────────────────────────────────────────────────────

@router.get("/principles")
def list_principles():
    c = _get_constitution()
    return {"principles": c.principles}

@router.get("/principles/{principle_id}")
def get_principle(principle_id: str):
    c = _get_constitution()
    p = c.get_principle(principle_id)
    if p is None:
        raise HTTPException(404, f"Principle '{principle_id}' not found")
    return p

@router.post("/principles")
def add_principle(body: PrincipleCreate):
    c = _get_constitution()
    try:
        c.add_principle(id=body.id, text=body.text, weight=body.weight)
        return {"status": "added", "id": body.id}
    except ValueError as e:
        raise HTTPException(409, str(e))

@router.put("/principles/{principle_id}")
def update_principle(principle_id: str, body: PrincipleUpdate):
    c = _get_constitution()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        c.update_principle(principle_id, **updates)
        return {"status": "updated", "id": principle_id}
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.delete("/principles/{principle_id}")
def remove_principle(principle_id: str):
    c = _get_constitution()
    try:
        c.remove_principle(principle_id)
        return {"status": "removed", "id": principle_id}
    except ValueError as e:
        raise HTTPException(404, str(e))


# ── Constraints ───────────────────────────────────────────────────────────

@router.get("/constraints")
def list_constraints():
    c = _get_constitution()
    return {"constraints": c.constraints}

@router.post("/constraints")
def add_constraint(body: ConstraintBody):
    c = _get_constitution()
    c.add_constraint(body.constraint)
    return {"status": "added"}

@router.delete("/constraints")
def remove_constraint(body: ConstraintBody):
    c = _get_constitution()
    try:
        c.remove_constraint(body.constraint)
        return {"status": "removed"}
    except ValueError as e:
        raise HTTPException(404, str(e))


# ── Voice & Decisions ─────────────────────────────────────────────────────

@router.get("/voice")
def get_voice():
    c = _get_constitution()
    return c.voice

@router.put("/voice")
def update_voice(body: VoiceUpdate):
    c = _get_constitution()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    c.update_voice(**updates)
    return {"status": "updated"}

@router.get("/decisions")
def get_decisions():
    c = _get_constitution()
    return c.decisions

@router.put("/decisions")
def update_decisions(body: DecisionsUpdate):
    c = _get_constitution()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    c.update_decisions(**updates)
    return {"status": "updated"}


# ── Actions ───────────────────────────────────────────────────────────────

@router.post("/check-action")
def check_action(body: ActionCheck):
    c = _get_constitution()
    return c.check_action(body.action)

@router.post("/check-escalation")
def check_escalation(body: ActionCheck):
    c = _get_constitution()
    return c.check_escalation(body.action)


# ── Save & Import ─────────────────────────────────────────────────────────

@router.post("/save")
def save_constitution(body: SaveBody):
    c = _get_constitution()
    c.save(changed_by=body.changed_by)
    return {"status": "saved", "version": c.version}

@router.post("/reload")
def reload_constitution():
    c = _get_constitution()
    c.reload()
    return {"status": "reloaded", "version": c.version}

@router.post("/import")
def import_constitution(body: ConstitutionImport):
    """Replace the entire constitution with imported data."""
    c = _get_constitution()
    c._data = body.data
    c.save(changed_by="import")
    return {"status": "imported", "version": c.version}
