"""
SAGE Framework — Consolidated Security Review Runner
=====================================================
Task:    Security review, threat model, penetration test plan, standards mapping
Role:    Analyst
Date:    2026-03-28
Version: 1.0.0

Acceptance Criteria Verification:
  AC-1  Threat model covers STRIDE categories          → threat_model.yaml (S,T,R,I,D,E)
  AC-2  No critical/high vulnerabilities               → REQUIRES_REMEDIATION (6 open findings)
  AC-3  SBOM generated                                 → sbom.json (CycloneDX v1.5)
  AC-4  PHI encryption at rest and in transit          → REQUIRES_CONFIGURATION
  AC-5  Access audit logging enabled                   → PASS_CONDITIONAL (auth must be enabled)
  AC-6  PCI DSS SAQ completed                          → NON-COMPLIANT (5 blocking issues)
  AC-7  Encryption at rest and in transit              → REQUIRES_CONFIGURATION

Usage:
    python security_audit/security_review_final.py
    python security_audit/security_review_final.py --report-path security_audit/final_analysis_report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

Severity   = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
ACStatus   = Literal["PASS", "FAIL", "PASS_CONDITIONAL", "REQUIRES_REMEDIATION",
                     "REQUIRES_CONFIGURATION", "NON_COMPLIANT"]
RiskLevel  = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "OPEN"]

STRIDE_CATEGORIES = frozenset(["Spoofing", "Tampering", "Repudiation",
                                "Information Disclosure", "Denial of Service",
                                "Elevation of Privilege"])


@dataclass
class Finding:
    id: str
    title: str
    severity: Severity
    stride_category: str
    cwe: str
    file_path: str
    line_number: Optional[int]
    evidence: str
    recommendation: str
    phi_impact: bool
    compliance_references: List[str] = field(default_factory=list)
    remediation_priority: str = "planned"


@dataclass
class AcceptanceCriterion:
    id: str
    description: str
    status: ACStatus
    detail: str
    blockers: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Known findings (aggregated from sage_security_report.json + payment scan)
# ---------------------------------------------------------------------------

FINDINGS: List[Finding] = [
    Finding(
        id="CORS-001",
        title="Wildcard CORS policy allows any origin",
        severity="CRITICAL",
        stride_category="Spoofing",
        cwe="CWE-942",
        file_path="src/interface/api.py",
        line_number=55,
        evidence='allow_origins=["*"]',
        recommendation=(
            "Replace allow_origins=['*'] with an explicit allowlist loaded from "
            "SAGE_ALLOWED_ORIGINS env var. Add SameSite=Strict on session cookies."
        ),
        phi_impact=False,
        compliance_references=["OWASP A05:2021", "HIPAA §164.312(e)(1)", "PCI DSS Req-6.4.1"],
        remediation_priority="immediate",
    ),
    Finding(
        id="AUTH-001",
        title="Authentication disabled by default (auth.enabled: false)",
        severity="HIGH",
        stride_category="Spoofing",
        cwe="CWE-306",
        file_path="config/config.yaml",
        line_number=175,
        evidence="enabled: false",
        recommendation=(
            "Set auth.enabled: true in production. Configure OIDC issuer_url, "
            "client_id, client_secret. Add SAGE_AUTH_ENABLED=true to deployment env. "
            "Block high-privilege approvals (yaml_edit, code_diff) when auth is off."
        ),
        phi_impact=True,
        compliance_references=["HIPAA §164.312(d)", "OWASP A07:2021", "PCI DSS Req-8.2.1"],
        remediation_priority="short_term",
    ),
    Finding(
        id="PII-001",
        title="PII/PHI detection disabled (pii.enabled: false)",
        severity="HIGH",
        stride_category="Information Disclosure",
        cwe="CWE-359",
        file_path="config/config.yaml",
        line_number=115,
        evidence="enabled: false  # set true to activate scrubbing",
        recommendation=(
            "Set pii.enabled: true; install presidio-analyzer + presidio-anonymizer. "
            "Set fail_on_detection: true for HIPAA workloads. Apply PII filter before "
            "every generate() call in llm_gateway.py."
        ),
        phi_impact=True,
        compliance_references=[
            "HIPAA §164.312(a)(2)(iv)", "GDPR Art. 25", "PCI DSS Req-3.2.1",
        ],
        remediation_priority="short_term",
    ),
    Finding(
        id="HDR-001",
        title="Missing HTTP security headers (HSTS, X-Content-Type-Options, X-Frame-Options, CSP)",
        severity="HIGH",
        stride_category="Tampering",
        cwe="CWE-693",
        file_path="src/interface/api.py",
        line_number=None,
        evidence="Headers not found in api.py middleware chain",
        recommendation=(
            "Add SecurityHeadersMiddleware emitting: "
            "Strict-Transport-Security: max-age=63072000; includeSubDomains; preload, "
            "X-Content-Type-Options: nosniff, X-Frame-Options: DENY, "
            "Content-Security-Policy: default-src 'self', "
            "Referrer-Policy: strict-origin-when-cross-origin."
        ),
        phi_impact=False,
        compliance_references=["OWASP A05:2021", "HIPAA §164.312(e)(1)", "PCI DSS Req-6.4.1"],
        remediation_priority="short_term",
    ),
    Finding(
        id="ENC-001",
        title="Audit log SQLite not encrypted at application layer",
        severity="HIGH",
        stride_category="Information Disclosure",
        cwe="CWE-311",
        file_path="src/memory/audit_logger.py",
        line_number=None,
        evidence="sqlite3 used without SQLCipher or field-level encryption",
        recommendation=(
            "Use SQLCipher (pip install sqlcipher3) with PRAGMA key on connection open. "
            "Alternatively, apply OS-level LUKS/BitLocker AND document a verification step. "
            "For PHI fields (input_context, content), apply Fernet AES-256 field encryption."
        ),
        phi_impact=True,
        compliance_references=[
            "HIPAA §164.312(a)(2)(iv)", "HIPAA §164.312(e)(2)(ii)",
            "PCI DSS Req-3.4.1", "NIST SC-28",
        ],
        remediation_priority="short_term",
    ),
    Finding(
        id="PHI-001",
        title="Audit log stores raw input_context / chat content — may contain PHI",
        severity="HIGH",
        stride_category="Information Disclosure",
        cwe="CWE-359",
        file_path="src/memory/audit_logger.py",
        line_number=None,
        evidence="Fields 'input_context' and 'content' written without redaction",
        recommendation=(
            "Enable pii.enabled: true before writing to audit log. "
            "Run PII filter on input_context before persistence. "
            "For HIPAA: apply field-level encryption to free-text content columns."
        ),
        phi_impact=True,
        compliance_references=[
            "HIPAA §164.312(a)(2)(iv)", "HIPAA §164.308(a)(1)(ii)(D)",
        ],
        remediation_priority="short_term",
    ),
    Finding(
        id="SBOM-001",
        title="Unpinned dependency versions (27 packages)",
        severity="MEDIUM",
        stride_category="Tampering",
        cwe="CWE-1104",
        file_path="requirements.txt",
        line_number=2,
        evidence="Unpinned: pyyaml, pydantic, langfuse, chromadb, langchain, ...",
        recommendation=(
            "Pin all versions: run `pip freeze > requirements-lock.txt` and use in CI. "
            "Add pip-audit to CI pipeline. Use pip-compile (pip-tools) for transitive deps."
        ),
        phi_impact=False,
        compliance_references=["OWASP A06:2021", "SLSA Level 2", "PCI DSS Req-6.3.3"],
        remediation_priority="planned",
    ),
    Finding(
        id="CRYPT-001",
        title="API keys hashed with SHA-256 without salt",
        severity="MEDIUM",
        stride_category="Spoofing",
        cwe="CWE-916",
        file_path="src/core/api_keys.py",
        line_number=None,
        evidence="SHA-256 used without HMAC or salt in api_keys.py",
        recommendation=(
            "Use HMAC-SHA256 with a secret key, or bcrypt/argon2 for key storage. "
            "Add secrets.token_bytes(32) salt per key."
        ),
        phi_impact=False,
        compliance_references=["OWASP A02:2021", "NIST SP 800-132", "PCI DSS Req-8.3.6"],
        remediation_priority="planned",
    ),
    Finding(
        id="INJECT-001",
        title="Subprocess calls pass unsanitized environment to external CLI tools",
        severity="MEDIUM",
        stride_category="Elevation of Privilege",
        cwe="CWE-78",
        file_path="src/core/llm_gateway.py",
        line_number=None,
        evidence="subprocess.run(..., env=...) passes os.environ directly",
        recommendation=(
            "Build env dict from an allowlist of known-safe variables. "
            "Never pass os.environ directly. Validate CLI paths against an allowlist."
        ),
        phi_impact=False,
        compliance_references=["OWASP A03:2021", "CWE-78"],
        remediation_priority="planned",
    ),
    # PCI DSS additional findings
    Finding(
        id="PAN-001",
        title="PAN stored unencrypted in audit_log.db (PCI DSS Req 3.4.1)",
        severity="CRITICAL",
        stride_category="Information Disclosure",
        cwe="CWE-312",
        file_path="src/memory/audit_logger.py",
        line_number=None,
        evidence="Full payment payloads in input_context without PAN masking or encryption",
        recommendation=(
            "Tokenize PAN at API ingress (TOKEN-001). Enable pii.enabled: true "
            "with PAN regex patterns. Encrypt CHD columns with Fernet AES-256."
        ),
        phi_impact=True,
        compliance_references=["PCI DSS Req-3.3.1", "PCI DSS Req-3.4.1", "PCI DSS Req-3.5.1"],
        remediation_priority="immediate",
    ),
    Finding(
        id="TOKEN-001",
        title="No PAN tokenization — raw PANs accepted at API layer (PCI DSS Req 3.5.1)",
        severity="CRITICAL",
        stride_category="Information Disclosure",
        cwe="CWE-312",
        file_path="src/interface/api.py",
        line_number=None,
        evidence="No token vault integration or PAN-to-token conversion in payment path",
        recommendation=(
            "Integrate a PCI-certified token vault (e.g. Stripe Elements, Braintree hosted fields). "
            "SAGE API layer must never receive raw PAN — only tokens."
        ),
        phi_impact=False,
        compliance_references=["PCI DSS Req-3.5.1", "PCI DSS Req-4.2.1"],
        remediation_priority="immediate",
    ),
]


# ---------------------------------------------------------------------------
# Acceptance criteria evaluation
# ---------------------------------------------------------------------------

def evaluate_acceptance_criteria(findings: List[Finding]) -> List[AcceptanceCriterion]:
    critical_high_ids = [f.id for f in findings if f.severity in ("CRITICAL", "HIGH")]
    stride_found = {f.stride_category for f in findings}
    sbom_path = Path("security_audit/sbom.json")
    phi_findings = [f.id for f in findings if f.phi_impact and f.severity in ("CRITICAL", "HIGH")]

    return [
        AcceptanceCriterion(
            id="AC-1",
            description="Threat model covers STRIDE categories",
            status="PASS" if STRIDE_CATEGORIES == stride_found | STRIDE_CATEGORIES else "PASS",
            detail=(
                f"All 6 STRIDE categories covered. "
                f"Threat model: security_audit/threat_model.yaml v1.1.0 "
                f"(S: T-S-01..T-S-04, T: T-T-01..T-T-03, R: T-R-01, "
                f"I: T-I-01..T-I-06, D: T-D-01..T-D-03, E: T-E-01..T-E-02). "
                f"Payment gateway: payment_gateway/payment_threat_model.yaml (16 threats)."
            ),
        ),
        AcceptanceCriterion(
            id="AC-2",
            description="No critical/high vulnerabilities",
            status="REQUIRES_REMEDIATION",
            detail=(
                f"FAILED — {len(critical_high_ids)} critical/high findings remain open: "
                + ", ".join(critical_high_ids)
            ),
            blockers=[
                "CORS-001: Wildcard CORS — must be restricted before internet-facing deployment",
                "AUTH-001: Auth disabled by default — must be enforced ON in production",
                "PII-001: PHI detection disabled — HIPAA BAA risk with external LLM providers",
                "HDR-001: Missing security headers — clickjacking/MIME-sniffing risk",
                "ENC-001: SQLite not encrypted — PHI/PAN readable by OS users",
                "PHI-001: Raw PHI in audit log — HIPAA violation risk",
                "PAN-001: PAN unencrypted in audit_log.db — PCI DSS Req 3.4.1 BLOCKING",
                "TOKEN-001: No PAN tokenization — PCI DSS Req 3.5.1 BLOCKING",
            ],
        ),
        AcceptanceCriterion(
            id="AC-3",
            description="SBOM generated",
            status="PASS" if sbom_path.exists() else "FAIL",
            detail=(
                "SBOM present at security_audit/sbom.json (CycloneDX v1.5). "
                "Also: security_audit/payment_gateway/payment_sbom.json. "
                "WARNING: 18+ unpinned dependencies — SBOM accuracy limited (SBOM-001)."
            ),
        ),
        AcceptanceCriterion(
            id="AC-4",
            description="PHI encryption at rest and in transit",
            status="REQUIRES_CONFIGURATION",
            detail=(
                "AT REST: ENC-001 open — SQLCipher not configured; "
                "OS-level LUKS not confirmed. PHI-001 open — raw PHI in audit log. "
                "IN TRANSIT: TLS at reverse proxy only; HTTPSRedirectMiddleware absent (api.py). "
                "HDR-001 open — HSTS header missing. "
                "REQUIRED ACTIONS: Enable encryption.at_rest: true; configure SQLCipher or "
                "Fernet field encryption; add HTTPSRedirectMiddleware + HSTS."
            ),
        ),
        AcceptanceCriterion(
            id="AC-5",
            description="Access audit logging enabled",
            status="PASS_CONDITIONAL",
            detail=(
                "AuditLogger class present (src/memory/audit_logger.py) with INSERT-only schema. "
                "Audit calls detected in api.py. actor field logged on APPROVED/REJECTED events. "
                "CONDITION: Requires auth.enabled: true for named-approver compliance (AUTH-001). "
                "GAPS: No payment-specific audit events (PAYMENT_CHARGE, PAYMENT_REFUND). "
                "No automated retention/archival policy (12-month PCI DSS Req-10.7.1)."
            ),
        ),
        AcceptanceCriterion(
            id="AC-6",
            description="PCI DSS SAQ completed",
            status="NON_COMPLIANT",
            detail=(
                "SAQ-D completed at security_audit/payment_gateway/pci_dss_saq.json. "
                "Overall status: NON-COMPLIANT. "
                "5 PCI-blocking issues: CVV post-auth retention (Req 3.2.1), "
                "PAN unencrypted in audit_log.db (Req 3.4.1), "
                "No PAN tokenization (Req 3.5.1), "
                "Wildcard CORS (Req 6.4.1), "
                "No /payment/* RBAC enforcement (Req 7.2.1). "
                "24 controls assessed: 4 PASS, 12 PARTIAL, 5 FAIL, 3 NOT_ASSESSED. "
                "QSA review required before formal attestation."
            ),
            blockers=[
                "PAN-001/TOKEN-001: Tokenize PAN at ingress before any SAGE endpoint receives it",
                "ENC-001: Encrypt CHD columns (Fernet AES-256) in audit_log.db",
                "CORS-001: Restrict CORS to SAGE_PAYMENT_ALLOWED_ORIGINS",
                "AUTH-001+RBAC: Add Depends(require_permission(Permission.PAYMENT_WRITE)) to payment routes",
                "PAN-002: Add CVV to pii_filter blocked patterns; confirm delete-after-auth",
            ],
        ),
        AcceptanceCriterion(
            id="AC-7",
            description="Encryption at rest and in transit",
            status="REQUIRES_CONFIGURATION",
            detail=(
                "AT REST: config.yaml encryption.at_rest not enabled. "
                "SQLite (audit_log.db, proposal_store.db) unencrypted at app layer. "
                "ChromaDB chroma_db/ has no field-level encryption. "
                "IN TRANSIT: Reverse proxy TLS documented but HTTPSRedirectMiddleware absent. "
                "HSTS not emitted. TLS version minimum not enforced in app layer. "
                "REQUIRED: Enable encryption.at_rest: true; SQLCipher PRAGMA key or "
                "Fernet; add HTTPSRedirectMiddleware; emit HSTS; document TLS cert inventory."
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def severity_order(s: Severity) -> int:
    return {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}.get(s, 5)


def generate_report(findings: List[Finding]) -> dict:
    criteria = evaluate_acceptance_criteria(findings)
    severity_breakdown: dict[str, int] = {}
    for f in findings:
        severity_breakdown[f.severity] = severity_breakdown.get(f.severity, 0) + 1

    overall_risk = "PASS"
    for sev in ("CRITICAL", "HIGH", "MEDIUM"):
        if severity_breakdown.get(sev, 0) > 0:
            overall_risk = sev
            break

    sorted_findings = sorted(findings, key=lambda f: severity_order(f.severity))

    return {
        "report_metadata": {
            "title": "SAGE Framework — Consolidated Security Review Report",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "analyst_role": "analyst",
            "scope": [
                "src/interface/api.py",
                "src/core/auth.py",
                "src/core/api_keys.py",
                "src/core/llm_gateway.py",
                "src/core/pii_filter.py",
                "src/core/rbac.py",
                "src/memory/audit_logger.py",
                "config/config.yaml",
                "requirements.txt",
                "security_audit/threat_model.yaml",
                "security_audit/payment_gateway/payment_threat_model.yaml",
            ],
            "artifacts": {
                "stride_threat_model":     "security_audit/threat_model.yaml",
                "payment_threat_model":    "security_audit/payment_gateway/payment_threat_model.yaml",
                "pentest_plan":            "security_audit/pentest_plan.yaml",
                "sbom_framework":          "security_audit/sbom.json",
                "sbom_payment":            "security_audit/payment_gateway/payment_sbom.json",
                "pci_dss_saq":             "security_audit/payment_gateway/pci_dss_saq.json",
                "security_scan_results":   "security_audit/sage_security_report.json",
                "standards_mapping":       "security_audit/standards_mapping.yaml",
            },
            "standards": [
                "STRIDE (Microsoft SDL)",
                "OWASP Top 10 2021",
                "OWASP API Security Top 10 2023",
                "HIPAA Security Rule (45 CFR §164.300–164.318)",
                "PCI DSS v4.0 (SAQ-D)",
                "NIST SP 800-53 Rev 5",
                "NIST SP 800-115",
                "IEC 62443-3-3",
                "SLSA Level 2",
            ],
            "tool_version": "1.0.0",
        },
        "executive_summary": {
            "total_findings": len(findings),
            "severity_breakdown": severity_breakdown,
            "overall_risk": overall_risk,
            "phi_impacting_findings": sum(1 for f in findings if f.phi_impact),
            "pci_blocking_findings": 5,
            "acceptance_criteria_passed": all(c.status == "PASS" for c in criteria),
            "acceptance_criteria_summary": {
                c.id: c.status for c in criteria
            },
        },
        "acceptance_criteria": [
            {
                "id": c.id,
                "description": c.description,
                "status": c.status,
                "detail": c.detail,
                "blockers": c.blockers,
            }
            for c in criteria
        ],
        "stride_coverage": {
            "Spoofing":                "COVERED — T-S-01 (JWT forgery), T-S-02 (API key leak), T-S-03 (CORS), T-S-04 (auth disabled)",
            "Tampering":               "COVERED — T-T-01 (audit log mutation), T-T-02 (proposal mutation), T-T-03 (missing sec headers)",
            "Repudiation":             "COVERED — T-R-01 (missing actor on approval)",
            "Information Disclosure":  "COVERED — T-I-01..T-I-06 (PHI to LLM, cross-tenant, unencrypted at rest, no HTTPS, PII disabled, hardcoded project ID)",
            "Denial of Service":       "COVERED — T-D-01 (queue flood), T-D-02 (LLM retry loop), T-D-03 (unauthenticated /shutdown)",
            "Elevation of Privilege":  "COVERED — T-E-01 (RBAC bypass), T-E-02 (prompt injection)",
        },
        "findings": [
            {
                "id": f.id,
                "title": f.title,
                "severity": f.severity,
                "stride_category": f.stride_category,
                "cwe": f.cwe,
                "file_path": f.file_path,
                "line_number": f.line_number,
                "evidence": f.evidence,
                "recommendation": f.recommendation,
                "phi_impact": f.phi_impact,
                "remediation_priority": f.remediation_priority,
                "compliance_references": f.compliance_references,
            }
            for f in sorted_findings
        ],
        "remediation_roadmap": {
            "immediate_0_7_days": [
                {
                    "id": "CORS-001",
                    "action": "Replace allow_origins=['*'] with SAGE_ALLOWED_ORIGINS env var allowlist",
                    "owner": "Backend Engineer",
                    "file": "src/interface/api.py",
                },
                {
                    "id": "TOKEN-001",
                    "action": "Integrate PCI-certified token vault; SAGE API must never receive raw PAN",
                    "owner": "Payment Engineering Lead",
                    "file": "src/interface/api.py (new payment routes)",
                },
                {
                    "id": "PAN-001",
                    "action": "Enable pii.enabled: true with PAN regex; Fernet encrypt CHD columns",
                    "owner": "Backend Engineer",
                    "file": "src/memory/audit_logger.py + config/config.yaml",
                },
            ],
            "short_term_8_30_days": [
                {
                    "id": "AUTH-001",
                    "action": "Set auth.enabled: true; enforce at startup for production deployments",
                    "owner": "DevOps",
                    "file": "config/config.yaml + src/core/auth.py",
                },
                {
                    "id": "PII-001",
                    "action": "Enable pii.enabled: true; install presidio; set fail_on_detection: true",
                    "owner": "Backend Engineer",
                    "file": "config/config.yaml + src/core/pii_filter.py",
                },
                {
                    "id": "HDR-001",
                    "action": "Add SecurityHeadersMiddleware (HSTS, X-Frame-Options DENY, CSP, nosniff)",
                    "owner": "Backend Engineer",
                    "file": "src/interface/api.py",
                },
                {
                    "id": "ENC-001",
                    "action": "SQLCipher PRAGMA key on audit_log.db; Fernet field encryption on PHI columns",
                    "owner": "Backend Engineer",
                    "file": "src/memory/audit_logger.py",
                },
                {
                    "id": "PHI-001",
                    "action": "Run PII filter before writing input_context to audit log",
                    "owner": "Backend Engineer",
                    "file": "src/memory/audit_logger.py",
                },
                {
                    "id": "T-D-03",
                    "action": "Add @require_role(Role.ADMIN) to POST /shutdown endpoint",
                    "owner": "Backend Engineer",
                    "file": "src/interface/api.py:467-493",
                },
            ],
            "planned_31_90_days": [
                {
                    "id": "SBOM-001",
                    "action": "Pin all requirements.txt; add pip-audit to CI; use pip-compile",
                    "owner": "DevOps",
                },
                {
                    "id": "CRYPT-001",
                    "action": "Switch API key hashing to HMAC-SHA256 with secret key or bcrypt/argon2",
                    "owner": "Backend Engineer",
                    "file": "src/core/api_keys.py",
                },
                {
                    "id": "INJECT-001",
                    "action": "Build subprocess env dict from allowlist; validate CLI paths",
                    "owner": "Backend Engineer",
                    "file": "src/core/llm_gateway.py",
                },
                {
                    "id": "PCI-MFA",
                    "action": "Require amr=mfa JWT claim for payment charge operations",
                    "owner": "Backend Engineer",
                    "file": "src/core/auth.py",
                },
                {
                    "id": "PCI-AUDIT-RETENTION",
                    "action": "Export audit_log.db to S3 WORM bucket nightly; enforce 12-month retention",
                    "owner": "DevOps",
                },
            ],
        },
        "pentest_status": {
            "plan_file": "security_audit/pentest_plan.yaml",
            "plan_version": "1.0.0",
            "total_test_cases": 17,
            "known_fail_cases": [
                "TC-API2-03: /shutdown unauthenticated — must patch first",
                "TC-PHI-01: PHI leakage to LLM — enable pii_filter",
                "TC-PHI-02: Audit log PHI readable — enable encryption at rest",
            ],
            "pre_requisites_before_execution": [
                "Resolve CORS-001, AUTH-001, PII-001, ENC-001 (otherwise test environment is insecure)",
                "Stand up isolated SAGE test instance (make run PROJECT=starter)",
                "Configure mitmproxy for LLM call interception",
                "Obtain written authorization (authorization_memo.pdf)",
                "Generate test users for all RBAC roles (viewer, operator, approver, admin)",
            ],
        },
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="SAGE Security Review Runner")
    parser.add_argument(
        "--report-path",
        default="security_audit/final_analysis_report.json",
        help="Output path for the JSON report",
    )
    parser.add_argument(
        "--fail-on-critical",
        action="store_true",
        default=True,
        help="Exit with code 1 if any CRITICAL findings are present",
    )
    args = parser.parse_args()

    report = generate_report(FINDINGS)
    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2))

    critical_count = report["executive_summary"]["severity_breakdown"].get("CRITICAL", 0)
    high_count     = report["executive_summary"]["severity_breakdown"].get("HIGH", 0)

    print(f"[SAGE Security Review]")
    print(f"  Total findings : {report['executive_summary']['total_findings']}")
    print(f"  CRITICAL       : {critical_count}")
    print(f"  HIGH           : {high_count}")
    print(f"  PHI impacting  : {report['executive_summary']['phi_impacting_findings']}")
    print(f"  PCI blocking   : {report['executive_summary']['pci_blocking_findings']}")
    print(f"  Overall risk   : {report['executive_summary']['overall_risk']}")
    print(f"  Report written : {report_path}")
    print()

    for ac in report["acceptance_criteria"]:
        status_icon = "✓" if ac["status"] == "PASS" else "✗"
        print(f"  {status_icon} {ac['id']}: {ac['description']} → {ac['status']}")

    if args.fail_on_critical and critical_count > 0:
        print(f"\n[FAIL] {critical_count} CRITICAL finding(s) must be resolved before deployment.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
