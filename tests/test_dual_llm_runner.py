"""Tests for src.integrations.dual_llm_runner.score_confidence (rule-based scorer).

Previously untested (SAGE self-improvement loop, issue #23).
"""

from src.integrations.dual_llm_runner import score_confidence


def test_full_confidence_for_rich_valid_output():
    out = {
        "severity": "HIGH",
        "root_cause_hypothesis": "UART RX buffer overflow due to burst > 256 bytes",
        "recommended_action": "increase buffer to 512 and add flow control",
    }
    assert score_confidence(out) == 1.0


def test_non_dict_scores_zero():
    assert score_confidence("not a dict") == 0.0
    assert score_confidence(None) == 0.0


def test_invalid_severity_reduces_score():
    good = {
        "severity": "HIGH",
        "root_cause_hypothesis": "a well described and sufficiently long root cause here",
    }
    bad = dict(good, severity="BANANA")
    assert score_confidence(bad) < score_confidence(good)


def test_generic_phrase_reduces_score():
    out = {
        "severity": "HIGH",
        "root_cause_hypothesis": "unknown error, something went wrong, padding padding padding",
    }
    assert score_confidence(out) < 1.0


def test_very_short_output_penalised():
    assert score_confidence({"severity": "LOW", "root_cause": "x"}) < 1.0


def test_score_is_clamped_between_zero_and_one():
    out = {"severity": "NOPE", "root_cause": "unknown error", "x": "y"}
    s = score_confidence(out)
    assert 0.0 <= s <= 1.0
