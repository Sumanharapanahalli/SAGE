"""
Performance Qualification (PQ) Tests
======================================
Verifies that SAGE performs correctly under realistic workload
conditions representative of actual use in a medical device context.

PQ confirms: "Does the system perform reliably in practice?"
"""

import time
import pytest


class TestTraceabilityPerformance:
    """PQ-001: Traceability matrix handles realistic data volumes."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        from src.core.traceability import TraceabilityMatrix, TraceLevel
        self.tm = TraceabilityMatrix(db_path=str(tmp_path / "pq_trace.db"))
        self.TraceLevel = TraceLevel

    def test_bulk_item_creation(self):
        """Create 200 trace items in under 5 seconds."""
        start = time.monotonic()
        for i in range(200):
            self.tm.add_item(
                level=self.TraceLevel.SOFTWARE_REQ,
                title=f"Requirement PQ-{i:04d}",
                description=f"Performance test requirement {i}",
            )
        elapsed = time.monotonic() - start
        assert elapsed < 5.0, f"200 items took {elapsed:.1f}s (limit: 5s)"

        items = self.tm.list_items(level=self.TraceLevel.SOFTWARE_REQ)
        assert len(items) == 200

    def test_bulk_link_creation(self):
        """Create 100 trace links in under 3 seconds."""
        reqs = [self.tm.add_item(level=self.TraceLevel.SOFTWARE_REQ, title=f"R-{i}") for i in range(100)]
        tests = [self.tm.add_item(level=self.TraceLevel.UNIT_TEST, title=f"T-{i}") for i in range(100)]

        start = time.monotonic()
        for r, t in zip(reqs, tests):
            self.tm.add_link(r.id, t.id, link_type="verifies")
        elapsed = time.monotonic() - start
        assert elapsed < 3.0, f"100 links took {elapsed:.1f}s (limit: 3s)"

    def test_coverage_report_with_large_dataset(self):
        """Coverage report completes in under 2 seconds for 200 items."""
        for i in range(100):
            r = self.tm.add_item(level=self.TraceLevel.SYSTEM_REQ, title=f"R-{i}")
            t = self.tm.add_item(level=self.TraceLevel.UNIT_TEST, title=f"T-{i}")
            if i % 2 == 0:  # 50% linked
                self.tm.add_link(r.id, t.id)

        start = time.monotonic()
        report = self.tm.coverage_report()
        elapsed = time.monotonic() - start
        assert elapsed < 2.0, f"Coverage report took {elapsed:.1f}s (limit: 2s)"
        assert report["total_items"] == 200

    def test_gap_analysis_with_large_dataset(self):
        """Gap analysis completes in under 2 seconds for 100 requirements."""
        for i in range(100):
            self.tm.add_item(level=self.TraceLevel.SOFTWARE_REQ, title=f"R-{i}")

        start = time.monotonic()
        gaps = self.tm.gap_analysis()
        elapsed = time.monotonic() - start
        assert elapsed < 2.0, f"Gap analysis took {elapsed:.1f}s (limit: 2s)"
        assert gaps["requirements_count"] == 100


class TestAuditIntegrityPerformance:
    """PQ-002: Audit integrity chain handles high-volume logging."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        from src.core.audit_integrity import AuditIntegrityManager
        self.mgr = AuditIntegrityManager(db_path=str(tmp_path / "pq_audit.db"))

    def test_chain_append_throughput(self):
        """Append 500 entries in under 10 seconds."""
        start = time.monotonic()
        for i in range(500):
            self.mgr.append_entry(f"PQ-EVT-{i:04d}", {
                "action": "test_operation",
                "actor": "pq_test",
                "detail": f"Performance test entry {i}",
            })
        elapsed = time.monotonic() - start
        assert elapsed < 10.0, f"500 entries took {elapsed:.1f}s (limit: 10s)"

    def test_chain_verification_throughput(self):
        """Verify chain of 500 entries in under 5 seconds."""
        for i in range(500):
            self.mgr.append_entry(f"PQ-EVT-{i:04d}", {"seq": i})

        start = time.monotonic()
        result = self.mgr.verify_chain()
        elapsed = time.monotonic() - start
        assert result["valid"] is True
        assert result["verified_entries"] == 500
        assert elapsed < 5.0, f"Verification of 500 entries took {elapsed:.1f}s (limit: 5s)"


class TestChangeControlPerformance:
    """PQ-003: Change control handles concurrent request volume."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        from src.core.change_control import ChangeControlManager
        self.ccm = ChangeControlManager(db_path=str(tmp_path / "pq_change.db"))

    def test_bulk_request_creation(self):
        """Create 100 change requests in under 5 seconds."""
        start = time.monotonic()
        for i in range(100):
            self.ccm.create_request(
                title=f"PQ Change {i}",
                description=f"Performance test change request {i}",
                category="corrective",
                priority="medium",
                requester="pq_test",
            )
        elapsed = time.monotonic() - start
        assert elapsed < 5.0, f"100 CRs took {elapsed:.1f}s (limit: 5s)"

        all_reqs = self.ccm.list_requests()
        assert len(all_reqs) == 100

    def test_metrics_with_large_dataset(self):
        """Metrics calculation for 100 CRs in under 1 second."""
        for i in range(100):
            self.ccm.create_request(f"CR-{i}", f"Desc {i}", "corrective", "high", "test")

        start = time.monotonic()
        metrics = self.ccm.get_metrics()
        elapsed = time.monotonic() - start
        assert metrics["total_requests"] == 100
        assert elapsed < 1.0, f"Metrics took {elapsed:.1f}s (limit: 1s)"


class TestDocumentGenerationPerformance:
    """PQ-004: Document generation handles large requirement sets."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from src.core.doc_generator import DocumentGenerator
        self.gen = DocumentGenerator(project_name="medtech_pq", version="1.0")

    def test_srs_with_500_requirements(self):
        """Generate SRS with 500 requirements in under 2 seconds."""
        reqs = [
            {"id": f"REQ-{i:04d}", "type": "functional", "title": f"Requirement {i}",
             "description": f"Description for requirement {i}",
             "acceptance_criteria": [f"AC-{i}-1", f"AC-{i}-2"],
             "priority": "high", "verification_method": "test", "status": "approved"}
            for i in range(500)
        ]
        start = time.monotonic()
        doc = self.gen.generate_srs(reqs)
        elapsed = time.monotonic() - start
        assert elapsed < 2.0, f"SRS generation took {elapsed:.1f}s (limit: 2s)"
        assert "REQ-0000" in doc
        assert "REQ-0499" in doc

    def test_rtm_with_1000_items(self):
        """Generate RTM with 1000 items in under 3 seconds."""
        data = [
            {"id": f"ITEM-{i:04d}", "level": "software_requirement", "title": f"Item {i}",
             "status": "active",
             "traces_to": [{"target_id": f"ITEM-{i+500:04d}"}] if i < 500 else [],
             "traced_from": [{"source_id": f"ITEM-{i-500:04d}"}] if i >= 500 else []}
            for i in range(1000)
        ]
        start = time.monotonic()
        doc = self.gen.generate_rtm(data)
        elapsed = time.monotonic() - start
        assert elapsed < 3.0, f"RTM generation took {elapsed:.1f}s (limit: 3s)"
        assert "ITEM-0000" in doc
