"""Tests for prompt complexity classification and model routing."""
import pytest

from src.core.complexity_classifier import ComplexityClassifier, Complexity


class TestComplexityClassifier:
    @pytest.fixture
    def classifier(self):
        return ComplexityClassifier()

    def test_short_simple_prompt_is_low(self, classifier):
        result = classifier.classify("What time is it?")
        assert result == Complexity.LOW

    def test_medium_length_prompt_is_medium(self, classifier):
        prompt = (
            "Analyze the following log entries and identify any patterns "
            "that suggest memory leaks or resource exhaustion. "
            "Consider both heap allocation and file descriptor usage."
        )
        result = classifier.classify(prompt)
        assert result in (Complexity.MEDIUM, Complexity.HIGH)

    def test_long_prompt_with_code_is_high(self, classifier):
        prompt = "Review this implementation:\n" + "def foo():\n    pass\n" * 50
        prompt += "\nIdentify security vulnerabilities, performance issues, and suggest refactoring."
        result = classifier.classify(prompt)
        assert result == Complexity.HIGH

    def test_tool_usage_keywords_increase_complexity(self, classifier):
        result = classifier.classify(
            "Generate an implementation_plan with code_diff for the new authentication module."
        )
        assert result in (Complexity.MEDIUM, Complexity.HIGH)

    def test_score_returns_numeric(self, classifier):
        score = classifier.score("hello")
        assert isinstance(score, (int, float))
        assert 0 <= score <= 100

    def test_classify_with_system_prompt(self, classifier):
        result = classifier.classify(
            "Fix bug",
            system_prompt="You are a senior developer reviewing code for safety-critical firmware."
        )
        # System prompt context should bump complexity
        assert result in (Complexity.MEDIUM, Complexity.HIGH)


class TestModelRouting:
    def test_route_returns_model_name(self):
        from src.core.complexity_classifier import route_to_model
        model = route_to_model(Complexity.LOW, {
            "low": "gemini-2.5-flash",
            "medium": "gemini-2.5-flash",
            "high": "gemini-2.5-pro",
        })
        assert model == "gemini-2.5-flash"

    def test_route_high_complexity(self):
        from src.core.complexity_classifier import route_to_model
        model = route_to_model(Complexity.HIGH, {
            "low": "gemini-2.5-flash",
            "medium": "gemini-2.5-flash",
            "high": "gemini-2.5-pro",
        })
        assert model == "gemini-2.5-pro"

    def test_route_fallback_when_no_config(self):
        from src.core.complexity_classifier import route_to_model
        model = route_to_model(Complexity.MEDIUM, {})
        assert model is None
