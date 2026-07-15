"""Tests for the regulatory handler (src.core.regulatory_compliance).

Stateless singleton over a static standards registry — no store to inject,
so the handler imports it lazily at call time and these tests call it directly.
"""

from __future__ import annotations

import pytest

from handlers import regulatory
from rpc import RPC_INVALID_PARAMS, RpcError

PRODUCT = {
    "product_name": "CardioRisk CDS",
    "product_type": "samd",
    "risk_class": "IIb",
    "target_regions": ["us", "eu"],
    "uses_ai_ml": True,
    "processes_images": True,
    "processes_signals": False,
    "existing_artifacts": ["software_requirements_spec", "traceability_matrix"],
}


def test_standards_returns_wrapped_registry():
    out = regulatory.standards({})
    assert out["total"] == len(out["standards"])
    assert out["total"] > 0
    ids = {s["id"] for s in out["standards"]}
    assert {"iec_62304", "eu_mdr", "fda_aiml"} <= ids
    for s in out["standards"]:
        assert s["name"] and s["region"] and s["reference"]
        assert isinstance(s["requirements"], list)
        assert isinstance(s["required_artifacts"], list)


def test_standard_returns_one_standard():
    out = regulatory.standard({"standard_id": "iec_62304"})
    assert out["id"] == "iec_62304"
    assert "software_development_plan" in out["required_artifacts"]


def test_standard_rejects_unknown_id():
    with pytest.raises(RpcError) as exc:
        regulatory.standard({"standard_id": "not-a-standard"})
    assert exc.value.code == RPC_INVALID_PARAMS


def test_standard_requires_standard_id():
    with pytest.raises(RpcError):
        regulatory.standard({})


def test_assess_auto_detects_standards_from_the_profile():
    out = regulatory.assess({"product": PRODUCT})
    assert out["product_name"] == "CardioRisk CDS"
    assert isinstance(out["overall_score"], float)
    assert out["standards_assessed"] == len(out["assessments"])
    # us + eu + international + AI/ML standards must all be auto-detected.
    assert {
        "iec_62304",
        "iso_14971",
        "fda_swv",
        "eu_mdr",
        "eu_ai_act",
        "fda_aiml",
    } <= set(out["assessments"])
    a = out["assessments"]["iec_62304"]
    assert a["standard_name"]
    assert 0 <= a["compliance_score"] <= 100
    assert "software_requirements_spec" in a["met_artifacts"]
    assert "soup_inventory" in a["missing_artifacts"]
    assert isinstance(a["gaps"], list)


def test_assess_honours_explicit_standard_ids():
    out = regulatory.assess({"product": PRODUCT, "standard_ids": ["iso_14971"]})
    assert list(out["assessments"]) == ["iso_14971"]
    assert out["standards_assessed"] == 1


def test_assess_treats_empty_standard_ids_as_auto_detect():
    out = regulatory.assess({"product": PRODUCT, "standard_ids": []})
    assert out["standards_assessed"] > 1


def test_assess_rejects_bad_standard_ids_type():
    with pytest.raises(RpcError):
        regulatory.assess({"product": PRODUCT, "standard_ids": "iso_14971"})


def test_assess_requires_a_product_object():
    with pytest.raises(RpcError) as exc:
        regulatory.assess({})
    assert exc.value.code == RPC_INVALID_PARAMS
    with pytest.raises(RpcError):
        regulatory.assess({"product": "CardioRisk"})


def test_gap_analysis_returns_per_requirement_status():
    out = regulatory.gap_analysis({"product": PRODUCT, "standard_id": "iec_62304"})
    assert out["standard_id"] == "iec_62304"
    assert len(out["gaps"]) > 0
    for g in out["gaps"]:
        assert g["status"] in ("met", "partial", "missing")
        assert g["priority"] in ("high", "medium")
        assert g["remediation"]


def test_gap_analysis_rejects_unknown_standard():
    with pytest.raises(RpcError) as exc:
        regulatory.gap_analysis({"product": PRODUCT, "standard_id": "nope"})
    assert exc.value.code == RPC_INVALID_PARAMS


def test_checklist_generates_items_with_evidence():
    out = regulatory.checklist({"standard_id": "iso_14971"})
    assert out["standard_id"] == "iso_14971"
    assert len(out["items"]) > 0
    first = out["items"][0]
    assert first["id"].startswith("iso_14971-")
    assert first["checked"] is False
    assert first["evidence_needed"]


def test_checklist_rejects_unknown_standard():
    with pytest.raises(RpcError) as exc:
        regulatory.checklist({"standard_id": "nope"})
    assert exc.value.code == RPC_INVALID_PARAMS


def test_roadmap_returns_phases_and_total_weeks():
    out = regulatory.roadmap({"product": PRODUCT})
    assert out["product_name"] == "CardioRisk CDS"
    assert out["target_regions"] == ["us", "eu"]
    assert len(out["phases"]) > 0
    assert out["total_estimated_weeks"] == sum(
        p["estimated_weeks"] for p in out["phases"]
    )
    for p in out["phases"]:
        assert p["phase_name"] and p["description"]
        assert p["standards"]  # empty phases are filtered out
        assert p["deliverables"]


def test_roadmap_requires_a_product_object():
    with pytest.raises(RpcError):
        regulatory.roadmap({})
