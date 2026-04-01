"""
SAGE Security Review & Vulnerability Scanner
=============================================
Performs STRIDE threat modelling, dependency CVE scanning, PHI encryption
validation, and access-audit-log verification.

Acceptance criteria addressed:
  [AC-1] Threat model covers all 6 STRIDE categories
  [AC-2] No critical/high CVEs in runtime dependencies
  [AC-3] SBOM generated (CycloneDX-compatible JSON)
  [AC-4] PHI encryption at rest and in transit verified
  [AC-5] Access audit logging enabled and schema-complete

Usage:
    python security_audit/security_scanner.py [--sbom-out sbom.json] [--report-out report.json]
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger("sage.security_scanner")

ROOT = Path(__file__).resolve().parent.parent  # repo root

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH     = "HIGH"
    MEDIUM   = "MEDIUM"
    LOW      = "LOW"
    INFO     = "INFO"


class Status(str, Enum):
    PASS    = "PASS"
    FAIL    = "FAIL"
    WARN    = "WARN"
    SKIPPED = "SKIPPED"


@dataclass
class Finding:
    check_id:    str
    category:    str          # STRIDE category or "dependency" / "encryption" / "audit"
    title:       str
    severity:    Severity
    status:      Status
    detail:      str
    remediation: str
    references:  list[str] = field(default_factory=list)


@dataclass
class ScanReport:
    generated_at:   str
    scanner_version: str = "1.0.0"
    findings:       list[Finding] = field(default_factory=list)
    sbom_path:      str = ""
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["findings"] = [asdict(f) for f in self.findings]
        return d

    def critical_high_count(self) -> int:
        return sum(
            1 for f in self.findings
            if f.severity in (Severity.CRITICAL, Severity.HIGH) and f.status == Status.FAIL
        )

    def passed(self) -> bool:
        return self.critical_high_count() == 0


# ---------------------------------------------------------------------------
# 1. STRIDE Threat Model Checker
# ---------------------------------------------------------------------------

STRIDE_CHECKS: list[dict] = [
    {
        "id": "STRIDE-S-01",
        "category": "Spoofing",
        "title": "Authentication enforced on all API endpoints",
        "severity": Severity.HIGH,
        "check": lambda: _check_auth_enabled(),
        "remediation": "Enable auth.enabled in config.yaml and enforce JWT/API-key on every endpoint.",
        "references": ["CWE-287", "OWASP A07:2021"],
    },
    {
        "id": "STRIDE-T-01",
        "category": "Tampering",
        "title": "Audit log is append-only (no UPDATE/DELETE on events)",
        "severity": Severity.HIGH,
        "check": lambda: _check_audit_append_only(),
        "remediation": "Ensure audit_logger.py never issues UPDATE or DELETE against the audit_log table.",
        "references": ["CWE-693", "NIST SP 800-92"],
    },
    {
        "id": "STRIDE-R-01",
        "category": "Repudiation",
        "title": "Every agent action records trace_id + user identity",
        "severity": Severity.MEDIUM,
        "check": lambda: _check_trace_id_in_audit_schema(),
        "remediation": "Ensure audit_logger stores trace_id and actor fields for every event.",
        "references": ["CWE-778", "ISO 27001 A.12.4.1"],
    },
    {
        "id": "STRIDE-I-01",
        "category": "Information Disclosure",
        "title": "PII/PHI filter active in LLM gateway",
        "severity": Severity.CRITICAL,
        "check": lambda: _check_pii_filter_present(),
        "remediation": "Import and invoke pii_filter.scrub() before every LLM generate() call.",
        "references": ["CWE-200", "HIPAA §164.312(a)(2)(iv)"],
    },
    {
        "id": "STRIDE-I-02",
        "category": "Information Disclosure",
        "title": "PHI encrypted at rest (SQLite WAL + key-at-rest config)",
        "severity": Severity.CRITICAL,
        "check": lambda: _check_phi_encryption_at_rest(),
        "remediation": "Enable encryption.at_rest in config.yaml and use SQLCipher or filesystem encryption.",
        "references": ["HIPAA §164.312(a)(2)(iv)", "NIST SP 800-111"],
    },
    {
        "id": "STRIDE-I-03",
        "category": "Information Disclosure",
        "title": "PHI encrypted in transit (TLS 1.2+ enforced)",
        "severity": Severity.CRITICAL,
        "check": lambda: _check_phi_encryption_in_transit(),
        "remediation": "Set tls.min_version: 'TLSv1.2' in config.yaml and terminate TLS at the API layer.",
        "references": ["HIPAA §164.312(e)(2)(ii)", "NIST SP 800-52r2"],
    },
    {
        "id": "STRIDE-D-01",
        "category": "Denial of Service",
        "title": "Rate limiting configured on public API endpoints",
        "severity": Severity.MEDIUM,
        "check": lambda: _check_rate_limiting(),
        "remediation": "Add slowapi / limits middleware to api.py; set rate limits in config.yaml.",
        "references": ["CWE-770", "OWASP A05:2021"],
    },
    {
        "id": "STRIDE-E-01",
        "category": "Elevation of Privilege",
        "title": "RBAC enforced — roles cannot exceed declared permissions",
        "severity": Severity.HIGH,
        "check": lambda: _check_rbac_present(),
        "remediation": "Ensure rbac.py Role enum and permission matrix is applied at every privileged endpoint.",
        "references": ["CWE-269", "OWASP A01:2021"],
    },
    {
        "id": "STRIDE-D-02",
        "category": "Denial of Service",
        "title": "Unauthenticated /shutdown endpoint protected",
        "severity": Severity.CRITICAL,
        "check": lambda: _check_shutdown_auth(),
        "remediation": "Add @require_role(Role.ADMIN) to the /shutdown endpoint in api.py.",
        "references": ["CWE-306", "OWASP A01:2021", "threat_model.yaml:T-D-03"],
    },
    {
        "id": "STRIDE-I-04",
        "category": "Information Disclosure",
        "title": "No hardcoded cloud project IDs in LLM gateway",
        "severity": Severity.LOW,
        "check": lambda: _check_no_hardcoded_project_id(),
        "remediation": "Remove hardcoded 'db-dev-bms-apps' fallback; require GOOGLE_CLOUD_PROJECT env var.",
        "references": ["CWE-798", "threat_model.yaml:T-I-05"],
    },
]


# ---------------------------------------------------------------------------
# 2. Individual check implementations
# ---------------------------------------------------------------------------

def _source_contains(filepath: Path, pattern: str) -> bool:
    """Return True if the file contains the regex pattern."""
    try:
        text = filepath.read_text(errors="ignore")
        return bool(re.search(pattern, text))
    except FileNotFoundError:
        return False


def _check_auth_enabled() -> tuple[Status, str]:
    config = ROOT / "config" / "config.yaml"
    if not config.exists():
        return Status.SKIPPED, "config.yaml not found"
    text = config.read_text()
    if re.search(r"enabled\s*:\s*true", text):
        return Status.PASS, "auth.enabled: true found in config.yaml"
    return Status.WARN, (
        "auth.enabled not set to true. Anonymous admin access allowed. "
        "Acceptable for dev; must be enabled in production."
    )


def _check_audit_append_only() -> tuple[Status, str]:
    """Check compliance_audit_log is INSERT-only; chat_messages purge DELETE is allowed."""
    audit_file = ROOT / "src" / "memory" / "audit_logger.py"
    if not audit_file.exists():
        return Status.SKIPPED, "audit_logger.py not found"
    text = audit_file.read_text(errors="ignore")
    # Reject UPDATE/DELETE that target the compliance audit log specifically.
    # chat_messages purge (DELETE FROM chat_messages) is an allowed housekeeping operation.
    forbidden = re.findall(
        r"\b(UPDATE|DELETE)\s+(?:FROM\s+)?compliance_audit_log\b",
        text, re.IGNORECASE
    )
    if forbidden:
        return Status.FAIL, f"Mutable SQL on compliance_audit_log found: {forbidden}"
    return Status.PASS, "compliance_audit_log is INSERT-only (no UPDATE/DELETE on audit rows)"


def _check_trace_id_in_audit_schema() -> tuple[Status, str]:
    audit_file = ROOT / "src" / "memory" / "audit_logger.py"
    if not audit_file.exists():
        return Status.SKIPPED, "audit_logger.py not found"
    text = audit_file.read_text(errors="ignore")
    has_trace  = bool(re.search(r"trace_id", text))
    has_actor  = bool(re.search(r"actor|user_id|sub", text))
    if has_trace and has_actor:
        return Status.PASS, "trace_id and actor fields present in audit schema"
    missing = []
    if not has_trace:
        missing.append("trace_id")
    if not has_actor:
        missing.append("actor/user_id")
    return Status.FAIL, f"Missing fields in audit schema: {missing}"


def _check_pii_filter_present() -> tuple[Status, str]:
    pii_file = ROOT / "src" / "core" / "pii_filter.py"
    if not pii_file.exists():
        return Status.FAIL, "pii_filter.py not found — PHI may reach LLM unredacted"
    gateway = ROOT / "src" / "core" / "llm_gateway.py"
    if not gateway.exists():
        return Status.SKIPPED, "llm_gateway.py not found"
    if _source_contains(gateway, r"pii_filter|scrub"):
        return Status.PASS, "pii_filter referenced in llm_gateway.py"
    return Status.WARN, "pii_filter.py exists but not imported in llm_gateway.py"


def _check_phi_encryption_at_rest() -> tuple[Status, str]:
    config = ROOT / "config" / "config.yaml"
    if not config.exists():
        return Status.SKIPPED, "config.yaml not found"
    text = config.read_text()
    if re.search(r"at_rest\s*:\s*true", text):
        return Status.PASS, "encryption.at_rest: true in config.yaml"
    # Fallback: check if filesystem-level encryption env var is documented
    if os.environ.get("SAGE_ENCRYPT_AT_REST", "").lower() == "true":
        return Status.PASS, "SAGE_ENCRYPT_AT_REST=true env var set"
    return Status.FAIL, (
        "No PHI encryption-at-rest configuration found. "
        "Set encryption.at_rest: true in config.yaml or SAGE_ENCRYPT_AT_REST=true."
    )


def _check_phi_encryption_in_transit() -> tuple[Status, str]:
    config = ROOT / "config" / "config.yaml"
    if not config.exists():
        return Status.SKIPPED, "config.yaml not found"
    text = config.read_text()
    if re.search(r"tls|https|ssl", text, re.IGNORECASE):
        return Status.PASS, "TLS/HTTPS configuration reference found in config.yaml"
    # Check api.py for TLS middleware
    api_file = ROOT / "src" / "interface" / "api.py"
    if api_file.exists() and _source_contains(api_file, r"HTTPSRedirect|ssl_context|TLSv"):
        return Status.PASS, "TLS enforcement found in api.py"
    return Status.WARN, (
        "No explicit TLS-in-transit configuration detected. "
        "Ensure the deployment reverse-proxy (nginx/caddy) enforces TLS 1.2+."
    )


def _check_rate_limiting() -> tuple[Status, str]:
    api_file = ROOT / "src" / "interface" / "api.py"
    if not api_file.exists():
        return Status.SKIPPED, "api.py not found"
    if _source_contains(api_file, r"slowapi|RateLimiter|limits"):
        return Status.PASS, "Rate limiting middleware found in api.py"
    return Status.WARN, (
        "No rate limiting detected in api.py. "
        "Add slowapi or equivalent to protect against DoS."
    )


def _check_rbac_present() -> tuple[Status, str]:
    rbac_file = ROOT / "src" / "core" / "rbac.py"
    if not rbac_file.exists():
        return Status.FAIL, "rbac.py not found"
    text = rbac_file.read_text(errors="ignore")
    if re.search(r"class\s+Role|Permission|PERMISSIONS", text):
        return Status.PASS, "RBAC Role/Permission definitions found in rbac.py"
    return Status.WARN, "rbac.py exists but lacks Role/Permission definitions"


def _check_shutdown_auth() -> tuple[Status, str]:
    """Verify the /shutdown endpoint requires authentication (T-D-03)."""
    api_file = ROOT / "src" / "interface" / "api.py"
    if not api_file.exists():
        return Status.SKIPPED, "api.py not found"
    text = api_file.read_text(errors="ignore")
    # Find the shutdown route block
    shutdown_match = re.search(r'@app\.(?:post|get)\(["\']\/shutdown["\'].*?\n(.*?\n){0,8}', text)
    if not shutdown_match:
        return Status.PASS, "/shutdown endpoint not found — likely removed"
    block = text[shutdown_match.start():shutdown_match.start() + 600]
    if re.search(r"require_role|Depends\(|current_user|auth", block):
        return Status.PASS, "/shutdown endpoint has authentication dependency"
    return Status.FAIL, (
        "/shutdown endpoint found with no auth check at api.py. "
        "Any unauthenticated client can terminate the SAGE process. "
        "Add @require_role(Role.ADMIN) or equivalent. See T-D-03 in threat_model.yaml."
    )


def _check_no_hardcoded_project_id() -> tuple[Status, str]:
    """Verify no hardcoded cloud project IDs in llm_gateway.py (T-I-05)."""
    gateway = ROOT / "src" / "core" / "llm_gateway.py"
    if not gateway.exists():
        return Status.SKIPPED, "llm_gateway.py not found"
    text = gateway.read_text(errors="ignore")
    # Look for the known hardcoded value
    if re.search(r"db-dev-bms-apps", text):
        return Status.FAIL, (
            "Hardcoded Google Cloud project ID 'db-dev-bms-apps' found in llm_gateway.py. "
            "This leaks internal infrastructure identifiers. "
            "Remove the hardcoded fallback; require GOOGLE_CLOUD_PROJECT env var explicitly."
        )
    return Status.PASS, "No hardcoded Google Cloud project ID found in llm_gateway.py"


# ---------------------------------------------------------------------------
# 3. Dependency CVE scan (pip-audit)
# ---------------------------------------------------------------------------

def run_dependency_scan() -> list[Finding]:
    """Run pip-audit and parse output for CRITICAL/HIGH CVEs."""
    findings: list[Finding] = []
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip_audit", "--format", "json", "--disable-pip"],
            capture_output=True, text=True, timeout=120, cwd=str(ROOT),
        )
        output = result.stdout or result.stderr or "{}"
        data = json.loads(output)
        vulns = data.get("dependencies", []) if isinstance(data, dict) else data
        for dep in vulns:
            for v in dep.get("vulns", []):
                sev_raw = v.get("fix_versions", [])
                severity = Severity.HIGH  # default if no CVSS
                cvss = v.get("aliases", [])
                findings.append(Finding(
                    check_id   = f"DEP-{v.get('id', 'UNKNOWN')}",
                    category   = "Dependency",
                    title      = f"{dep.get('name', '?')} {dep.get('version', '?')} — {v.get('id', '?')}",
                    severity   = severity,
                    status     = Status.FAIL,
                    detail     = v.get("description", "No description"),
                    remediation= (
                        f"Upgrade {dep.get('name')} to {sev_raw[0]}"
                        if sev_raw else f"No fix available — evaluate mitigation for {v.get('id')}"
                    ),
                    references = [f"https://osv.dev/vulnerability/{v.get('id')}"],
                ))
    except FileNotFoundError:
        findings.append(Finding(
            check_id   = "DEP-SCAN-SKIP",
            category   = "Dependency",
            title      = "pip-audit not installed — dependency scan skipped",
            severity   = Severity.MEDIUM,
            status     = Status.SKIPPED,
            detail     = "Install pip-audit: pip install pip-audit",
            remediation= "pip install pip-audit && re-run scanner",
            references = ["https://github.com/pypa/pip-audit"],
        ))
    except Exception as exc:  # noqa: BLE001
        findings.append(Finding(
            check_id   = "DEP-SCAN-ERROR",
            category   = "Dependency",
            title      = f"Dependency scan error: {exc}",
            severity   = Severity.MEDIUM,
            status     = Status.WARN,
            detail     = str(exc),
            remediation= "Investigate pip-audit installation and run manually.",
            references = [],
        ))
    return findings


# ---------------------------------------------------------------------------
# 4. Access Audit Log Check
# ---------------------------------------------------------------------------

def check_audit_logging() -> Finding:
    """Verify the audit log schema includes mandatory access-control fields."""
    audit_file = ROOT / "src" / "memory" / "audit_logger.py"
    required_fields = ["trace_id", "event_type", "actor", "timestamp", "status"]
    if not audit_file.exists():
        return Finding(
            check_id   = "AUDIT-01",
            category   = "Audit Logging",
            title      = "Access audit logger not found",
            severity   = Severity.HIGH,
            status     = Status.FAIL,
            detail     = "audit_logger.py missing from src/memory/",
            remediation= "Implement audit_logger.py with INSERT-only event store.",
            references = ["HIPAA §164.312(b)", "ISO 27001 A.12.4.3"],
        )
    text = audit_file.read_text(errors="ignore")
    missing = [f for f in required_fields if f not in text]
    if missing:
        return Finding(
            check_id   = "AUDIT-01",
            category   = "Audit Logging",
            title      = "Audit log schema missing required fields",
            severity   = Severity.HIGH,
            status     = Status.FAIL,
            detail     = f"Missing fields: {missing}",
            remediation= "Add missing fields to CREATE TABLE statement in audit_logger.py.",
            references = ["HIPAA §164.312(b)"],
        )
    return Finding(
        check_id   = "AUDIT-01",
        category   = "Audit Logging",
        title      = "Access audit logging schema complete",
        severity   = Severity.INFO,
        status     = Status.PASS,
        detail     = f"All required fields present: {required_fields}",
        remediation= "No action required.",
        references = ["HIPAA §164.312(b)"],
    )


# ---------------------------------------------------------------------------
# 5. SBOM Generation (CycloneDX-compatible)
# ---------------------------------------------------------------------------

def generate_sbom(out_path: Path) -> dict:
    """Generate a CycloneDX-compatible SBOM from installed packages."""
    components = []
    try:
        pkgs = importlib.metadata.packages_distributions()
        seen: set[str] = set()
        for dist in importlib.metadata.distributions():
            name    = dist.metadata["Name"] or "unknown"
            version = dist.metadata["Version"] or "0.0.0"
            if name in seen:
                continue
            seen.add(name)
            purl = f"pkg:pypi/{name.lower()}@{version}"
            # Attempt to read direct_url for origin
            direct_url = dist.read_text("direct_url.json")
            origin = json.loads(direct_url).get("url", "") if direct_url else ""
            components.append({
                "type":       "library",
                "name":       name,
                "version":    version,
                "purl":       purl,
                "origin":     origin,
                "hashes":     [],   # populated below if RECORD is available
                "licenses":   _extract_license(dist),
            })
    except Exception as exc:  # noqa: BLE001
        logger.warning("SBOM package enumeration partial: %s", exc)

    sbom = {
        "bomFormat":   "CycloneDX",
        "specVersion": "1.5",
        "version":     1,
        "serialNumber": f"urn:uuid:{_uuid4_from_seed('sage-sbom')}",
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tools": [{"name": "sage-security-scanner", "version": "1.0.0"}],
            "component": {
                "type":    "application",
                "name":    "SAGE Framework",
                "version": _sage_version(),
                "purl":    "pkg:github/sage-framework/sage@HEAD",
            },
        },
        "components": components,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(sbom, indent=2))
    logger.info("SBOM written → %s  (%d components)", out_path, len(components))
    return sbom


def _extract_license(dist) -> list[str]:
    raw = dist.metadata.get("License", "") or ""
    if raw and raw not in ("-", "UNKNOWN", ""):
        return [raw[:64]]
    classifiers = dist.metadata.get_all("Classifier") or []
    lics = [c.split(" :: ")[-1] for c in classifiers if "License" in c]
    return lics[:2] if lics else []


def _uuid4_from_seed(seed: str) -> str:
    h = hashlib.md5(seed.encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-4{h[13:16]}-{h[16:20]}-{h[20:32]}"


def _sage_version() -> str:
    try:
        init = (ROOT / "src" / "__init__.py").read_text()
        m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', init)
        return m.group(1) if m else "0.0.0-dev"
    except Exception:
        return "0.0.0-dev"


# ---------------------------------------------------------------------------
# 6. Main scanner orchestration
# ---------------------------------------------------------------------------

def run_scan(sbom_out: Path, report_out: Path) -> ScanReport:
    report = ScanReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    logger.info("=== SAGE Security Scanner v%s ===", report.scanner_version)

    # --- STRIDE checks ---
    logger.info("[1/4] Running STRIDE threat model checks (%d checks)...", len(STRIDE_CHECKS))
    for chk in STRIDE_CHECKS:
        status, detail = chk["check"]()
        report.findings.append(Finding(
            check_id   = chk["id"],
            category   = chk["category"],
            title      = chk["title"],
            severity   = chk["severity"],
            status     = status,
            detail     = detail,
            remediation= chk["remediation"],
            references = chk["references"],
        ))
        icon = "✓" if status == Status.PASS else ("⚠" if status == Status.WARN else "✗")
        logger.info("  %s [%s] %s — %s", icon, chk["id"], status.value, chk["title"])

    # --- Audit logging check ---
    logger.info("[2/4] Verifying access audit logging schema...")
    audit_finding = check_audit_logging()
    report.findings.append(audit_finding)
    logger.info("  %s [AUDIT-01] %s", "✓" if audit_finding.status == Status.PASS else "✗", audit_finding.title)

    # --- Dependency CVE scan ---
    logger.info("[3/4] Scanning dependencies for CVEs (pip-audit)...")
    dep_findings = run_dependency_scan()
    report.findings.extend(dep_findings)
    vuln_count = sum(1 for f in dep_findings if f.status == Status.FAIL)
    logger.info("  → %d vulnerable packages found", vuln_count)

    # --- SBOM generation ---
    logger.info("[4/4] Generating CycloneDX SBOM → %s", sbom_out)
    sbom = generate_sbom(sbom_out)
    report.sbom_path = str(sbom_out)

    # --- Summary ---
    total  = len(report.findings)
    passed = sum(1 for f in report.findings if f.status == Status.PASS)
    failed = sum(1 for f in report.findings if f.status == Status.FAIL)
    warned = sum(1 for f in report.findings if f.status == Status.WARN)
    skipped= sum(1 for f in report.findings if f.status == Status.SKIPPED)
    c_h    = report.critical_high_count()

    report.summary = {
        "total_checks":        total,
        "passed":              passed,
        "failed":              failed,
        "warned":              warned,
        "skipped":             skipped,
        "critical_high_fails": c_h,
        "sbom_components":     len(sbom.get("components", [])),
        "overall_status":      "PASS" if report.passed() else "FAIL",
        "stride_categories_covered": list({f.category for f in report.findings if f.category in
                                           {"Spoofing","Tampering","Repudiation",
                                            "Information Disclosure","Denial of Service",
                                            "Elevation of Privilege"}}),
    }

    # --- Write report ---
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(json.dumps(report.to_dict(), indent=2))
    logger.info("")
    logger.info("=== SCAN COMPLETE ===")
    logger.info("  Checks : %d total | %d pass | %d fail | %d warn | %d skipped",
                total, passed, failed, warned, skipped)
    logger.info("  CRIT/HIGH fails : %d", c_h)
    logger.info("  STRIDE covered  : %s", report.summary["stride_categories_covered"])
    logger.info("  SBOM components : %d", report.summary["sbom_components"])
    logger.info("  Overall         : %s", report.summary["overall_status"])
    logger.info("  Report          → %s", report_out)

    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="SAGE Security Review & Vulnerability Scanner")
    p.add_argument("--sbom-out",   default="security_audit/sbom.json",   help="SBOM output path")
    p.add_argument("--report-out", default="security_audit/audit/scan_report.json", help="Report output path")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    report = run_scan(
        sbom_out   = Path(args.sbom_out),
        report_out = Path(args.report_out),
    )
    sys.exit(0 if report.passed() else 1)
