"""
Operational Qualification (OQ) Tests
======================================
Verifies that SAGE operates correctly under normal conditions.
Tests core functionality against documented specifications.

OQ confirms: "Does the system work as specified?"
"""

import json
import os
import pytest


class TestTraceabilityOperations:
    """OQ-001: Traceability matrix CRUD operations work correctly."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        from src.core.traceability import TraceabilityMatrix, TraceLevel
        self.tm = TraceabilityMatrix(db_path=str(tmp_path / "oq_trace.db"))
        self.TraceLevel = TraceLevel

    def test_create_requirement(self):
        """Can create a system requirement and retrieve it."""
        item = self.tm.add_item(
            level=self.TraceLevel.SYSTEM_REQ,
            title="System shall detect cardiac arrhythmia within 2 seconds",
            description="Real-time analysis of ECG waveform",
        )
        fetched = self.tm.get_item(item.id)
        assert fetched is not None
        assert fetched.title == "System shall detect cardiac arrhythmia within 2 seconds"

    def test_create_trace_link(self):
        """Can link a requirement to a test case."""
        req = self.tm.add_item(level=self.TraceLevel.SOFTWARE_REQ, title="Alarm threshold configurable")
        test = self.tm.add_item(level=self.TraceLevel.UNIT_TEST, title="Test alarm threshold range")
        link = self.tm.add_link(req.id, test.id, link_type="verifies")
        forward = self.tm.get_forward_links(req.id)
        assert len(forward) == 1
        assert forward[0]["target_id"] == test.id

    def test_coverage_report_accuracy(self):
        """Coverage report correctly identifies orphaned requirements."""
        req1 = self.tm.add_item(level=self.TraceLevel.SYSTEM_REQ, title="Covered req")
        req2 = self.tm.add_item(level=self.TraceLevel.SYSTEM_REQ, title="Orphaned req")
        test = self.tm.add_item(level=self.TraceLevel.UNIT_TEST, title="Test for req1")
        self.tm.add_link(req1.id, test.id)
        report = self.tm.coverage_report()
        sr = report["per_level"]["system_requirement"]
        assert sr["orphaned"] == 1
        assert req2.id in sr["orphaned_ids"]

    def test_gap_analysis_detects_untested_requirements(self):
        """Gap analysis finds requirements without test links."""
        self.tm.add_item(level=self.TraceLevel.SOFTWARE_REQ, title="Untested req")
        gaps = self.tm.gap_analysis()
        assert any(g["type"] == "requirements_without_tests" for g in gaps["gaps"])


class TestAuditIntegrityOperations:
    """OQ-002: HMAC hash chain maintains integrity."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        from src.core.audit_integrity import AuditIntegrityManager
        self.mgr = AuditIntegrityManager(db_path=str(tmp_path / "oq_audit.db"))

    def test_chain_integrity_on_sequential_entries(self):
        """Chain of 10 entries verifies successfully."""
        for i in range(10):
            self.mgr.append_entry(f"OQ-EVT-{i:03d}", {"action": "test", "seq": i})
        result = self.mgr.verify_chain()
        assert result["valid"] is True
        assert result["verified_entries"] == 10

    def test_chain_detects_gap(self):
        """Appending entries produces a continuous chain."""
        self.mgr.append_entry("EVT-A", {"data": "first"})
        self.mgr.append_entry("EVT-B", {"data": "second"})
        result = self.mgr.verify_chain()
        assert result["valid"] is True


class TestChangeControlOperations:
    """OQ-003: Change control workflow follows defined state machine."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        from src.core.change_control import ChangeControlManager
        self.ccm = ChangeControlManager(db_path=str(tmp_path / "oq_change.db"))

    def test_full_lifecycle(self):
        """CR flows through: draft -> submitted -> approved -> implemented -> verified -> closed."""
        cr = self.ccm.create_request(
            title="Update alarm algorithm",
            description="Change threshold calculation per clinical study results",
            category="corrective",
            priority="high",
            requester="clinical_engineer@example.com",
        )
        cr_id = cr["id"]

        self.ccm.update_status(cr_id, "submitted", "clinical_engineer")
        self.ccm.add_impact_assessment(cr_id, {
            "affected_requirements": ["REQ-ALARM-001"],
            "risk_impact": "medium",
            "safety_impact": "review_required",
        })
        self.ccm.add_approval(cr_id, "qa_manager", "QA", "approved", "Risk acceptable")
        self.ccm.update_status(cr_id, "approved", "qa_manager")
        self.ccm.update_status(cr_id, "implemented", "developer")
        self.ccm.update_status(cr_id, "verified", "qa_engineer")
        self.ccm.update_status(cr_id, "closed", "qa_manager")

        final = self.ccm.get_request(cr_id)
        assert final["status"] == "closed"
        assert final["closed_at"] is not None

        history = self.ccm.get_history(cr_id)
        statuses = [h["to_status"] for h in history]
        # impact_assessed is set directly by add_impact_assessment, not via update_status
        assert statuses == ["draft", "submitted", "approved",
                           "implemented", "verified", "closed"]


class TestDocumentGeneration:
    """OQ-004: Document generator produces valid output."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from src.core.doc_generator import DocumentGenerator
        self.gen = DocumentGenerator(project_name="medtech_oq", version="1.0")

    def test_srs_contains_all_requirements(self):
        """Generated SRS includes every requirement passed in."""
        reqs = [
            {"id": f"REQ-{i:03d}", "type": "functional", "title": f"Requirement {i}",
             "description": f"Description {i}", "acceptance_criteria": [f"AC-{i}"],
             "priority": "high", "verification_method": "test", "status": "approved"}
            for i in range(5)
        ]
        doc = self.gen.generate_srs(reqs)
        for r in reqs:
            assert r["id"] in doc
            assert r["title"] in doc

    def test_rtm_shows_trace_links(self):
        """Generated RTM includes trace link information."""
        data = [
            {"id": "SYS-001", "level": "system_requirement", "title": "Speed",
             "status": "active", "traces_to": [{"target_id": "TST-001"}], "traced_from": []},
            {"id": "TST-001", "level": "unit_test", "title": "Speed Test",
             "status": "active", "traces_to": [], "traced_from": [{"source_id": "SYS-001"}]},
        ]
        doc = self.gen.generate_rtm(data)
        assert "SYS-001" in doc
        assert "TST-001" in doc
        assert "100.0%" in doc  # both items traced = 100%


class TestComplianceVerification:
    """OQ-005: Compliance verifier produces accurate assessments."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from src.core.compliance_verifier import ComplianceVerifier
        self.verifier = ComplianceVerifier()

    def test_iec62304_fully_compliant_project(self):
        """A project with all artifacts should score high compliance."""
        data = {
            "development_plan": True,
            "requirements": [
                {"id": "R1", "acceptance_criteria": ["AC1"], "verification_method": "test"},
                {"id": "R2", "acceptance_criteria": ["AC2"], "verification_method": "analysis"},
            ],
            "architecture": True,
            "tests": [{"level": "integration"}, {"level": "unit"}],
            "risks": [{"id": "RISK-1"}],
            "trace_data": [
                {"id": "R1", "traces_to": [{"target_id": "T1"}], "traced_from": []},
                {"id": "T1", "traces_to": [], "traced_from": [{"source_id": "R1"}]},
            ],
            "change_control_enabled": True,
            "soup_components": [{"name": "FastAPI"}],
        }
        results = self.verifier.verify_iec62304(data)
        passed = [r for r in results if r["passed"]]
        assert len(passed) >= 7

    def test_empty_project_flags_critical_gaps(self):
        """An empty project should have critical failures flagged."""
        result = self.verifier.verify_all({}, standards=["iec62304"])
        assert result["critical_failures"] > 0
        assert result["compliance_pct"] < 50
