"""
Regulatory Document Generation Engine
=======================================
Generates structured compliance documents from live SAGE data.

Supported document types:
  - Software Requirements Specification (SRS) — IEC 62304 §5.2
  - Risk Management File — ISO 14971
  - Verification & Validation Plan — IEC 62304 §5.5/5.7
  - Requirements Traceability Matrix (RTM) — IEC 62304 §5.1.1
  - SOUP Inventory — IEC 62304 §8.1.2
  - Design History File Index — FDA 21 CFR 820.30

Output: Markdown (suitable for conversion to PDF via pandoc or similar).
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class DocumentGenerator:
    """Generate regulatory compliance documents from live project data."""

    def __init__(self, project_name: str = "", version: str = "1.0"):
        self.project_name = project_name or os.environ.get("SAGE_PROJECT", "unknown")
        self.version = version
        self.generated_at = datetime.now(timezone.utc).isoformat()

    def _header(self, title: str, standard_ref: str) -> str:
        return (
            f"# {title}\n\n"
            f"**Project:** {self.project_name}  \n"
            f"**Document Version:** {self.version}  \n"
            f"**Standard Reference:** {standard_ref}  \n"
            f"**Generated:** {self.generated_at}  \n"
            f"**Generator:** SAGE Regulatory Document Engine  \n\n"
            f"---\n\n"
        )

    def generate_srs(self, requirements: List[dict], project_info: dict = None) -> str:
        """
        Generate Software Requirements Specification per IEC 62304 §5.2.

        Args:
            requirements: list of requirement dicts with id, type, title, description,
                         acceptance_criteria, priority, verification_method
            project_info: optional dict with intended_use, safety_class, etc.
        """
        info = project_info or {}
        doc = self._header("Software Requirements Specification (SRS)", "IEC 62304 §5.2")

        doc += "## 1. Purpose and Scope\n\n"
        doc += f"**Intended Use:** {info.get('intended_use', 'TBD')}  \n"
        doc += f"**Safety Classification:** {info.get('safety_class', 'TBD')}  \n"
        doc += f"**Regulatory Pathway:** {info.get('regulatory_pathway', 'TBD')}  \n\n"

        doc += "## 2. Requirements Summary\n\n"
        doc += f"Total requirements: {len(requirements)}\n\n"

        # Group by type
        by_type: Dict[str, list] = {}
        for req in requirements:
            rtype = req.get("type", "unclassified")
            by_type.setdefault(rtype, []).append(req)

        for rtype, reqs in sorted(by_type.items()):
            doc += f"### 2.{list(by_type.keys()).index(rtype) + 1}. {rtype.replace('_', ' ').title()} Requirements\n\n"
            doc += "| ID | Title | Priority | Verification | Status |\n"
            doc += "|---|---|---|---|---|\n"
            for r in reqs:
                doc += (
                    f"| {r.get('id', 'N/A')} | {r.get('title', 'N/A')} | "
                    f"{r.get('priority', 'N/A')} | {r.get('verification_method', 'N/A')} | "
                    f"{r.get('status', 'N/A')} |\n"
                )
            doc += "\n"

            for r in reqs:
                doc += f"#### {r.get('id', 'N/A')}: {r.get('title', 'N/A')}\n\n"
                doc += f"**Description:** {r.get('description', 'TBD')}  \n"
                doc += f"**Rationale:** {r.get('rationale', 'TBD')}  \n"
                criteria = r.get("acceptance_criteria", [])
                if criteria:
                    doc += "**Acceptance Criteria:**\n"
                    for c in criteria:
                        doc += f"- {c}\n"
                doc += "\n"

        doc += "## 3. Document History\n\n"
        doc += "| Version | Date | Author | Changes |\n"
        doc += "|---|---|---|---|\n"
        doc += f"| {self.version} | {self.generated_at[:10]} | SAGE Generator | Initial generation |\n\n"

        return doc

    def generate_risk_management(self, risks: List[dict], project_info: dict = None) -> str:
        """
        Generate Risk Management File per ISO 14971.

        Args:
            risks: list of risk dicts with id, hazard, severity, probability,
                   risk_level, mitigation, residual_risk
        """
        info = project_info or {}
        doc = self._header("Risk Management File", "ISO 14971:2019")

        doc += "## 1. Risk Management Plan\n\n"
        doc += f"**Risk Acceptability Criteria:** {info.get('risk_criteria', 'ALARP (As Low As Reasonably Practicable)')}\n"
        doc += f"**Risk Assessment Method:** {info.get('risk_method', 'FMEA + FTA')}\n\n"

        doc += "## 2. Risk Analysis\n\n"
        doc += "| ID | Hazard | Severity | Probability | Risk Level | Mitigation | Residual Risk |\n"
        doc += "|---|---|---|---|---|---|---|\n"
        for r in risks:
            doc += (
                f"| {r.get('id', 'N/A')} | {r.get('hazard', 'N/A')} | "
                f"{r.get('severity', 'N/A')} | {r.get('probability', 'N/A')} | "
                f"{r.get('risk_level', 'N/A')} | {r.get('mitigation', 'N/A')} | "
                f"{r.get('residual_risk', 'N/A')} |\n"
            )
        doc += "\n"

        # Statistics
        high_risks = [r for r in risks if r.get("risk_level", "").upper() in ("HIGH", "CRITICAL")]
        doc += "## 3. Risk Summary\n\n"
        doc += f"- **Total hazards identified:** {len(risks)}\n"
        doc += f"- **High/Critical risks:** {len(high_risks)}\n"
        doc += f"- **Risks with mitigation:** {sum(1 for r in risks if r.get('mitigation'))}\n\n"

        if high_risks:
            doc += "### 3.1 High/Critical Risks Requiring Review\n\n"
            for r in high_risks:
                doc += f"- **{r.get('id')}**: {r.get('hazard')} — {r.get('mitigation', 'NO MITIGATION DEFINED')}\n"
            doc += "\n"

        return doc

    def generate_rtm(self, trace_data: List[dict]) -> str:
        """
        Generate Requirements Traceability Matrix per IEC 62304 §5.1.1.

        Args:
            trace_data: output from TraceabilityMatrix.export_matrix()
        """
        doc = self._header("Requirements Traceability Matrix (RTM)", "IEC 62304 §5.1.1")

        doc += "## 1. Traceability Overview\n\n"
        doc += f"Total traced items: {len(trace_data)}\n\n"

        doc += "## 2. Full Traceability Matrix\n\n"
        doc += "| ID | Level | Title | Status | Traces To | Traced From |\n"
        doc += "|---|---|---|---|---|---|\n"
        for item in trace_data:
            traces_to = ", ".join(
                f"{t.get('target_id', '')}" for t in item.get("traces_to", [])
            ) or "—"
            traced_from = ", ".join(
                f"{t.get('source_id', '')}" for t in item.get("traced_from", [])
            ) or "—"
            doc += (
                f"| {item.get('id', 'N/A')} | {item.get('level', 'N/A')} | "
                f"{item.get('title', 'N/A')} | {item.get('status', 'N/A')} | "
                f"{traces_to} | {traced_from} |\n"
            )
        doc += "\n"

        # Coverage summary
        levels = {}
        for item in trace_data:
            lvl = item.get("level", "unknown")
            levels.setdefault(lvl, {"total": 0, "traced": 0})
            levels[lvl]["total"] += 1
            if item.get("traces_to") or item.get("traced_from"):
                levels[lvl]["traced"] += 1

        doc += "## 3. Coverage Summary\n\n"
        doc += "| Level | Total | Traced | Coverage |\n"
        doc += "|---|---|---|---|\n"
        for lvl, data in sorted(levels.items()):
            pct = round(data["traced"] / data["total"] * 100, 1) if data["total"] else 0
            doc += f"| {lvl} | {data['total']} | {data['traced']} | {pct}% |\n"
        doc += "\n"

        return doc

    def generate_vv_plan(self, requirements: List[dict], project_info: dict = None) -> str:
        """
        Generate Verification & Validation Plan per IEC 62304 §5.5/5.7.
        """
        info = project_info or {}
        doc = self._header("Verification & Validation Plan", "IEC 62304 §5.5 / §5.7")

        doc += "## 1. Verification Strategy\n\n"
        doc += "### 1.1 Verification Methods\n\n"
        doc += "| Method | Description | When Used |\n"
        doc += "|---|---|---|\n"
        doc += "| Test | Execution of software with defined inputs | Functional requirements |\n"
        doc += "| Analysis | Examination of documentation/code | Non-functional requirements |\n"
        doc += "| Inspection | Visual examination of artifacts | Coding standards, documentation |\n"
        doc += "| Demonstration | Showing capability to stakeholders | User-facing features |\n\n"

        doc += "### 1.2 Test Levels\n\n"
        doc += "| Level | Scope | Responsibility |\n"
        doc += "|---|---|---|\n"
        doc += "| Unit Test | Individual functions/methods | Developer |\n"
        doc += "| Integration Test | Component interactions | Developer + QA |\n"
        doc += "| System Test | End-to-end system behavior | QA |\n"
        doc += "| Acceptance Test | User requirements met | Product Owner |\n\n"

        doc += "## 2. Requirements Coverage Plan\n\n"
        doc += "| Requirement ID | Title | Verification Method | Test Level | Status |\n"
        doc += "|---|---|---|---|---|\n"
        for r in requirements:
            doc += (
                f"| {r.get('id', 'N/A')} | {r.get('title', 'N/A')} | "
                f"{r.get('verification_method', 'test')} | "
                f"{r.get('test_level', 'unit')} | "
                f"{r.get('verification_status', 'planned')} |\n"
            )
        doc += "\n"

        doc += "## 3. Validation Activities\n\n"
        doc += f"**Intended Use:** {info.get('intended_use', 'TBD')}  \n"
        doc += f"**User Population:** {info.get('user_population', 'TBD')}  \n"
        doc += f"**Validation Environment:** {info.get('validation_env', 'TBD')}  \n\n"

        doc += "### 3.1 Validation Test Cases\n\n"
        doc += "| ID | Scenario | Expected Outcome | Pass/Fail |\n"
        doc += "|---|---|---|---|\n"
        doc += "| VAL-001 | Normal use scenario | System performs as intended | TBD |\n"
        doc += "| VAL-002 | Edge case / error scenario | System handles gracefully | TBD |\n"
        doc += "| VAL-003 | Performance under load | Meets performance requirements | TBD |\n\n"

        return doc

    def generate_soup_inventory(self, dependencies: List[dict]) -> str:
        """
        Generate SOUP (Software of Unknown Provenance) Inventory per IEC 62304 §8.1.2.

        Args:
            dependencies: list of dicts with name, version, license, purpose,
                         risk_class, anomaly_list_url
        """
        doc = self._header("SOUP Inventory", "IEC 62304 §8.1.2")

        doc += "## 1. SOUP Components\n\n"
        doc += "| # | Component | Version | License | Purpose | Risk Class | Known Anomalies |\n"
        doc += "|---|---|---|---|---|---|---|\n"
        for i, dep in enumerate(dependencies, 1):
            doc += (
                f"| {i} | {dep.get('name', 'N/A')} | {dep.get('version', 'N/A')} | "
                f"{dep.get('license', 'N/A')} | {dep.get('purpose', 'N/A')} | "
                f"{dep.get('risk_class', 'N/A')} | "
                f"{dep.get('anomaly_list_url', 'N/A')} |\n"
            )
        doc += "\n"

        doc += "## 2. SOUP Risk Assessment\n\n"
        doc += "Each SOUP component is assessed for:\n"
        doc += "- **Functional risk**: Could a SOUP failure cause a hazardous situation?\n"
        doc += "- **Cybersecurity risk**: Does it introduce attack surface?\n"
        doc += "- **License compliance**: Is the license compatible with product distribution?\n\n"

        return doc

    def generate_document(self, doc_type: str, data: dict) -> str:
        """
        Main entry point — generate a document by type.

        Args:
            doc_type: one of 'srs', 'risk_management', 'rtm', 'vv_plan', 'soup_inventory'
            data: dict with keys appropriate for the document type

        Returns:
            Markdown string of the generated document
        """
        generators = {
            "srs": lambda d: self.generate_srs(
                d.get("requirements", []), d.get("project_info")
            ),
            "risk_management": lambda d: self.generate_risk_management(
                d.get("risks", []), d.get("project_info")
            ),
            "rtm": lambda d: self.generate_rtm(d.get("trace_data", [])),
            "vv_plan": lambda d: self.generate_vv_plan(
                d.get("requirements", []), d.get("project_info")
            ),
            "soup_inventory": lambda d: self.generate_soup_inventory(
                d.get("dependencies", [])
            ),
        }

        generator = generators.get(doc_type)
        if not generator:
            raise ValueError(
                f"Unknown document type '{doc_type}'. "
                f"Supported: {', '.join(generators.keys())}"
            )

        return generator(data)

    def list_document_types(self) -> List[dict]:
        """List all available document types with descriptions."""
        return [
            {
                "type": "srs",
                "name": "Software Requirements Specification",
                "standard": "IEC 62304 §5.2",
                "required_data": ["requirements"],
            },
            {
                "type": "risk_management",
                "name": "Risk Management File",
                "standard": "ISO 14971:2019",
                "required_data": ["risks"],
            },
            {
                "type": "rtm",
                "name": "Requirements Traceability Matrix",
                "standard": "IEC 62304 §5.1.1",
                "required_data": ["trace_data"],
            },
            {
                "type": "vv_plan",
                "name": "Verification & Validation Plan",
                "standard": "IEC 62304 §5.5/5.7",
                "required_data": ["requirements"],
            },
            {
                "type": "soup_inventory",
                "name": "SOUP Inventory",
                "standard": "IEC 62304 §8.1.2",
                "required_data": ["dependencies"],
            },
        ]
