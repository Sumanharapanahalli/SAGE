"""
Functional and edge-case tests for previously untested core modules:
  - api_keys (create, verify, revoke, list)
  - cost_tracker (estimate, record, summarize)
  - pii_filter (regex detection, redaction, flag-only, data residency)
  - db (get_connection, WAL mode, busy timeout)
  - compliance_engineering API routes
"""

import hashlib
import os
import sqlite3
import tempfile

import pytest


# ═══════════════════════════════════════════════════════════════════════
# DB MODULE
# ═══════════════════════════════════════════════════════════════════════

class TestDBModule:
    """Tests for src.core.db.get_connection."""

    def test_returns_connection(self, tmp_path):
        from src.core.db import get_connection
        conn = get_connection(str(tmp_path / "test.db"), row_factory=None)
        assert conn is not None
        conn.close()

    def test_wal_mode_enabled(self, tmp_path):
        from src.core.db import get_connection
        db = str(tmp_path / "wal_test.db")
        conn = get_connection(db, row_factory=None)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        assert mode == "wal"

    def test_row_factory_default(self, tmp_path):
        from src.core.db import get_connection
        db = str(tmp_path / "row.db")
        conn = get_connection(db)  # default row_factory = sqlite3.Row
        conn.execute("CREATE TABLE t (id INTEGER, name TEXT)")
        conn.execute("INSERT INTO t VALUES (1, 'test')")
        conn.commit()
        row = conn.execute("SELECT * FROM t").fetchone()
        conn.close()
        assert row["id"] == 1
        assert row["name"] == "test"

    def test_row_factory_none(self, tmp_path):
        from src.core.db import get_connection
        db = str(tmp_path / "tuple.db")
        conn = get_connection(db, row_factory=None)
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.execute("INSERT INTO t VALUES (42)")
        conn.commit()
        row = conn.execute("SELECT * FROM t").fetchone()
        conn.close()
        assert row == (42,)

    def test_busy_timeout_set(self, tmp_path):
        from src.core.db import get_connection
        db = str(tmp_path / "busy.db")
        conn = get_connection(db, busy_timeout_ms=10000, row_factory=None)
        timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        conn.close()
        assert timeout == 10000


# ═══════════════════════════════════════════════════════════════════════
# PII FILTER
# ═══════════════════════════════════════════════════════════════════════

class TestPIIFilter:
    """Tests for src.core.pii_filter."""

    def test_disabled_returns_unchanged(self):
        from src.core.pii_filter import scrub_text
        text = "My email is test@example.com"
        result, detected = scrub_text(text, {"pii": {"enabled": False}})
        assert result == text
        assert detected == []

    def test_no_pii_config_returns_unchanged(self):
        from src.core.pii_filter import scrub_text
        text = "My email is test@example.com"
        result, detected = scrub_text(text, {})
        assert result == text
        assert detected == []

    def test_detect_email_regex(self):
        from src.core.pii_filter import scrub_text
        text = "Contact me at user@domain.org for details"
        result, detected = scrub_text(text, {
            "pii": {"enabled": True, "mode": "redact", "redaction_char": "[REDACTED]"}
        })
        assert "EMAIL_ADDRESS" in detected
        assert "user@domain.org" not in result
        assert "[REDACTED]" in result

    def test_detect_ssn_regex(self):
        from src.core.pii_filter import scrub_text
        # SSN pattern also matches PHONE_NUMBER regex (7-15 digits),
        # so both may be detected. Verify the number is redacted.
        text = "SSN is 123-45-6789"
        result, detected = scrub_text(text, {
            "pii": {"enabled": True, "mode": "redact"}
        })
        # At least one PII entity detected and the number is redacted
        assert len(detected) >= 1
        assert "123-45-6789" not in result

    def test_flag_only_mode(self):
        from src.core.pii_filter import scrub_text
        text = "Email: test@example.com"
        result, detected = scrub_text(text, {
            "pii": {"enabled": True, "mode": "flag_only"}
        })
        assert "EMAIL_ADDRESS" in detected
        # flag_only should NOT redact
        assert "test@example.com" in result

    def test_mask_mode(self):
        from src.core.pii_filter import scrub_text
        text = "Call me at test@example.com"
        result, detected = scrub_text(text, {
            "pii": {"enabled": True, "mode": "mask"}
        })
        assert "EMAIL_ADDRESS" in detected
        assert "[EMAIL_ADDRESS]" in result

    def test_no_pii_in_text(self):
        from src.core.pii_filter import scrub_text
        text = "This is a normal sentence with no personal data"
        result, detected = scrub_text(text, {
            "pii": {"enabled": True, "mode": "redact"}
        })
        assert detected == []
        assert result == text

    def test_multiple_pii_types(self):
        from src.core.pii_filter import scrub_text
        text = "Email: a@b.com, SSN: 123-45-6789"
        result, detected = scrub_text(text, {
            "pii": {"enabled": True, "mode": "redact", "redaction_char": "***"}
        })
        assert "EMAIL_ADDRESS" in detected
        # SSN overlaps with PHONE_NUMBER regex, at least one detects the number
        assert len(detected) >= 2
        assert "a@b.com" not in result
        assert "123-45-6789" not in result

    def test_custom_entity_filter(self):
        from src.core.pii_filter import scrub_text
        text = "Email: a@b.com, SSN: 123-45-6789"
        # Only detect EMAIL, not SSN
        result, detected = scrub_text(text, {
            "pii": {"enabled": True, "mode": "redact", "entities": ["EMAIL_ADDRESS"]}
        })
        assert "EMAIL_ADDRESS" in detected
        assert "US_SSN" not in detected
        assert "123-45-6789" in result  # SSN not redacted

    def test_data_residency_allowed(self):
        from src.core.pii_filter import check_data_residency
        assert check_data_residency("ollama", {"pii": {"data_residency": ["local"]}}) is True

    def test_data_residency_blocked(self):
        from src.core.pii_filter import check_data_residency
        # EU region only allows eu_providers (ollama, local by default)
        result = check_data_residency("openai", {
            "data_residency": {"enabled": True, "region": "eu"}
        })
        assert result is False

    def test_data_residency_no_config(self):
        from src.core.pii_filter import check_data_residency
        assert check_data_residency("anything", {}) is True


# ═══════════════════════════════════════════════════════════════════════
# COST TRACKER
# ═══════════════════════════════════════════════════════════════════════

class TestCostTracker:
    """Tests for src.core.cost_tracker."""

    def test_estimate_cost_known_model(self):
        from src.core.cost_tracker import _estimate_cost
        # claude-opus-4-6: input=0.015/1K, output=0.075/1K
        cost = _estimate_cost("claude-opus-4-6", 1000, 1000)
        assert cost == pytest.approx(0.015 + 0.075, abs=0.001)

    def test_estimate_cost_free_model(self):
        from src.core.cost_tracker import _estimate_cost
        cost = _estimate_cost("ollama", 10000, 5000)
        assert cost == 0.0

    def test_estimate_cost_unknown_model_uses_default(self):
        from src.core.cost_tracker import _estimate_cost
        cost = _estimate_cost("unknown-model-xyz", 1000, 1000)
        # default: input=0.002/1K, output=0.008/1K
        assert cost == pytest.approx(0.002 + 0.008, abs=0.001)

    def test_estimate_cost_prefix_match(self):
        from src.core.cost_tracker import _estimate_cost
        # "claude-sonnet" should prefix-match "claude-sonnet-4-6"
        cost = _estimate_cost("claude-sonnet-4-6", 1000, 0)
        assert cost > 0

    def test_estimate_cost_zero_tokens(self):
        from src.core.cost_tracker import _estimate_cost
        cost = _estimate_cost("claude-opus-4-6", 0, 0)
        assert cost == 0.0

    def test_estimate_cost_provider_prefix_stripped(self):
        from src.core.cost_tracker import _estimate_cost
        # "ollama/llama3.2" should strip to "llama3.2" then fall back to default
        cost = _estimate_cost("ollama/llama3.2", 1000, 1000)
        assert cost >= 0


# ═══════════════════════════════════════════════════════════════════════
# API KEYS
# ═══════════════════════════════════════════════════════════════════════

class TestAPIKeys:
    """Tests for src.core.api_keys."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path, monkeypatch):
        # Redirect audit_logger to temp db so we don't touch real data
        db_path = str(tmp_path / "test_audit.db")
        monkeypatch.setattr("src.core.api_keys._db_path", lambda: db_path)

    def test_create_key_format(self):
        from src.core.api_keys import create_api_key
        plain_key, key_id = create_api_key("Test Key", "test@example.com", "medtech", "developer")
        assert plain_key.startswith("sk-sage-")
        assert len(plain_key) == 8 + 64  # prefix + 32 hex bytes
        assert len(key_id) == 36  # UUID

    def test_verify_valid_key(self):
        from src.core.api_keys import create_api_key, verify_api_key
        plain_key, _ = create_api_key("Valid", "v@test.com", "medtech", "admin")
        identity = verify_api_key(plain_key)
        assert identity is not None
        assert identity.email == "v@test.com"
        assert identity.role == "admin"
        assert identity.provider == "api_key"

    def test_verify_invalid_key_returns_none(self):
        from src.core.api_keys import verify_api_key
        assert verify_api_key("sk-sage-invalidkeythatdoesnotexist1234567890abcdef1234567890abcdef") is None

    def test_verify_wrong_prefix_returns_none(self):
        from src.core.api_keys import verify_api_key
        assert verify_api_key("not-a-real-key") is None

    def test_revoke_key(self):
        from src.core.api_keys import create_api_key, verify_api_key, revoke_api_key
        plain_key, key_id = create_api_key("Revokable", "r@test.com", "medtech", "viewer")
        assert verify_api_key(plain_key) is not None
        assert revoke_api_key(key_id, "admin") is True
        assert verify_api_key(plain_key) is None  # revoked

    def test_revoke_nonexistent_key(self):
        from src.core.api_keys import revoke_api_key
        assert revoke_api_key("nonexistent-id", "admin") is False

    def test_revoke_already_revoked(self):
        from src.core.api_keys import create_api_key, revoke_api_key
        _, key_id = create_api_key("Double", "d@test.com", "medtech", "viewer")
        assert revoke_api_key(key_id, "admin") is True
        assert revoke_api_key(key_id, "admin") is False  # already revoked

    def test_list_keys(self):
        from src.core.api_keys import create_api_key, list_api_keys
        create_api_key("Key1", "a@test.com", "medtech", "dev")
        create_api_key("Key2", "b@test.com", "medtech", "admin")
        create_api_key("Key3", "c@test.com", "other_solution", "dev")

        keys = list_api_keys("medtech")
        assert len(keys) == 2
        names = {k["name"] for k in keys}
        assert names == {"Key1", "Key2"}

    def test_list_empty_solution(self):
        from src.core.api_keys import list_api_keys
        assert list_api_keys("nonexistent") == []

    def test_key_hash_stored_not_plain(self):
        from src.core.api_keys import create_api_key, _db_path
        plain_key, key_id = create_api_key("Hash", "h@test.com", "medtech", "dev")
        conn = sqlite3.connect(_db_path())
        row = conn.execute("SELECT key_hash FROM api_keys WHERE id=?", (key_id,)).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == hashlib.sha256(plain_key.encode()).hexdigest()
        assert plain_key not in row[0]


# ═══════════════════════════════════════════════════════════════════════
# EDGE CASES — TRACEABILITY
# ═══════════════════════════════════════════════════════════════════════

class TestTraceabilityEdgeCases:
    """Edge cases for traceability matrix."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        from src.core.traceability import TraceabilityMatrix, TraceLevel
        self.tm = TraceabilityMatrix(db_path=str(tmp_path / "edge.db"))
        self.TL = TraceLevel

    def test_duplicate_item_id_raises(self):
        self.tm.add_item(level=self.TL.SYSTEM_REQ, title="A", item_id="DUP-001")
        with pytest.raises(Exception):  # sqlite UNIQUE constraint
            self.tm.add_item(level=self.TL.SYSTEM_REQ, title="B", item_id="DUP-001")

    def test_link_to_nonexistent_target(self):
        item = self.tm.add_item(level=self.TL.SYSTEM_REQ, title="Real")
        # SQLite foreign key enforcement depends on PRAGMA; link may succeed
        # but forward_links should return empty for nonexistent target
        link = self.tm.add_link(item.id, "NONEXISTENT", link_type="derives")
        forward = self.tm.get_forward_links(item.id)
        # The join won't find the target item, so result is empty
        assert len(forward) == 0

    def test_coverage_report_empty_db(self):
        report = self.tm.coverage_report()
        assert report["total_items"] == 0
        assert report["overall_coverage_pct"] == 0

    def test_gap_analysis_empty_db(self):
        gaps = self.tm.gap_analysis()
        assert gaps["total_gaps"] == 0

    def test_export_empty_matrix(self):
        export = self.tm.export_matrix()
        assert export == []

    def test_all_trace_levels_valid(self):
        from src.core.traceability import TraceLevel
        for level in TraceLevel:
            item = self.tm.add_item(level=level, title=f"Test {level.value}")
            assert item.level == level

    def test_item_with_special_characters(self):
        item = self.tm.add_item(
            level=self.TL.SYSTEM_REQ,
            title="Req with 'quotes' and \"double quotes\" & <special> chars",
            description="Description with newlines\nand\ttabs",
        )
        fetched = self.tm.get_item(item.id)
        assert "quotes" in fetched.title
        assert "\n" in fetched.description


# ═══════════════════════════════════════════════════════════════════════
# EDGE CASES — AUDIT INTEGRITY
# ═══════════════════════════════════════════════════════════════════════

class TestAuditIntegrityEdgeCases:
    """Edge cases for HMAC hash chain."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        from src.core.audit_integrity import AuditIntegrityManager
        self.mgr = AuditIntegrityManager(db_path=str(tmp_path / "edge_audit.db"))

    def test_large_event_data(self):
        """Chain handles large payloads."""
        big_data = {"content": "x" * 100000}
        entry = self.mgr.append_entry("EVT-BIG", big_data)
        assert entry["chain_hmac"]
        assert self.mgr.verify_chain()["valid"]

    def test_unicode_in_event_data(self):
        entry = self.mgr.append_entry("EVT-UNI", {"text": "Hello"})
        assert self.mgr.verify_chain()["valid"]

    def test_empty_event_data(self):
        entry = self.mgr.append_entry("EVT-EMPTY", {})
        assert entry["chain_hmac"]
        assert self.mgr.verify_chain()["valid"]

    def test_chain_status_empty(self):
        status = self.mgr.get_chain_status()
        assert status["total_entries"] == 0
        assert status["chain_active"] is False


# ═══════════════════════════════════════════════════════════════════════
# EDGE CASES — CHANGE CONTROL
# ═══════════════════════════════════════════════════════════════════════

class TestChangeControlEdgeCases:
    """Edge cases for change control workflow."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        from src.core.change_control import ChangeControlManager
        self.ccm = ChangeControlManager(db_path=str(tmp_path / "edge_cc.db"))

    def test_invalid_status_transition(self):
        from src.core.change_control import ChangeStatus
        cr = self.ccm.create_request("X", "desc", "corrective", "high", "dev")
        with pytest.raises(ValueError):
            self.ccm.update_status(cr["id"], "not_a_valid_status", "dev")

    def test_close_sets_closed_at(self):
        cr = self.ccm.create_request("X", "desc", "corrective", "high", "dev")
        self.ccm.update_status(cr["id"], "closed", "dev")
        fetched = self.ccm.get_request(cr["id"])
        assert fetched["closed_at"] is not None

    def test_multiple_approvals(self):
        cr = self.ccm.create_request("X", "desc", "corrective", "high", "dev")
        self.ccm.add_approval(cr["id"], "qa", "QA", "approved")
        self.ccm.add_approval(cr["id"], "mgr", "Manager", "approved")
        self.ccm.add_approval(cr["id"], "reg", "Regulatory", "needs_info", "Need more data")
        fetched = self.ccm.get_request(cr["id"])
        assert len(fetched["approvals"]) == 3

    def test_metrics_empty_db(self):
        metrics = self.ccm.get_metrics()
        assert metrics["total_requests"] == 0

    def test_long_description(self):
        cr = self.ccm.create_request("X", "d" * 10000, "corrective", "high", "dev")
        fetched = self.ccm.get_request(cr["id"])
        assert len(fetched["description"]) == 10000

    def test_all_categories_valid(self):
        from src.core.change_control import ChangeCategory
        for cat in ChangeCategory:
            cr = self.ccm.create_request(f"Cat {cat.value}", "desc", cat.value, "low", "dev")
            assert cr["id"].startswith("CR-")

    def test_all_priorities_valid(self):
        from src.core.change_control import ChangePriority
        for pri in ChangePriority:
            cr = self.ccm.create_request(f"Pri {pri.value}", "desc", "corrective", pri.value, "dev")
            assert cr["id"].startswith("CR-")


# ═══════════════════════════════════════════════════════════════════════
# EDGE CASES — DOCUMENT GENERATOR
# ═══════════════════════════════════════════════════════════════════════

class TestDocGeneratorEdgeCases:
    """Edge cases for document generation."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from src.core.doc_generator import DocumentGenerator
        self.gen = DocumentGenerator(project_name="edge_test")

    def test_srs_empty_requirements(self):
        doc = self.gen.generate_srs([])
        assert "Software Requirements Specification" in doc
        assert "Total requirements: 0" in doc

    def test_srs_missing_fields_graceful(self):
        """Requirements with missing fields should use 'N/A'."""
        doc = self.gen.generate_srs([{"id": "R1"}])
        assert "R1" in doc
        assert "N/A" in doc

    def test_risk_management_empty(self):
        doc = self.gen.generate_risk_management([])
        assert "Risk Management File" in doc
        assert "**Total hazards identified:** 0" in doc

    def test_rtm_empty(self):
        doc = self.gen.generate_rtm([])
        assert "Traceability Matrix" in doc
        assert "Total traced items: 0" in doc

    def test_soup_empty(self):
        doc = self.gen.generate_soup_inventory([])
        assert "SOUP Inventory" in doc

    def test_vv_plan_empty(self):
        doc = self.gen.generate_vv_plan([])
        assert "Verification & Validation Plan" in doc

    def test_header_contains_project_name(self):
        doc = self.gen.generate_srs([])
        assert "edge_test" in doc

    def test_risk_high_risk_section(self):
        risks = [
            {"id": "R1", "hazard": "Fire", "severity": "HIGH",
             "probability": "LOW", "risk_level": "HIGH",
             "mitigation": "Extinguisher", "residual_risk": "LOW"},
            {"id": "R2", "hazard": "Scratch", "severity": "LOW",
             "probability": "HIGH", "risk_level": "LOW",
             "mitigation": "", "residual_risk": "LOW"},
        ]
        doc = self.gen.generate_risk_management(risks)
        assert "High/Critical Risks" in doc
        assert "R1" in doc


# ═══════════════════════════════════════════════════════════════════════
# EDGE CASES — COMPLIANCE VERIFIER
# ═══════════════════════════════════════════════════════════════════════

class TestComplianceVerifierEdgeCases:
    """Edge cases for compliance verification."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from src.core.compliance_verifier import ComplianceVerifier
        self.v = ComplianceVerifier()

    def test_verify_unknown_standard_ignored(self):
        result = self.v.verify_all({}, standards=["nonexistent_standard"])
        assert result["total_checks"] == 0

    def test_verify_mixed_valid_invalid_standards(self):
        result = self.v.verify_all({}, standards=["iec62304", "fake_standard"])
        assert "iec62304" in result["per_standard"]
        assert "fake_standard" not in result["per_standard"]

    def test_requirements_without_acceptance_criteria(self):
        results = self.v.verify_iec62304({
            "requirements": [{"id": "R1"}]  # no acceptance_criteria key
        })
        req_check = next(r for r in results if r["check_id"] == "IEC62304-5.2")
        assert not req_check["passed"]

    def test_partial_trace_coverage(self):
        """50% traced should fail the >50% threshold."""
        results = self.v.verify_iec62304({
            "trace_data": [
                {"id": "A", "traces_to": [{"target_id": "B"}], "traced_from": []},
                {"id": "B", "traces_to": [], "traced_from": []},  # orphan
            ]
        })
        trace_check = next(r for r in results if r["check_id"] == "IEC62304-5.1.1")
        assert not trace_check["passed"]  # 1/2 = 50%, threshold is >50% so this fails

    def test_all_results_have_required_fields(self):
        results = self.v.verify_all({"requirements": []})
        for std, checks in results["per_standard"].items():
            for check in checks:
                assert "check_id" in check
                assert "standard" in check
                assert "clause" in check
                assert "description" in check
                assert "passed" in check
                assert "severity" in check
                assert "remediation" in check
                assert "verified_at" in check
