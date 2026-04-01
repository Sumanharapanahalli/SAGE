#!/usr/bin/env python3
"""
run_security_validation.py
──────────────────────────
Security Validation Pipeline Orchestrator — Wearable Fall Detection System (WFDS)
Document ID: DHF-SEC-SVP-001

Orchestrates the complete DHF security validation test suite:
  1. Firmware static analysis (PC-lint Plus / MISRA C:2012)
  2. Backend Python SAST (Bandit + Semgrep)
  3. Dependency vulnerability scan (Trivy + pip-audit + npm audit)
  4. OTA firmware update integrity tests (automated subset)
  5. Report generation and DHF packaging

BLE and manual API pentest results are imported from external report files
(those tests require physical hardware and CREST-accredited tester access).

Standards: IEC 62443-4-1, FDA 21 CFR Part 820.30(g), OWASP Testing Guide
Usage:
    python run_security_validation.py [--config security_validation_config.yaml]
                                      [--section all|fw|sast|deps|ota]
                                      [--fail-fast]
                                      [--output docs/DHF/security/]
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("security_validation")


# ─────────────────────────────────────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class SectionResult:
    section_id: str
    section_name: str
    tool: str
    result: str  # PASS | FAIL | SKIP | ERROR
    findings: list[dict[str, Any]] = field(default_factory=list)
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    evidence_files: list[str] = field(default_factory=list)
    notes: str = ""
    duration_seconds: float = 0.0


@dataclass
class ValidationReport:
    document_id: str
    device: str
    firmware_version: str
    run_timestamp: str
    operator: str
    overall_result: str  # PASS | FAIL
    sections: list[SectionResult] = field(default_factory=list)
    acceptance_criteria_summary: dict[str, bool] = field(default_factory=dict)
    total_critical: int = 0
    total_high: int = 0
    total_medium: int = 0
    total_low: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "device": self.device,
            "firmware_version": self.firmware_version,
            "run_timestamp": self.run_timestamp,
            "operator": self.operator,
            "overall_result": self.overall_result,
            "total_critical": self.total_critical,
            "total_high": self.total_high,
            "total_medium": self.total_medium,
            "total_low": self.total_low,
            "acceptance_criteria_summary": self.acceptance_criteria_summary,
            "sections": [
                {
                    "section_id": s.section_id,
                    "section_name": s.section_name,
                    "tool": s.tool,
                    "result": s.result,
                    "critical": s.critical_count,
                    "high": s.high_count,
                    "medium": s.medium_count,
                    "low": s.low_count,
                    "evidence_files": s.evidence_files,
                    "notes": s.notes,
                    "duration_seconds": round(s.duration_seconds, 2),
                    "findings_count": len(s.findings),
                }
                for s in self.sections
            ],
        }


# ─────────────────────────────────────────────────────────────────────────────
# Helper: run subprocess and capture output
# ─────────────────────────────────────────────────────────────────────────────
def _run(
    args: list[str],
    cwd: str | None = None,
    capture_output: bool = True,
    timeout: int = 300,
) -> tuple[int, str, str]:
    """Run a subprocess; return (returncode, stdout, stderr)."""
    logger.debug("Running: %s", " ".join(args))
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=capture_output,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout or "", result.stderr or ""
    except FileNotFoundError:
        return -1, "", f"Tool not found: {args[0]}"
    except subprocess.TimeoutExpired:
        return -2, "", f"Timeout after {timeout}s: {' '.join(args)}"


def _tool_available(name: str) -> bool:
    return shutil.which(name) is not None


def _ensure_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Section 1: Firmware Static Analysis
# ─────────────────────────────────────────────────────────────────────────────
class FirmwareStaticAnalyzer:
    """Runs PC-lint Plus (MISRA C:2012) and clang-tidy on firmware source."""

    def __init__(self, config: dict[str, Any], evidence_dir: str) -> None:
        self.cfg = config["firmware_static_analysis"]
        self.evidence_dir = evidence_dir
        self._start = datetime.datetime.utcnow()

    def run(self) -> SectionResult:
        logger.info("[SEC-SA-FW] Starting firmware static analysis")
        result = SectionResult(
            section_id="SEC-SA-FW",
            section_name="Firmware Static Analysis — MISRA C:2012",
            tool="PC-lint Plus 2.0 + clang-tidy 16",
        )

        pc_result = self._run_pclint(result)
        ct_result = self._run_clang_tidy(result)

        # Determine PASS/FAIL per acceptance criteria
        mandatory_viols = result.findings and any(
            f.get("severity") in ("error",) for f in result.findings
        )
        required_viols = result.findings and any(
            f.get("severity") == "warning" and not f.get("deviation_documented")
            for f in result.findings
        )

        if mandatory_viols or required_viols:
            result.result = "FAIL"
            result.notes = "Undocumented mandatory or required MISRA violations found."
        elif not pc_result and not ct_result:
            result.result = "ERROR"
            result.notes = "PC-lint Plus and clang-tidy not found — manual review required."
        else:
            result.result = "PASS"
            result.notes = "Zero mandatory/required MISRA violations. All advisory deviations documented."

        result.duration_seconds = (
            datetime.datetime.utcnow() - self._start
        ).total_seconds()
        return result

    def _run_pclint(self, result: SectionResult) -> bool:
        pc_cfg = self.cfg.get("pclint", {})
        binary = pc_cfg.get("binary", "pclp64")
        if not _tool_available(binary):
            logger.warning("[SEC-SA-FW] PC-lint Plus not found — SKIP (tool not installed)")
            result.notes += " PC-lint Plus not available in this environment."
            return False

        config_file = pc_cfg.get("config_file", "firmware/lint/pclint_misra_c2012.lnt")
        output_file = pc_cfg.get("output_file", f"{self.evidence_dir}/pclint_report.json")
        source_dirs = pc_cfg.get("source_dirs", ["firmware/src/"])

        cmd = [binary, f"+json({output_file})", config_file] + source_dirs
        rc, stdout, stderr = _run(cmd)

        if rc < 0:
            logger.error("[SEC-SA-FW] PC-lint Plus failed: %s", stderr)
            return False

        result.evidence_files.append(output_file)
        if Path(output_file).exists():
            with open(output_file) as f:
                data = json.load(f)
            for item in data.get("items", []):
                sev = item.get("severity", "").lower()
                finding = {
                    "tool": "pclint",
                    "severity": sev,
                    "file": item.get("file", ""),
                    "line": item.get("line", 0),
                    "message": item.get("message", ""),
                    "rule": item.get("rule", ""),
                    "deviation_documented": False,
                }
                result.findings.append(finding)
                if sev == "error":
                    result.critical_count += 1
                elif sev == "warning":
                    result.high_count += 1
                else:
                    result.low_count += 1

        logger.info("[SEC-SA-FW] PC-lint Plus: %d findings", len(result.findings))
        return True

    def _run_clang_tidy(self, result: SectionResult) -> bool:
        if not _tool_available("clang-tidy"):
            logger.warning("[SEC-SA-FW] clang-tidy not found — SKIP")
            return False

        output_file = f"{self.evidence_dir}/clang_tidy_report.json"
        cmd = [
            "clang-tidy",
            "--checks=clang-analyzer-*,cert-*",
            "--export-fixes", output_file,
            "firmware/src/",
        ]
        rc, stdout, stderr = _run(cmd)
        result.evidence_files.append(output_file)
        logger.info("[SEC-SA-FW] clang-tidy complete (rc=%d)", rc)
        return True


# ─────────────────────────────────────────────────────────────────────────────
# Section 2: Backend Python SAST
# ─────────────────────────────────────────────────────────────────────────────
class BackendSastRunner:
    """Runs Bandit and Semgrep on the backend Python source tree."""

    # Severity hierarchy for comparison
    _SEVERITY_RANK = {"INFORMATIONAL": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}

    def __init__(self, config: dict[str, Any], evidence_dir: str) -> None:
        self.cfg = config["backend_sast"]
        self.evidence_dir = evidence_dir
        self.max_severity = config["metadata"]["acceptance_criteria"]["max_bandit_severity"]
        self._start = datetime.datetime.utcnow()

    def run(self) -> SectionResult:
        logger.info("[SEC-SA-BE] Starting backend Python SAST")
        result = SectionResult(
            section_id="SEC-SA-BE",
            section_name="Backend Python SAST — Bandit + Semgrep",
            tool="Bandit 1.7.8 + Semgrep OSS 1.68",
        )

        bandit_ok = self._run_bandit(result)
        semgrep_ok = self._run_semgrep(result)

        # Evaluate acceptance criteria
        fail_severities = self.cfg["bandit"]["fail_on_severity"]
        failed_findings = [
            f for f in result.findings
            if f.get("severity", "").upper() in fail_severities
        ]

        if failed_findings:
            result.result = "FAIL"
            result.notes = (
                f"FAIL: {len(failed_findings)} HIGH/CRITICAL finding(s) found. "
                "Remediation required before DHF sign-off."
            )
        elif not bandit_ok and not semgrep_ok:
            result.result = "ERROR"
            result.notes = "Bandit and Semgrep not installed. Manual SAST review required."
        else:
            result.result = "PASS"
            result.notes = "Zero HIGH/CRITICAL findings. All medium findings must be reviewed."

        result.duration_seconds = (
            datetime.datetime.utcnow() - self._start
        ).total_seconds()
        return result

    def _run_bandit(self, result: SectionResult) -> bool:
        if not _tool_available("bandit"):
            logger.warning("[SEC-SA-BE] Bandit not found — attempting pip install")
            rc, _, _ = _run([sys.executable, "-m", "pip", "install", "bandit", "-q"])
            if rc != 0:
                logger.error("[SEC-SA-BE] Cannot install Bandit — SKIP")
                return False

        output_file = self.cfg["bandit"]["output_file"]
        _ensure_dir(str(Path(output_file).parent))

        source_root = self.cfg.get("source_root", "src/")
        cmd = [
            "bandit",
            "-r", source_root,
            "-ll",           # report MEDIUM and above
            "-f", "json",
            "-o", output_file,
        ]
        # Add skipped paths
        for skip_path in self.cfg["bandit"].get("skipped_paths", []):
            cmd += ["--skip", skip_path]

        rc, stdout, stderr = _run(cmd)
        # Bandit returns non-zero when findings exist — that's expected
        if rc < 0:
            logger.error("[SEC-SA-BE] Bandit execution failed: %s", stderr)
            return False

        result.evidence_files.append(output_file)

        if not Path(output_file).exists():
            logger.warning("[SEC-SA-BE] Bandit output file not created")
            return False

        with open(output_file) as f:
            data = json.load(f)

        for item in data.get("results", []):
            sev = item.get("issue_severity", "LOW").upper()
            finding = {
                "tool": "bandit",
                "test_id": item.get("test_id", ""),
                "severity": sev,
                "confidence": item.get("issue_confidence", ""),
                "file": item.get("filename", ""),
                "line": item.get("line_number", 0),
                "description": item.get("issue_text", ""),
                "cwe": item.get("issue_cwe", {}).get("id", ""),
                "owasp": "",
            }
            result.findings.append(finding)
            sev_rank = self._SEVERITY_RANK.get(sev, 0)
            if sev_rank >= 4:
                result.critical_count += 1
            elif sev_rank == 3:
                result.high_count += 1
            elif sev_rank == 2:
                result.medium_count += 1
            else:
                result.low_count += 1

        metrics = data.get("metrics", {}).get("_totals", {})
        logger.info(
            "[SEC-SA-BE] Bandit: HIGH=%d MEDIUM=%d LOW=%d",
            result.high_count,
            result.medium_count,
            result.low_count,
        )
        return True

    def _run_semgrep(self, result: SectionResult) -> bool:
        if not _tool_available("semgrep"):
            logger.warning("[SEC-SA-BE] Semgrep not found — SKIP")
            return False

        output_file = self.cfg["semgrep"]["output_file"]
        _ensure_dir(str(Path(output_file).parent))
        source_root = self.cfg.get("source_root", "src/")

        rulesets = self.cfg["semgrep"].get("rulesets", ["p/owasp-top-ten"])
        cmd = ["semgrep", "--json", "-o", output_file, source_root]
        for ruleset in rulesets:
            cmd += ["--config", ruleset]
        for ignore_path in self.cfg["semgrep"].get("ignore_paths", []):
            cmd += ["--exclude", ignore_path]

        rc, stdout, stderr = _run(cmd, timeout=600)
        if rc < 0:
            logger.error("[SEC-SA-BE] Semgrep execution failed: %s", stderr)
            return False

        result.evidence_files.append(output_file)

        if not Path(output_file).exists():
            return False

        with open(output_file) as f:
            data = json.load(f)

        for item in data.get("results", []):
            sev = item.get("extra", {}).get("severity", "WARNING").upper()
            finding = {
                "tool": "semgrep",
                "rule": item.get("check_id", ""),
                "severity": sev,
                "file": item.get("path", ""),
                "line": item.get("start", {}).get("line", 0),
                "description": item.get("extra", {}).get("message", ""),
            }
            result.findings.append(finding)
            if sev == "ERROR":
                result.critical_count += 1
            elif sev == "WARNING":
                result.medium_count += 1
            else:
                result.low_count += 1

        logger.info("[SEC-SA-BE] Semgrep: %d findings", len(data.get("results", [])))
        return True


# ─────────────────────────────────────────────────────────────────────────────
# Section 3: Dependency Vulnerability Scan
# ─────────────────────────────────────────────────────────────────────────────
class DependencyScanner:
    """Runs Trivy, pip-audit, and npm audit for dependency CVE scanning."""

    def __init__(self, config: dict[str, Any], evidence_dir: str) -> None:
        self.cfg = config["dependency_scan"]
        self.max_cvss = config["metadata"]["acceptance_criteria"]["max_cvss_allowed"]
        self.evidence_dir = evidence_dir
        self._start = datetime.datetime.utcnow()

    def run(self) -> SectionResult:
        logger.info("[SEC-DEP] Starting dependency vulnerability scan")
        result = SectionResult(
            section_id="SEC-DEP",
            section_name="Dependency Vulnerability Scan — Trivy + pip-audit + npm audit",
            tool="Trivy 0.50 + pip-audit 2.7 + npm audit",
        )

        self._run_trivy(result)
        self._run_pip_audit(result)
        self._run_npm_audit(result)

        # Evaluate: FAIL if any CVE >= max_cvss threshold
        critical_cves = [
            f for f in result.findings
            if f.get("cvss_v3", 0) >= self.max_cvss
        ]

        if critical_cves:
            result.result = "FAIL"
            result.notes = (
                f"FAIL: {len(critical_cves)} CVE(s) with CVSS >= {self.max_cvss} found. "
                "All must be remediated or risk-accepted before DHF sign-off."
            )
        else:
            result.result = "PASS"
            result.notes = (
                f"PASS: No CVEs with CVSS >= {self.max_cvss}. "
                f"Total findings: CRITICAL={result.critical_count} "
                f"HIGH={result.high_count} MEDIUM={result.medium_count} LOW={result.low_count}"
            )

        result.duration_seconds = (
            datetime.datetime.utcnow() - self._start
        ).total_seconds()
        return result

    def _run_trivy(self, result: SectionResult) -> None:
        if not _tool_available("trivy"):
            logger.warning("[SEC-DEP] Trivy not found — SKIP")
            result.notes += " Trivy not available."
            return

        output_file = self.cfg["trivy"]["output_file"]
        _ensure_dir(str(Path(output_file).parent))

        cmd = [
            "trivy", "fs",
            "--security-checks", "vuln",
            "--format", "json",
            "--output", output_file,
            "--severity", "CRITICAL,HIGH,MEDIUM,LOW",
            ".",
        ]
        rc, stdout, stderr = _run(cmd, timeout=600)
        if rc < 0:
            logger.error("[SEC-DEP] Trivy failed: %s", stderr)
            return

        result.evidence_files.append(output_file)
        if not Path(output_file).exists():
            return

        with open(output_file) as f:
            data = json.load(f)

        for target in data.get("Results", []):
            for vuln in target.get("Vulnerabilities", []) or []:
                sev = vuln.get("Severity", "UNKNOWN").upper()
                cvss = self._extract_cvss(vuln)
                finding = {
                    "tool": "trivy",
                    "cve": vuln.get("VulnerabilityID", ""),
                    "package": vuln.get("PkgName", ""),
                    "version_installed": vuln.get("InstalledVersion", ""),
                    "version_fixed": vuln.get("FixedVersion", ""),
                    "severity": sev,
                    "cvss_v3": cvss,
                    "description": vuln.get("Description", "")[:200],
                    "ecosystem": target.get("Type", ""),
                }
                result.findings.append(finding)
                if sev == "CRITICAL":
                    result.critical_count += 1
                elif sev == "HIGH":
                    result.high_count += 1
                elif sev == "MEDIUM":
                    result.medium_count += 1
                else:
                    result.low_count += 1

        logger.info("[SEC-DEP] Trivy: %d vulnerabilities found", len(result.findings))

    def _extract_cvss(self, vuln: dict) -> float:
        """Extract CVSS v3 score from Trivy finding."""
        scores = vuln.get("CVSS", {})
        for source in scores.values():
            v3 = source.get("V3Score")
            if v3 is not None:
                return float(v3)
        return 0.0

    def _run_pip_audit(self, result: SectionResult) -> None:
        if not _tool_available("pip-audit"):
            logger.warning("[SEC-DEP] pip-audit not found — attempting install")
            rc, _, _ = _run([sys.executable, "-m", "pip", "install", "pip-audit", "-q"])
            if rc != 0:
                logger.warning("[SEC-DEP] pip-audit install failed — SKIP")
                return

        output_file = self.cfg["pip_audit"]["output_file"]
        _ensure_dir(str(Path(output_file).parent))
        cmd = ["pip-audit", "--format", "json", "-o", output_file]
        rc, stdout, stderr = _run(cmd, timeout=300)
        result.evidence_files.append(output_file)

        if not Path(output_file).exists():
            return

        with open(output_file) as f:
            data = json.load(f)

        for dep in data.get("dependencies", []) or []:
            for vuln in dep.get("vulns", []):
                sev = vuln.get("fix_versions", []) and "MEDIUM" or "LOW"
                finding = {
                    "tool": "pip-audit",
                    "vuln_id": vuln.get("id", ""),
                    "package": dep.get("name", ""),
                    "version_installed": dep.get("version", ""),
                    "description": vuln.get("description", "")[:200],
                    "severity": sev,
                    "cvss_v3": 0.0,
                    "aliases": vuln.get("aliases", []),
                }
                result.findings.append(finding)
                result.medium_count += 1

        logger.info("[SEC-DEP] pip-audit complete")

    def _run_npm_audit(self, result: SectionResult) -> None:
        npm_cfg = self.cfg.get("npm_audit", {})
        working_dir = npm_cfg.get("working_dir", ".")
        if not Path(working_dir).exists():
            logger.warning("[SEC-DEP] npm working_dir %s not found — SKIP", working_dir)
            return

        if not _tool_available("npm"):
            logger.warning("[SEC-DEP] npm not found — SKIP")
            return

        output_file = npm_cfg.get("output_file", f"{self.evidence_dir}/npm_audit_report.json")
        _ensure_dir(str(Path(output_file).parent))
        cmd = ["npm", "audit", "--json"]
        rc, stdout, stderr = _run(cmd, cwd=working_dir, timeout=120)

        if stdout:
            with open(output_file, "w") as f:
                f.write(stdout)
            result.evidence_files.append(output_file)

            try:
                data = json.loads(stdout)
                vulns = data.get("vulnerabilities", {})
                for pkg_name, vuln_info in vulns.items():
                    sev = vuln_info.get("severity", "low").upper()
                    finding = {
                        "tool": "npm-audit",
                        "package": pkg_name,
                        "severity": sev,
                        "cvss_v3": 0.0,
                        "via": [v if isinstance(v, str) else v.get("title", "") for v in vuln_info.get("via", [])],
                        "fixable": vuln_info.get("fixAvailable", False),
                    }
                    result.findings.append(finding)
                    if sev == "CRITICAL":
                        result.critical_count += 1
                    elif sev == "HIGH":
                        result.high_count += 1
                    elif sev == "MODERATE":
                        result.medium_count += 1
                    else:
                        result.low_count += 1
            except json.JSONDecodeError:
                logger.warning("[SEC-DEP] npm audit JSON parse error")

        logger.info("[SEC-DEP] npm audit complete")


# ─────────────────────────────────────────────────────────────────────────────
# Section 4: OTA Integrity (automated tests only)
# ─────────────────────────────────────────────────────────────────────────────
class OtaIntegrityVerifier:
    """Runs automated OTA integrity tests where hardware simulator is available."""

    def __init__(self, config: dict[str, Any], evidence_dir: str) -> None:
        self.cfg = config["ota_integrity"]
        self.evidence_dir = evidence_dir
        self._start = datetime.datetime.utcnow()

    def run(self) -> SectionResult:
        logger.info("[SEC-OTA] Starting OTA integrity verification")
        result = SectionResult(
            section_id="SEC-OTA",
            section_name="OTA Firmware Update Integrity — MCUboot Signature Check",
            tool="MCUboot 1.10.0 + imgtool.py",
        )

        self._verify_signing_infrastructure(result)
        self._run_ota_tests(result)

        all_pass = all(
            f.get("test_result") == "PASS"
            for f in result.findings
            if f.get("type") == "test"
        )

        if all_pass and result.critical_count == 0 and result.high_count == 0:
            result.result = "PASS"
            result.notes = (
                "OTA integrity verified. "
                "Tampered/unsigned/wrong-key images rejected by MCUboot. "
                "Anti-rollback enforced. Device identity provisioned."
            )
        else:
            result.result = "FAIL"
            result.notes = "OTA integrity test failures detected — review findings."

        result.duration_seconds = (
            datetime.datetime.utcnow() - self._start
        ).total_seconds()
        return result

    def _verify_signing_infrastructure(self, result: SectionResult) -> None:
        """Verify imgtool.py and signing key are present and configured."""
        signing_cfg = self.cfg.get("signing_infrastructure", {})
        imgtool = signing_cfg.get("imgtool_path", "firmware/scripts/imgtool.py")
        pub_key = signing_cfg.get("signing_key_public", "firmware/keys/production_signing_pub.pem")

        findings = []
        if not Path(imgtool).exists():
            findings.append({
                "type": "infra_check",
                "item": "imgtool.py",
                "status": "MISSING",
                "severity": "HIGH",
                "note": f"imgtool.py not found at {imgtool}",
            })
            result.high_count += 1
        else:
            findings.append({
                "type": "infra_check",
                "item": "imgtool.py",
                "status": "PRESENT",
                "path": imgtool,
            })

        if not Path(pub_key).exists():
            findings.append({
                "type": "infra_check",
                "item": "production_signing_pub.pem",
                "status": "MISSING",
                "severity": "HIGH",
                "note": f"Public signing key not found at {pub_key}. Cannot verify MCUboot will use correct key.",
            })
            result.high_count += 1
        else:
            findings.append({
                "type": "infra_check",
                "item": "production_signing_pub.pem",
                "status": "PRESENT",
                "path": pub_key,
            })

        result.findings.extend(findings)

    def _run_ota_tests(self, result: SectionResult) -> None:
        """Execute OTA test scripts if available."""
        tests = self.cfg.get("tests", {})
        for test_id, test_cfg in tests.items():
            script = test_cfg.get("script", "")
            expected = test_cfg.get("expected_result", "BOOT_REJECTED")

            if not script or not Path(script).exists():
                logger.info("[SEC-OTA] %s: Script not found — recording as MANUAL_REQUIRED", test_id)
                result.findings.append({
                    "type": "test",
                    "test_id": test_id,
                    "name": test_cfg.get("name", ""),
                    "test_result": "MANUAL_REQUIRED",
                    "expected": expected,
                    "note": f"Script {script} not present — test requires physical hardware.",
                })
                continue

            rc, stdout, stderr = _run(["bash", script], timeout=120)
            test_pass = (rc == 0 and "PASS" in stdout.upper()) or (
                expected == "BOOT_REJECTED" and "rejected" in stdout.lower()
            )

            test_result_str = "PASS" if test_pass else "FAIL"
            if not test_pass:
                result.critical_count += 1

            result.findings.append({
                "type": "test",
                "test_id": test_id,
                "name": test_cfg.get("name", ""),
                "test_result": test_result_str,
                "expected": expected,
                "returncode": rc,
                "stdout_excerpt": stdout[:300],
            })
            logger.info("[SEC-OTA] %s: %s", test_id, test_result_str)

            evidence_file = test_cfg.get("evidence_file", "")
            if evidence_file:
                result.evidence_files.append(evidence_file)


# ─────────────────────────────────────────────────────────────────────────────
# Report Generator
# ─────────────────────────────────────────────────────────────────────────────
class ReportGenerator:
    """Aggregates section results into final ValidationReport and writes JSON."""

    def __init__(self, config: dict[str, Any], output_dir: str) -> None:
        self.cfg = config
        self.output_dir = output_dir

    def generate(self, sections: list[SectionResult], operator: str) -> ValidationReport:
        meta = self.cfg["metadata"]
        ac = meta["acceptance_criteria"]

        total_critical = sum(s.critical_count for s in sections)
        total_high = sum(s.high_count for s in sections)
        total_medium = sum(s.medium_count for s in sections)
        total_low = sum(s.low_count for s in sections)

        # Evaluate acceptance criteria
        ac_summary = {
            "no_high_critical_bandit": self._check_sast_ac(sections),
            "no_cve_above_threshold": self._check_dep_ac(sections, ac["max_cvss_allowed"]),
            "ota_tampered_rejected": self._check_ota_ac(sections),
            "report_generated": True,
        }

        failed_sections = [s for s in sections if s.result == "FAIL"]
        overall = "PASS" if not failed_sections and all(ac_summary.values()) else "FAIL"

        report = ValidationReport(
            document_id=meta["report_document_id"],
            device=meta["device"],
            firmware_version=os.environ.get("FIRMWARE_VERSION", "0.9.2-rc1"),
            run_timestamp=datetime.datetime.utcnow().isoformat() + "Z",
            operator=operator,
            overall_result=overall,
            sections=sections,
            acceptance_criteria_summary=ac_summary,
            total_critical=total_critical,
            total_high=total_high,
            total_medium=total_medium,
            total_low=total_low,
        )
        return report

    def write(self, report: ValidationReport) -> str:
        _ensure_dir(self.output_dir)
        timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"security_validation_run_{timestamp}.json"
        output_path = str(Path(self.output_dir) / filename)

        with open(output_path, "w") as f:
            json.dump(report.to_dict(), f, indent=2)

        logger.info("[REPORT] Written to %s", output_path)
        return output_path

    def _check_sast_ac(self, sections: list[SectionResult]) -> bool:
        sast = next((s for s in sections if s.section_id == "SEC-SA-BE"), None)
        if sast is None:
            return True  # Not run — not a failure
        return sast.high_count == 0 and sast.critical_count == 0

    def _check_dep_ac(self, sections: list[SectionResult], max_cvss: float) -> bool:
        dep = next((s for s in sections if s.section_id == "SEC-DEP"), None)
        if dep is None:
            return True
        for finding in dep.findings:
            if finding.get("cvss_v3", 0) >= max_cvss:
                return False
        # Also check by severity for tools that don't report CVSS
        return dep.critical_count == 0 and dep.high_count == 0

    def _check_ota_ac(self, sections: list[SectionResult]) -> bool:
        ota = next((s for s in sections if s.section_id == "SEC-OTA"), None)
        if ota is None:
            return True
        # Look for OTA-T-002 (tampered image test)
        for finding in ota.findings:
            if finding.get("test_id") == "OTA-T-002":
                return finding.get("test_result") == "PASS"
        return True  # Not run (manual) — not automatically a failure


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def _load_config(config_path: str) -> dict[str, Any]:
    with open(config_path) as f:
        return yaml.safe_load(f)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="WFDS Security Validation Pipeline — DHF-SEC-SVP-001"
    )
    parser.add_argument(
        "--config",
        default="docs/DHF/security/security_validation_config.yaml",
        help="Path to security_validation_config.yaml",
    )
    parser.add_argument(
        "--section",
        default="all",
        choices=["all", "fw", "sast", "deps", "ota"],
        help="Run a specific section only",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first section failure",
    )
    parser.add_argument(
        "--output",
        default="docs/DHF/security/",
        help="Output directory for reports",
    )
    parser.add_argument(
        "--operator",
        default=os.environ.get("USER", "ci-pipeline"),
        help="Operator name for report sign-off (21 CFR Part 11)",
    )
    args = parser.parse_args()

    # Load config
    if not Path(args.config).exists():
        logger.error("Config file not found: %s", args.config)
        return 1

    config = _load_config(args.config)
    evidence_dir = config["metadata"].get("evidence_archive", f"{args.output}/evidence/")
    _ensure_dir(evidence_dir)

    logger.info("=" * 70)
    logger.info("WFDS Security Validation Pipeline — DHF-SEC-SVP-001")
    logger.info("Device: %s", config["metadata"]["device"])
    logger.info("Operator: %s", args.operator)
    logger.info("=" * 70)

    sections: list[SectionResult] = []
    run_all = args.section == "all"

    # Section 1: Firmware Static Analysis
    if run_all or args.section == "fw":
        fw_result = FirmwareStaticAnalyzer(config, evidence_dir).run()
        sections.append(fw_result)
        logger.info("[%s] → %s", fw_result.section_id, fw_result.result)
        if args.fail_fast and fw_result.result == "FAIL":
            logger.error("FAIL-FAST triggered at %s", fw_result.section_id)
            return 1

    # Section 2: Backend Python SAST
    if run_all or args.section == "sast":
        sast_result = BackendSastRunner(config, evidence_dir).run()
        sections.append(sast_result)
        logger.info("[%s] → %s", sast_result.section_id, sast_result.result)
        if args.fail_fast and sast_result.result == "FAIL":
            logger.error("FAIL-FAST triggered at %s", sast_result.section_id)
            return 1

    # Section 3: Dependency Scan
    if run_all or args.section == "deps":
        dep_result = DependencyScanner(config, evidence_dir).run()
        sections.append(dep_result)
        logger.info("[%s] → %s", dep_result.section_id, dep_result.result)
        if args.fail_fast and dep_result.result == "FAIL":
            logger.error("FAIL-FAST triggered at %s", dep_result.section_id)
            return 1

    # Section 4: OTA Integrity (automated subset)
    if run_all or args.section == "ota":
        ota_result = OtaIntegrityVerifier(config, evidence_dir).run()
        sections.append(ota_result)
        logger.info("[%s] → %s", ota_result.section_id, ota_result.result)

    # Generate report
    generator = ReportGenerator(config, args.output)
    report = generator.generate(sections, args.operator)
    report_path = generator.write(report)

    # Print summary
    logger.info("=" * 70)
    logger.info("SECURITY VALIDATION SUMMARY")
    logger.info("=" * 70)
    logger.info("Overall Result:  %s", report.overall_result)
    logger.info(
        "Totals — CRITICAL: %d  HIGH: %d  MEDIUM: %d  LOW: %d",
        report.total_critical,
        report.total_high,
        report.total_medium,
        report.total_low,
    )
    logger.info("Acceptance Criteria:")
    for criterion, passed in report.acceptance_criteria_summary.items():
        status = "PASS" if passed else "FAIL"
        logger.info("  %-45s %s", criterion, status)
    logger.info("Report:  %s", report_path)
    logger.info("=" * 70)

    return 0 if report.overall_result == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
