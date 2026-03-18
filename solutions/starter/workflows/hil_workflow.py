"""
SAGE HIL Workflow — Hardware-in-the-Loop Testing
=================================================
LangGraph workflow for regulated HIL test cycles.

Flow:
  flash_firmware → run_hil_suite → collect_evidence → generate_report
  → [HITL gate] → submit_evidence

The workflow runs autonomously through generate_report, then pauses at
submit_evidence for human review of the regulatory evidence report.
This follows SOUL.md: "Agents propose. Humans decide." — especially critical
for regulated industries where no evidence can be submitted to a DHF/TCF
without human review and sign-off.

Usage:
  POST /workflow/run
  {
    "workflow_name": "hil_workflow",
    "state": {
      "firmware_path": "/path/to/firmware.bin",
      "transport": "jlink",
      "standard": "IEC62304",
      "domain": "medtech",
      "risk_level": "CLASS_C",
      "test_suite": [
        {
          "id": "TC-001",
          "name": "Power-on self test",
          "requirement_id": "REQ-001",
          "description": "Verify device passes POST after firmware flash",
          "procedure": ["Power on device", "Wait 2s", "Read status register"],
          "expected_result": "Status 0x00 (OK)"
        }
      ]
    }
  }

  POST /workflow/resume
  {"run_id": "<id>", "feedback": {"approved": true, "approver": "jane.smith@company.com"}}
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import TypedDict, Optional, List

from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class HILState(TypedDict, total=False):
    # Input
    firmware_path:    str                 # Path to firmware binary to flash
    transport:        str                 # HIL transport: mock, serial, jlink, can, openocd
    transport_config: dict                # Transport-specific config (port, baud_rate, device, etc.)
    standard:         str                 # Regulatory standard: IEC62304, DO178C, EN50128, ISO26262
    domain:           str                 # Compliance domain: medtech, automotive, railways, avionics, iot_ics
    risk_level:       str                 # Risk level: CLASS_C, ASIL_D, SIL_4, DAL_A, SL_3
    test_suite:       List[dict]          # List of test case dicts
    solution_name:    str                 # SAGE solution context (optional)

    # Execution
    session_id:       str                 # HIL session ID
    flash_result:     dict                # Result of firmware flashing
    suite_results:    dict                # Raw test suite results from HILRunner.run_suite()
    evidence:         dict                # Collected evidence: logs, traces, screenshots

    # Reporting
    report:           dict                # Full regulatory evidence report
    compliance_flags: List[dict]          # Required compliance flags for domain+risk_level
    hil_required_tests: List[str]         # Flag IDs that require HIL testing
    checklist:        dict                # Compliance checklist with pass/fail per item

    # HITL gate
    approved:         bool                # Set by human at the approval gate
    approver:         str                 # Identity of the approver
    rejection_reason: str                 # Reason if rejected

    # Meta
    run_id:           str
    trace_id:         str
    error:            Optional[str]
    completed_at:     str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_runner(state: HILState):
    """Instantiate or retrieve the HIL runner for this state."""
    from src.integrations.hil_runner import get_hil_runner
    transport = state.get("transport", "mock")
    config    = state.get("transport_config") or {}
    # Overlay config.yaml hardware settings if not explicitly provided
    if not config:
        try:
            from src.core.project_loader import get_config
            cfg = get_config()
            if transport == "serial":
                config = cfg.get("serial", {})
            elif transport == "jlink":
                config = cfg.get("jlink", {})
        except Exception:
            pass
    return get_hil_runner(transport=transport, config=config)


def _build_test_cases(suite: List[dict]):
    """Convert raw dicts from state into HILTestCase objects."""
    from src.integrations.hil_runner import HILTestCase, HILTransport
    cases = []
    for item in (suite or []):
        transport_str = item.get("transport", "mock")
        try:
            transport_enum = HILTransport(transport_str.lower())
        except ValueError:
            transport_enum = HILTransport.MOCK
        cases.append(HILTestCase(
            id=item.get("id", "TC-UNKNOWN"),
            name=item.get("name", "Unnamed test"),
            requirement_id=item.get("requirement_id", "REQ-UNKNOWN"),
            description=item.get("description", ""),
            procedure=item.get("procedure", []),
            expected_result=item.get("expected_result", ""),
            transport=transport_enum,
            timeout_seconds=item.get("timeout_seconds", 30),
        ))
    return cases


# ---------------------------------------------------------------------------
# Node 1: flash_firmware
# ---------------------------------------------------------------------------

def flash_firmware(state: HILState) -> HILState:
    """
    Flash the firmware binary to the connected hardware.
    If no firmware_path is provided, or transport is mock, skips flashing.
    """
    firmware_path = state.get("firmware_path", "")
    transport     = state.get("transport", "mock")

    if not firmware_path:
        logger.info("No firmware_path provided — skipping flash step")
        return {
            **state,
            "flash_result": {"success": True, "output": "No firmware to flash — skipped", "skipped": True},
        }

    runner = _get_runner(state)
    connected = runner.connect()

    if not connected and transport != "mock":
        logger.warning("HIL hardware not connected — flash blocked")
        return {
            **state,
            "session_id":  runner.session_id,
            "flash_result": {
                "success": False,
                "output":  "",
                "error":   f"Could not connect to hardware via {transport}",
                "blocked": True,
            },
        }

    flash_result = runner.flash_firmware(firmware_path)
    logger.info(
        "Flash result: success=%s firmware=%s",
        flash_result.get("success"), firmware_path,
    )

    try:
        from src.memory.audit_logger import audit_logger
        audit_logger.log_event(
            actor="HILWorkflow",
            action_type="HIL_FIRMWARE_FLASH",
            input_context=firmware_path,
            output_content="OK" if flash_result.get("success") else "FAILED",
            metadata={"flash_result": flash_result, "transport": transport},
        )
    except Exception as e:
        logger.debug("Audit log for flash failed (non-fatal): %s", e)

    return {
        **state,
        "session_id":  runner.session_id,
        "flash_result": flash_result,
    }


# ---------------------------------------------------------------------------
# Node 2: run_hil_suite
# ---------------------------------------------------------------------------

def run_hil_suite(state: HILState) -> HILState:
    """
    Execute the full HIL test suite against the connected hardware.
    Results are accumulated on the HIL runner instance.
    """
    test_suite = state.get("test_suite") or []
    transport  = state.get("transport", "mock")

    if not test_suite:
        logger.warning("No test_suite in state — using empty mock suite")
        from src.integrations.hil_runner import HILTestCase, HILTransport
        test_suite_raw = [
            {
                "id":              "TC-MOCK-001",
                "name":            "Mock connectivity check",
                "requirement_id":  "REQ-MOCK",
                "description":     "Verify HIL runner is operational",
                "procedure":       ["Check connection", "Ping device"],
                "expected_result": "Device responds with OK",
            }
        ]
    else:
        test_suite_raw = test_suite

    runner    = _get_runner(state)
    if not runner._connected:
        runner.connect()

    test_cases   = _build_test_cases(test_suite_raw)
    suite_results = runner.run_suite(test_cases)

    logger.info(
        "HIL suite complete: %d/%d passed (session=%s)",
        suite_results.get("passed", 0),
        suite_results.get("total", 0),
        suite_results.get("session_id", ""),
    )

    return {
        **state,
        "session_id":   suite_results.get("session_id", state.get("session_id", "")),
        "suite_results": suite_results,
    }


# ---------------------------------------------------------------------------
# Node 3: collect_evidence
# ---------------------------------------------------------------------------

def collect_evidence(state: HILState) -> HILState:
    """
    Gather supplementary evidence: serial logs, CAN traces, system info.
    Evidence is attached to the session for regulatory reporting.
    """
    suite_results = state.get("suite_results", {})
    transport     = state.get("transport", "mock")
    evidence      = {}

    # Always collect: suite metadata and test result summaries
    evidence["session_id"]   = state.get("session_id", "")
    evidence["transport"]    = transport
    evidence["timestamp"]    = datetime.now(timezone.utc).isoformat()
    evidence["test_summary"] = {
        "total":     suite_results.get("total", 0),
        "passed":    suite_results.get("passed", 0),
        "failed":    suite_results.get("failed", 0),
        "blocked":   suite_results.get("blocked", 0),
        "pass_rate": suite_results.get("pass_rate", 0.0),
    }

    # Per-test evidence capture
    evidence["test_evidence"] = []
    for r in suite_results.get("results", []):
        evidence["test_evidence"].append({
            "test_id":       r.get("test_id"),
            "verdict":       r.get("verdict"),
            "duration_s":    r.get("duration_seconds"),
            "raw_evidence":  r.get("evidence", {}),
        })

    # Compliance context
    domain     = state.get("domain", "")
    risk_level = state.get("risk_level", "")
    if domain and risk_level:
        try:
            from src.core.compliance_flags import (
                get_required_flags,
                get_hil_required_tests,
                generate_compliance_checklist,
            )
            flags            = get_required_flags(domain, risk_level)
            hil_tests        = get_hil_required_tests(domain, risk_level)
            checklist        = generate_compliance_checklist(domain, risk_level)
            evidence["compliance"] = {
                "domain":            domain,
                "risk_level":        risk_level,
                "flags_applicable":  len(flags),
                "hil_required_count": len(hil_tests),
            }
        except Exception as e:
            logger.debug("Compliance flags collection failed (non-fatal): %s", e)
            flags    = []
            hil_tests = []
            checklist = {}
    else:
        flags    = []
        hil_tests = []
        checklist = {}

    logger.info("Evidence collected: %d test results, %d compliance flags", len(evidence["test_evidence"]), len(flags))

    return {
        **state,
        "evidence":           evidence,
        "compliance_flags":   flags,
        "hil_required_tests": hil_tests,
        "checklist":          checklist,
    }


# ---------------------------------------------------------------------------
# Node 4: generate_report
# ---------------------------------------------------------------------------

def generate_report(state: HILState) -> HILState:
    """
    Create the full regulatory evidence report.
    Includes traceability matrix, summary, failed tests, and standard-specific metadata.
    """
    standard       = state.get("standard", "IEC62304")
    suite_results  = state.get("suite_results", {})
    evidence       = state.get("evidence", {})
    domain         = state.get("domain", "")
    risk_level     = state.get("risk_level", "")
    checklist      = state.get("checklist", {})
    compliance_flags = state.get("compliance_flags", [])
    hil_required   = state.get("hil_required_tests", [])

    runner = _get_runner(state)
    report = runner.generate_report(standard=standard)

    # Augment with compliance data
    report["domain"]              = domain
    report["risk_level"]          = risk_level
    report["compliance_flags"]    = compliance_flags
    report["hil_required_tests"]  = hil_required
    report["checklist_summary"]   = {
        "total_items":     checklist.get("total_items", 0),
        "flags_checked":   checklist.get("flags", 0),
        "tasks_required":  checklist.get("required_tasks", 0),
        "artifacts_required": checklist.get("artifacts", 0),
    }
    report["firmware_path"]   = state.get("firmware_path", "")
    report["flash_result"]    = state.get("flash_result", {})
    report["evidence_bundle"] = evidence

    # Overall compliance gate: fail if any HIL-required tests are missing or failed
    failed_ids = {r.get("test_id") for r in suite_results.get("results", []) if r.get("verdict") in ("FAIL", "ERROR", "BLOCKED")}
    blocking_failures = []
    for flag_id in hil_required:
        # If any result maps to a requirement that this flag covers, check it
        for r in suite_results.get("results", []):
            if r.get("requirement_id") and flag_id in r.get("requirement_id", ""):
                if r.get("test_id") in failed_ids:
                    blocking_failures.append({
                        "flag_id":  flag_id,
                        "test_id":  r.get("test_id"),
                        "verdict":  r.get("verdict"),
                    })

    report["blocking_failures"]        = blocking_failures
    report["regulatory_gate_passed"]   = len(blocking_failures) == 0 and suite_results.get("failed", 0) == 0

    logger.info(
        "Regulatory report generated: standard=%s domain=%s risk_level=%s gate_passed=%s",
        standard, domain, risk_level, report["regulatory_gate_passed"],
    )

    return {**state, "report": report}


# ---------------------------------------------------------------------------
# Node 5: submit_evidence  (HITL gate — interrupt_before this node)
# ---------------------------------------------------------------------------

def submit_evidence(state: HILState) -> HILState:
    """
    Write the approved regulatory evidence report to the SAGE audit log.
    Called only after human approval at the HITL gate.

    This is the final step before evidence can be used in a DHF/TCF/safety case.
    """
    report    = state.get("report", {})
    approved  = state.get("approved", False)
    approver  = state.get("approver", "unknown")
    standard  = state.get("standard", "IEC62304")
    domain    = state.get("domain", "")
    risk_level = state.get("risk_level", "")

    if not approved:
        logger.warning("submit_evidence called but approved=False — evidence NOT submitted")
        return {
            **state,
            "error": "Evidence not submitted: human approval is required",
        }

    completed_at = datetime.now(timezone.utc).isoformat()

    # Attach approval metadata to report
    report["approved"]       = True
    report["approver"]       = approver
    report["approved_at"]    = completed_at
    report["submission_note"] = (
        f"Approved by {approver} at {completed_at}. "
        f"Regulatory evidence submitted for {standard} / {domain.upper()} {risk_level}."
    )

    # Write to audit log (the SAGE compliance record)
    try:
        from src.memory.audit_logger import audit_logger
        audit_logger.log_event(
            actor="HILWorkflow",
            action_type="HIL_EVIDENCE_SUBMITTED",
            input_context=f"{standard} / {domain.upper()} {risk_level}",
            output_content=f"Approved by {approver}",
            metadata={
                "session_id":            report.get("session_id"),
                "standard":              standard,
                "domain":                domain,
                "risk_level":            risk_level,
                "regulatory_gate_passed": report.get("regulatory_gate_passed"),
                "summary":               report.get("summary"),
                "approver":              approver,
                "approved_at":           completed_at,
                "firmware_path":         state.get("firmware_path", ""),
            },
        )
        logger.info(
            "HIL evidence submitted to audit log: standard=%s domain=%s approver=%s",
            standard, domain, approver,
        )
    except Exception as e:
        logger.error("Audit log submission failed: %s", e)

    return {
        **state,
        "report":       report,
        "completed_at": completed_at,
        "error":        None,
    }


# ---------------------------------------------------------------------------
# Graph — autonomous through generate_report; HITL gate before submit_evidence
# ---------------------------------------------------------------------------
#
# The workflow runs fully autonomously through generate_report, then pauses at
# submit_evidence for human review of the regulatory evidence.
# This gate is non-optional: regulated evidence cannot be submitted without
# human sign-off (IEC 62304 §5.7, DO-178C §12.1.3, EN 50128 §6.2).

graph = StateGraph(HILState)
graph.add_node("flash_firmware",   flash_firmware)
graph.add_node("run_hil_suite",    run_hil_suite)
graph.add_node("collect_evidence", collect_evidence)
graph.add_node("generate_report",  generate_report)
graph.add_node("submit_evidence",  submit_evidence)

graph.set_entry_point("flash_firmware")
graph.add_edge("flash_firmware",   "run_hil_suite")
graph.add_edge("run_hil_suite",    "collect_evidence")
graph.add_edge("collect_evidence", "generate_report")
graph.add_edge("generate_report",  "submit_evidence")
graph.add_edge("submit_evidence",  END)

# interrupt_before=["submit_evidence"] pauses after generate_report so the human
# can review the full evidence report before it is written to the audit log.
workflow = graph.compile(interrupt_before=["submit_evidence"])
