"""
SAGE[ai] - Functional Safety Computation Engine
================================================
Actual computation engines for safety-critical analysis:

- FMEA: Failure Mode and Effects Analysis with RPN scoring
- FTA:  Fault Tree Analysis with AND/OR gates, probability, minimal cut sets
- SIL:  Safety Integrity Level classification per IEC 61508
- ASIL: Automotive Safety Integrity Level per ISO 26262
- IEC 62304: Software safety class determination (A, B, C)
- Safety requirements generation from hazard analysis

These are NOT LLM approximations — they are deterministic computation engines
that produce auditable, reproducible results for regulatory submission.

Reference Standards:
  IEC 61508 (Functional Safety)
  ISO 26262 (Automotive Functional Safety)
  IEC 62304 (Medical Device Software Lifecycle)
  ISO 14971 (Risk Management for Medical Devices)
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ASIL classification matrix per ISO 26262
# Severity × Exposure × Controllability → ASIL
# ---------------------------------------------------------------------------

ASIL_MATRIX = {
    # (severity, exposure, controllability) → ASIL
    # S0 = no injuries → always QM
    ("S0", "E1", "C1"): "QM", ("S0", "E1", "C2"): "QM", ("S0", "E1", "C3"): "QM",
    ("S0", "E2", "C1"): "QM", ("S0", "E2", "C2"): "QM", ("S0", "E2", "C3"): "QM",
    ("S0", "E3", "C1"): "QM", ("S0", "E3", "C2"): "QM", ("S0", "E3", "C3"): "QM",
    ("S0", "E4", "C1"): "QM", ("S0", "E4", "C2"): "QM", ("S0", "E4", "C3"): "QM",
    # S1 = light injuries
    ("S1", "E1", "C1"): "QM", ("S1", "E1", "C2"): "QM", ("S1", "E1", "C3"): "QM",
    ("S1", "E2", "C1"): "QM", ("S1", "E2", "C2"): "QM", ("S1", "E2", "C3"): "QM",
    ("S1", "E3", "C1"): "QM", ("S1", "E3", "C2"): "QM", ("S1", "E3", "C3"): "A",
    ("S1", "E4", "C1"): "QM", ("S1", "E4", "C2"): "A",  ("S1", "E4", "C3"): "B",
    # S2 = severe injuries
    ("S2", "E1", "C1"): "QM", ("S2", "E1", "C2"): "QM", ("S2", "E1", "C3"): "QM",
    ("S2", "E2", "C1"): "QM", ("S2", "E2", "C2"): "QM", ("S2", "E2", "C3"): "A",
    ("S2", "E3", "C1"): "QM", ("S2", "E3", "C2"): "A",  ("S2", "E3", "C3"): "B",
    ("S2", "E4", "C1"): "A",  ("S2", "E4", "C2"): "B",  ("S2", "E4", "C3"): "C",
    # S3 = life-threatening / fatal
    ("S3", "E1", "C1"): "QM", ("S3", "E1", "C2"): "QM", ("S3", "E1", "C3"): "A",
    ("S3", "E2", "C1"): "QM", ("S3", "E2", "C2"): "A",  ("S3", "E2", "C3"): "B",
    ("S3", "E3", "C1"): "A",  ("S3", "E3", "C2"): "B",  ("S3", "E3", "C3"): "C",
    ("S3", "E4", "C1"): "B",  ("S3", "E4", "C2"): "C",  ("S3", "E4", "C3"): "D",
}

# SIL ranges per IEC 61508 (continuous mode, per hour)
SIL_RANGES = [
    # (max_pfh, sil_level)
    (1e-8, 4),   # SIL 4: < 1e-8
    (1e-7, 3),   # SIL 3: 1e-8 to 1e-7
    (1e-6, 2),   # SIL 2: 1e-7 to 1e-6
    (1e-5, 1),   # SIL 1: 1e-6 to 1e-5
]


class FunctionalSafetyEngine:
    """
    Deterministic functional safety computation engine.

    All computations are reproducible and auditable — no LLM involved.
    """

    def __init__(self):
        self.logger = logging.getLogger("FunctionalSafety")

    # ------------------------------------------------------------------
    # FMEA (Failure Mode and Effects Analysis)
    # ------------------------------------------------------------------

    def calculate_fmea_entry(
        self,
        component: str,
        failure_mode: str,
        effect: str,
        severity: int,
        occurrence: int,
        detection: int,
    ) -> Dict:
        """
        Calculate FMEA entry with Risk Priority Number.

        Args:
            severity: 1-10 (10 = most severe, e.g., death)
            occurrence: 1-10 (10 = most frequent)
            detection: 1-10 (10 = hardest to detect)

        Returns:
            Dict with RPN, risk level, and recommended action priority.
        """
        for name, val in [("severity", severity), ("occurrence", occurrence), ("detection", detection)]:
            if not (1 <= val <= 10):
                raise ValueError(f"{name} must be 1-10, got {val}")

        rpn = severity * occurrence * detection

        if rpn > 200 or severity >= 9:
            risk_level = "critical"
        elif rpn > 100:
            risk_level = "high"
        elif rpn > 50:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "id": f"FMEA-{uuid.uuid4().hex[:6].upper()}",
            "component": component,
            "failure_mode": failure_mode,
            "effect": effect,
            "severity": severity,
            "occurrence": occurrence,
            "detection": detection,
            "rpn": rpn,
            "risk_level": risk_level,
            "action_required": risk_level in ("critical", "high"),
        }

    def generate_fmea_table(self, entries: List[Dict]) -> Dict:
        """Generate complete FMEA table sorted by RPN descending."""
        computed = []
        for entry in entries:
            computed.append(self.calculate_fmea_entry(
                component=entry["component"],
                failure_mode=entry["failure_mode"],
                effect=entry["effect"],
                severity=entry["severity"],
                occurrence=entry["occurrence"],
                detection=entry["detection"],
            ))

        computed.sort(key=lambda e: e["rpn"], reverse=True)

        critical = sum(1 for e in computed if e["risk_level"] == "critical")
        high = sum(1 for e in computed if e["risk_level"] == "high")

        return {
            "entries": computed,
            "summary": {
                "total_entries": len(computed),
                "critical_count": critical,
                "high_count": high,
                "max_rpn": max((e["rpn"] for e in computed), default=0),
                "action_items": critical + high,
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # FTA (Fault Tree Analysis)
    # ------------------------------------------------------------------

    def calculate_fta(self, tree: Dict) -> Dict:
        """
        Calculate fault tree probability and minimal cut sets.

        Tree format:
            {"top_event": "...", "gate": "OR|AND", "children": [...]}
            Children can be events ({"event": "...", "probability": 0.001})
            or nested gates.
        """
        probability = self._compute_gate_probability(tree)
        cut_sets = self._compute_minimal_cut_sets(tree)

        return {
            "top_event": tree.get("top_event", "Unknown"),
            "probability": probability,
            "minimal_cut_sets": cut_sets,
            "single_point_failures": [cs for cs in cut_sets if len(cs) == 1],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _compute_gate_probability(self, node: Dict) -> float:
        """Recursively compute probability through AND/OR gates."""
        if "probability" in node:
            return node["probability"]

        gate = node.get("gate", "OR")
        children_probs = [self._compute_gate_probability(c) for c in node.get("children", [])]

        if not children_probs:
            return 0.0

        if gate == "AND":
            result = 1.0
            for p in children_probs:
                result *= p
            return result
        else:  # OR
            result = 1.0
            for p in children_probs:
                result *= (1.0 - p)
            return 1.0 - result

    def _compute_minimal_cut_sets(self, node: Dict) -> List[List[str]]:
        """Compute minimal cut sets from fault tree."""
        if "event" in node:
            return [[node["event"]]]

        gate = node.get("gate", "OR")
        children_cuts = [self._compute_minimal_cut_sets(c) for c in node.get("children", [])]

        if not children_cuts:
            return []

        if gate == "OR":
            # Union: each child's cut sets are independent paths to failure
            result = []
            for child_cuts in children_cuts:
                result.extend(child_cuts)
            return result
        else:  # AND
            # Cross-product: all combinations must fail simultaneously
            result = children_cuts[0]
            for next_cuts in children_cuts[1:]:
                new_result = []
                for existing in result:
                    for new in next_cuts:
                        combined = sorted(set(existing + new))
                        if combined not in new_result:
                            new_result.append(combined)
                result = new_result
            return result

    # ------------------------------------------------------------------
    # SIL Classification (IEC 61508)
    # ------------------------------------------------------------------

    def classify_sil(self, probability_dangerous_failure_per_hour: float) -> Dict:
        """
        Classify Safety Integrity Level per IEC 61508.

        Args:
            probability_dangerous_failure_per_hour: PFH value

        Returns:
            Dict with SIL level (1-4) and description.
        """
        pfh = probability_dangerous_failure_per_hour
        sil = 0
        for max_pfh, level in SIL_RANGES:
            if pfh <= max_pfh:
                sil = level
                break

        if sil == 0 and pfh > 1e-5:
            sil = 0  # Below SIL 1

        descriptions = {
            0: "Below SIL 1 — insufficient safety integrity",
            1: "SIL 1 — basic safety integrity",
            2: "SIL 2 — moderate safety integrity",
            3: "SIL 3 — high safety integrity (e.g., pacemakers)",
            4: "SIL 4 — highest safety integrity (e.g., nuclear, rail)",
        }

        return {
            "sil": sil,
            "pfh": pfh,
            "description": descriptions.get(sil, f"SIL {sil}"),
            "standard": "IEC 61508",
        }

    # ------------------------------------------------------------------
    # ASIL Classification (ISO 26262)
    # ------------------------------------------------------------------

    def classify_asil(self, severity: str, exposure: str, controllability: str) -> Dict:
        """
        Classify ASIL per ISO 26262 from hazard parameters.

        Args:
            severity: S0-S3
            exposure: E1-E4
            controllability: C1-C3
        """
        key = (severity, exposure, controllability)
        asil = ASIL_MATRIX.get(key, "QM")

        asil_descriptions = {
            "QM": "Quality Management only — no safety requirement",
            "A": "ASIL A — lowest automotive safety integrity",
            "B": "ASIL B — moderate automotive safety integrity",
            "C": "ASIL C — high automotive safety integrity",
            "D": "ASIL D — highest automotive safety integrity",
        }

        return {
            "asil": asil,
            "severity": severity,
            "exposure": exposure,
            "controllability": controllability,
            "description": asil_descriptions.get(asil, f"ASIL {asil}"),
            "standard": "ISO 26262",
        }

    # ------------------------------------------------------------------
    # IEC 62304 Software Safety Class
    # ------------------------------------------------------------------

    def classify_iec62304(self, risk_level: str) -> Dict:
        """
        Determine IEC 62304 software safety class from risk analysis.

        Args:
            risk_level: "death_possible", "injury_possible", "no_injury"
        """
        class_map = {
            "death_possible": "C",
            "serious_injury_possible": "C",
            "injury_possible": "B",
            "no_injury": "A",
        }
        safety_class = class_map.get(risk_level, "C")  # Default to C (conservative)

        class_descriptions = {
            "A": "Class A — no injury possible. Minimal documentation required.",
            "B": "Class B — non-serious injury possible. Architecture + integration testing required.",
            "C": "Class C — death or serious injury possible. Full lifecycle verification required.",
        }

        class_requirements = {
            "A": ["development_plan", "requirements", "release", "maintenance"],
            "B": ["development_plan", "requirements", "architecture", "architecture_verification",
                   "integration_testing", "system_testing", "release", "maintenance"],
            "C": ["development_plan", "requirements", "architecture", "architecture_verification",
                   "detailed_design", "unit_implementation", "unit_verification",
                   "integration_testing", "system_testing", "release", "maintenance",
                   "code_review", "full_traceability"],
        }

        return {
            "safety_class": safety_class,
            "description": class_descriptions[safety_class],
            "required_processes": class_requirements[safety_class],
            "standard": "IEC 62304:2006/AMD1:2015",
        }

    # ------------------------------------------------------------------
    # Safety Requirements Generation
    # ------------------------------------------------------------------

    def generate_safety_requirements(self, hazard: Dict) -> List[Dict]:
        """Generate safety requirements from a single hazard."""
        hazard_id = hazard.get("id", "HAZ-???")
        description = hazard.get("description", "")
        asil = hazard.get("asil", "D")
        safety_class = hazard.get("iec62304_class", "C")

        reqs = []

        # Detection requirement
        reqs.append({
            "id": f"SR-{hazard_id}-DET",
            "description": f"The system shall detect the condition: {description}",
            "type": "detection",
            "asil": asil,
            "iec62304_class": safety_class,
            "traces_to": hazard_id,
            "verification_method": "test",
        })

        # Mitigation requirement
        reqs.append({
            "id": f"SR-{hazard_id}-MIT",
            "description": f"The system shall mitigate the hazard: {description} within safe operating limits",
            "type": "mitigation",
            "asil": asil,
            "iec62304_class": safety_class,
            "traces_to": hazard_id,
            "verification_method": "test",
        })

        # Notification requirement
        reqs.append({
            "id": f"SR-{hazard_id}-NOT",
            "description": f"The system shall alert the operator when: {description} is detected",
            "type": "notification",
            "asil": asil,
            "iec62304_class": safety_class,
            "traces_to": hazard_id,
            "verification_method": "demonstration",
        })

        return reqs

    # ------------------------------------------------------------------
    # Full Safety Analysis (E2E)
    # ------------------------------------------------------------------

    def run_safety_analysis(
        self,
        product_name: str,
        hazards: List[Dict],
        fmea_entries: List[Dict],
    ) -> Dict:
        """
        Run complete safety analysis lifecycle.

        hazards → ASIL classification → FMEA → IEC 62304 class → safety requirements
        """
        # 1. ASIL classification for each hazard
        asil_results = []
        max_asil = "QM"
        asil_order = {"QM": 0, "A": 1, "B": 2, "C": 3, "D": 4}

        for hazard in hazards:
            asil_result = self.classify_asil(
                severity=hazard.get("severity", "S3"),
                exposure=hazard.get("exposure", "E4"),
                controllability=hazard.get("controllability", "C3"),
            )
            asil_results.append({
                "hazard_id": hazard["id"],
                "hazard_description": hazard["description"],
                **asil_result,
            })
            if asil_order.get(asil_result["asil"], 0) > asil_order.get(max_asil, 0):
                max_asil = asil_result["asil"]

        # 2. FMEA table
        fmea_table = self.generate_fmea_table(fmea_entries)

        # 3. IEC 62304 class (worst case from hazards)
        worst_risk = "death_possible" if any(
            h.get("severity") == "S3" for h in hazards
        ) else "injury_possible" if any(
            h.get("severity") == "S2" for h in hazards
        ) else "no_injury"

        iec62304 = self.classify_iec62304(worst_risk)

        # 4. Safety requirements
        all_reqs = []
        for hazard in hazards:
            hazard_enriched = {
                **hazard,
                "asil": next(
                    (a["asil"] for a in asil_results if a["hazard_id"] == hazard["id"]),
                    max_asil
                ),
                "iec62304_class": iec62304["safety_class"],
            }
            all_reqs.extend(self.generate_safety_requirements(hazard_enriched))

        return {
            "product_name": product_name,
            "asil_classifications": asil_results,
            "max_asil": max_asil,
            "fmea_table": fmea_table,
            "iec62304_class": iec62304["safety_class"],
            "iec62304_details": iec62304,
            "safety_requirements": all_reqs,
            "risk_summary": {
                "total_hazards": len(hazards),
                "critical_fmea_entries": fmea_table["summary"]["critical_count"],
                "total_safety_requirements": len(all_reqs),
                "highest_asil": max_asil,
                "software_safety_class": iec62304["safety_class"],
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


# Singleton
functional_safety = FunctionalSafetyEngine()
