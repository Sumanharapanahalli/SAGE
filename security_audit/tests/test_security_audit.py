"""Security audit tests — validates that the remediation code blocks each attack.

Runs against the secure_app (port 5002) in-process using Flask test client.
Does NOT require a live network connection.
"""
import json
import os
import sys
import unittest

# ---------------------------------------------------------------------------
# Load secure_app module from remediation directory
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "remediation"))
sys.path.insert(0, os.path.join(_REPO_ROOT, "audit"))

# Ensure markupsafe is importable (may not be installed in all envs)
try:
    from markupsafe import escape as _escape  # noqa: F401
    _HAS_MARKUPSAFE = True
except ImportError:
    _HAS_MARKUPSAFE = False

try:
    from secure_app import app, init_db
    _HAS_SECURE_APP = True
    _IMPORT_ERR = None
except ImportError as _imp_err:
    _HAS_SECURE_APP = False
    _IMPORT_ERR = _imp_err


@unittest.skipUnless(_HAS_SECURE_APP, "secure_app not importable (missing deps)")
class TestSQLInjectionFix(unittest.TestCase):
    """FIX 1: SQL injection bypass must be blocked."""

    def setUp(self):
        app.config["TESTING"] = True
        app.config["SECRET_KEY"] = "test-secret-key"
        self.client = app.test_client()
        init_db()

    def test_sqli_bypass_rejected(self):
        """Classic ' OR '1'='1 should not log in."""
        resp = self.client.post("/login", data={
            "username": "' OR '1'='1",
            "password": "' OR '1'='1",
        })
        self.assertEqual(resp.status_code, 401)
        body = json.loads(resp.data)
        self.assertEqual(body["status"], "fail")

    def test_sqli_union_rejected(self):
        """UNION-based injection should not log in."""
        resp = self.client.post("/login", data={
            "username": "admin' UNION SELECT 1,'admin','admin','x'--",
            "password": "anything",
        })
        self.assertIn(resp.status_code, (400, 401))

    def test_legitimate_login_works(self):
        """Valid credentials must still work after the fix."""
        resp = self.client.post("/login", data={
            "username": "admin",
            "password": "admin-strong-passphrase-2024!",
        })
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.data)
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["username"], "admin")


@unittest.skipUnless(_HAS_SECURE_APP, "secure_app not importable")
class TestXSSFix(unittest.TestCase):
    """FIX 2: XSS payloads must be neutralised."""

    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_script_tag_not_reflected(self):
        payload = "<script>alert('XSS')</script>"
        resp = self.client.get(f"/search?q={payload}")
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.data)
        # The raw script tag must NOT appear in any value
        response_text = json.dumps(body)
        self.assertNotIn("<script>", response_text)

    def test_img_onerror_not_reflected(self):
        payload = '<img src=x onerror=alert(1)>'
        resp = self.client.get(f"/search?q={payload}")
        body = json.loads(resp.data)
        response_text = json.dumps(body)
        self.assertNotIn("<img", response_text)

    def test_benign_query_returned(self):
        resp = self.client.get("/search?q=hello+world")
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.data)
        self.assertIn("hello", body["query"])


@unittest.skipUnless(_HAS_SECURE_APP, "secure_app not importable")
class TestBrokenAuthFix(unittest.TestCase):
    """FIX 3: X-User-Role header must be ignored."""

    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_header_injection_blocked(self):
        """Sending X-User-Role: admin without a valid session must be forbidden."""
        resp = self.client.get("/admin", headers={"X-User-Role": "admin"})
        self.assertEqual(resp.status_code, 403)

    def test_unauthenticated_admin_blocked(self):
        resp = self.client.get("/admin")
        self.assertEqual(resp.status_code, 403)

    def test_admin_session_grants_access(self):
        """A properly authenticated admin session must work."""
        init_db()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "admin"
            sess["role"] = "admin"
        resp = self.client.get("/admin")
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.data)
        self.assertIn("users", body)


@unittest.skipUnless(_HAS_SECURE_APP, "secure_app not importable")
class TestIDORFix(unittest.TestCase):
    """FIX 4: Users must not access documents they don't own."""

    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        init_db()

    def test_idor_blocked_for_non_owner(self):
        """Alice (user_id=2) must not access doc 1 (owned by admin, id=1)."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = 2
            sess["username"] = "alice"
            sess["role"] = "user"
        resp = self.client.get("/document/1")
        # Must be 404 (not 403, to avoid object enumeration)
        self.assertEqual(resp.status_code, 404)

    def test_owner_can_access_own_doc(self):
        """Alice can access her own document (doc 2)."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = 2
            sess["username"] = "alice"
            sess["role"] = "user"
        resp = self.client.get("/document/2")
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.data)
        self.assertEqual(body["title"], "Alice's Note")

    def test_admin_can_access_all_docs(self):
        """Admin may read any document."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "admin"
            sess["role"] = "admin"
        resp = self.client.get("/document/2")
        self.assertEqual(resp.status_code, 200)


@unittest.skipUnless(_HAS_SECURE_APP, "secure_app not importable")
class TestSSRFFix(unittest.TestCase):
    """FIX 5: SSRF — private IPs and non-https schemes must be blocked."""

    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "admin"
            sess["role"] = "admin"

    def test_http_scheme_blocked(self):
        resp = self.client.get("/fetch?url=http://169.254.169.254/latest/meta-data/")
        self.assertEqual(resp.status_code, 400)
        body = json.loads(resp.data)
        self.assertIn("https", body["error"])

    def test_file_scheme_blocked(self):
        resp = self.client.get("/fetch?url=file:///etc/passwd")
        self.assertEqual(resp.status_code, 400)

    def test_localhost_blocked(self):
        """Even with https scheme, localhost must be blocked by IP check."""
        resp = self.client.get("/fetch?url=https://localhost/admin")
        self.assertIn(resp.status_code, (400, 500))


@unittest.skipUnless(_HAS_SECURE_APP, "secure_app not importable")
class TestCommandInjectionFix(unittest.TestCase):
    """FIX 6: Shell metacharacters must be rejected."""

    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_semicolon_injection_blocked(self):
        resp = self.client.get("/ping?host=8.8.8.8;echo INJECTED")
        self.assertEqual(resp.status_code, 400)
        body = json.loads(resp.data)
        self.assertIn("invalid host", body["error"])

    def test_pipe_injection_blocked(self):
        resp = self.client.get("/ping?host=8.8.8.8|cat /etc/passwd")
        self.assertEqual(resp.status_code, 400)

    def test_backtick_injection_blocked(self):
        resp = self.client.get("/ping?host=`whoami`")
        self.assertEqual(resp.status_code, 400)

    def test_valid_hostname_allowed(self):
        """Ping with a valid hostname format must not be rejected by validation."""
        resp = self.client.get("/ping?host=example.com")
        # May fail at network level (no real ping in test), but input validation passes
        self.assertNotEqual(resp.status_code, 400)

    def test_valid_ipv4_allowed(self):
        resp = self.client.get("/ping?host=8.8.8.8")
        self.assertNotEqual(resp.status_code, 400)


class TestAuditReportStructure(unittest.TestCase):
    """Validates the audit report meets all acceptance criteria (offline)."""

    def test_minimum_five_findings(self):
        """Report must contain at least 5 findings."""
        try:
            from owasp_audit import OWASPAuditor
            auditor = OWASPAuditor(base_url="http://127.0.0.1:9999")  # offline
            report = auditor.run_full_audit()
            self.assertGreaterEqual(report["total_findings"], 5)
        except ImportError:
            self.skipTest("owasp_audit not importable")

    def test_all_severities_assigned(self):
        """Every finding must have a valid severity."""
        try:
            from owasp_audit import OWASPAuditor
            auditor = OWASPAuditor(base_url="http://127.0.0.1:9999")
            report = auditor.run_full_audit()
            valid_severities = {"Critical", "High", "Medium", "Low"}
            for finding in report["findings"]:
                self.assertIn(finding["severity"], valid_severities,
                              f"{finding['vuln_id']} has invalid severity")
        except ImportError:
            self.skipTest("owasp_audit not importable")

    def test_all_findings_have_poc_and_remediation(self):
        """Every finding must have poc_payload and remediation_summary."""
        try:
            from owasp_audit import OWASPAuditor
            auditor = OWASPAuditor(base_url="http://127.0.0.1:9999")
            report = auditor.run_full_audit()
            for finding in report["findings"]:
                self.assertTrue(finding["poc_payload"], f"{finding['vuln_id']} missing PoC")
                self.assertTrue(finding["remediation_summary"],
                                f"{finding['vuln_id']} missing remediation")
        except ImportError:
            self.skipTest("owasp_audit not importable")

    def test_critical_findings_present(self):
        """Must have at least one Critical severity finding."""
        try:
            from owasp_audit import OWASPAuditor
            auditor = OWASPAuditor(base_url="http://127.0.0.1:9999")
            report = auditor.run_full_audit()
            critical_count = report["severity_summary"].get("Critical", 0)
            self.assertGreater(critical_count, 0, "No Critical findings found")
        except ImportError:
            self.skipTest("owasp_audit not importable")

    def test_cvss_scores_in_range(self):
        """All CVSS scores must be between 0.0 and 10.0."""
        try:
            from owasp_audit import OWASPAuditor
            auditor = OWASPAuditor(base_url="http://127.0.0.1:9999")
            report = auditor.run_full_audit()
            for finding in report["findings"]:
                score = finding["cvss_score"]
                self.assertGreaterEqual(score, 0.0)
                self.assertLessEqual(score, 10.0)
        except ImportError:
            self.skipTest("owasp_audit not importable")


if __name__ == "__main__":
    unittest.main(verbosity=2)
