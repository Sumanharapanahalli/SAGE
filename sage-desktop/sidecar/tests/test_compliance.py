"""Tests for the compliance handler.

Unlike every other handler, compliance_flags.py is a pure, stateless
module (a static domain -> requirements dict + pure functions) — there is
no store/instance to wire at startup, so these handlers import it directly.
"""

from __future__ import annotations

import pytest

from handlers import compliance
from rpc import RpcError


def test_domains_returns_the_supported_domain_list():
    out = compliance.domains({})
    assert "domains" in out
    domain_names = {d["domain"] for d in out["domains"]}
    assert "medtech" in domain_names
    for d in out["domains"]:
        assert "standard" in d and "risk_levels" in d


def test_flags_returns_required_flags_for_a_domain():
    out = compliance.flags({"domain": "medtech", "risk_level": "CLASS_C"})
    assert out["domain"] == "medtech"
    assert out["risk_level"] == "CLASS_C"
    assert isinstance(out["flags"], list)
    assert out["total_flags"] == len(out["flags"])


def test_flags_defaults_risk_level_to_high():
    out = compliance.flags({"domain": "medtech"})
    assert out["risk_level"] == "HIGH"


def test_flags_rejects_unknown_domain():
    with pytest.raises(RpcError):
        compliance.flags({"domain": "not-a-real-domain"})


def test_flags_requires_domain_param():
    with pytest.raises(RpcError):
        compliance.flags({})


def test_checklist_generates_full_checklist_for_a_domain():
    out = compliance.checklist({"domain": "medtech", "risk_level": "CLASS_C"})
    assert out is not None
    assert isinstance(out, dict)


def test_checklist_rejects_unknown_domain():
    with pytest.raises(RpcError):
        compliance.checklist({"domain": "not-a-real-domain"})


def test_gap_assessment_returns_missing_and_percentage():
    out = compliance.gap_assessment(
        {
            "domain": "medtech",
            "risk_level": "CLASS_C",
            "completed_tasks": [],
        }
    )
    assert isinstance(out, dict)


def test_gap_assessment_requires_domain_and_risk_level():
    with pytest.raises(RpcError):
        compliance.gap_assessment({"completed_tasks": []})


def test_gap_assessment_rejects_unknown_domain():
    with pytest.raises(RpcError):
        compliance.gap_assessment(
            {
                "domain": "not-a-real-domain",
                "risk_level": "HIGH",
                "completed_tasks": [],
            }
        )


def test_gap_assessment_defaults_completed_tasks_to_empty_list():
    # Must not raise when completed_tasks is omitted.
    out = compliance.gap_assessment({"domain": "medtech", "risk_level": "CLASS_C"})
    assert isinstance(out, dict)
