"""End-to-end registration tests for activity.* and regulatory.*.

Both handlers were fully written and unit-tested but never registered in
``_build_dispatcher`` — every call returned -32601. These tests drive the REAL
NDJSON event loop (io.StringIO in/out, same as test_main.py) so a regression
that drops a registration, or drops the ``activity._logger`` injection in
``_wire_handlers``, fails here.
"""
from __future__ import annotations

import io
import json
import os
import sqlite3
import uuid

import pytest

import app as sidecar_app

SAGE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SOLUTION = "four_in_a_line"
SOLUTION_PATH = os.path.join(SAGE_ROOT, "solutions", SOLUTION)

PRODUCT = {
    "product_name": "CardioRisk CDS",
    "product_type": "samd",
    "risk_class": "IIb",
    "target_regions": ["us", "eu"],
    "uses_ai_ml": True,
    "existing_artifacts": ["software_requirements_spec", "traceability_matrix"],
}


def _req(id: str, method: str, params: dict | None = None) -> str:
    return json.dumps(
        {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}
    )


def _drive(lines: list[str], argv: list[str] | None = None) -> list[dict]:
    stdin = io.StringIO("".join(line + "\n" for line in lines))
    stdout = io.StringIO()
    sidecar_app.run(stdin=stdin, stdout=stdout, argv=argv or [])
    stdout.seek(0)
    return [json.loads(ln) for ln in stdout.read().splitlines() if ln.strip()]


@pytest.fixture
def solution_argv(tmp_path):
    """Drive the sidecar as the four_in_a_line solution, with its .sage/ dir
    redirected at a tmp path so the test never writes into the repo."""
    if not os.path.isdir(SOLUTION_PATH):
        pytest.skip("four_in_a_line solution not present on this branch")
    return ["--solution-name", SOLUTION, "--solution-path", str(tmp_path)]


def _seed_audit(tmp_path, **kw) -> None:
    """Insert one row into the audit DB the sidecar wired for this solution.

    AuditLogger.__init__ CREATEs the table, so the sidecar must be driven at
    least once before seeding (the fixture callers do exactly that).
    """
    db = str(tmp_path / ".sage" / "audit_log.db")
    conn = sqlite3.connect(db)
    conn.execute(
        """INSERT INTO compliance_audit_log
           (id, timestamp, trace_id, event_type, status, actor, action_type,
            output_content, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            kw.get("id", str(uuid.uuid4())),
            kw.get("timestamp", "2026-07-13T10:00:00"),
            kw.get("trace_id"),
            kw.get("event_type"),
            kw.get("status", "OK"),
            kw.get("actor", "AI_Agent"),
            kw.get("action_type", "ANALYSIS"),
            kw.get("output_content"),
            json.dumps(kw.get("metadata", {})),
        ),
    )
    conn.commit()
    conn.close()


# ---------- activity ----------

def test_activity_list_is_registered_and_wired(tmp_path, solution_argv):
    # First pass: creates .sage/audit_log.db (AuditLogger CREATEs the table).
    out = _drive([_req("a0", "activity.list")], argv=solution_argv)
    assert "result" in out[0], f"got error: {out[0]}"
    assert out[0]["result"]["total"] == 0
    assert out[0]["result"]["category"] == "all"

    # Second pass: with real rows, the triage feed classifies them.
    _seed_audit(tmp_path, event_type="TASK_COMPLETED", action_type="ANALYSIS",
                output_content="Board analysis finished", trace_id="tr-ok")
    _seed_audit(tmp_path, event_type="ANALYSIS", action_type="ANALYSIS",
                output_content="Traceback: connection error contacting provider",
                trace_id="tr-bad")
    out = _drive(
        [
            _req("a1", "activity.list"),
            _req("a2", "activity.list", {"category": "errors"}),
            _req("a3", "activity.list", {"query": "board"}),
        ],
        argv=solution_argv,
    )
    assert out[0]["result"]["total"] == 2
    # errors match on the free text of output_content alone — the whole point.
    assert out[1]["result"]["total"] == 1
    assert out[1]["result"]["events"][0]["category"] == "errors"
    assert out[2]["result"]["total"] == 1
    assert out[2]["result"]["events"][0]["trace_id"] == "tr-ok"


def test_activity_list_rejects_unknown_category(solution_argv):
    out = _drive([_req("a4", "activity.list", {"category": "nope"})], argv=solution_argv)
    assert out[0]["error"]["code"] == -32602


def test_activity_list_without_a_solution_reports_the_missing_logger(monkeypatch):
    """No solution → no AuditLogger → a clean InvalidParams, not a crash.

    ``_logger`` is module-level state that a previous _drive() in this process
    may already have set (a real sidecar process is always fresh), so reset it
    explicitly rather than depending on test order.
    """
    from handlers import activity

    monkeypatch.setattr(activity, "_logger", None)
    out = _drive([_req("a5", "activity.list")], argv=[])
    assert out[0]["error"]["code"] == -32602


# ---------- regulatory ----------
# Stateless singleton over a static registry — no solution needed.

def test_regulatory_standards_is_registered():
    out = _drive([_req("r1", "regulatory.standards")])
    assert "result" in out[0], f"got error: {out[0]}"
    ids = {s["id"] for s in out[0]["result"]["standards"]}
    assert {"iec_62304", "fda_21cfr11", "eu_mdr"} <= ids
    assert out[0]["result"]["total"] == len(out[0]["result"]["standards"])


def test_regulatory_standard_is_registered():
    out = _drive([_req("r2", "regulatory.standard", {"standard_id": "iec_62304"})])
    assert out[0]["result"]["id"] == "iec_62304"


def test_regulatory_standard_unknown_id_is_invalid_params():
    out = _drive([_req("r3", "regulatory.standard", {"standard_id": "nope"})])
    assert out[0]["error"]["code"] == -32602


def test_regulatory_checklist_is_registered():
    out = _drive([_req("r4", "regulatory.checklist", {"standard_id": "iso_14971"})])
    assert out[0]["result"]["standard_id"] == "iso_14971"
    assert out[0]["result"]["items"][0]["checked"] is False


def test_regulatory_assess_is_registered():
    out = _drive([_req("r5", "regulatory.assess", {"product": PRODUCT})])
    assert out[0]["result"]["product_name"] == "CardioRisk CDS"
    assert out[0]["result"]["standards_assessed"] > 1
    assert "iec_62304" in out[0]["result"]["assessments"]


def test_regulatory_assess_requires_a_product():
    out = _drive([_req("r6", "regulatory.assess", {})])
    assert out[0]["error"]["code"] == -32602


def test_regulatory_gap_analysis_is_registered():
    out = _drive(
        [_req("r7", "regulatory.gap_analysis",
              {"product": PRODUCT, "standard_id": "iec_62304"})]
    )
    assert out[0]["result"]["standard_id"] == "iec_62304"
    assert len(out[0]["result"]["gaps"]) > 0


def test_regulatory_roadmap_is_registered():
    out = _drive([_req("r8", "regulatory.roadmap", {"product": PRODUCT})])
    result = out[0]["result"]
    assert result["target_regions"] == ["us", "eu"]
    assert result["total_estimated_weeks"] == sum(
        p["estimated_weeks"] for p in result["phases"]
    )


def test_every_new_method_is_in_the_dispatcher():
    d = sidecar_app._build_dispatcher()
    for method in (
        "activity.list",
        "regulatory.standards",
        "regulatory.standard",
        "regulatory.checklist",
        "regulatory.assess",
        "regulatory.gap_analysis",
        "regulatory.roadmap",
    ):
        assert method in d._handlers, f"{method} not registered"
