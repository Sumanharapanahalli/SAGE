"""
Compliance Engineering Routes
==============================
API endpoints for traceability, change control, document generation,
audit integrity, and compliance verification.

These endpoints close the regulatory gaps identified in the compliance audit:
  - Bidirectional traceability matrix (IEC 62304 §5.1.1)
  - Cryptographic audit log integrity (21 CFR Part 11 §11.10(e))
  - Regulatory document generation (IEC 62304, ISO 14971)
  - Change control workflow (IEC 62304 §6.1, ISO 26262 §8.7)
  - Multi-standard compliance verification
"""

import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compliance", tags=["Compliance Engineering"])


# ─── Pydantic Models ────────────────────────────────────────────────────

class TraceItemCreate(BaseModel):
    level: str
    title: str
    description: str = ""
    source_file: str = ""
    source_line: int = 0
    item_id: Optional[str] = None


class TraceLinkCreate(BaseModel):
    source_id: str
    target_id: str
    link_type: str = "derives"
    rationale: str = ""
    created_by: str = "system"


class ChangeRequestCreate(BaseModel):
    title: str
    description: str
    category: str  # corrective, preventive, adaptive, perfective
    priority: str  # critical, high, medium, low
    requester: str
    affected_items: List[str] = []


class ChangeStatusUpdate(BaseModel):
    new_status: str
    changed_by: str
    comments: str = ""


class ImpactAssessmentInput(BaseModel):
    affected_requirements: List[str] = []
    affected_components: List[str] = []
    affected_tests: List[str] = []
    risk_impact: str = "none"
    regulatory_impact: str = "none"
    safety_impact: str = "none"
    effort_estimate: str = ""
    notes: str = ""


class ApprovalInput(BaseModel):
    approver: str
    role: str
    decision: str  # approved, rejected, needs_info
    comments: str = ""


class DocumentRequest(BaseModel):
    doc_type: str  # srs, risk_management, rtm, vv_plan, soup_inventory
    data: dict = {}
    project_name: str = ""
    version: str = "1.0"


class VerificationRequest(BaseModel):
    project_data: dict
    standards: Optional[List[str]] = None


class IntegrityAppendRequest(BaseModel):
    audit_event_id: str
    event_data: dict


# ─── Lazy accessors ─────────────────────────────────────────────────────

_trace_matrix = None
_change_control = None


def _get_trace_matrix():
    global _trace_matrix
    if _trace_matrix is None:
        from src.core.traceability import TraceabilityMatrix
        _trace_matrix = TraceabilityMatrix()
    return _trace_matrix


def _get_change_control():
    global _change_control
    if _change_control is None:
        from src.core.change_control import ChangeControlManager
        _change_control = ChangeControlManager()
    return _change_control


# ═══════════════════════════════════════════════════════════════════════
# TRACEABILITY MATRIX
# ═══════════════════════════════════════════════════════════════════════

@router.post("/traceability/items")
def create_trace_item(req: TraceItemCreate):
    """Create a new traceability item."""
    try:
        from src.core.traceability import TraceLevel
        level = TraceLevel(req.level)
        tm = _get_trace_matrix()
        item = tm.add_item(
            level=level, title=req.title, description=req.description,
            source_file=req.source_file, source_line=req.source_line,
            item_id=req.item_id,
        )
        return {"status": "created", "item": item.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/traceability/items")
def list_trace_items(level: Optional[str] = None, status: str = "active"):
    """List traceability items, optionally filtered by level."""
    try:
        from src.core.traceability import TraceLevel
        lvl = TraceLevel(level) if level else None
        tm = _get_trace_matrix()
        items = tm.list_items(level=lvl, status=status)
        return {"items": [i.to_dict() for i in items], "count": len(items)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/traceability/items/{item_id}")
def get_trace_item(item_id: str):
    """Get a specific traceability item with its links."""
    tm = _get_trace_matrix()
    item = tm.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
    forward = tm.get_forward_links(item_id)
    backward = tm.get_backward_links(item_id)
    return {"item": item.to_dict(), "traces_to": forward, "traced_from": backward}


@router.post("/traceability/links")
def create_trace_link(req: TraceLinkCreate):
    """Create a traceability link between two items."""
    try:
        tm = _get_trace_matrix()
        link = tm.add_link(
            source_id=req.source_id, target_id=req.target_id,
            link_type=req.link_type, rationale=req.rationale,
            created_by=req.created_by,
        )
        return {"status": "created", "link": link.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/traceability/coverage")
def traceability_coverage():
    """Get traceability coverage report."""
    tm = _get_trace_matrix()
    return tm.coverage_report()


@router.get("/traceability/gaps")
def traceability_gaps():
    """Get traceability gap analysis."""
    tm = _get_trace_matrix()
    return tm.gap_analysis()


@router.get("/traceability/export")
def export_traceability():
    """Export full traceability matrix."""
    tm = _get_trace_matrix()
    return {"matrix": tm.export_matrix()}


# ═══════════════════════════════════════════════════════════════════════
# CHANGE CONTROL
# ═══════════════════════════════════════════════════════════════════════

@router.post("/change-control/requests")
def create_change_request(req: ChangeRequestCreate):
    """Create a new change request."""
    try:
        ccm = _get_change_control()
        result = ccm.create_request(
            title=req.title, description=req.description,
            category=req.category, priority=req.priority,
            requester=req.requester, affected_items=req.affected_items,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/change-control/requests")
def list_change_requests(status: Optional[str] = None):
    """List change requests, optionally filtered by status."""
    ccm = _get_change_control()
    return {"requests": ccm.list_requests(status=status)}


@router.get("/change-control/requests/{cr_id}")
def get_change_request(cr_id: str):
    """Get a specific change request."""
    ccm = _get_change_control()
    request = ccm.get_request(cr_id)
    if not request:
        raise HTTPException(status_code=404, detail=f"Change request {cr_id} not found")
    return request


@router.put("/change-control/requests/{cr_id}/status")
def update_change_status(cr_id: str, req: ChangeStatusUpdate):
    """Update the status of a change request."""
    try:
        ccm = _get_change_control()
        return ccm.update_status(cr_id, req.new_status, req.changed_by, req.comments)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/change-control/requests/{cr_id}/impact")
def add_impact_assessment(cr_id: str, req: ImpactAssessmentInput):
    """Add impact assessment to a change request."""
    ccm = _get_change_control()
    return ccm.add_impact_assessment(cr_id, req.model_dump())


@router.post("/change-control/requests/{cr_id}/approvals")
def add_change_approval(cr_id: str, req: ApprovalInput):
    """Add an approval decision to a change request."""
    try:
        ccm = _get_change_control()
        return ccm.add_approval(cr_id, req.approver, req.role, req.decision, req.comments)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/change-control/requests/{cr_id}/history")
def get_change_history(cr_id: str):
    """Get full status history for a change request."""
    ccm = _get_change_control()
    return {"history": ccm.get_history(cr_id)}


@router.get("/change-control/metrics")
def change_control_metrics():
    """Get change control metrics for compliance reporting."""
    ccm = _get_change_control()
    return ccm.get_metrics()


# ═══════════════════════════════════════════════════════════════════════
# DOCUMENT GENERATION
# ═══════════════════════════════════════════════════════════════════════

@router.post("/documents/generate")
def generate_document(req: DocumentRequest):
    """Generate a regulatory compliance document."""
    try:
        from src.core.doc_generator import DocumentGenerator
        gen = DocumentGenerator(project_name=req.project_name, version=req.version)
        content = gen.generate_document(req.doc_type, req.data)
        return {"doc_type": req.doc_type, "content": content}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/documents/types")
def list_document_types():
    """List available document types."""
    from src.core.doc_generator import DocumentGenerator
    gen = DocumentGenerator()
    return {"types": gen.list_document_types()}


# ═══════════════════════════════════════════════════════════════════════
# AUDIT INTEGRITY
# ═══════════════════════════════════════════════════════════════════════

@router.post("/audit/integrity/append")
def append_integrity_entry(req: IntegrityAppendRequest):
    """Append an entry to the audit integrity chain."""
    try:
        from src.core.audit_integrity import AuditIntegrityManager
        from src.memory.audit_logger import DB_PATH
        mgr = AuditIntegrityManager(DB_PATH)
        return mgr.append_entry(req.audit_event_id, req.event_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit/integrity/verify")
def verify_audit_integrity():
    """Verify the audit log integrity chain."""
    from src.core.audit_integrity import AuditIntegrityManager
    from src.memory.audit_logger import DB_PATH
    mgr = AuditIntegrityManager(DB_PATH)
    return mgr.verify_chain()


@router.get("/audit/integrity/status")
def audit_integrity_status():
    """Get audit integrity chain status."""
    from src.core.audit_integrity import AuditIntegrityManager
    from src.memory.audit_logger import DB_PATH
    mgr = AuditIntegrityManager(DB_PATH)
    return mgr.get_chain_status()


# ═══════════════════════════════════════════════════════════════════════
# COMPLIANCE VERIFICATION
# ═══════════════════════════════════════════════════════════════════════

@router.post("/verify")
def verify_compliance(req: VerificationRequest):
    """Run compliance verification against specified standards."""
    from src.core.compliance_verifier import ComplianceVerifier
    verifier = ComplianceVerifier()
    return verifier.verify_all(req.project_data, req.standards)


@router.get("/verify/standards")
def list_verification_standards():
    """List available verification standards."""
    return {
        "standards": [
            {"id": "iec62304", "name": "IEC 62304", "domain": "Medical Device Software"},
            {"id": "iso26262", "name": "ISO 26262", "domain": "Automotive Functional Safety"},
            {"id": "do178c", "name": "DO-178C", "domain": "Avionics Software"},
            {"id": "en50128", "name": "EN 50128", "domain": "Railway Signalling Software"},
            {"id": "21cfr_part11", "name": "21 CFR Part 11", "domain": "Electronic Records & Signatures"},
        ]
    }
