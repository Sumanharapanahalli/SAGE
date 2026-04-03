"""
Test suite for Functional Safety Computation Engine

Covers:
- FMEA: Risk Priority Number calculation, severity/occurrence/detection scoring
- FTA: Fault tree construction with AND/OR gates, minimal cut sets, probability
- SIL/ASIL: Classification from hazard parameters per IEC 61508 / ISO 26262
- IEC 62304: Software safety class determination (A, B, C)
- Safety requirements generation from hazard analysis
- Full safety lifecycle E2E

TDD — tests written BEFORE implementation.
"""

import pytest


class TestFMEA:
    """Failure Mode and Effects Analysis computation."""

    @pytest.fixture
    def engine(self):
        from src.core.functional_safety import FunctionalSafetyEngine
        return FunctionalSafetyEngine()

    def test_rpn_calculation(self, engine):
        """RPN = Severity x Occurrence x Detection."""
        result = engine.calculate_fmea_entry(
            component="Pacing pulse generator",
            failure_mode="No output pulse",
            effect="Loss of cardiac pacing — patient asystole",
            severity=10,
            occurrence=3,
            detection=4,
        )
        assert result["rpn"] == 10 * 3 * 4  # 120
        assert result["severity"] == 10
        assert result["risk_level"] in ("critical", "high", "medium", "low")

    def test_rpn_high_risk_flagged(self, engine):
        """RPN > 200 should be flagged as critical."""
        result = engine.calculate_fmea_entry(
            component="Battery",
            failure_mode="Premature depletion",
            effect="Device shutdown — loss of therapy",
            severity=10,
            occurrence=5,
            detection=5,
        )
        assert result["rpn"] == 250
        assert result["risk_level"] == "critical"

    def test_rpn_low_risk(self, engine):
        """RPN < 50 should be low risk."""
        result = engine.calculate_fmea_entry(
            component="LED indicator",
            failure_mode="LED not illuminating",
            effect="User unaware of device status — cosmetic",
            severity=2,
            occurrence=2,
            detection=2,
        )
        assert result["rpn"] == 8
        assert result["risk_level"] == "low"

    def test_fmea_table(self, engine):
        """Generate complete FMEA table from multiple entries."""
        entries = [
            {"component": "Pulse Gen", "failure_mode": "No output", "effect": "Asystole",
             "severity": 10, "occurrence": 3, "detection": 4},
            {"component": "Lead", "failure_mode": "Fracture", "effect": "Intermittent pacing",
             "severity": 8, "occurrence": 4, "detection": 5},
            {"component": "Battery", "failure_mode": "Early depletion", "effect": "Shutdown",
             "severity": 10, "occurrence": 2, "detection": 3},
        ]
        table = engine.generate_fmea_table(entries)
        assert len(table["entries"]) == 3
        # Should be sorted by RPN descending
        rpns = [e["rpn"] for e in table["entries"]]
        assert rpns == sorted(rpns, reverse=True)
        assert "summary" in table

    def test_severity_validation(self, engine):
        """Severity, occurrence, detection must be 1-10."""
        with pytest.raises(ValueError):
            engine.calculate_fmea_entry(
                component="X", failure_mode="Y", effect="Z",
                severity=11, occurrence=3, detection=4,
            )


class TestFTA:
    """Fault Tree Analysis computation."""

    @pytest.fixture
    def engine(self):
        from src.core.functional_safety import FunctionalSafetyEngine
        return FunctionalSafetyEngine()

    def test_or_gate_probability(self, engine):
        """OR gate: P(top) = 1 - (1-P(A)) * (1-P(B))."""
        tree = {
            "top_event": "Loss of pacing",
            "gate": "OR",
            "children": [
                {"event": "Pulse generator failure", "probability": 0.001},
                {"event": "Lead fracture", "probability": 0.002},
            ],
        }
        result = engine.calculate_fta(tree)
        expected = 1 - (1 - 0.001) * (1 - 0.002)  # ~0.002998
        assert abs(result["probability"] - expected) < 1e-6

    def test_and_gate_probability(self, engine):
        """AND gate: P(top) = P(A) * P(B)."""
        tree = {
            "top_event": "Dual redundancy failure",
            "gate": "AND",
            "children": [
                {"event": "Primary channel failure", "probability": 0.001},
                {"event": "Backup channel failure", "probability": 0.001},
            ],
        }
        result = engine.calculate_fta(tree)
        expected = 0.001 * 0.001  # 0.000001
        assert abs(result["probability"] - expected) < 1e-9

    def test_nested_gates(self, engine):
        """Nested AND/OR gates compute correctly."""
        tree = {
            "top_event": "Patient harm",
            "gate": "OR",
            "children": [
                {"event": "Software error", "probability": 0.005},
                {
                    "gate": "AND",
                    "children": [
                        {"event": "Sensor A fails", "probability": 0.01},
                        {"event": "Sensor B fails", "probability": 0.01},
                    ],
                },
            ],
        }
        result = engine.calculate_fta(tree)
        and_prob = 0.01 * 0.01  # 0.0001
        expected = 1 - (1 - 0.005) * (1 - and_prob)
        assert abs(result["probability"] - expected) < 1e-6

    def test_minimal_cut_sets(self, engine):
        """Identify minimal cut sets from fault tree."""
        tree = {
            "top_event": "System failure",
            "gate": "OR",
            "children": [
                {"event": "Single point failure A", "probability": 0.01},
                {
                    "gate": "AND",
                    "children": [
                        {"event": "Redundant B1", "probability": 0.01},
                        {"event": "Redundant B2", "probability": 0.01},
                    ],
                },
            ],
        }
        result = engine.calculate_fta(tree)
        cuts = result["minimal_cut_sets"]
        # Single point failure A is a 1-element cut set
        # B1 AND B2 is a 2-element cut set
        assert any(len(c) == 1 for c in cuts)
        assert any(len(c) == 2 for c in cuts)


class TestSILASIL:
    """Safety Integrity Level / Automotive Safety Integrity Level classification."""

    @pytest.fixture
    def engine(self):
        from src.core.functional_safety import FunctionalSafetyEngine
        return FunctionalSafetyEngine()

    def test_asil_d_classification(self, engine):
        """Highest severity + exposure + low controllability = ASIL D."""
        result = engine.classify_asil(
            severity="S3",       # Life-threatening
            exposure="E4",       # High probability
            controllability="C3" # Difficult to control
        )
        assert result["asil"] == "D"

    def test_asil_qm_classification(self, engine):
        """Low severity = QM (no safety requirement)."""
        result = engine.classify_asil(
            severity="S0",
            exposure="E4",
            controllability="C3"
        )
        assert result["asil"] == "QM"

    def test_asil_b_classification(self, engine):
        """Medium parameters = ASIL B."""
        result = engine.classify_asil(
            severity="S2",
            exposure="E3",
            controllability="C2"
        )
        assert result["asil"] in ("A", "B", "C")  # Mid-range

    def test_sil_classification(self, engine):
        """SIL from probability of dangerous failure per hour."""
        result = engine.classify_sil(
            probability_dangerous_failure_per_hour=1e-7
        )
        assert result["sil"] == 3  # 1e-8 to 1e-7 = SIL 3

    def test_sil_4_highest(self, engine):
        result = engine.classify_sil(probability_dangerous_failure_per_hour=1e-9)
        assert result["sil"] == 4

    def test_sil_1_lowest(self, engine):
        result = engine.classify_sil(probability_dangerous_failure_per_hour=1e-5)
        assert result["sil"] == 1

    def test_iec62304_class_from_risk(self, engine):
        """IEC 62304 software safety class from risk analysis."""
        assert engine.classify_iec62304("death_possible")["safety_class"] == "C"
        assert engine.classify_iec62304("injury_possible")["safety_class"] == "B"
        assert engine.classify_iec62304("no_injury")["safety_class"] == "A"


class TestSafetyRequirements:
    """Generate safety requirements from hazard analysis."""

    @pytest.fixture
    def engine(self):
        from src.core.functional_safety import FunctionalSafetyEngine
        return FunctionalSafetyEngine()

    def test_generate_safety_requirements_from_hazard(self, engine):
        """Each hazard should produce at least one safety requirement."""
        hazard = {
            "id": "HAZ-001",
            "description": "Loss of cardiac pacing output",
            "severity": "S3",
            "asil": "D",
            "iec62304_class": "C",
        }
        reqs = engine.generate_safety_requirements(hazard)
        assert len(reqs) >= 1
        for req in reqs:
            assert "id" in req
            assert "description" in req
            assert req["traces_to"] == "HAZ-001"
            assert "verification_method" in req


class TestSafetyLifecycleE2E:
    """End-to-end: hazards → FMEA → FTA → SIL → safety requirements."""

    @pytest.fixture
    def engine(self):
        from src.core.functional_safety import FunctionalSafetyEngine
        return FunctionalSafetyEngine()

    def test_pacemaker_safety_lifecycle(self, engine):
        """Full safety lifecycle for a pacemaker."""
        result = engine.run_safety_analysis(
            product_name="Cardiac Pacemaker",
            hazards=[
                {
                    "id": "HAZ-001",
                    "description": "Loss of pacing output",
                    "cause": "Pulse generator software fault",
                    "effect": "Patient asystole — death",
                    "severity": "S3", "exposure": "E4", "controllability": "C3",
                },
                {
                    "id": "HAZ-002",
                    "description": "Overpacing",
                    "cause": "Rate control algorithm error",
                    "effect": "Ventricular fibrillation — death",
                    "severity": "S3", "exposure": "E3", "controllability": "C3",
                },
            ],
            fmea_entries=[
                {"component": "Pulse Gen", "failure_mode": "No output", "effect": "Asystole",
                 "severity": 10, "occurrence": 3, "detection": 4},
                {"component": "Rate Control", "failure_mode": "Runaway pacing", "effect": "VFib",
                 "severity": 10, "occurrence": 2, "detection": 5},
            ],
        )

        assert "fmea_table" in result
        assert "asil_classifications" in result
        assert "iec62304_class" in result
        assert result["iec62304_class"] == "C"  # Death possible
        assert "safety_requirements" in result
        assert len(result["safety_requirements"]) >= 2
        assert "risk_summary" in result
