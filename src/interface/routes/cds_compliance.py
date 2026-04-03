"""
CDS Compliance Routes
=====================
API endpoints for FDA Clinical Decision Support Software compliance
per the January 2026 guidance (media/109618).
"""

import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cds", tags=["CDS Compliance"])


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class DataSourceModel(BaseModel):
    name: str
    type: str


class ClassifyFunctionRequest(BaseModel):
    function_description: str
    input_types: List[str]
    output_type: str
    intended_user: str
    urgency: str
    data_sources: List[DataSourceModel]


class ClassifyInputsRequest(BaseModel):
    input_types: List[str]


class ValidateSourcesRequest(BaseModel):
    sources: List[DataSourceModel]


class ClassifyOutputRequest(BaseModel):
    output_type: str


class TransparencyReportRequest(BaseModel):
    function_description: str
    inputs_used: List[str]
    data_sources: List[DataSourceModel]
    algorithm_description: str
    known_limitations: List[str]


class LabelingRequest(BaseModel):
    product_name: str
    intended_use: str
    intended_users: List[str]
    target_population: str
    algorithm_summary: str
    data_sources: List[DataSourceModel]
    validation_summary: str
    known_limitations: List[str]


class BiasWarningRequest(BaseModel):
    function_description: str
    intended_user: str


class BiasRiskRequest(BaseModel):
    function_description: str
    urgency: str
    decision_impact: str


class ClinicalLimitationsRequest(BaseModel):
    validated_populations: List[str]
    accuracy_metrics: Dict
    excluded_conditions: List[str]
    known_failure_modes: List[str]


class ValidationProtocolRequest(BaseModel):
    function_description: str
    target_population: str
    clinical_endpoints: List[str]
    gold_standard: str
    demographic_subgroups: List[str]


class OverRelianceRequest(BaseModel):
    total_recommendations: int
    accepted_without_modification: int
    average_review_time_seconds: float


class ReEvaluateRequest(BaseModel):
    change_description: str
    previous_classification: str
    function_description: str
    input_types: List[str]
    output_type: str
    intended_user: str
    urgency: str
    data_sources: List[DataSourceModel]


class PatientPopulationRequest(BaseModel):
    condition: str
    age_range: Dict
    included_conditions: List[str]
    excluded_conditions: List[str]
    demographic_coverage: List[str]


class CompliancePackageRequest(BaseModel):
    product_name: str
    function_description: str
    input_types: List[str]
    output_type: str
    intended_user: str
    urgency: str
    data_sources: List[DataSourceModel]
    algorithm_description: str
    known_limitations: List[str]
    target_population: str
    validation_summary: str


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_framework():
    from src.core.cds_compliance import cds_compliance
    return cds_compliance


def _sources_to_dicts(sources: List[DataSourceModel]) -> List[Dict]:
    return [{"name": s.name, "type": s.type} for s in sources]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/classify")
async def classify_function(req: ClassifyFunctionRequest):
    """Classify a software function against all 4 FDA CDS criteria."""
    try:
        return _get_framework().classify_cds_function(
            function_description=req.function_description,
            input_types=req.input_types,
            output_type=req.output_type,
            intended_user=req.intended_user,
            urgency=req.urgency,
            data_sources=_sources_to_dicts(req.data_sources),
        )
    except Exception as exc:
        logger.error("CDS classify failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/classify-inputs")
async def classify_inputs(req: ClassifyInputsRequest):
    """Classify input data types (image/signal/pattern/discrete)."""
    try:
        return _get_framework().classify_input_data(req.input_types)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/validate-sources")
async def validate_sources(req: ValidateSourcesRequest):
    """Validate data source provenance."""
    try:
        return _get_framework().validate_data_sources(_sources_to_dicts(req.sources))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/classify-output")
async def classify_output(req: ClassifyOutputRequest):
    """Classify CDS output type."""
    try:
        return _get_framework().classify_output_type(req.output_type)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/transparency-report")
async def transparency_report(req: TransparencyReportRequest):
    """Generate clinician-facing transparency report."""
    try:
        return _get_framework().generate_transparency_report(
            function_description=req.function_description,
            inputs_used=req.inputs_used,
            data_sources=_sources_to_dicts(req.data_sources),
            algorithm_description=req.algorithm_description,
            known_limitations=req.known_limitations,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/labeling")
async def generate_labeling(req: LabelingRequest):
    """Generate FDA-formatted CDS labeling."""
    try:
        return _get_framework().generate_cds_labeling(
            product_name=req.product_name,
            intended_use=req.intended_use,
            intended_users=req.intended_users,
            target_population=req.target_population,
            algorithm_summary=req.algorithm_summary,
            data_sources=_sources_to_dicts(req.data_sources),
            validation_summary=req.validation_summary,
            known_limitations=req.known_limitations,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/bias-warning")
async def bias_warning(req: BiasWarningRequest):
    """Generate automation bias warning label."""
    try:
        return _get_framework().generate_bias_warning_label(
            function_description=req.function_description,
            intended_user=req.intended_user,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/bias-risk")
async def bias_risk(req: BiasRiskRequest):
    """Assess automation bias risk."""
    try:
        return _get_framework().assess_automation_bias_risk(
            function_description=req.function_description,
            urgency=req.urgency,
            decision_impact=req.decision_impact,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/clinical-limitations")
async def clinical_limitations(req: ClinicalLimitationsRequest):
    """Generate clinical limitations disclosure."""
    try:
        return _get_framework().generate_clinical_limitations(
            validated_populations=req.validated_populations,
            accuracy_metrics=req.accuracy_metrics,
            excluded_conditions=req.excluded_conditions,
            known_failure_modes=req.known_failure_modes,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/validation-protocol")
async def validation_protocol(req: ValidationProtocolRequest):
    """Generate clinical validation protocol."""
    try:
        return _get_framework().generate_clinical_validation_protocol(
            function_description=req.function_description,
            target_population=req.target_population,
            clinical_endpoints=req.clinical_endpoints,
            gold_standard=req.gold_standard,
            demographic_subgroups=req.demographic_subgroups,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/over-reliance")
async def over_reliance(req: OverRelianceRequest):
    """Detect post-market over-reliance patterns."""
    try:
        return _get_framework().detect_over_reliance(
            total_recommendations=req.total_recommendations,
            accepted_without_modification=req.accepted_without_modification,
            average_review_time_seconds=req.average_review_time_seconds,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/reevaluate")
async def reevaluate(req: ReEvaluateRequest):
    """Re-evaluate CDS criteria after algorithm change."""
    try:
        return _get_framework().trigger_criterion_reevaluation(
            change_description=req.change_description,
            previous_classification=req.previous_classification,
            function_description=req.function_description,
            input_types=req.input_types,
            output_type=req.output_type,
            intended_user=req.intended_user,
            urgency=req.urgency,
            data_sources=_sources_to_dicts(req.data_sources),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/patient-population")
async def patient_population(req: PatientPopulationRequest):
    """Define patient population criteria."""
    try:
        return _get_framework().define_patient_population(
            condition=req.condition,
            age_range=req.age_range,
            included_conditions=req.included_conditions,
            excluded_conditions=req.excluded_conditions,
            demographic_coverage=req.demographic_coverage,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/compliance-package")
async def compliance_package(req: CompliancePackageRequest):
    """Generate complete FDA CDS compliance package."""
    try:
        return _get_framework().generate_compliance_package(
            product_name=req.product_name,
            function_description=req.function_description,
            input_types=req.input_types,
            output_type=req.output_type,
            intended_user=req.intended_user,
            urgency=req.urgency,
            data_sources=_sources_to_dicts(req.data_sources),
            algorithm_description=req.algorithm_description,
            known_limitations=req.known_limitations,
            target_population=req.target_population,
            validation_summary=req.validation_summary,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
