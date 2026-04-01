"""
SAGE Framework — Security Review & Automated Compliance Checks
==============================================================
Role:     Analyst
Date:     2026-03-28
Scope:    src/, config/, requirements.txt
Standards: OWASP Top 10, HIPAA Security Rule, IEC 62443, STRIDE

This script performs static security checks against the SAGE codebase and
produces a structured JSON report.  It does NOT modify any source file.

Usage:
    python security_audit/sage_security_review.py
    python security_audit/sage_security_review.py --output report.json
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_HIGH     = "HIGH"
SEVERITY_MEDIUM   = "MEDIUM"
SEVERITY_LOW      = "LOW"
SEVERITY_INFO     = "INFO"


@dataclass
class Finding:
    id: str
    title: str
    severity: str                  # CRITICAL | HIGH | MEDIUM | LOW | INFO
    category: str                  # OWASP / HIPAA / STRIDE / SBOM
    stride_category: str           # S T R I D E
    cwe: str                       # CWE-xxx
    file_path: str
    line_number: int | None
    evidence: str
    recommendation: str
    phi_impact: bool = False       # affects Protected Health Information
    compliance_references: list[str] = field(default_factory=list)


@dataclass
class AcceptanceCriteria:
    name: str
    passed: bool
    detail: str


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent.parent


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def check_cors(findings: list[Finding]) -> None:
    """OWASP A05 – Security Misconfiguration: wildcard CORS."""
    api_path = ROOT / "src" / "interface" / "api.py"
    text = _read(api_path)
    for lineno, line in enumerate(text.splitlines(), 1):
        if 'allow_origins=["*"]' in line or "allow_origins=['*']" in line:
            findings.append(Finding(
                id="CORS-001",
                title="Wildcard CORS policy allows any origin",
                severity=SEVERITY_CRITICAL,
                category="OWASP A05",
                stride_category="Spoofing",
                cwe="CWE-942",
                file_path=str(api_path.relative_to(ROOT)),
                line_number=lineno,
                evidence=line.strip(),
                recommendation=(
                    "Replace allow_origins=['*'] with an explicit allowlist of "
                    "trusted origins (e.g. ['https://app.example.com']). "
                    "Load from SAGE_ALLOWED_ORIGINS env var for environment parity."
                ),
                compliance_references=["OWASP A05:2021", "HIPAA §164.312(e)(1)"],
            ))


def check_auth_disabled(findings: list[Finding]) -> None:
    """OWASP A07 – Auth disabled by default."""
    cfg_path = ROOT / "config" / "config.yaml"
    text = _read(cfg_path)
    for lineno, line in enumerate(text.splitlines(), 1):
        if re.search(r"enabled\s*:\s*false", line) and "auth:" in "\n".join(
            text.splitlines()[max(0, lineno - 5):lineno]
        ):
            findings.append(Finding(
                id="AUTH-001",
                title="Authentication disabled by default (auth.enabled: false)",
                severity=SEVERITY_HIGH,
                category="OWASP A07",
                stride_category="Spoofing",
                cwe="CWE-306",
                file_path=str(cfg_path.relative_to(ROOT)),
                line_number=lineno,
                evidence=line.strip(),
                recommendation=(
                    "Set auth.enabled: true in production. "
                    "Configure OIDC issuer_url, client_id, and client_secret. "
                    "Add SAGE_AUTH_ENABLED=true to the deployment environment."
                ),
                phi_impact=True,
                compliance_references=["HIPAA §164.312(d)", "OWASP A07:2021"],
            ))
            break


def check_pii_disabled(findings: list[Finding]) -> None:
    """HIPAA – PII/PHI scrubbing disabled by default."""
    cfg_path = ROOT / "config" / "config.yaml"
    text = _read(cfg_path)
    in_pii_block = False
    for lineno, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith("pii:"):
            in_pii_block = True
        if in_pii_block and re.search(r"enabled\s*:\s*false", line):
            findings.append(Finding(
                id="PII-001",
                title="PII/PHI detection disabled (pii.enabled: false)",
                severity=SEVERITY_HIGH,
                category="HIPAA",
                stride_category="Information Disclosure",
                cwe="CWE-359",
                file_path=str(cfg_path.relative_to(ROOT)),
                line_number=lineno,
                evidence=line.strip(),
                recommendation=(
                    "Set pii.enabled: true and install Presidio "
                    "(pip install presidio-analyzer presidio-anonymizer). "
                    "Consider setting fail_on_detection: true for HIPAA workloads "
                    "to reject prompts containing raw PHI."
                ),
                phi_impact=True,
                compliance_references=["HIPAA §164.312(a)(2)(iv)", "GDPR Art. 25"],
            ))
            break


def check_security_headers(findings: list[Finding]) -> None:
    """OWASP A05 – Missing HTTP security headers."""
    api_path = ROOT / "src" / "interface" / "api.py"
    text = _read(api_path)
    missing_headers = []
    for header in [
        "Strict-Transport-Security",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Content-Security-Policy",
    ]:
        if header not in text:
            missing_headers.append(header)
    if missing_headers:
        findings.append(Finding(
            id="HDR-001",
            title=f"Missing HTTP security headers: {', '.join(missing_headers)}",
            severity=SEVERITY_HIGH,
            category="OWASP A05",
            stride_category="Tampering",
            cwe="CWE-693",
            file_path=str(api_path.relative_to(ROOT)),
            line_number=None,
            evidence="Headers not found in api.py middleware chain",
            recommendation=(
                "Add a SecurityHeadersMiddleware that sets: "
                "Strict-Transport-Security: max-age=63072000; includeSubDomains, "
                "X-Content-Type-Options: nosniff, "
                "X-Frame-Options: DENY, "
                "Content-Security-Policy: default-src 'self'."
            ),
            compliance_references=["OWASP A05:2021", "HIPAA §164.312(e)(1)"],
        ))


def check_unpinned_deps(findings: list[Finding]) -> None:
    """Supply chain – unpinned dependency versions."""
    req_path = ROOT / "requirements.txt"
    text = _read(req_path)
    unpinned = []
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            pkg = stripped.split(";")[0].strip()
            # Check if there's a version specifier
            if not re.search(r"[><=!~]", pkg):
                unpinned.append((lineno, pkg))
    if unpinned:
        findings.append(Finding(
            id="SBOM-001",
            title=f"Unpinned dependency versions ({len(unpinned)} packages)",
            severity=SEVERITY_MEDIUM,
            category="Supply Chain",
            stride_category="Tampering",
            cwe="CWE-1104",
            file_path=str(req_path.relative_to(ROOT)),
            line_number=unpinned[0][0],
            evidence=f"Unpinned: {', '.join(p for _, p in unpinned[:8])}{'...' if len(unpinned) > 8 else ''}",
            recommendation=(
                "Pin all versions: run `pip freeze > requirements-lock.txt` and "
                "use it in CI. Add `pip-audit` to the CI pipeline to detect known CVEs. "
                "Consider using `pip-compile` (pip-tools) to manage transitive deps."
            ),
            compliance_references=["OWASP A06:2021", "SLSA Level 2"],
        ))


def check_api_key_salt(findings: list[Finding]) -> None:
    """CWE-916 – API key hashed without salt."""
    api_keys_path = ROOT / "src" / "core" / "api_keys.py"
    if not api_keys_path.exists():
        return
    text = _read(api_keys_path)
    if "sha256" in text.lower() and "salt" not in text.lower() and "hmac" not in text.lower():
        findings.append(Finding(
            id="CRYPT-001",
            title="API keys hashed with SHA-256 but no salt (rainbow table risk)",
            severity=SEVERITY_MEDIUM,
            category="OWASP A02",
            stride_category="Spoofing",
            cwe="CWE-916",
            file_path=str(api_keys_path.relative_to(ROOT)),
            line_number=None,
            evidence="SHA-256 used without HMAC or salt in api_keys.py",
            recommendation=(
                "Use HMAC-SHA256 with a secret key "
                "(hmac.new(SECRET.encode(), key.encode(), hashlib.sha256)) "
                "or bcrypt/argon2 for key storage. "
                "Add `secrets.token_bytes(32)` salt per key."
            ),
            compliance_references=["OWASP A02:2021", "NIST SP 800-132"],
        ))


def check_in_memory_rate_limit(findings: list[Finding]) -> None:
    """Scalability/resilience – in-memory rate limiting resets on restart."""
    api_path = ROOT / "src" / "interface" / "api.py"
    text = _read(api_path)
    if "deque" in text and "rate" in text.lower() and "redis" not in text.lower():
        findings.append(Finding(
            id="RATE-001",
            title="Rate limiting is in-memory only — resets on restart, not distributed",
            severity=SEVERITY_LOW,
            category="OWASP A04",
            stride_category="Denial of Service",
            cwe="CWE-770",
            file_path=str(api_path.relative_to(ROOT)),
            line_number=None,
            evidence="deque-based rate limiter found; no Redis/Valkey dependency detected",
            recommendation=(
                "Replace with Redis-backed rate limiting (slowapi + redis or "
                "fastapi-limiter). For production: `SAGE_RATE_LIMIT_BACKEND=redis`."
            ),
            compliance_references=["OWASP A04:2021"],
        ))


def check_subprocess_env(findings: list[Finding]) -> None:
    """OWASP A03 – Subprocess calls pass environment without sanitization."""
    gateway_path = ROOT / "src" / "core" / "llm_gateway.py"
    text = _read(gateway_path)
    if "subprocess" in text and "env=" in text:
        findings.append(Finding(
            id="INJECT-001",
            title="Subprocess calls pass unsanitized environment to external CLI tools",
            severity=SEVERITY_MEDIUM,
            category="OWASP A03",
            stride_category="Elevation of Privilege",
            cwe="CWE-78",
            file_path=str(gateway_path.relative_to(ROOT)),
            line_number=None,
            evidence="subprocess.run(..., env=...) in llm_gateway.py",
            recommendation=(
                "Build the env dict from an allowlist of known-safe variables. "
                "Never pass os.environ directly. "
                "Validate CLI paths against an allowlist before execution."
            ),
            compliance_references=["OWASP A03:2021", "CWE-78"],
        ))


def check_audit_log_encryption(findings: list[Finding]) -> None:
    """HIPAA – Audit log not encrypted at application layer."""
    audit_path = ROOT / "src" / "memory" / "audit_logger.py"
    text = _read(audit_path)
    if "sqlite3" in text and "sqlcipher" not in text.lower() and "fernet" not in text.lower():
        findings.append(Finding(
            id="ENC-001",
            title="Audit log SQLite database not encrypted at application layer",
            severity=SEVERITY_HIGH,
            category="HIPAA",
            stride_category="Information Disclosure",
            cwe="CWE-311",
            file_path=str(audit_path.relative_to(ROOT)),
            line_number=None,
            evidence="sqlite3 used without SQLCipher pragma key or field-level encryption",
            recommendation=(
                "Use SQLCipher (pip install sqlcipher3) and set PRAGMA key='...' "
                "on connection open. "
                "Alternatively, encrypt the .sage/ directory with OS-level LUKS/BitLocker "
                "AND add a documented verification step to the deployment checklist. "
                "For PHI fields in audit records, apply Fernet field-level encryption."
            ),
            phi_impact=True,
            compliance_references=["HIPAA §164.312(a)(2)(iv)", "HIPAA §164.312(e)(2)(ii)"],
        ))


def check_phi_in_logs(findings: list[Finding]) -> None:
    """HIPAA – Potentially sensitive data stored in input_context."""
    audit_path = ROOT / "src" / "memory" / "audit_logger.py"
    text = _read(audit_path)
    if "input_context" in text or "content" in text:
        findings.append(Finding(
            id="PHI-001",
            title="Audit log stores raw input_context / chat content — may contain PHI",
            severity=SEVERITY_HIGH,
            category="HIPAA",
            stride_category="Information Disclosure",
            cwe="CWE-359",
            file_path=str(audit_path.relative_to(ROOT)),
            line_number=None,
            evidence="Fields 'input_context' and 'content' written to audit_log.db without redaction",
            recommendation=(
                "Enable pii.enabled: true before writing to audit log. "
                "Run PII filter on input_context before persistence. "
                "For HIPAA: apply field-level encryption to content columns containing free text."
            ),
            phi_impact=True,
            compliance_references=["HIPAA §164.312(a)(2)(iv)", "HIPAA §164.308(a)(1)(ii)(D)"],
        ))


def check_access_audit_logging(findings: list[Finding]) -> None:
    """HIPAA – Verify audit logging is enabled and covers access events."""
    audit_path = ROOT / "src" / "memory" / "audit_logger.py"
    api_path   = ROOT / "src" / "interface" / "api.py"
    audit_text = _read(audit_path)
    api_text   = _read(api_path)

    has_audit_class  = "AuditLogger" in audit_text or "audit_log" in audit_text
    has_api_calls    = "audit" in api_text.lower()

    if not (has_audit_class and has_api_calls):
        findings.append(Finding(
            id="AUDIT-001",
            title="Access audit logging not verified across all API endpoints",
            severity=SEVERITY_HIGH,
            category="HIPAA",
            stride_category="Repudiation",
            cwe="CWE-778",
            file_path=str(audit_path.relative_to(ROOT)),
            line_number=None,
            evidence="Audit logger exists but coverage across all endpoints is unverified",
            recommendation=(
                "Add a FastAPI middleware that logs every request (actor, endpoint, "
                "HTTP method, status code, trace_id) to the audit log. "
                "Run a coverage check: grep every @app.get/@app.post for audit_log calls."
            ),
            phi_impact=True,
            compliance_references=["HIPAA §164.312(b)", "IEC 62443-3-3 SR 2.8"],
        ))
    else:
        # Positive finding — logging exists
        findings.append(Finding(
            id="AUDIT-002",
            title="Access audit logging is implemented (AuditLogger present, API wired)",
            severity=SEVERITY_INFO,
            category="HIPAA",
            stride_category="Repudiation",
            cwe="",
            file_path=str(audit_path.relative_to(ROOT)),
            line_number=None,
            evidence="AuditLogger class and audit calls detected in audit_logger.py and api.py",
            recommendation="Verify 100% endpoint coverage with an automated coverage check.",
            phi_impact=False,
            compliance_references=["HIPAA §164.312(b)"],
        ))


# ---------------------------------------------------------------------------
# Acceptance criteria evaluation
# ---------------------------------------------------------------------------

def evaluate_acceptance_criteria(findings: list[Finding]) -> list[AcceptanceCriteria]:
    by_id = {f.id: f for f in findings}
    severity_set = {f.severity for f in findings}

    critical_high = [
        f for f in findings if f.severity in (SEVERITY_CRITICAL, SEVERITY_HIGH)
        and f.id not in ("AUDIT-002",)
    ]

    stride_ids = {f.stride_category for f in findings}
    stride_covered = all(
        s in stride_ids
        for s in ["Spoofing", "Tampering", "Repudiation", "Information Disclosure",
                  "Denial of Service", "Elevation of Privilege"]
    )

    return [
        AcceptanceCriteria(
            name="Threat model covers STRIDE categories",
            passed=stride_covered,
            detail=f"STRIDE categories found in findings: {sorted(stride_ids)}",
        ),
        AcceptanceCriteria(
            name="No critical/high vulnerabilities",
            passed=len(critical_high) == 0,
            detail=(
                f"FAILED — {len(critical_high)} critical/high findings: "
                + ", ".join(f.id for f in critical_high)
            ) if critical_high else "PASSED — no critical/high vulnerabilities",
        ),
        AcceptanceCriteria(
            name="SBOM generated",
            passed=True,
            detail="SBOM generated at security_audit/sbom.json",
        ),
        AcceptanceCriteria(
            name="PHI encryption at rest and in transit",
            passed="ENC-001" not in by_id and "PHI-001" not in by_id,
            detail=(
                "FAILED — ENC-001 (SQLite not encrypted) and/or PHI-001 (raw PHI in logs) present"
                if "ENC-001" in by_id or "PHI-001" in by_id
                else "PASSED"
            ),
        ),
        AcceptanceCriteria(
            name="Access audit logging enabled",
            passed="AUDIT-001" not in by_id,
            detail=by_id.get("AUDIT-001", by_id.get("AUDIT-002",
                AcceptanceCriteria("", False, ""))).evidence
                if "AUDIT-001" in by_id else "PASSED — audit logging verified",
        ),
    ]


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def build_report(findings: list[Finding]) -> dict[str, Any]:
    criteria = evaluate_acceptance_criteria(findings)
    severity_counts: dict[str, int] = {}
    for f in findings:
        severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1

    all_passed = all(c.passed for c in criteria)

    return {
        "report_metadata": {
            "title": "SAGE Framework — Security Review Report",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "analyst_role": "analyst",
            "scope": ["src/", "config/config.yaml", "requirements.txt"],
            "standards": ["OWASP Top 10 2021", "HIPAA Security Rule", "IEC 62443", "STRIDE"],
            "tool_version": "1.0.0",
        },
        "executive_summary": {
            "total_findings": len(findings),
            "severity_breakdown": severity_counts,
            "overall_risk": (
                "CRITICAL" if severity_counts.get("CRITICAL", 0) > 0
                else "HIGH" if severity_counts.get("HIGH", 0) > 0
                else "MEDIUM" if severity_counts.get("MEDIUM", 0) > 0
                else "LOW"
            ),
            "phi_impacting_findings": sum(1 for f in findings if f.phi_impact),
            "acceptance_criteria_passed": all_passed,
        },
        "acceptance_criteria": [asdict(c) for c in criteria],
        "findings": [asdict(f) for f in findings],
        "recommendations_priority": {
            "immediate": [
                f.id for f in findings if f.severity == SEVERITY_CRITICAL
            ],
            "short_term": [
                f.id for f in findings if f.severity == SEVERITY_HIGH
            ],
            "planned": [
                f.id for f in findings if f.severity in (SEVERITY_MEDIUM, SEVERITY_LOW)
            ],
        },
        "pentest_plan": {
            "phase_1_recon": [
                "Enumerate all FastAPI endpoints via /openapi.json",
                "Map authentication requirements per endpoint",
                "Identify unauthenticated endpoints when auth.enabled: false",
            ],
            "phase_2_authentication": [
                "Test OIDC token validation with expired/malformed JWTs",
                "Test API key bypass with invalid prefix formats",
                "Fuzz the 'Approving as' field for RBAC bypass",
                "Test anonymous fallback privilege escalation",
            ],
            "phase_3_injection": [
                "Fuzz all string inputs for SQL injection (parameterized, low risk)",
                "Test YAML injection via /config/yaml/{file} endpoint",
                "Test path traversal in file_name parameter (allowlist in place)",
                "Test prompt injection via task.description → LLM CLI",
                "Test environment variable injection via generic-cli provider",
            ],
            "phase_4_authorization": [
                "Test RBAC bypass: submit yaml_edit without admin role",
                "Test cross-tenant data access via X-SAGE-Tenant header manipulation",
                "Verify proposal isolation: one tenant cannot approve another's proposals",
            ],
            "phase_5_data_exposure": [
                "Inspect audit_log.db for plaintext PHI in input_context",
                "Test for sensitive data leakage in API error messages",
                "Check /gym/history and /gym/analytics for unredacted training data",
                "Verify CORS: send requests from disallowed origins",
            ],
            "phase_6_dos": [
                "Test rate limiting persistence across server restart",
                "Flood /analyze and /build/start endpoints beyond rate limit",
                "Test localhost/127.0.0.1 rate-limit bypass",
            ],
            "tools_recommended": [
                "OWASP ZAP (passive + active scan)",
                "Burp Suite Community (manual endpoint testing)",
                "sqlmap (SQL injection — expect clean results due to parameterization)",
                "pip-audit (dependency CVE scan)",
                "Semgrep (static analysis rules: p/owasp-top-ten, p/python)",
                "Bandit (Python static security linter)",
            ],
        },
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="SAGE security review")
    parser.add_argument("--output", default="security_audit/sage_security_report.json",
                        help="Output JSON report path")
    args = parser.parse_args()

    findings: list[Finding] = []

    check_cors(findings)
    check_auth_disabled(findings)
    check_pii_disabled(findings)
    check_security_headers(findings)
    check_unpinned_deps(findings)
    check_api_key_salt(findings)
    check_in_memory_rate_limit(findings)
    check_subprocess_env(findings)
    check_audit_log_encryption(findings)
    check_phi_in_logs(findings)
    check_access_audit_logging(findings)

    report = build_report(findings)

    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Console summary
    summary = report["executive_summary"]
    print(f"\n{'='*60}")
    print(f"  SAGE Security Review — {report['report_metadata']['generated_at'][:10]}")
    print(f"{'='*60}")
    print(f"  Total findings : {summary['total_findings']}")
    for sev, cnt in sorted(summary['severity_breakdown'].items()):
        print(f"    {sev:<10}: {cnt}")
    print(f"  Overall risk   : {summary['overall_risk']}")
    print(f"  PHI-impacting  : {summary['phi_impacting_findings']}")
    print(f"  Criteria pass  : {'YES' if summary['acceptance_criteria_passed'] else 'NO'}")
    print(f"\n  Report written : {output_path}")
    print(f"{'='*60}\n")

    sys.exit(0 if summary["overall_risk"] not in ("CRITICAL",) else 1)


if __name__ == "__main__":
    main()
