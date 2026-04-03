"""
Regulatory Compliance Routes
=============================
API endpoints for multi-standard regulatory compliance assessment.
"""

import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/regulatory", tags=["Regulatory Compliance"])


class ProductProfile(BaseModel):
    product_name: str
    product_type: str = "samd"
    risk_class: str = "II"
    intended_use: Optional[str] = None
    target_regions: List[str] = ["us"]
    uses_ai_ml: bool = False
    processes_images: bool = False
    processes_signals: bool = False
    intended_user: Optional[str] = None
    data_sources: List[str] = []
    existing_artifacts: List[str] = []


class AssessRequest(BaseModel):
    product: ProductProfile
    standard_ids: Optional[List[str]] = None


class GapAnalysisRequest(BaseModel):
    product: ProductProfile
    standard_id: str


def _get_framework():
    from src.core.regulatory_compliance import regulatory_compliance
    return regulatory_compliance


@router.get("/standards")
async def list_standards():
    """List all supported regulatory standards."""
    return _get_framework().list_standards()


@router.get("/standards/{standard_id}")
async def get_standard(standard_id: str):
    """Get details for a specific standard."""
    result = _get_framework().get_standard(standard_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Standard {standard_id} not found")
    return result


@router.post("/assess")
async def assess_compliance(req: AssessRequest):
    """Assess product compliance against standards."""
    try:
        return _get_framework().assess_compliance(
            product=req.product.model_dump(),
            standard_ids=req.standard_ids,
        )
    except Exception as exc:
        logger.error("Compliance assessment failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/gap-analysis")
async def gap_analysis(req: GapAnalysisRequest):
    """Generate gap analysis for a specific standard."""
    try:
        return _get_framework().generate_gap_analysis(
            product=req.product.model_dump(),
            standard_id=req.standard_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/checklist/{standard_id}")
async def get_checklist(standard_id: str):
    """Generate compliance checklist for a standard."""
    result = _get_framework().generate_checklist(standard_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/roadmap")
async def submission_roadmap(product: ProductProfile):
    """Generate regulatory submission roadmap."""
    try:
        return _get_framework().generate_submission_roadmap(product.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/full-report")
async def full_report(product: ProductProfile):
    """Generate comprehensive multi-standard compliance report."""
    try:
        return _get_framework().generate_full_compliance_report(product.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
