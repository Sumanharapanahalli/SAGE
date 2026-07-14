"""
Merge-Request Package Builder
=============================
Assembles the regulatory Merge-Request PR body for the Merge-Gate Governance
feature. A human reviews this at a high level, so the executive **Summary**
comes first ("decide in one read") followed by the detailed dossier
(impact → risk → traceability → evidence → changes → documentation).

Pure and deterministic: every function is a plain string transform with no
I/O, no clock, no randomness. Identical inputs always yield identical output,
which is what makes the rendered PR body a reproducible compliance artifact.

Contract (other modules build against these signatures):
    build_pr_title(work_item) -> str
    build_pr_body(*, work_item, mr_id, diff_stat, evidence,
                  change_summary, risk="", impact="",
                  docs_changed=None) -> str
"""

from __future__ import annotations

from typing import Any, Mapping

# Conventional-commit prefix for every SAGE-authored merge request.
_TITLE_PREFIX = "feat(sage): "
_TITLE_MAX = 72

# Ordered section headers emitted by build_pr_body(). The order is the
# contract: executive summary first, dossier after. Kept as a module constant
# so tests (and callers) can assert against the canonical sequence.
SECTION_HEADERS: tuple[str, ...] = (
    "## Summary — decide in one read",
    "## System impact",
    "## Risk assessment",
    "## Traceability",
    "## Test & build evidence",
    "## Changes",
    "## Documentation",
)


def build_pr_title(work_item: str) -> str:
    """Return a concise conventional-commit-style title (<= 72 chars).

    The work item text is lowercased at the first character only (preserving
    any acronyms), any trailing period is dropped, and the result is prefixed
    with ``feat(sage): ``. Over-long descriptions are trimmed at a word
    boundary so the title never exceeds 72 characters.

    >>> build_pr_title("Register the dead health preflight handler")
    'feat(sage): register the dead health preflight handler'
    """
    desc = (work_item or "").strip().rstrip(".").strip()
    if desc:
        desc = desc[0].lower() + desc[1:]

    max_desc = _TITLE_MAX - len(_TITLE_PREFIX)
    if len(desc) > max_desc:
        clipped = desc[:max_desc]
        # Prefer a clean word boundary; fall back to a hard cut if the first
        # token alone already overflows.
        boundary = clipped.rfind(" ")
        desc = (clipped[:boundary] if boundary > 0 else clipped).rstrip()

    return f"{_TITLE_PREFIX}{desc}"


def _is_safe_to_merge(evidence: Mapping[str, Any]) -> bool:
    """Derive the merge-safety verdict from the evidence dict.

    Safe only when the merge gate is explicitly green, or when there are zero
    failed tests AND the build is ok. Missing keys are treated as not-green
    (``None`` never equals ``0`` or ``"ok"``), so absent evidence is unsafe.
    """
    if evidence.get("gate_green") is True:
        return True
    tests = evidence.get("tests")
    failed = tests.get("failed") if isinstance(tests, Mapping) else None
    return failed == 0 and evidence.get("build") == "ok"


def _render_evidence(evidence: Mapping[str, Any]) -> str:
    """Render the evidence dict as a markdown bullet list.

    Known keys (tests, verify, build, gate_green) get friendly phrasing; any
    other keys present are rendered generically so nothing is silently dropped.
    """
    if not evidence:
        return "No test or build evidence provided."

    lines: list[str] = []
    handled: set[str] = set()

    tests = evidence.get("tests")
    if isinstance(tests, Mapping):
        passed = tests.get("passed", 0)
        failed = tests.get("failed", 0)
        lines.append(f"- Tests: {passed} passed, {failed} failed")
        handled.add("tests")

    if "verify" in evidence:
        lines.append(f"- `make verify` gates: {evidence['verify']}")
        handled.add("verify")

    if "build" in evidence:
        build = evidence["build"]
        marker = "ok" if build == "ok" else f"{build}"
        lines.append(f"- Build: {marker}")
        handled.add("build")

    if "gate_green" in evidence:
        state = "green" if evidence["gate_green"] is True else "not green"
        lines.append(f"- Merge gate: {state}")
        handled.add("gate_green")

    # Render any remaining keys generically — never drop evidence.
    for key, value in evidence.items():
        if key not in handled:
            lines.append(f"- {key}: {value}")

    return "\n".join(lines)


def build_pr_body(
    *,
    work_item: str,
    mr_id: str,
    diff_stat: str,
    evidence: dict,
    change_summary: str,
    risk: str = "",
    impact: str = "",
    docs_changed: list[str] | None = None,
) -> str:
    """Assemble the full GitHub-flavored-markdown PR body.

    Sections are emitted in the fixed :data:`SECTION_HEADERS` order: an
    executive summary the reviewer can decide on in one read, then the
    supporting dossier. All inputs are treated as plain text.
    """
    evidence = evidence or {}
    safe = _is_safe_to_merge(evidence)
    safe_line = "yes" if safe else "needs review — evidence not green"

    summary_body = (change_summary or work_item or "").strip()
    if not summary_body:
        summary_body = "No summary provided."

    impact_text = impact.strip() if impact and impact.strip() else "Not assessed"
    risk_text = (
        risk.strip()
        if risk and risk.strip()
        else "No elevated risk identified — routine low/medium change; "
        "verified by the evidence below."
    )

    if docs_changed:
        docs_block = "\n".join(f"- {doc}" for doc in docs_changed)
    else:
        docs_block = "No documentation changes"

    changes_body = (change_summary or "").strip() or "See diffstat below."

    parts = [
        f"{SECTION_HEADERS[0]}",
        summary_body,
        "",
        f"**Safe to merge:** {safe_line}",
        "",
        f"{SECTION_HEADERS[1]}",
        impact_text,
        "",
        f"{SECTION_HEADERS[2]}",
        risk_text,
        "",
        f"{SECTION_HEADERS[3]}",
        f"- Work item: {work_item}",
        f"- MR: {mr_id}",
        "- Links the change to the originating gap / requirement.",
        "",
        f"{SECTION_HEADERS[4]}",
        _render_evidence(evidence),
        "",
        f"{SECTION_HEADERS[5]}",
        changes_body,
        "",
        "```diffstat",
        diff_stat.rstrip("\n") if diff_stat else "(no diffstat provided)",
        "```",
        "",
        f"{SECTION_HEADERS[6]}",
        docs_block,
        "",
        "---",
        f"Authored by SAGE agents · reviewed & signed at merge · MR {mr_id}",
    ]

    return "\n".join(parts) + "\n"
