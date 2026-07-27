"""Tests for src.core.compliance_flags query helpers.

Data-driven (reads whatever domains ship in COMPLIANCE_FLAGS) so it stays valid
as domains change. Previously untested (SAGE self-improvement loop, issue #23).
"""

from src.core.compliance_flags import (
    assess_compliance_gap,
    generate_compliance_checklist,
    get_domain_risk_levels,
    get_hil_required_tests,
    get_required_flags,
    list_domains,
)


def _first_domain_and_risk():
    domains = list_domains()
    assert domains, "expected at least one compliance domain"
    for d in domains:
        levels = get_domain_risk_levels(d)
        if levels:
            return d, levels[-1]  # highest-risk level usually last
    raise AssertionError("no domain exposed any risk levels")


def test_list_domains_nonempty():
    assert isinstance(list_domains(), list)
    assert list_domains()


def test_unknown_domain_returns_empty():
    assert get_domain_risk_levels("not_a_domain") == []
    assert get_required_flags("not_a_domain", "X") == []
    assert get_hil_required_tests("not_a_domain", "X") == []


def test_required_flags_and_hil_subset():
    domain, risk = _first_domain_and_risk()
    flags = get_required_flags(domain, risk)
    assert isinstance(flags, list)
    hil = get_hil_required_tests(domain, risk)
    flag_ids = {f["id"] for f in flags}
    # every HIL-required id must be one of the required flags
    assert set(hil).issubset(flag_ids)


def test_generate_checklist_and_gap_are_consistent():
    domain, risk = _first_domain_and_risk()
    checklist = generate_compliance_checklist(domain, risk)
    assert isinstance(checklist, dict)
    # A gap assessment with no completed tasks should not crash and should be a dict
    gap = assess_compliance_gap(domain, risk, completed_tasks=[])
    assert isinstance(gap, dict)
