"""
Tests for regulatory compliance engineering modules:
  - Traceability matrix
  - Audit integrity (HMAC hash chain)
  - Document generation
  - Change control workflow
  - Compliance verifier
"""

import json
import os
import tempfile
import pytest

# ═══════════════════════════════════════════════════════════════════════
# TRACEABILITY MATRIX
# ═══════════════════════════════════════════════════════════════════════

class TestTraceabilityMatrix:
    """Tests for src.core.traceability.TraceabilityMatrix."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        from src.core.traceability import TraceabilityMatrix, TraceLevel
        self.db_path = str(tmp_path / "trace.db")
        self.tm = TraceabilityMatrix(db_path=self.db_path)
        self.TraceLevel = TraceLevel

    def test_add_and_get_item(self):
        item = self.tm.add_item(
            level=self.TraceLevel.SYSTEM_REQ,
            title="System shall boot in under 5 seconds",
            description="Performance requirement for boot time",
        )
        assert item.id.startswith("SYS")
        assert item.level == self.TraceLevel.SYSTEM_REQ
        assert item.title == "System shall boot in under 5 seconds"

        fetched = self.tm.get_item(item.id)
        assert fetched is not None
        assert fetched.title == item.title

    def test_add_item_with_custom_id(self):
        item = self.tm.add_item(
            level=self.TraceLevel.USER_NEED,
            title="User needs fast startup",
            item_id="UN-001",
        )
        assert item.id == "UN-001"

    def test_list_items_by_level(self):
        self.tm.add_item(level=self.TraceLevel.SYSTEM_REQ, title="Req A")
        self.tm.add_item(level=self.TraceLevel.SYSTEM_REQ, title="Req B")
        self.tm.add_item(level=self.TraceLevel.UNIT_TEST, title="Test 1")

        reqs = self.tm.list_items(level=self.TraceLevel.SYSTEM_REQ)
        assert len(reqs) == 2

        tests = self.tm.list_items(level=self.TraceLevel.UNIT_TEST)
        assert len(tests) == 1

    def test_add_link_and_forward_backward(self):
        req = self.tm.add_item(level=self.TraceLevel.SYSTEM_REQ, title="Req")
        test = self.tm.add_item(level=self.TraceLevel.UNIT_TEST, title="Test for Req")
        link = self.tm.add_link(req.id, test.id, link_type="verifies", rationale="Direct test")

        assert link.source_id == req.id
        assert link.target_id == test.id

        forward = self.tm.get_forward_links(req.id)
        assert len(forward) == 1
        assert forward[0]["target_id"] == test.id
        assert forward[0]["link_type"] == "verifies"

        backward = self.tm.get_backward_links(test.id)
        assert len(backward) == 1
        assert backward[0]["source_id"] == req.id

    def test_coverage_report(self):
        req = self.tm.add_item(level=self.TraceLevel.SYSTEM_REQ, title="Req 1")
        orphan = self.tm.add_item(level=self.TraceLevel.SYSTEM_REQ, title="Orphan Req")
        test = self.tm.add_item(level=self.TraceLevel.UNIT_TEST, title="Test 1")
        self.tm.add_link(req.id, test.id, link_type="verifies")

        report = self.tm.coverage_report()
        assert report["total_items"] == 3
        assert report["total_linked"] == 2  # req + test are linked
        assert "system_requirement" in report["per_level"]
        sr = report["per_level"]["system_requirement"]
        assert sr["total"] == 2
        assert sr["orphaned"] == 1
        assert orphan.id in sr["orphaned_ids"]

    def test_gap_analysis(self):
        req = self.tm.add_item(level=self.TraceLevel.SOFTWARE_REQ, title="SW Req")
        design = self.tm.add_item(level=self.TraceLevel.DESIGN, title="Design Element")
        # No links — both are gaps

        gaps = self.tm.gap_analysis()
        assert gaps["total_gaps"] >= 2
        gap_types = [g["type"] for g in gaps["gaps"]]
        assert "requirements_without_tests" in gap_types
        assert "design_without_implementation" in gap_types

    def test_export_matrix(self):
        req = self.tm.add_item(level=self.TraceLevel.SYSTEM_REQ, title="Req")
        test = self.tm.add_item(level=self.TraceLevel.UNIT_TEST, title="Test")
        self.tm.add_link(req.id, test.id)

        export = self.tm.export_matrix()
        assert len(export) == 2
        req_entry = next(e for e in export if e["id"] == req.id)
        assert len(req_entry["traces_to"]) == 1

    def test_get_nonexistent_item(self):
        assert self.tm.get_item("NONEXISTENT") is None

    def test_item_to_dict(self):
        item = self.tm.add_item(level=self.TraceLevel.VERIFICATION, title="V1")
        d = item.to_dict()
        assert d["level"] == "verification"
        assert d["title"] == "V1"


# ═══════════════════════════════════════════════════════════════════════
# AUDIT INTEGRITY
# ═══════════════════════════════════════════════════════════════════════

class TestAuditIntegrity:
    """Tests for src.core.audit_integrity.AuditIntegrityManager."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        from src.core.audit_integrity import AuditIntegrityManager, compute_hmac
        self.db_path = str(tmp_path / "audit.db")
        self.mgr = AuditIntegrityManager(db_path=self.db_path)
        self.compute_hmac = compute_hmac

    def test_empty_chain_is_valid(self):
        result = self.mgr.verify_chain()
        assert result["valid"] is True
        assert result["total_entries"] == 0

    def test_append_and_verify_single_entry(self):
        entry = self.mgr.append_entry("evt-001", {"action": "test", "actor": "user"})
        assert entry["sequence_num"] == 1
        assert len(entry["chain_hmac"]) == 64  # SHA256 hex

        result = self.mgr.verify_chain()
        assert result["valid"] is True
        assert result["verified_entries"] == 1

    def test_append_multiple_and_verify_chain(self):
        for i in range(5):
            self.mgr.append_entry(f"evt-{i:03d}", {"index": i})

        result = self.mgr.verify_chain()
        assert result["valid"] is True
        assert result["verified_entries"] == 5

    def test_chain_status(self):
        self.mgr.append_entry("evt-001", {"data": "hello"})
        status = self.mgr.get_chain_status()
        assert status["total_entries"] == 1
        assert status["chain_active"] is True
        assert status["first_entry_at"] is not None

    def test_get_last_hmac(self):
        assert self.mgr.get_last_hmac() == ""
        self.mgr.append_entry("evt-001", {"data": "test"})
        assert len(self.mgr.get_last_hmac()) == 64

    def test_hmac_deterministic(self):
        h1 = self.compute_hmac("same-data", "same-prev")
        h2 = self.compute_hmac("same-data", "same-prev")
        assert h1 == h2

    def test_hmac_different_input(self):
        h1 = self.compute_hmac("data-a", "")
        h2 = self.compute_hmac("data-b", "")
        assert h1 != h2


# ═══════════════════════════════════════════════════════════════════════
# DOCUMENT GENERATION
# ═══════════════════════════════════════════════════════════════════════

class TestDocumentGenerator:
    """Tests for src.core.doc_generator.DocumentGenerator."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from src.core.doc_generator import DocumentGenerator
        self.gen = DocumentGenerator(project_name="test_project", version="2.0")

    def test_generate_srs(self):
        reqs = [
            {"id": "REQ-001", "type": "functional", "title": "Login",
             "description": "User can log in", "acceptance_criteria": ["Must accept email/password"],
             "priority": "high", "verification_method": "test", "status": "approved"},
        ]
        doc = self.gen.generate_srs(reqs, {"intended_use": "Clinical monitoring"})
        assert "Software Requirements Specification" in doc
        assert "REQ-001" in doc
        assert "Login" in doc
        assert "Clinical monitoring" in doc
        assert "test_project" in doc

    def test_generate_risk_management(self):
        risks = [
            {"id": "RISK-001", "hazard": "Data loss", "severity": "HIGH",
             "probability": "LOW", "risk_level": "MEDIUM",
             "mitigation": "Automatic backup", "residual_risk": "LOW"},
        ]
        doc = self.gen.generate_risk_management(risks)
        assert "Risk Management File" in doc
        assert "RISK-001" in doc
        assert "Data loss" in doc

    def test_generate_rtm(self):
        trace = [
            {"id": "SYS-001", "level": "system_requirement", "title": "Speed",
             "status": "active", "traces_to": [{"target_id": "TST-001"}], "traced_from": []},
        ]
        doc = self.gen.generate_rtm(trace)
        assert "Traceability Matrix" in doc
        assert "SYS-001" in doc

    def test_generate_vv_plan(self):
        reqs = [
            {"id": "REQ-001", "title": "Login", "verification_method": "test",
             "test_level": "integration", "verification_status": "planned"},
        ]
        doc = self.gen.generate_vv_plan(reqs)
        assert "Verification & Validation Plan" in doc
        assert "REQ-001" in doc

    def test_generate_soup_inventory(self):
        deps = [
            {"name": "FastAPI", "version": "0.104.1", "license": "MIT",
             "purpose": "Web framework", "risk_class": "low",
             "anomaly_list_url": "https://github.com/tiangolo/fastapi/issues"},
        ]
        doc = self.gen.generate_soup_inventory(deps)
        assert "SOUP Inventory" in doc
        assert "FastAPI" in doc

    def test_generate_document_dispatcher(self):
        doc = self.gen.generate_document("srs", {"requirements": []})
        assert "Software Requirements Specification" in doc

    def test_generate_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown document type"):
            self.gen.generate_document("nonexistent", {})

    def test_list_document_types(self):
        types = self.gen.list_document_types()
        assert len(types) == 5
        type_ids = [t["type"] for t in types]
        assert "srs" in type_ids
        assert "rtm" in type_ids


# ═══════════════════════════════════════════════════════════════════════
# CHANGE CONTROL
# ═══════════════════════════════════════════════════════════════════════

class TestChangeControl:
    """Tests for src.core.change_control.ChangeControlManager."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        from src.core.change_control import ChangeControlManager
        self.db_path = str(tmp_path / "change.db")
        self.ccm = ChangeControlManager(db_path=self.db_path)

    def test_create_request(self):
        result = self.ccm.create_request(
            title="Fix null pointer in parser",
            description="Parser crashes on empty input",
            category="corrective",
            priority="high",
            requester="engineer@example.com",
        )
        assert result["id"].startswith("CR-")
        assert result["status"] == "draft"

    def test_get_request(self):
        created = self.ccm.create_request(
            title="Add validation", description="Input validation needed",
            category="preventive", priority="medium", requester="dev",
        )
        fetched = self.ccm.get_request(created["id"])
        assert fetched is not None
        assert fetched["title"] == "Add validation"
        assert fetched["status"] == "draft"

    def test_list_requests(self):
        self.ccm.create_request("A", "desc", "corrective", "high", "dev")
        self.ccm.create_request("B", "desc", "adaptive", "low", "dev")

        all_reqs = self.ccm.list_requests()
        assert len(all_reqs) == 2

        draft_reqs = self.ccm.list_requests(status="draft")
        assert len(draft_reqs) == 2

    def test_update_status(self):
        created = self.ccm.create_request("Fix", "desc", "corrective", "high", "dev")
        result = self.ccm.update_status(created["id"], "submitted", "dev", "Ready for review")
        assert result["old_status"] == "draft"
        assert result["new_status"] == "submitted"

        fetched = self.ccm.get_request(created["id"])
        assert fetched["status"] == "submitted"

    def test_add_impact_assessment(self):
        created = self.ccm.create_request("Fix", "desc", "corrective", "high", "dev")
        self.ccm.add_impact_assessment(created["id"], {
            "affected_requirements": ["REQ-001"],
            "risk_impact": "low",
        })
        fetched = self.ccm.get_request(created["id"])
        assert fetched["status"] == "impact_assessed"
        assert "REQ-001" in fetched["impact_assessment"]["affected_requirements"]

    def test_add_approval(self):
        created = self.ccm.create_request("Fix", "desc", "corrective", "high", "dev")
        result = self.ccm.add_approval(
            created["id"], approver="qa_lead", role="QA",
            decision="approved", comments="Looks good",
        )
        assert result["approval"]["decision"] == "approved"

        fetched = self.ccm.get_request(created["id"])
        assert len(fetched["approvals"]) == 1

    def test_get_history(self):
        created = self.ccm.create_request("Fix", "desc", "corrective", "high", "dev")
        self.ccm.update_status(created["id"], "submitted", "dev")
        self.ccm.update_status(created["id"], "approved", "manager")

        history = self.ccm.get_history(created["id"])
        assert len(history) == 3  # created + submitted + approved
        assert history[0]["to_status"] == "draft"
        assert history[1]["to_status"] == "submitted"
        assert history[2]["to_status"] == "approved"

    def test_get_metrics(self):
        self.ccm.create_request("A", "desc", "corrective", "high", "dev")
        self.ccm.create_request("B", "desc", "adaptive", "low", "dev")

        metrics = self.ccm.get_metrics()
        assert metrics["total_requests"] == 2
        assert metrics["by_status"]["draft"] == 2
        assert metrics["open_requests"] == 2

    def test_invalid_category_raises(self):
        with pytest.raises(ValueError):
            self.ccm.create_request("X", "desc", "invalid_cat", "high", "dev")

    def test_invalid_priority_raises(self):
        with pytest.raises(ValueError):
            self.ccm.create_request("X", "desc", "corrective", "invalid_pri", "dev")

    def test_nonexistent_request(self):
        assert self.ccm.get_request("CR-NONEXISTENT") is None

    def test_update_nonexistent_raises(self):
        with pytest.raises(ValueError):
            self.ccm.update_status("CR-NONEXISTENT", "submitted", "dev")


# ═══════════════════════════════════════════════════════════════════════
# COMPLIANCE VERIFIER
# ═══════════════════════════════════════════════════════════════════════

class TestComplianceVerifier:
    """Tests for src.core.compliance_verifier.ComplianceVerifier."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from src.core.compliance_verifier import ComplianceVerifier
        self.verifier = ComplianceVerifier()

    def test_verify_iec62304_minimal(self):
        """Minimal project data — most checks should fail."""
        results = self.verifier.verify_iec62304({})
        assert len(results) > 0
        # With no data, most checks fail
        failed = [r for r in results if not r["passed"]]
        assert len(failed) >= 5

    def test_verify_iec62304_with_data(self):
        """Project with some data — partial compliance."""
        data = {
            "development_plan": True,
            "requirements": [
                {"id": "R1", "acceptance_criteria": ["AC1"], "verification_method": "test"},
            ],
            "architecture": True,
            "tests": [{"level": "integration"}],
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
        assert len(passed) >= 7  # most checks pass with full data

    def test_verify_iso26262(self):
        results = self.verifier.verify_iso26262({
            "hazard_analysis": True,
            "requirements": [{"type": "safety"}],
            "asil_classification": "ASIL-B",
            "change_requests": [{"id": "CR-1"}],
        })
        passed = [r for r in results if r["passed"]]
        assert len(passed) == 4  # all pass

    def test_verify_do178c(self):
        results = self.verifier.verify_do178c({
            "development_plan": True,
            "requirements": [{"id": "R1"}],
            "tests": [{"id": "T1"}],
        })
        assert len(results) == 4
        # MC/DC should fail (not provided)
        mcdc = next(r for r in results if "MC/DC" in r["description"])
        assert not mcdc["passed"]

    def test_verify_en50128(self):
        results = self.verifier.verify_en50128({
            "requirements": [{"id": "R1"}],
            "architecture": True,
            "sil_level": "SIL 2",
            "tests": [{"id": "T1"}],
        })
        passed = [r for r in results if r["passed"]]
        assert len(passed) == 3

    def test_verify_21cfr_part11(self):
        results = self.verifier.verify_21cfr_part11({
            "system_validated": True,
            "audit_trail_active": True,
            "audit_integrity_verified": True,
            "access_controls": True,
        })
        passed = [r for r in results if r["passed"]]
        assert len(passed) == 4

    def test_verify_all_defaults(self):
        """verify_all with no standards runs all verifiers."""
        result = self.verifier.verify_all({})
        assert "iec62304" in result["per_standard"]
        assert "iso26262" in result["per_standard"]
        assert "do178c" in result["per_standard"]
        assert "en50128" in result["per_standard"]
        assert "21cfr_part11" in result["per_standard"]
        assert result["total_checks"] > 0
        assert result["compliance_pct"] >= 0

    def test_verify_all_specific_standards(self):
        result = self.verifier.verify_all({}, standards=["iec62304"])
        assert list(result["per_standard"].keys()) == ["iec62304"]

    def test_verification_result_structure(self):
        results = self.verifier.verify_iec62304({"requirements": []})
        for r in results:
            assert "check_id" in r
            assert "standard" in r
            assert "clause" in r
            assert "passed" in r
            assert "severity" in r
            assert "remediation" in r
