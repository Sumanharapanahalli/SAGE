"""
Functional Safety Routes
========================
API endpoints for FMEA, FTA, SIL/ASIL classification, and hardware tool access.
"""

import logging
from typing import Dict, List
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/safety", tags=["Functional Safety"])


class FMEAEntry(BaseModel):
    component: str
    failure_mode: str
    effect: str
    severity: int
    occurrence: int
    detection: int


class FMEARequest(BaseModel):
    entries: List[FMEAEntry]


class FTARequest(BaseModel):
    tree: Dict


class ASILRequest(BaseModel):
    severity: str
    exposure: str
    controllability: str


class SILRequest(BaseModel):
    probability_dangerous_failure_per_hour: float


class IEC62304Request(BaseModel):
    risk_level: str


class HazardEntry(BaseModel):
    id: str
    description: str
    cause: str = ""
    effect: str = ""
    severity: str = "S3"
    exposure: str = "E4"
    controllability: str = "C3"


class SafetyAnalysisRequest(BaseModel):
    product_name: str
    hazards: List[HazardEntry]
    fmea_entries: List[FMEAEntry]


def _get_engine():
    from src.core.functional_safety import functional_safety
    return functional_safety


@router.post("/fmea")
async def compute_fmea(req: FMEARequest):
    return _get_engine().generate_fmea_table([e.model_dump() for e in req.entries])


@router.post("/fta")
async def compute_fta(req: FTARequest):
    return _get_engine().calculate_fta(req.tree)


@router.post("/asil")
async def classify_asil(req: ASILRequest):
    return _get_engine().classify_asil(req.severity, req.exposure, req.controllability)


@router.post("/sil")
async def classify_sil(req: SILRequest):
    return _get_engine().classify_sil(req.probability_dangerous_failure_per_hour)


@router.post("/iec62304-class")
async def classify_iec62304(req: IEC62304Request):
    return _get_engine().classify_iec62304(req.risk_level)


@router.post("/analysis")
async def full_safety_analysis(req: SafetyAnalysisRequest):
    return _get_engine().run_safety_analysis(
        product_name=req.product_name,
        hazards=[h.model_dump() for h in req.hazards],
        fmea_entries=[e.model_dump() for e in req.fmea_entries],
    )


@router.get("/hardware-tools")
async def get_hardware_tools():
    from src.mcp_servers.hardware_tools import list_hardware_tools
    return list_hardware_tools()
