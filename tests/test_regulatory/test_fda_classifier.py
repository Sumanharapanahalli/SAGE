"""
Tests for FDA CDS Classifier Agent - 4-criterion test implementation.
"""

import pytest
from unittest.mock import Mock, patch
from src.core.regulatory.fda_classifier import FDAClassifierAgent, apply_four_criterion_test


def test_fda_classifier_non_device_cds():
    """Test FDA classifier correctly identifies Non-Device CDS."""
    intended_purpose = {
        "function": "Display lab results dashboard for physician review",
        "performance_claims": {
            "sensitivity": 0.95,
            "specificity": 0.90,
            "confidence_interval": "95%"
        },
        "target_population": {
            "age_range": [18, 85],
            "exclusions": []
        },
        "boundary_conditions": [
            "Displays information only",
            "No diagnostic recommendations"
        ],
        "user_group": "Board-certified physicians",
        "fda_classification": "Non-Device CDS",
        "mdr_class": "Class I"
    }

    classifier = FDAClassifierAgent()

    with patch.object(classifier, '_generate_llm_analysis') as mock_llm:
        mock_llm.return_value = {
            "criterion_1_medical_images": False,
            "criterion_2_display_only": True,
            "criterion_3_recommendations_not_diagnosis": True,
            "criterion_4_user_verifiable": True,
            "reasoning": "Displays lab data only, no image analysis, user can verify"
        }

        result = classifier.classify(intended_purpose)

        assert result["classification"] == "Non-Device CDS"
        assert result["confidence"] == "HIGH"
        assert all(result["criteria_met"])
        assert "Displays lab data only" in result["reasoning"]


def test_fda_classifier_device_cds():
    """Test FDA classifier correctly identifies Device CDS."""
    intended_purpose = {
        "function": "Analyze retinal images for diabetic retinopathy screening",
        "performance_claims": {
            "sensitivity": 0.87,
            "specificity": 0.90,
            "confidence_interval": "95%"
        },
        "target_population": {
            "age_range": [18, 85],
            "exclusions": ["pregnancy"]
        },
        "boundary_conditions": [
            "For screening purposes only",
            "Requires ophthalmologist confirmation"
        ],
        "user_group": "Ophthalmologists",
        "fda_classification": "Device CDS",
        "mdr_class": "Class II"
    }

    classifier = FDAClassifierAgent()

    with patch.object(classifier, '_generate_llm_analysis') as mock_llm:
        mock_llm.return_value = {
            "criterion_1_medical_images": True,  # Analyzes retinal images
            "criterion_2_display_only": False,
            "criterion_3_recommendations_not_diagnosis": True,
            "criterion_4_user_verifiable": True,
            "reasoning": "Analyzes medical images (retinal), provides screening recommendations"
        }

        result = classifier.classify(intended_purpose)

        assert result["classification"] == "Device CDS"
        assert result["confidence"] == "HIGH"
        assert not result["criteria_met"][0]  # Fails criterion 1 (analyzes images)
        assert "Analyzes medical images" in result["reasoning"]


def test_apply_four_criterion_test():
    """Test the four-criterion test logic directly."""
    criteria = {
        "criterion_1_medical_images": False,    # Does NOT analyze medical images
        "criterion_2_display_only": True,       # Displays medical information only
        "criterion_3_recommendations_not_diagnosis": True,  # Recommendations, not diagnosis
        "criterion_4_user_verifiable": True     # User can verify
    }

    classification, confidence = apply_four_criterion_test(criteria)

    assert classification == "Non-Device CDS"
    assert confidence == "HIGH"

    # Test Device CDS case (fails criterion 1)
    criteria["criterion_1_medical_images"] = True
    classification, confidence = apply_four_criterion_test(criteria)

    assert classification == "Device CDS"
    assert confidence == "HIGH"
