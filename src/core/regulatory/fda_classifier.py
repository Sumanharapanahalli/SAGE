"""
FDA CDS Classifier Agent - Automated 4-criterion test for medical device CDS.

Implements the FDA 4-part test to determine if software qualifies as
"Non-Device CDS" vs "Device CDS" requiring FDA oversight.

4 Criteria:
1. Not analyzing medical images or physiological signals
2. Displays medical information only
3. Provides recommendations/options, not specific diagnoses
4. Users can independently verify (considering automation bias)
"""

from typing import Dict, Any, Tuple, List
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FDAClassificationResult:
    """Result of FDA CDS classification."""

    classification: str  # "Device CDS" or "Non-Device CDS"
    confidence: str  # "HIGH", "MEDIUM", "LOW"
    criteria_met: List[bool]  # Results for each of the 4 criteria
    reasoning: str  # Explanation of classification
    requires_human_review: bool = False


class FDAClassifierAgent:
    """
    Agent that applies the FDA 4-criterion test to determine CDS classification.

    Non-Device CDS (exempt from FDA device regulations):
    - Does NOT analyze medical images/physiological signals (criterion 1)
    - Displays medical information only (criterion 2)
    - Provides recommendations/options, not specific diagnoses (criterion 3)
    - Users can independently verify results (criterion 4)

    Device CDS (subject to FDA device regulations):
    - Fails any of the above criteria
    """

    def __init__(self):
        self.name = "FDA CDS Classifier"

    def classify(self, intended_purpose: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify intended purpose using FDA 4-criterion test.

        Args:
            intended_purpose: IntendedPurpose configuration dict

        Returns:
            Classification result with criteria analysis
        """
        logger.info(
            f"Classifying intended purpose: {intended_purpose.get('function', 'Unknown')}"
        )

        # Analyze each criterion using LLM reasoning
        llm_analysis = self._generate_llm_analysis(intended_purpose)

        # Apply 4-criterion test logic
        classification, confidence = apply_four_criterion_test(llm_analysis)

        criteria_met = [
            not llm_analysis[
                "criterion_1_medical_images"
            ],  # Must NOT analyze images
            llm_analysis["criterion_2_display_only"],
            llm_analysis["criterion_3_recommendations_not_diagnosis"],
            llm_analysis["criterion_4_user_verifiable"],
        ]

        # Determine if human review is needed
        requires_human_review = (
            confidence == "LOW"
            or self._has_ambiguous_language(intended_purpose)
        )

        result = {
            "classification": classification,
            "confidence": confidence,
            "criteria_met": criteria_met,
            "reasoning": llm_analysis["reasoning"],
            "requires_human_review": requires_human_review,
        }

        logger.info(
            f"Classification result: {classification} ({confidence} confidence)"
        )
        return result

    def _generate_llm_analysis(self, intended_purpose: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use LLM to analyze intended purpose against 4 criteria.

        In real implementation, this would call the LLM with structured prompts.
        For now, returns static analysis based on function text.
        """
        function_text = intended_purpose.get("function", "").lower()
        boundary_conditions = [
            bc.lower() for bc in intended_purpose.get("boundary_conditions", [])
        ]

        # Simple heuristic analysis (replace with LLM call in production)
        analyzes_images = any(
            term in function_text
            for term in [
                "image",
                "scan",
                "x-ray",
                "mri",
                "ct",
                "ultrasound",
                "ecg",
                "ekg",
                "retinal",
                "radiologic",
                "pathology",
                "microscopy",
            ]
        )

        display_only = any(
            phrase in function_text
            for phrase in ["display", "show", "present", "dashboard", "view"]
        ) or any("display" in bc for bc in boundary_conditions)

        recommendations_not_diagnosis = any(
            phrase in function_text
            for phrase in ["recommendation", "suggest", "option", "support", "assist"]
        ) and not any(
            phrase in function_text
            for phrase in ["diagnose", "diagnosis", "diagnostic"]
        )

        user_verifiable = any(
            phrase in " ".join(boundary_conditions)
            for phrase in ["physician verification", "user verify", "independently verify"]
        )

        reasoning = (
            f"Function analysis: analyzes_images={analyzes_images}, "
            f"display_only={display_only}, recommendations={recommendations_not_diagnosis}, "
            f"verifiable={user_verifiable}"
        )

        return {
            "criterion_1_medical_images": analyzes_images,
            "criterion_2_display_only": display_only,
            "criterion_3_recommendations_not_diagnosis": recommendations_not_diagnosis,
            "criterion_4_user_verifiable": user_verifiable,
            "reasoning": reasoning,
        }

    def _has_ambiguous_language(self, intended_purpose: Dict[str, Any]) -> bool:
        """Check if intended purpose contains ambiguous language requiring human review."""
        function_text = intended_purpose.get("function", "").lower()

        ambiguous_terms = [
            "artificial intelligence",
            "machine learning",
            "ai",
            "algorithm",
            "automated diagnosis",
            "clinical decision",
            "treatment recommendation",
        ]

        return any(term in function_text for term in ambiguous_terms)


def apply_four_criterion_test(criteria: Dict[str, bool]) -> Tuple[str, str]:
    """
    Apply FDA 4-criterion test to determine CDS classification.

    Non-Device CDS requires ALL criteria to be met:
    1. Does NOT analyze medical images/physiological signals
    2. Displays medical information only
    3. Provides recommendations, not diagnoses
    4. User can independently verify

    Args:
        criteria: Dict with criterion results

    Returns:
        (classification, confidence) tuple
    """
    # Non-Device CDS: must pass all criteria
    all_criteria_met = (
        not criteria["criterion_1_medical_images"]  # Does NOT analyze images
        and criteria["criterion_2_display_only"]
        and criteria["criterion_3_recommendations_not_diagnosis"]
        and criteria["criterion_4_user_verifiable"]
    )

    if all_criteria_met:
        return "Non-Device CDS", "HIGH"
    else:
        return "Device CDS", "HIGH"
