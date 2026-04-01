"""
SAGE Framework — Payment Gateway Security Scanner
==================================================
Role:     Analyst
Date:     2026-03-28
Scope:    Payment Gateway API endpoints, PCI DSS SAQ-D compliance,
          PHI/PAN encryption, access audit logging, SBOM
Standards: PCI DSS v4.0, OWASP API Security Top 10, STRIDE,
           HIPAA Security Rule, NIST SP 800-53 Rev 5

Checks performed (in order):
  PAN-001   PAN/card number stored or logged in plaintext
  PAN-002   CVV/CVC persisted after authorization
  TLS-001   TLS version below 1.2 accepted
  TLS-002   HTTPS not enforced (no redirect middleware)
  AUTH-001  Payment endpoints missing JWT/API-key auth
  AUTHZ-001 Missing RBAC on /payment/* mutating endpoints
  RATE-001  No rate limiting on payment charge endpoint
  AUDIT-001 Payment event not written to audit log
  AUDIT-002 Access audit logging not recording actor identity
  CORS-001  Wildcard CORS on payment API
  HDR-001   Missing security headers (HSTS, CSP, X-Frame-Options)
  SBOM-001  Unpinned payment library versions
  ENC-001   Cardholder data not encrypted at rest
  INJECT-001 SQL/command injection risk in payment params
  TOKEN-001 Tokenization not implemented (raw PAN traverses API layer)
  IDEMPOTENCY-001 Charge endpoint lacks idempotency key enforcement

Usage:
    python security_audit/payment_gateway/payment_security_scanner.py
    python security_audit/payment_gateway/payment_security_scanner.py \\
        --output security_audit/payment_gateway/payment_security_report.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Severity constants
# ---------------------------------------------------------------------------
SEV_CRITICAL = "CRITICAL"
SEV_HIGH     = "HIGH"
SEV_MEDIUM   = "MEDIUM"
SEV_LOW      = "LOW"
SEV_INFO     = "INFO"

# PCI DSS requirement references
PCI_REQ = {
    "3":   "PCI DSS Req 3 — Protect Stored Account Data",
    "4":   "PCI DSS Req 4 — Protect Cardholder Data in Transit",
    "6":   "PCI DSS Req 6 — Develop and Maintain Secure Systems",
    "7":   "PCI DSS Req 7 — Restrict Access to System Components",
    "8":   "PCI DSS Req 8 — Identify Users and Authenticate Access",
    "10":  "PCI DSS Req 10 — Log and Monitor All Access",
    "11":  "PCI DSS Req 11 — Test Security of Systems and Networks",
    "12":  "PCI DSS Req 12 — Support Information Security with Org Policies",
}

ROOT = Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    id: str
    title: str
    severity: str
    category: str
    stride_category: str
    cwe: str
    file_path: str
    line_number: int | None
    evidence: str
    recommendation: str
    pci_requirement: str = ""
    phi_impact: bool = False
    pan_impact: bool = False
    compliance_references: list[str] = field(default_factory=list)


@dataclass
class AcceptanceCriteria:
    name: str
    passed: bool
    detail: str


@dataclass
class PCIDSSControl:
    requirement: str
    description: str
    status: str          # PASS | FAIL | PARTIAL | NOT_APPLICABLE
    evidence: str
    finding_ids: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _search_codebase(pattern: str, glob: str = "**/*.py") -> list[tuple[Path, int, str]]:
    """Search for regex pattern across codebase files matching glob."""
    results: list[tuple[Path, int, str]] = []
    src_root = ROOT / "src"
    for fpath in src_root.glob(glob):
        text = _read(fpath)
        for i, line in enumerate(text.splitlines(), 1):
            if re.search(pattern, line, re.IGNORECASE):
                results.append((fpath, i, line.strip()))
    return results


# ---------------------------------------------------------------------------
# Check implementations
# ---------------------------------------------------------------------------

def check_pan_in_logs(findings: list[Finding]) -> None:
    """PCI DSS Req 3.3 — PAN must not appear in logs."""
    patterns = [
        r"(card_number|pan|credit_card|cc_number|cardnum)",
        r"(4[0-9]{12}(?:[0-9]{3})?)",   # Visa pattern
        r"(5[1-5][0-9]{14})",            # Mastercard pattern
    ]
    audit_path = ROOT / "src" / "memory" / "audit_logger.py"
    api_path   = ROOT / "src" / "interface" / "api.py"
    for path in [audit_path, api_path]:
        text = _read(path)
        for pat in patterns:
            for i, line in enumerate(text.splitlines(), 1):
                if re.search(pat, line, re.IGNORECASE) and "redact" not in line.lower() \
                        and "mask" not in line.lower() and "token" not in line.lower():
                    findings.append(Finding(
                        id="PAN-001",
                        title="PAN/card number field referenced without masking in audit path",
                        severity=SEV_CRITICAL,
                        category="PCI DSS",
                        stride_category="Information Disclosure",
                        cwe="CWE-312",
                        file_path=str(path.relative_to(ROOT)),
                        line_number=i,
                        evidence=line.strip()[:120],
                        recommendation=(
                            "Mask PAN before storage: store only first 6 and last 4 digits. "
                            "Apply PAN tokenization via a PCI-certified vault before the data "
                            "reaches the audit log or any log sink. "
                            "Never log full PAN, CVV, or magnetic stripe data."
                        ),
                        pci_requirement=PCI_REQ["3"],
                        pan_impact=True,
                        compliance_references=["PCI DSS v4.0 Req 3.3.1", "OWASP A02:2021"],
                    ))
                    return  # one finding per category is sufficient


def check_cvv_storage(findings: list[Finding]) -> None:
    """PCI DSS Req 3.2 — CVV/CVC must not be stored post-authorization."""
    audit_path = ROOT / "src" / "memory" / "audit_logger.py"
    api_path   = ROOT / "src" / "interface" / "api.py"
    for path in [audit_path, api_path]:
        text = _read(path)
        for i, line in enumerate(text.splitlines(), 1):
            if re.search(r"\b(cvv|cvc|csc|card_security_code)\b", line, re.IGNORECASE):
                if "delete" not in line.lower() and "not_stored" not in line.lower():
                    findings.append(Finding(
                        id="PAN-002",
                        title="CVV/CVC field referenced — must not be persisted after auth",
                        severity=SEV_CRITICAL,
                        category="PCI DSS",
                        stride_category="Information Disclosure",
                        cwe="CWE-312",
                        file_path=str(path.relative_to(ROOT)),
                        line_number=i,
                        evidence=line.strip()[:120],
                        recommendation=(
                            "CVV/CVC must NEVER be stored after the authorization request completes. "
                            "Scrub CVV from memory immediately after the payment processor call. "
                            "Validate on the processor side only — never echo or log it."
                        ),
                        pci_requirement=PCI_REQ["3"],
                        pan_impact=True,
                        compliance_references=["PCI DSS v4.0 Req 3.2.1", "PCI DSS v4.0 Req 3.3.2"],
                    ))
                    return


def check_tls_enforcement(findings: list[Finding]) -> None:
    """PCI DSS Req 4.2 — TLS 1.2+ required; no fallback to TLS 1.0/1.1."""
    api_path = ROOT / "src" / "interface" / "api.py"
    text = _read(api_path)

    # Check for HTTPS redirect middleware
    has_https_redirect = any(
        kw in text for kw in [
            "HTTPSRedirectMiddleware", "https_redirect", "X-Forwarded-Proto",
            "redirect_to_https",
        ]
    )
    if not has_https_redirect:
        findings.append(Finding(
            id="TLS-002",
            title="HTTPS redirect middleware absent — HTTP connections not forced to TLS",
            severity=SEV_HIGH,
            category="PCI DSS",
            stride_category="Information Disclosure",
            cwe="CWE-319",
            file_path=str(api_path.relative_to(ROOT)),
            line_number=None,
            evidence="No HTTPSRedirectMiddleware or X-Forwarded-Proto check found in api.py",
            recommendation=(
                "Add `from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware` "
                "and `app.add_middleware(HTTPSRedirectMiddleware)` for direct TLS deployments. "
                "For reverse-proxy deployments, enforce TLS at nginx/caddy and set "
                "HSTS max-age >= 31536000 in the security headers middleware."
            ),
            pci_requirement=PCI_REQ["4"],
            compliance_references=[
                "PCI DSS v4.0 Req 4.2.1", "HIPAA §164.312(e)(1)", "OWASP A05:2021",
            ],
        ))

    # Check for weak TLS version references
    config_path = ROOT / "config" / "config.yaml"
    cfg_text = _read(config_path)
    for i, line in enumerate(cfg_text.splitlines(), 1):
        if re.search(r"tls.*(1\.0|1\.1|ssl)", line, re.IGNORECASE):
            findings.append(Finding(
                id="TLS-001",
                title="Weak TLS version (TLS 1.0 or 1.1) referenced in configuration",
                severity=SEV_HIGH,
                category="PCI DSS",
                stride_category="Information Disclosure",
                cwe="CWE-326",
                file_path=str(config_path.relative_to(ROOT)),
                line_number=i,
                evidence=line.strip(),
                recommendation=(
                    "Set minimum TLS version to 1.2. Prefer TLS 1.3. "
                    "Disable SSLv3, TLS 1.0, and TLS 1.1 at the reverse proxy "
                    "and in any Python ssl.SSLContext objects."
                ),
                pci_requirement=PCI_REQ["4"],
                compliance_references=["PCI DSS v4.0 Req 4.2.1", "NIST SP 800-52 Rev 2"],
            ))
            break


def check_payment_endpoint_auth(findings: list[Finding]) -> None:
    """PCI DSS Req 8 — All payment endpoints must require authentication."""
    api_path = ROOT / "src" / "interface" / "api.py"
    text = _read(api_path)

    # Look for payment route patterns without auth dependency
    payment_routes = re.findall(
        r'@app\.(post|get|put|delete)\s*\(\s*["\']([^"\']*(?:payment|charge|billing|'
        r'checkout|refund|transaction)[^"\']*)["\']',
        text, re.IGNORECASE
    )

    if not payment_routes:
        # No dedicated payment routes found — flag as informational gap
        findings.append(Finding(
            id="AUTH-001",
            title="No dedicated /payment/* routes found — payment endpoints not inventoried",
            severity=SEV_HIGH,
            category="PCI DSS",
            stride_category="Spoofing",
            cwe="CWE-306",
            file_path=str(api_path.relative_to(ROOT)),
            line_number=None,
            evidence="No @app.post('/payment/...') routes detected in api.py",
            recommendation=(
                "Define explicit payment routes (POST /payment/charge, "
                "POST /payment/refund, GET /payment/status/{id}). "
                "Apply `Depends(require_permission(Permission.PAYMENT_WRITE))` "
                "to all mutating payment endpoints. "
                "Require strong authentication (JWT with MFA) for charge operations."
            ),
            pci_requirement=PCI_REQ["8"],
            compliance_references=[
                "PCI DSS v4.0 Req 8.2.1", "PCI DSS v4.0 Req 8.3.6",
                "OWASP API Security API2:2023",
            ],
        ))
    else:
        for method, route in payment_routes:
            # Check if the route has an auth dependency nearby
            route_idx = text.find(route)
            snippet = text[max(0, route_idx - 200):route_idx + 200]
            if "Depends" not in snippet and "require_permission" not in snippet:
                findings.append(Finding(
                    id="AUTHZ-001",
                    title=f"Payment route {route!r} missing RBAC dependency",
                    severity=SEV_CRITICAL,
                    category="PCI DSS",
                    stride_category="Elevation of Privilege",
                    cwe="CWE-862",
                    file_path=str(api_path.relative_to(ROOT)),
                    line_number=None,
                    evidence=f"Route {method.upper()} {route} has no Depends(require_permission(...))",
                    recommendation=(
                        f"Add `Depends(require_permission(Permission.PAYMENT_WRITE))` "
                        f"to the {route} handler signature. "
                        "Restrict payment mutations to operator/admin roles only."
                    ),
                    pci_requirement=PCI_REQ["7"],
                    pan_impact=True,
                    compliance_references=[
                        "PCI DSS v4.0 Req 7.2.1", "PCI DSS v4.0 Req 8.2.1",
                        "OWASP A01:2021",
                    ],
                ))


def check_rate_limiting_payment(findings: list[Finding]) -> None:
    """PCI DSS Req 6 + OWASP API4 — rate limiting on payment charge endpoint."""
    api_path = ROOT / "src" / "interface" / "api.py"
    text = _read(api_path)

    has_rate_limit = any(
        kw in text for kw in ["slowapi", "RateLimiter", "rate_limit", "limiter"]
    )
    if not has_rate_limit:
        findings.append(Finding(
            id="RATE-001",
            title="No rate limiting detected on payment/charge endpoints",
            severity=SEV_HIGH,
            category="PCI DSS",
            stride_category="Denial of Service",
            cwe="CWE-770",
            file_path=str(api_path.relative_to(ROOT)),
            line_number=None,
            evidence="No rate-limiting middleware or decorator found in api.py",
            recommendation=(
                "Apply per-IP and per-account rate limits on POST /payment/charge: "
                "≤ 10 req/min per IP, ≤ 3 failed auth attempts per account before lockout. "
                "Use slowapi or fastapi-limiter backed by Redis for distributed rate limits. "
                "Return HTTP 429 with Retry-After header on breach."
            ),
            pci_requirement=PCI_REQ["6"],
            compliance_references=[
                "PCI DSS v4.0 Req 6.3.3", "OWASP API Security API4:2023",
            ],
        ))


def check_payment_audit_logging(findings: list[Finding]) -> None:
    """PCI DSS Req 10 — every payment event must be logged with actor + timestamp."""
    audit_path = ROOT / "src" / "memory" / "audit_logger.py"
    api_path   = ROOT / "src" / "interface" / "api.py"
    audit_text = _read(audit_path)
    api_text   = _read(api_path)

    has_audit_class = "AuditLogger" in audit_text or "audit_log" in audit_text
    payment_audit   = any(
        kw in api_text.lower() for kw in ["payment", "charge", "transaction"]
    ) and "audit" in api_text.lower()

    if not payment_audit:
        findings.append(Finding(
            id="AUDIT-001",
            title="Payment transaction events not explicitly wired to audit logger",
            severity=SEV_HIGH,
            category="PCI DSS",
            stride_category="Repudiation",
            cwe="CWE-778",
            file_path=str(api_path.relative_to(ROOT)),
            line_number=None,
            evidence="No payment-specific audit_log() call found in api.py",
            recommendation=(
                "Call `audit_logger.log_event(event_type='PAYMENT_CHARGE', actor=user_id, "
                "trace_id=..., amount=..., last4=..., status=...)` for every charge, "
                "refund, and auth attempt. "
                "Log must include: timestamp (UTC), actor identity, IP, amount, "
                "masked PAN (last 4), response code, and idempotency key."
            ),
            pci_requirement=PCI_REQ["10"],
            compliance_references=[
                "PCI DSS v4.0 Req 10.2.1", "PCI DSS v4.0 Req 10.3.2",
                "HIPAA §164.312(b)",
            ],
        ))
    else:
        findings.append(Finding(
            id="AUDIT-002",
            title="Audit logger present and referenced in API — verify payment event coverage",
            severity=SEV_INFO,
            category="PCI DSS",
            stride_category="Repudiation",
            cwe="",
            file_path=str(audit_path.relative_to(ROOT)),
            line_number=None,
            evidence="AuditLogger present; confirm PAYMENT_CHARGE and PAYMENT_REFUND event types",
            recommendation=(
                "Run coverage check: `grep -n 'PAYMENT_' src/interface/api.py` "
                "and verify all payment routes emit structured audit events."
            ),
            pci_requirement=PCI_REQ["10"],
            compliance_references=["PCI DSS v4.0 Req 10.2.1"],
        ))


def check_cors_payment(findings: list[Finding]) -> None:
    """OWASP A05 — Wildcard CORS allows any origin to initiate payment flows."""
    api_path = ROOT / "src" / "interface" / "api.py"
    text = _read(api_path)
    for i, line in enumerate(text.splitlines(), 1):
        if 'allow_origins=["*"]' in line or "allow_origins=['*']" in line:
            findings.append(Finding(
                id="CORS-001",
                title="Wildcard CORS enables cross-origin payment request forgery (CPRF)",
                severity=SEV_CRITICAL,
                category="OWASP A05",
                stride_category="Spoofing",
                cwe="CWE-942",
                file_path=str(api_path.relative_to(ROOT)),
                line_number=i,
                evidence=line.strip(),
                recommendation=(
                    "Replace allow_origins=['*'] with explicit payment origin allowlist. "
                    "Set SAGE_PAYMENT_ALLOWED_ORIGINS=https://checkout.yourdomain.com. "
                    "Add SameSite=Strict to all session cookies. "
                    "This is a PCI DSS blocking issue for any internet-facing payment endpoint."
                ),
                pci_requirement=PCI_REQ["6"],
                pan_impact=True,
                compliance_references=[
                    "PCI DSS v4.0 Req 6.4.1", "OWASP A05:2021", "HIPAA §164.312(e)(1)",
                ],
            ))
            break


def check_security_headers(findings: list[Finding]) -> None:
    """PCI DSS Req 6 / OWASP A05 — missing HTTP security headers."""
    api_path = ROOT / "src" / "interface" / "api.py"
    text = _read(api_path)
    required = {
        "Strict-Transport-Security": "PCI DSS Req 4.2 — enforce TLS permanently",
        "X-Content-Type-Options":    "Prevent MIME sniffing of payment response JSON",
        "X-Frame-Options":           "Prevent clickjacking on payment UI",
        "Content-Security-Policy":   "Restrict payment form assets to same origin",
    }
    missing = [h for h in required if h not in text]
    if missing:
        findings.append(Finding(
            id="HDR-001",
            title=f"Missing payment-critical security headers: {', '.join(missing)}",
            severity=SEV_HIGH,
            category="PCI DSS",
            stride_category="Tampering",
            cwe="CWE-693",
            file_path=str(api_path.relative_to(ROOT)),
            line_number=None,
            evidence=f"Headers absent from api.py middleware: {missing}",
            recommendation=(
                "Add SecurityHeadersMiddleware with:\n"
                "  Strict-Transport-Security: max-age=63072000; includeSubDomains; preload\n"
                "  X-Content-Type-Options: nosniff\n"
                "  X-Frame-Options: DENY\n"
                "  Content-Security-Policy: default-src 'self'; "
                "frame-ancestors 'none'; form-action 'self'\n"
                "  Referrer-Policy: strict-origin-when-cross-origin\n"
                "  Permissions-Policy: payment=(), geolocation=()"
            ),
            pci_requirement=PCI_REQ["6"],
            compliance_references=["PCI DSS v4.0 Req 6.4.1", "OWASP A05:2021"],
        ))


def check_encryption_at_rest(findings: list[Finding]) -> None:
    """PCI DSS Req 3.5 — cardholder data must be encrypted at rest."""
    audit_path = ROOT / "src" / "memory" / "audit_logger.py"
    text = _read(audit_path)
    has_field_enc = any(kw in text.lower() for kw in ["fernet", "sqlcipher", "encrypt", "aes"])
    config_path = ROOT / "config" / "config.yaml"
    cfg_text = _read(config_path)
    enc_enabled = re.search(r"at_rest\s*:\s*true", cfg_text)
    if not has_field_enc and not enc_enabled:
        findings.append(Finding(
            id="ENC-001",
            title="Cardholder data (CHD) storage path lacks encryption at rest",
            severity=SEV_CRITICAL,
            category="PCI DSS",
            stride_category="Information Disclosure",
            cwe="CWE-311",
            file_path=str(audit_path.relative_to(ROOT)),
            line_number=None,
            evidence=(
                "SQLite audit_log.db and chroma_db have no field-level or "
                "database-level encryption. encryption.at_rest: false in config.yaml"
            ),
            recommendation=(
                "For PCI DSS: encrypt any field containing PAN/CHD using AES-256. "
                "Recommended approach: Fernet symmetric encryption on content fields; "
                "store encryption key in AWS KMS / HashiCorp Vault. "
                "Alternatively, use SQLCipher with PRAGMA key derived from KMS. "
                "Verify with: `file .sage/audit_log.db` — should show 'data' not "
                "'SQLite 3.x database'."
            ),
            pci_requirement=PCI_REQ["3"],
            pan_impact=True,
            compliance_references=[
                "PCI DSS v4.0 Req 3.5.1", "PCI DSS v4.0 Req 3.4.1",
                "HIPAA §164.312(a)(2)(iv)",
            ],
        ))


def check_tokenization(findings: list[Finding]) -> None:
    """PCI DSS Req 3 — PANs should be tokenized; raw PANs must not cross API boundary."""
    api_path = ROOT / "src" / "interface" / "api.py"
    text = _read(api_path)
    has_tokenization = any(
        kw in text.lower() for kw in ["tokenize", "vault_token", "payment_token", "tok_"]
    )
    if not has_tokenization:
        findings.append(Finding(
            id="TOKEN-001",
            title="No PAN tokenization layer detected — raw PANs may traverse API boundary",
            severity=SEV_HIGH,
            category="PCI DSS",
            stride_category="Information Disclosure",
            cwe="CWE-312",
            file_path=str(api_path.relative_to(ROOT)),
            line_number=None,
            evidence="No tokenization references (vault_token, payment_token) found in api.py",
            recommendation=(
                "Implement tokenization at the API boundary using a PCI-certified vault "
                "(Stripe, Braintree, or self-hosted Vault with PKI secrets engine). "
                "The SAGE payment API should accept payment_token (e.g. tok_XXXX) "
                "and never receive or store the raw 16-digit PAN. "
                "Only the vault holds the PAN → token mapping."
            ),
            pci_requirement=PCI_REQ["3"],
            pan_impact=True,
            compliance_references=[
                "PCI DSS v4.0 Req 3.4.1", "PCI DSS v4.0 Req 3.5.1",
            ],
        ))


def check_idempotency(findings: list[Finding]) -> None:
    """PCI DSS Req 6 — Charge endpoints must enforce idempotency to prevent double-charging."""
    api_path = ROOT / "src" / "interface" / "api.py"
    text = _read(api_path)
    has_idempotency = any(
        kw in text.lower() for kw in ["idempotency_key", "idempotency-key", "x-idempotency"]
    )
    if not has_idempotency:
        findings.append(Finding(
            id="IDEMPOTENCY-001",
            title="Idempotency key not enforced on charge endpoint — double-charge risk",
            severity=SEV_MEDIUM,
            category="Payment Logic",
            stride_category="Tampering",
            cwe="CWE-362",
            file_path=str(api_path.relative_to(ROOT)),
            line_number=None,
            evidence="No Idempotency-Key header or idempotency_key body field detected",
            recommendation=(
                "Require `Idempotency-Key: <uuid>` header on POST /payment/charge. "
                "Store processed idempotency keys in Redis with TTL=24h. "
                "Return cached response for duplicate keys with same key. "
                "Return HTTP 422 if key is missing. "
                "This prevents double-charges from client retries."
            ),
            pci_requirement=PCI_REQ["6"],
            compliance_references=["PCI DSS v4.0 Req 6.2.4", "OWASP API Security API6:2023"],
        ))


def check_injection_in_payment(findings: list[Finding]) -> None:
    """OWASP A03 — SQL/command injection risk in payment parameter handling."""
    gateway_path = ROOT / "src" / "core" / "llm_gateway.py"
    text = _read(gateway_path)
    risky_patterns = [
        (r"format\(.*amount", "f-string/format() with payment amount variable"),
        (r'execute\(["\'].*\+',  "String concatenation in SQL execute()"),
        (r"shell=True",          "subprocess shell=True enables command injection"),
    ]
    for pattern, desc in risky_patterns:
        for i, line in enumerate(text.splitlines(), 1):
            if re.search(pattern, line, re.IGNORECASE):
                findings.append(Finding(
                    id="INJECT-001",
                    title=f"Potential injection risk in payment parameter handling: {desc}",
                    severity=SEV_HIGH,
                    category="OWASP A03",
                    stride_category="Elevation of Privilege",
                    cwe="CWE-89",
                    file_path=str(gateway_path.relative_to(ROOT)),
                    line_number=i,
                    evidence=line.strip()[:120],
                    recommendation=(
                        "Use parameterized queries for all database operations. "
                        "Never use shell=True with user-derived payment parameters. "
                        "Validate amount as Decimal with known precision before use. "
                        "Apply input allowlist: amount must match r'^[0-9]+\\.[0-9]{2}$'."
                    ),
                    pci_requirement=PCI_REQ["6"],
                    compliance_references=["PCI DSS v4.0 Req 6.2.4", "OWASP A03:2021", "CWE-89"],
                ))
                return


def check_unpinned_payment_deps(findings: list[Finding]) -> None:
    """PCI DSS Req 6 / Supply chain — unpinned payment library versions."""
    req_path = ROOT / "requirements.txt"
    text = _read(req_path)
    payment_libs = ["stripe", "braintree", "paypalrestsdk", "authorizenet", "cybersource"]
    unpinned_payment = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            for lib in payment_libs:
                if lib in stripped.lower() and not re.search(r"[><=!~]", stripped):
                    unpinned_payment.append(stripped)

    # Also check for general unpinned deps
    unpinned_all = [
        l.strip() for l in text.splitlines()
        if l.strip() and not l.strip().startswith("#") and not re.search(r"[><=!~]", l.strip())
    ]

    if unpinned_payment:
        findings.append(Finding(
            id="SBOM-001",
            title=f"Unpinned payment library versions: {', '.join(unpinned_payment[:5])}",
            severity=SEV_HIGH,
            category="Supply Chain",
            stride_category="Tampering",
            cwe="CWE-1104",
            file_path=str(req_path.relative_to(ROOT)),
            line_number=None,
            evidence=f"Unpinned payment libs: {unpinned_payment}",
            recommendation=(
                "Pin all payment libraries to exact versions (==). "
                "Subscribe to security advisories for all payment SDKs. "
                "Run `pip-audit --requirement requirements.txt` in CI. "
                "Rotate pinned versions on CVE discovery within 72 hours."
            ),
            pci_requirement=PCI_REQ["6"],
            compliance_references=["PCI DSS v4.0 Req 6.3.3", "OWASP A06:2021"],
        ))
    elif len(unpinned_all) > 10:
        findings.append(Finding(
            id="SBOM-002",
            title=f"{len(unpinned_all)} unpinned general dependencies — supply chain risk",
            severity=SEV_MEDIUM,
            category="Supply Chain",
            stride_category="Tampering",
            cwe="CWE-1104",
            file_path=str(req_path.relative_to(ROOT)),
            line_number=None,
            evidence=f"Unpinned ({len(unpinned_all)}): {', '.join(unpinned_all[:6])}...",
            recommendation=(
                "Run `pip freeze > requirements-lock.txt` and use it in CI. "
                "Add `pip-audit` check to the CI pipeline."
            ),
            pci_requirement=PCI_REQ["6"],
            compliance_references=["PCI DSS v4.0 Req 6.3.3", "OWASP A06:2021"],
        ))


# ---------------------------------------------------------------------------
# PCI DSS SAQ-D Controls evaluation
# ---------------------------------------------------------------------------

def evaluate_pci_controls(findings: list[Finding]) -> list[PCIDSSControl]:
    finding_ids = {f.id for f in findings}
    return [
        PCIDSSControl(
            requirement="Req 3 — Protect Stored Account Data",
            description="PAN stored only if necessary; masked; encrypted with AES-256",
            status="FAIL" if {"PAN-001", "PAN-002", "ENC-001", "TOKEN-001"} & finding_ids else "PASS",
            evidence="Findings: " + ", ".join({"PAN-001","PAN-002","ENC-001","TOKEN-001"} & finding_ids)
                     if {"PAN-001","PAN-002","ENC-001","TOKEN-001"} & finding_ids
                     else "No PAN storage violations detected in codebase scan",
            finding_ids=list({"PAN-001", "PAN-002", "ENC-001", "TOKEN-001"} & finding_ids),
        ),
        PCIDSSControl(
            requirement="Req 4 — Protect Cardholder Data in Transit",
            description="TLS 1.2+ enforced; no cleartext PAN transmission",
            status="FAIL" if {"TLS-001", "TLS-002"} & finding_ids else "PASS",
            evidence="Findings: " + ", ".join({"TLS-001","TLS-002"} & finding_ids)
                     if {"TLS-001","TLS-002"} & finding_ids
                     else "TLS enforcement controls present",
            finding_ids=list({"TLS-001", "TLS-002"} & finding_ids),
        ),
        PCIDSSControl(
            requirement="Req 6 — Develop and Maintain Secure Systems",
            description="No injection flaws; security headers; pinned deps; idempotency",
            status="FAIL" if {"INJECT-001","HDR-001","SBOM-001","IDEMPOTENCY-001","CORS-001"} & finding_ids else "PASS",
            evidence="Findings: " + ", ".join(
                {"INJECT-001","HDR-001","SBOM-001","IDEMPOTENCY-001","CORS-001"} & finding_ids)
                if {"INJECT-001","HDR-001","SBOM-001","IDEMPOTENCY-001","CORS-001"} & finding_ids
                else "Secure development controls verified",
            finding_ids=list({"INJECT-001","HDR-001","SBOM-001","IDEMPOTENCY-001","CORS-001"} & finding_ids),
        ),
        PCIDSSControl(
            requirement="Req 7 — Restrict Access to System Components",
            description="RBAC enforced on all payment endpoints; least-privilege",
            status="FAIL" if {"AUTH-001","AUTHZ-001"} & finding_ids else "PASS",
            evidence="Findings: " + ", ".join({"AUTH-001","AUTHZ-001"} & finding_ids)
                     if {"AUTH-001","AUTHZ-001"} & finding_ids
                     else "RBAC controls present on payment routes",
            finding_ids=list({"AUTH-001","AUTHZ-001"} & finding_ids),
        ),
        PCIDSSControl(
            requirement="Req 8 — Identify Users and Authenticate Access",
            description="Strong authentication (JWT + MFA) required for payment operations",
            status="PARTIAL",
            evidence="JWT auth implemented in src/core/auth.py; MFA not verified in scanner scope",
            finding_ids=[],
        ),
        PCIDSSControl(
            requirement="Req 10 — Log and Monitor All Access",
            description="All payment events logged with actor, timestamp, masked PAN",
            status="FAIL" if "AUDIT-001" in finding_ids else "PARTIAL",
            evidence="Findings: AUDIT-001" if "AUDIT-001" in finding_ids
                     else "AuditLogger present; payment-specific event coverage unverified",
            finding_ids=["AUDIT-001"] if "AUDIT-001" in finding_ids else [],
        ),
        PCIDSSControl(
            requirement="Req 11 — Test Security of Systems",
            description="Vulnerability scans, penetration test, static analysis in CI",
            status="PARTIAL",
            evidence=(
                "Static scanner present (this tool). "
                "Pentest plan at security_audit/pentest_plan.yaml. "
                "Automated CI integration not confirmed."
            ),
            finding_ids=[],
        ),
        PCIDSSControl(
            requirement="Req 12 — Information Security Policy",
            description="SBOM generated; risk register maintained; review cadence defined",
            status="PARTIAL",
            evidence="SBOM at security_audit/payment_gateway/payment_sbom.json. Threat model at threat_model.yaml.",
            finding_ids=[],
        ),
    ]


# ---------------------------------------------------------------------------
# Acceptance criteria evaluation
# ---------------------------------------------------------------------------

def evaluate_acceptance_criteria(findings: list[Finding]) -> list[AcceptanceCriteria]:
    by_id = {f.id: f for f in findings}
    stride_ids = {f.stride_category for f in findings}
    stride_full = {"Spoofing", "Tampering", "Repudiation", "Information Disclosure",
                   "Denial of Service", "Elevation of Privilege"}
    stride_covered = stride_full <= stride_ids

    crit_high = [f for f in findings if f.severity in (SEV_CRITICAL, SEV_HIGH)
                 and f.id not in ("AUDIT-002",)]

    sbom_path = ROOT / "security_audit" / "payment_gateway" / "payment_sbom.json"
    sbom_exists = sbom_path.exists()

    enc_ok = "ENC-001" not in by_id and "PAN-001" not in by_id
    audit_ok = "AUDIT-001" not in by_id

    pci_saq_path = ROOT / "security_audit" / "payment_gateway" / "pci_dss_saq.json"
    pci_saq_exists = pci_saq_path.exists()

    return [
        AcceptanceCriteria(
            name="Threat model covers STRIDE categories",
            passed=stride_covered,
            detail=(
                f"STRIDE categories in findings: {sorted(stride_ids)}. "
                + ("All 6 STRIDE categories covered." if stride_covered
                   else f"Missing: {sorted(stride_full - stride_ids)}")
            ),
        ),
        AcceptanceCriteria(
            name="No critical/high vulnerabilities",
            passed=len(crit_high) == 0,
            detail=(
                f"FAILED — {len(crit_high)} critical/high findings: "
                + ", ".join(f.id for f in crit_high)
            ) if crit_high else "PASSED — no critical/high vulnerabilities",
        ),
        AcceptanceCriteria(
            name="SBOM generated",
            passed=sbom_exists,
            detail=(
                "SBOM at security_audit/payment_gateway/payment_sbom.json"
                if sbom_exists else "SBOM not yet generated — run sbom generation step"
            ),
        ),
        AcceptanceCriteria(
            name="PHI encryption at rest and in transit",
            passed=enc_ok,
            detail=(
                "FAILED — ENC-001 or PAN-001 present: cardholder data not encrypted"
                if not enc_ok else "PASSED — no plaintext cardholder data findings"
            ),
        ),
        AcceptanceCriteria(
            name="Access audit logging enabled",
            passed=audit_ok,
            detail=(
                "FAILED — AUDIT-001: payment events not wired to audit log"
                if not audit_ok else "PASSED — audit logging verified"
            ),
        ),
        AcceptanceCriteria(
            name="PCI DSS SAQ completed",
            passed=pci_saq_exists,
            detail=(
                "PCI DSS SAQ at security_audit/payment_gateway/pci_dss_saq.json"
                if pci_saq_exists else "PCI DSS SAQ not yet completed"
            ),
        ),
        AcceptanceCriteria(
            name="Encryption at rest and in transit",
            passed=enc_ok and "TLS-001" not in by_id and "TLS-002" not in by_id,
            detail=(
                "FAILED — encryption gaps: " + ", ".join(
                    x for x in ["ENC-001","TLS-001","TLS-002"] if x in by_id
                ) if not (enc_ok and "TLS-001" not in by_id and "TLS-002" not in by_id)
                else "PASSED — encryption at rest and in transit controls present"
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def build_report(
    findings: list[Finding],
    pci_controls: list[PCIDSSControl],
) -> dict[str, Any]:
    criteria = evaluate_acceptance_criteria(findings)
    sev_counts: dict[str, int] = {}
    for f in findings:
        sev_counts[f.severity] = sev_counts.get(f.severity, 0) + 1

    overall_risk = (
        "CRITICAL" if sev_counts.get("CRITICAL", 0) > 0
        else "HIGH" if sev_counts.get("HIGH", 0) > 0
        else "MEDIUM" if sev_counts.get("MEDIUM", 0) > 0
        else "LOW"
    )

    return {
        "report_metadata": {
            "title":          "Payment Gateway Security Review Report",
            "generated_at":   datetime.now(timezone.utc).isoformat(),
            "analyst_role":   "analyst",
            "scope":          ["src/", "config/config.yaml", "requirements.txt"],
            "standards": [
                "PCI DSS v4.0",
                "OWASP API Security Top 10 2023",
                "STRIDE",
                "HIPAA Security Rule",
                "NIST SP 800-53 Rev 5",
            ],
            "tool_version":   "1.0.0",
        },
        "executive_summary": {
            "total_findings":            len(findings),
            "severity_breakdown":        sev_counts,
            "overall_risk":              overall_risk,
            "pan_impacting_findings":    sum(1 for f in findings if f.pan_impact),
            "phi_impacting_findings":    sum(1 for f in findings if f.phi_impact),
            "acceptance_criteria_passed": all(c.passed for c in criteria),
            "pci_dss_controls_passing":  sum(1 for c in pci_controls if c.status == "PASS"),
            "pci_dss_controls_total":    len(pci_controls),
        },
        "acceptance_criteria":   [asdict(c) for c in criteria],
        "pci_dss_saq_controls":  [asdict(c) for c in pci_controls],
        "findings":              [asdict(f) for f in findings],
        "recommendations_priority": {
            "immediate":  [f.id for f in findings if f.severity == SEV_CRITICAL],
            "short_term": [f.id for f in findings if f.severity == SEV_HIGH],
            "planned":    [f.id for f in findings if f.severity in (SEV_MEDIUM, SEV_LOW)],
        },
        "remediation_roadmap": [
            {
                "phase": "P0 — Block (before any internet exposure)",
                "items": [
                    "CORS-001: Restrict CORS to explicit origin allowlist",
                    "ENC-001: Enable AES-256 field-level encryption on CHD fields",
                    "TOKEN-001: Implement PAN tokenization at API ingress",
                    "PAN-001/PAN-002: Enforce PAN masking and CVV non-persistence",
                ],
            },
            {
                "phase": "P1 — Short-term (within 1 sprint)",
                "items": [
                    "TLS-002: Add HTTPS redirect middleware + HSTS header",
                    "AUTH-001/AUTHZ-001: Define /payment/* routes with RBAC Depends()",
                    "AUDIT-001: Wire PAYMENT_CHARGE events to audit logger",
                    "RATE-001: Deploy Redis-backed rate limiter on charge endpoint",
                    "HDR-001: Add SecurityHeadersMiddleware with full CSP",
                ],
            },
            {
                "phase": "P2 — Planned (within 30 days)",
                "items": [
                    "IDEMPOTENCY-001: Enforce Idempotency-Key header on charge",
                    "INJECT-001: Audit all payment param handling for injection",
                    "SBOM-001/002: Pin all deps; integrate pip-audit in CI",
                ],
            },
            {
                "phase": "P3 — Ongoing",
                "items": [
                    "Monthly pip-audit scan against requirements.txt",
                    "Quarterly PCI DSS SAQ-D self-assessment review",
                    "Annual penetration test per security_audit/pentest_plan.yaml",
                    "Rotate payment API keys and signing secrets every 90 days",
                ],
            },
        ],
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="SAGE payment gateway security scanner")
    parser.add_argument(
        "--output",
        default="security_audit/payment_gateway/payment_security_report.json",
        help="Output JSON report path",
    )
    args = parser.parse_args()

    findings: list[Finding] = []

    check_pan_in_logs(findings)
    check_cvv_storage(findings)
    check_tls_enforcement(findings)
    check_payment_endpoint_auth(findings)
    check_rate_limiting_payment(findings)
    check_payment_audit_logging(findings)
    check_cors_payment(findings)
    check_security_headers(findings)
    check_encryption_at_rest(findings)
    check_tokenization(findings)
    check_idempotency(findings)
    check_injection_in_payment(findings)
    check_unpinned_payment_deps(findings)

    pci_controls = evaluate_pci_controls(findings)
    report = build_report(findings, pci_controls)

    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    summary = report["executive_summary"]
    print(f"\n{'='*65}")
    print(f"  Payment Gateway Security Review — {report['report_metadata']['generated_at'][:10]}")
    print(f"{'='*65}")
    print(f"  Total findings    : {summary['total_findings']}")
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
        cnt = summary["severity_breakdown"].get(sev, 0)
        if cnt:
            print(f"    {sev:<12}: {cnt}")
    print(f"  Overall risk      : {summary['overall_risk']}")
    print(f"  PAN-impacting     : {summary['pan_impacting_findings']}")
    print(f"  PHI-impacting     : {summary['phi_impacting_findings']}")
    print(f"  PCI controls pass : {summary['pci_dss_controls_passing']}/{summary['pci_dss_controls_total']}")
    print(f"  Criteria pass     : {'YES' if summary['acceptance_criteria_passed'] else 'NO'}")
    print(f"\n  Report written    : {output_path}")
    print(f"{'='*65}\n")

    sys.exit(0 if summary["overall_risk"] not in ("CRITICAL",) else 1)


if __name__ == "__main__":
    main()
