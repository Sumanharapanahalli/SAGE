"""Tests for src.core.sage_intelligence — SLM wrapper graceful behaviour.

The module must degrade gracefully when the SLM (Ollama) is unavailable.
Previously untested (SAGE self-improvement loop, issue #23).
"""

from src.core.sage_intelligence import SAGEIntelligence, TaskTier


def test_task_tier_values():
    assert TaskTier.LIGHT.value == "light"
    assert TaskTier.STANDARD.value == "standard"
    assert TaskTier.HEAVY.value == "heavy"


def test_is_a_singleton():
    assert SAGEIntelligence() is SAGEIntelligence()


def test_classify_task_tier_degrades_to_a_valid_tier():
    # With no SLM available the classifier must still return a TaskTier, not raise.
    tier = SAGEIntelligence().classify_task_tier("triage this short log line")
    assert isinstance(tier, TaskTier)


def test_rule_based_yaml_lint_returns_list():
    issues = SAGEIntelligence()._rule_based_yaml_lint("prompts.yaml", "roles: {}\n")
    assert isinstance(issues, list)
