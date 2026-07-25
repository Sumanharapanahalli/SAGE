"""
Unit tests for src/core/mr_package.py

Covers the Merge-Request package builder: section ordering (executive summary
first), traceability content, the Safe-to-merge verdict, diffstat fencing,
documentation rendering, title derivation, and determinism/purity.
"""

import pytest

pytestmark = pytest.mark.unit

from src.core.mr_package import build_pr_body, build_pr_title  # noqa: E402


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

WORK_ITEM = "Register the dead health preflight handler"
MR_ID = "MR-4271"
DIFF_STAT = " src/interface/api.py | 12 ++++++++----\n 1 file changed, 8 insertions(+), 4 deletions(-)"


def _green_evidence():
    return {
        "tests": {"passed": 42, "failed": 0},
        "verify": "8/8",
        "build": "ok",
        "gate_green": True,
    }


def _body(**overrides):
    kwargs = dict(
        work_item=WORK_ITEM,
        mr_id=MR_ID,
        diff_stat=DIFF_STAT,
        evidence=_green_evidence(),
        change_summary="Wire the health preflight handler into the router so the "
        "dead endpoint responds again.",
        risk="Low — additive route registration, no data migration.",
        impact="Restores the /health preflight response used by the load balancer.",
        docs_changed=["docs/api/health.md"],
    )
    kwargs.update(overrides)
    return build_pr_body(**kwargs)


# ---------------------------------------------------------------------------
# Section ordering — executive summary first, dossier after
# ---------------------------------------------------------------------------

# Stable ASCII prefixes (avoids em-dash / middle-dot encoding fragility).
ORDERED_HEADERS = [
    "## Summary",
    "## System impact",
    "## Risk assessment",
    "## Traceability",
    "## Test & build evidence",
    "## Changes",
    "## Documentation",
]


class TestSectionOrdering:
    def test_all_headers_present(self):
        body = _body()
        for header in ORDERED_HEADERS:
            assert header in body, f"missing section header: {header}"

    def test_headers_appear_in_contract_order(self):
        body = _body()
        indices = [body.index(header) for header in ORDERED_HEADERS]
        assert indices == sorted(indices), (
            f"section headers are out of order: {list(zip(ORDERED_HEADERS, indices))}"
        )

    def test_summary_precedes_system_impact(self):
        body = _body()
        assert body.index("## Summary") < body.index("## System impact")

    def test_system_impact_precedes_risk(self):
        body = _body()
        assert body.index("## System impact") < body.index("## Risk assessment")


# ---------------------------------------------------------------------------
# Traceability — work_item and mr_id inside the Traceability section itself
# ---------------------------------------------------------------------------


def _section_slice(body: str, header: str) -> str:
    """Return the text from *header* up to the next '## ' header (or EOF)."""
    start = body.index(header)
    rest = body[start + len(header) :]
    nxt = rest.find("\n## ")
    return rest if nxt == -1 else rest[:nxt]


class TestTraceability:
    def test_traceability_contains_work_item_and_mr_id(self):
        body = _body()
        section = _section_slice(body, "## Traceability")
        assert WORK_ITEM in section
        assert MR_ID in section


# ---------------------------------------------------------------------------
# Safe-to-merge verdict
# ---------------------------------------------------------------------------


class TestSafeToMerge:
    def test_yes_when_gate_green_true(self):
        body = _body(evidence={"gate_green": True})
        summary = _section_slice(body, "## Summary")
        assert "Safe to merge:" in summary
        assert "yes" in summary
        assert "needs review" not in summary

    def test_yes_when_zero_failed_and_build_ok(self):
        body = _body(evidence={"tests": {"passed": 10, "failed": 0}, "build": "ok"})
        summary = _section_slice(body, "## Summary")
        assert "yes" in summary

    def test_needs_review_when_a_test_failed(self):
        # Internally consistent: a failed test and no clean-build override.
        body = _body(evidence={"tests": {"passed": 9, "failed": 1}, "build": "ok"})
        summary = _section_slice(body, "## Summary")
        assert "needs review" in summary

    def test_needs_review_when_build_failed(self):
        body = _body(evidence={"tests": {"passed": 10, "failed": 0}, "build": "failed"})
        summary = _section_slice(body, "## Summary")
        assert "needs review" in summary

    def test_needs_review_when_evidence_empty(self):
        body = _body(evidence={})
        summary = _section_slice(body, "## Summary")
        assert "needs review" in summary


# ---------------------------------------------------------------------------
# Diffstat is rendered inside a fenced code block
# ---------------------------------------------------------------------------


class TestDiffstatFence:
    def test_diff_stat_between_fences(self):
        body = _body()
        # Locate an opening fence, then the closing fence, and assert the
        # diff_stat text lives between them.
        open_idx = body.index("```diffstat")
        close_idx = body.index("```", open_idx + len("```diffstat"))
        fenced = body[open_idx:close_idx]
        assert "1 file changed, 8 insertions(+), 4 deletions(-)" in fenced

    def test_empty_diff_stat_still_fenced(self):
        body = _body(diff_stat="")
        assert "```diffstat" in body


# ---------------------------------------------------------------------------
# Documentation section
# ---------------------------------------------------------------------------


class TestDocumentation:
    def test_docs_changed_rendered(self):
        body = _body(docs_changed=["docs/api/health.md", "docs/changelog.md"])
        section = _section_slice(body, "## Documentation")
        assert "docs/api/health.md" in section
        assert "docs/changelog.md" in section

    def test_no_docs_changed_placeholder(self):
        body = _body(docs_changed=None)
        section = _section_slice(body, "## Documentation")
        assert "No documentation changes" in section

    def test_empty_docs_list_placeholder(self):
        body = _body(docs_changed=[])
        section = _section_slice(body, "## Documentation")
        assert "No documentation changes" in section


# ---------------------------------------------------------------------------
# Defaults for empty risk / impact
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_impact_not_assessed_when_empty(self):
        body = _body(impact="")
        section = _section_slice(body, "## System impact")
        assert "Not assessed" in section

    def test_risk_has_default_note_when_empty(self):
        body = _body(risk="")
        section = _section_slice(body, "## Risk assessment")
        # Some non-empty default guidance is emitted.
        assert section.strip()
        assert "low" in section.lower() or "risk" in section.lower()


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------


class TestFooter:
    def test_footer_present_with_mr_id(self):
        body = _body()
        assert "Authored by SAGE agents" in body
        assert f"MR {MR_ID}" in body


# ---------------------------------------------------------------------------
# Title derivation
# ---------------------------------------------------------------------------


class TestTitle:
    def test_matches_conventional_commit_example(self):
        assert (
            build_pr_title("Register the dead health preflight handler")
            == "feat(sage): register the dead health preflight handler"
        )

    def test_title_within_72_chars(self):
        long_item = (
            "Register the dead health preflight handler and also wire up the "
            "entire load balancer preflight subsystem end to end"
        )
        title = build_pr_title(long_item)
        assert len(title) <= 72

    def test_title_derived_from_work_item(self):
        title = build_pr_title("Register the dead health preflight handler")
        assert title.startswith("feat(sage):")
        assert "preflight" in title

    def test_title_no_trailing_period(self):
        title = build_pr_title("Fix the crash.")
        assert not title.endswith(".")


# ---------------------------------------------------------------------------
# Determinism / purity — the only assertion covering "deterministic, no I/O"
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_identical_inputs_produce_identical_output(self):
        first = _body()
        second = _body()
        assert first == second

    def test_title_deterministic(self):
        assert build_pr_title(WORK_ITEM) == build_pr_title(WORK_ITEM)
