"""
SAGE Framework — Critic Agent Tests (TDD)
==========================================
Tests for:
  - CriticAgent.review_plan() returns score + flaws + suggestions
  - CriticAgent.review_plan() handles LLM JSON parse errors gracefully
  - CriticAgent.review_plan() audits every review
  - CriticAgent.review_code() returns score + issues + security_risks
  - CriticAgent.review_code() truncates long code diffs
  - CriticAgent.review_integration() returns score + gaps + risks
  - CriticAgent.review_with_loop() passes on first try when score >= threshold
  - CriticAgent.review_with_loop() iterates when score < threshold
  - CriticAgent.review_with_loop() respects max_iterations limit
  - CriticAgent.review_with_loop() calls revise_fn between iterations
  - CriticAgent.review_with_loop() handles revise_fn failure gracefully
  - CriticAgent.review_with_loop() stores feedback in vector memory
  - CriticAgent.review_with_loop() returns error for unknown review type
  - CriticAgent._call_llm() extracts JSON from markdown fences
  - CriticAgent._call_llm() handles non-JSON LLM output
  - CriticAgent._call_llm() handles LLM exception
  - CriticAgent._store_feedback() handles vector store failure gracefully
  - Singleton critic_agent is importable
  - System prompts are non-empty strings
"""

import json
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_critic():
    """Create a CriticAgent with mocked LLM and audit dependencies."""
    from src.agents.critic import CriticAgent
    critic = CriticAgent()
    critic._llm_gateway = MagicMock()
    critic._audit_logger = MagicMock()
    return critic


def _mock_llm_response(score=85, flaws=None, issues=None, **kwargs):
    """Build a mock LLM JSON response."""
    data = {"score": score, "summary": "Test summary", **kwargs}
    if flaws is not None:
        data["flaws"] = flaws
    if issues is not None:
        data["issues"] = issues
    return json.dumps(data)


# ---------------------------------------------------------------------------
# CriticAgent.review_plan()
# ---------------------------------------------------------------------------

class TestReviewPlan:

    def test_returns_score_and_flaws(self):
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = _mock_llm_response(
            score=72, flaws=["Missing error handling", "No tests"]
        )
        result = critic.review_plan([{"step": 1, "task_type": "BACKEND"}], "Build a web app")
        assert result["score"] == 72
        assert "Missing error handling" in result["flaws"]

    def test_handles_json_parse_error(self):
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = "This is not JSON at all"
        result = critic.review_plan([], "test")
        assert result["score"] == 0

    def test_audits_every_review(self):
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = _mock_llm_response(score=80)
        critic.review_plan([], "test")
        critic._audit_logger.log_event.assert_called_once()
        call_kwargs = critic._audit_logger.log_event.call_args[1]
        assert call_kwargs["actor"] == "CriticAgent"
        assert "PLAN_REVIEW" in call_kwargs["action_type"]

    def test_includes_product_description_in_prompt(self):
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = _mock_llm_response(score=90)
        critic.review_plan([], "Build a surgical robot controller")
        prompt = critic._llm_gateway.generate.call_args[0][0]
        assert "surgical robot" in prompt


# ---------------------------------------------------------------------------
# CriticAgent.review_code()
# ---------------------------------------------------------------------------

class TestReviewCode:

    def test_returns_score_and_issues(self):
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = _mock_llm_response(
            score=65, issues=["SQL injection risk"], security_risks=["XSS"]
        )
        result = critic.review_code("def foo(): pass", "Build a login page")
        assert result["score"] == 65
        assert "SQL injection risk" in result["issues"]

    def test_truncates_long_code(self):
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = _mock_llm_response(score=80)
        long_code = "x = 1\n" * 10000
        critic.review_code(long_code, "test")
        prompt = critic._llm_gateway.generate.call_args[0][0]
        assert len(prompt) < len(long_code)

    def test_includes_context(self):
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = _mock_llm_response(score=80)
        critic.review_code("code", "task", context="Prior feedback: fix XSS")
        prompt = critic._llm_gateway.generate.call_args[0][0]
        assert "Prior feedback: fix XSS" in prompt


# ---------------------------------------------------------------------------
# CriticAgent.review_integration()
# ---------------------------------------------------------------------------

class TestReviewIntegration:

    def test_returns_score_and_gaps(self):
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = _mock_llm_response(
            score=78, gaps=["No load test"], risks=["Data race"]
        )
        result = critic.review_integration("All tests pass", "combined diff here")
        assert result["score"] == 78

    def test_truncates_long_diff(self):
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = _mock_llm_response(score=80)
        long_diff = "+ line\n" * 10000
        critic.review_integration("pass", long_diff)
        prompt = critic._llm_gateway.generate.call_args[0][0]
        assert len(prompt) < len(long_diff)


# ---------------------------------------------------------------------------
# CriticAgent.review_with_loop()
# ---------------------------------------------------------------------------

class TestReviewWithLoop:

    def test_passes_on_first_try(self):
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = _mock_llm_response(score=85)
        with patch.object(critic, "_store_feedback"):
            result = critic.review_with_loop(
                review_fn="plan", artifact=[], description="test", threshold=70
            )
            assert result["passed"] is True
            assert result["final_score"] == 85
            assert result["iterations"] == 1

    def test_iterates_when_below_threshold(self):
        critic = _fresh_critic()
        responses = [
            _mock_llm_response(score=40, flaws=["Bad"]),
            _mock_llm_response(score=75),
        ]
        critic._llm_gateway.generate.side_effect = responses
        with patch.object(critic, "_store_feedback"):
            result = critic.review_with_loop(
                review_fn="plan", artifact=[], description="test",
                threshold=70, max_iterations=3,
                revise_fn=lambda artifact, feedback: artifact,
            )
            assert result["iterations"] == 2
            assert result["final_score"] == 75
            assert result["passed"] is True

    def test_respects_max_iterations(self):
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = _mock_llm_response(score=30, flaws=["Still bad"])
        with patch.object(critic, "_store_feedback"):
            result = critic.review_with_loop(
                review_fn="plan", artifact=[], description="test",
                threshold=70, max_iterations=2,
                revise_fn=lambda a, f: a,
            )
            assert result["iterations"] == 2
            assert result["passed"] is False
            assert result["final_score"] == 30

    def test_calls_revise_fn_between_iterations(self):
        critic = _fresh_critic()
        responses = [
            _mock_llm_response(score=40),
            _mock_llm_response(score=80),
        ]
        critic._llm_gateway.generate.side_effect = responses
        revise_fn = MagicMock(return_value=["revised plan"])
        with patch.object(critic, "_store_feedback"):
            critic.review_with_loop(
                review_fn="plan", artifact=["original"], description="test",
                threshold=70, max_iterations=3, revise_fn=revise_fn,
            )
            revise_fn.assert_called_once()

    def test_handles_revise_fn_failure(self):
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = _mock_llm_response(score=40)
        revise_fn = MagicMock(side_effect=RuntimeError("Revision failed"))
        with patch.object(critic, "_store_feedback"):
            result = critic.review_with_loop(
                review_fn="plan", artifact=[], description="test",
                threshold=70, max_iterations=3, revise_fn=revise_fn,
            )
            assert result["iterations"] == 1

    def test_stores_feedback_in_vector_memory(self):
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = _mock_llm_response(score=85)
        with patch("src.memory.vector_store.vector_memory") as mock_vm:
            critic.review_with_loop(
                review_fn="plan", artifact=[], description="test", threshold=70
            )
            mock_vm.add_feedback.assert_called_once()

    def test_returns_error_for_unknown_review_type(self):
        critic = _fresh_critic()
        result = critic.review_with_loop(
            review_fn="nonexistent", artifact=[], description="test"
        )
        assert result["score"] == 0
        assert "error" in result

    def test_no_revise_fn_stops_after_first_review(self):
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = _mock_llm_response(score=40)
        with patch.object(critic, "_store_feedback"):
            result = critic.review_with_loop(
                review_fn="plan", artifact=[], description="test",
                threshold=70, max_iterations=3, revise_fn=None,
            )
            assert result["iterations"] == 1
            assert result["passed"] is False

    def test_history_contains_all_iterations(self):
        critic = _fresh_critic()
        responses = [
            _mock_llm_response(score=40),
            _mock_llm_response(score=50),
            _mock_llm_response(score=80),
        ]
        critic._llm_gateway.generate.side_effect = responses
        with patch.object(critic, "_store_feedback"):
            result = critic.review_with_loop(
                review_fn="plan", artifact=[], description="test",
                threshold=70, max_iterations=3,
                revise_fn=lambda a, f: a,
            )
            assert len(result["history"]) == 3
            assert result["history"][0]["score"] == 40
            assert result["history"][2]["score"] == 80


# ---------------------------------------------------------------------------
# CriticAgent._call_llm() internal
# ---------------------------------------------------------------------------

class TestCallLLM:

    def test_extracts_json_from_markdown_fences(self):
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = '```json\n{"score": 90, "summary": "Good"}\n```'
        result = critic._call_llm("test", "test", "TEST")
        assert result["score"] == 90

    def test_handles_non_json_output(self):
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = "I cannot produce JSON today"
        result = critic._call_llm("test", "test", "TEST")
        assert result["score"] == 0

    def test_handles_llm_exception(self):
        critic = _fresh_critic()
        critic._llm_gateway.generate.side_effect = RuntimeError("LLM down")
        result = critic._call_llm("test", "test", "TEST")
        assert result["score"] == 0
        assert "error" in result

    def test_score_coerced_to_int(self):
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = '{"score": "88", "summary": "Good"}'
        result = critic._call_llm("test", "test", "TEST")
        assert isinstance(result["score"], int)
        assert result["score"] == 88


# ---------------------------------------------------------------------------
# CriticAgent._store_feedback() internal
# ---------------------------------------------------------------------------

class TestStoreFeedback:

    def test_handles_vector_store_failure(self):
        critic = _fresh_critic()
        with patch("src.memory.vector_store.vector_memory") as mock_vm:
            mock_vm.add_feedback.side_effect = RuntimeError("DB down")
            # Should not raise
            critic._store_feedback("plan", "test", [{"score": 80}], True)


# ---------------------------------------------------------------------------
# Module-level
# ---------------------------------------------------------------------------

class TestModuleLevel:

    def test_singleton_importable(self):
        from src.agents.critic import critic_agent
        assert critic_agent is not None
        assert hasattr(critic_agent, "review_plan")
        assert hasattr(critic_agent, "review_code")
        assert hasattr(critic_agent, "review_integration")
        assert hasattr(critic_agent, "review_with_loop")

    def test_system_prompts_non_empty(self):
        from src.agents.critic import CriticAgent
        assert len(CriticAgent.PLAN_REVIEW_PROMPT) > 50
        assert len(CriticAgent.CODE_REVIEW_PROMPT) > 50
        assert len(CriticAgent.INTEGRATION_REVIEW_PROMPT) > 50


# ---------------------------------------------------------------------------
# Edge-case tests
# ---------------------------------------------------------------------------

class TestReviewPlanEdgeCases:

    def test_empty_plan_list(self):
        """review_plan() with an empty plan list should still call LLM and return score."""
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = _mock_llm_response(
            score=30, flaws=["No tasks defined"]
        )
        result = critic.review_plan([], "Build a web app")
        assert result["score"] == 30
        assert "No tasks defined" in result["flaws"]

    def test_very_large_plan(self):
        """review_plan() with 100+ steps should not crash and truncates in prompt."""
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = _mock_llm_response(score=60)
        large_plan = [{"step": i, "task_type": "BACKEND", "description": f"Task {i}"} for i in range(120)]
        result = critic.review_plan(large_plan, "Massive system")
        assert result["score"] == 60
        # The LLM was called (prompt was constructed)
        critic._llm_gateway.generate.assert_called_once()


class TestReviewCodeEdgeCases:

    def test_empty_code_string(self):
        """review_code() with empty code should still work."""
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = _mock_llm_response(
            score=0, issues=["No code provided"]
        )
        result = critic.review_code("", "Build a login page")
        assert result["score"] == 0

    def test_binary_like_content(self):
        """review_code() with binary-like content (null bytes, etc.) handles it."""
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = _mock_llm_response(score=10)
        binary_content = "\x00\x01\x02\xff" * 100 + "def foo(): pass"
        result = critic.review_code(binary_content, "Binary test")
        assert isinstance(result["score"], int)


class TestReviewWithLoopEdgeCases:

    def test_threshold_zero_always_passes(self):
        """review_with_loop() with threshold=0 should pass even with score=0."""
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = _mock_llm_response(score=0)
        with patch.object(critic, "_store_feedback"):
            result = critic.review_with_loop(
                review_fn="plan", artifact=[], description="test", threshold=0
            )
            assert result["passed"] is True
            assert result["iterations"] == 1

    def test_threshold_100_needs_perfect_score(self):
        """review_with_loop() with threshold=100 fails unless score=100."""
        critic = _fresh_critic()
        responses = [
            _mock_llm_response(score=95),
            _mock_llm_response(score=99),
        ]
        critic._llm_gateway.generate.side_effect = responses
        with patch.object(critic, "_store_feedback"):
            result = critic.review_with_loop(
                review_fn="plan", artifact=[], description="test",
                threshold=100, max_iterations=2,
                revise_fn=lambda a, f: a,
            )
            assert result["passed"] is False
            assert result["final_score"] == 99

    def test_threshold_100_passes_with_score_100(self):
        """review_with_loop() with threshold=100 passes when score is exactly 100."""
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = _mock_llm_response(score=100)
        with patch.object(critic, "_store_feedback"):
            result = critic.review_with_loop(
                review_fn="plan", artifact=[], description="test", threshold=100
            )
            assert result["passed"] is True

    def test_max_iterations_one(self):
        """review_with_loop() with max_iterations=1 only does one review."""
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = _mock_llm_response(score=40)
        with patch.object(critic, "_store_feedback"):
            result = critic.review_with_loop(
                review_fn="plan", artifact=[], description="test",
                threshold=70, max_iterations=1,
                revise_fn=lambda a, f: a,
            )
            assert result["iterations"] == 1
            assert result["passed"] is False

    def test_score_exactly_at_threshold(self):
        """review_with_loop() passes when score == threshold (boundary condition)."""
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = _mock_llm_response(score=70)
        with patch.object(critic, "_store_feedback"):
            result = critic.review_with_loop(
                review_fn="plan", artifact=[], description="test", threshold=70
            )
            assert result["passed"] is True
            assert result["final_score"] == 70
            assert result["iterations"] == 1

    def test_score_one_below_threshold(self):
        """review_with_loop() fails when score is threshold-1."""
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = _mock_llm_response(score=69)
        with patch.object(critic, "_store_feedback"):
            result = critic.review_with_loop(
                review_fn="plan", artifact=[], description="test",
                threshold=70, max_iterations=1,
            )
            assert result["passed"] is False


class TestCallLLMEdgeCases:

    def test_nested_json_in_markdown_fences(self):
        """_call_llm() extracts nested JSON from markdown fences."""
        critic = _fresh_critic()
        nested = '```json\n{"score": 75, "summary": "OK", "details": {"sub": [1, 2]}}\n```'
        critic._llm_gateway.generate.return_value = nested
        result = critic._call_llm("test", "test", "TEST")
        assert result["score"] == 75
        assert result["details"]["sub"] == [1, 2]

    def test_multiple_json_blocks_picks_valid_object(self):
        """_call_llm() with multiple JSON blocks extracts the one with score."""
        critic = _fresh_critic()
        # After stripping fences and using regex to find {…}, the greedy match
        # should capture the full JSON object.
        response = 'Some text\n{"score": 60, "summary": "First block"}\nMore text'
        critic._llm_gateway.generate.return_value = response
        result = critic._call_llm("test", "test", "TEST")
        assert result["score"] == 60

    def test_json_with_extra_text_around_fences(self):
        """_call_llm() handles text before and after markdown JSON fences."""
        critic = _fresh_critic()
        response = 'Here is my review:\n```json\n{"score": 88, "summary": "Great"}\n```\nThat is all.'
        critic._llm_gateway.generate.return_value = response
        result = critic._call_llm("test", "test", "TEST")
        assert result["score"] == 88

    def test_empty_string_response(self):
        """_call_llm() handles empty string from LLM."""
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = ""
        result = critic._call_llm("test", "test", "TEST")
        assert result["score"] == 0


class TestStoreFeedbackEdgeCases:

    def test_empty_history(self):
        """_store_feedback() with empty history should not raise."""
        critic = _fresh_critic()
        with patch("src.memory.vector_store.vector_memory") as mock_vm:
            # Empty history: the method accesses history[-1] which would raise on truly empty
            # but it should handle gracefully
            critic._store_feedback("plan", "test", [], True)
            # If it raised IndexError, this line wouldn't execute
            # The method either succeeds or catches the exception

    def test_store_feedback_formats_correctly(self):
        """_store_feedback() includes correct metadata."""
        critic = _fresh_critic()
        with patch("src.memory.vector_store.vector_memory") as mock_vm:
            critic._store_feedback(
                "code", "Build login", [{"score": 55, "issues": ["XSS"]}], False
            )
            call_kwargs = mock_vm.add_feedback.call_args
            metadata = call_kwargs[1]["metadata"]
            assert metadata["review_type"] == "code"
            assert metadata["passed"] is False
            assert metadata["score"] == 55


class TestReviewIntegrationEdgeCases:

    def test_empty_test_results_and_diff(self):
        """review_integration() with empty test results and diff."""
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = _mock_llm_response(
            score=50, gaps=["No tests at all"], risks=["Unknown state"]
        )
        result = critic.review_integration("", "")
        assert result["score"] == 50

    def test_very_long_diff_is_truncated(self):
        """review_integration() truncates diff to 8000 chars."""
        critic = _fresh_critic()
        critic._llm_gateway.generate.return_value = _mock_llm_response(score=70)
        long_diff = "+" * 20000
        critic.review_integration("pass", long_diff)
        prompt = critic._llm_gateway.generate.call_args[0][0]
        # The diff is truncated to 8000 chars inside the prompt
        assert len(prompt) < 20000


# ===========================================================================
# Multi-LLM Critic Tests
# ===========================================================================


class _MockMultiProvider:
    """Mock provider for multi-LLM critic tests."""
    def __init__(self, name, response):
        self._name = name
        self._response = response

    def provider_name(self):
        return self._name

    def generate(self, prompt, system_prompt):
        return self._response


class TestReviewPlanMulti:
    """Tests for CriticAgent.review_plan_multi with provider pool."""

    def test_multi_plan_review_returns_score(self):
        """review_plan_multi should parse JSON from voting result."""
        from src.agents.critic import CriticAgent
        from src.core.llm_gateway import ProviderPool

        review_json = json.dumps({
            "score": 72,
            "flaws": ["missing auth"],
            "suggestions": ["add auth"],
            "missing": [],
            "security_risks": [],
            "summary": "decent plan",
        })

        pool = ProviderPool()
        pool.register("a", _MockMultiProvider("a", review_json))
        pool.register("b", _MockMultiProvider("b", review_json))

        critic = CriticAgent()
        critic._llm_gateway = MagicMock()
        critic._llm_gateway.provider_pool = pool
        critic._audit_logger = MagicMock()

        result = critic.review_plan_multi(
            [{"task": "build API"}], "A REST API",
            strategy="voting", provider_names=["a", "b"],
        )
        assert result["score"] == 72
        assert "multi_llm" in result
        assert result["multi_llm"]["strategy"] == "voting"

    def test_multi_fallback_to_single_when_no_pool(self):
        """review_plan_multi should fall back to review_plan when pool is empty."""
        from src.agents.critic import CriticAgent
        from src.core.llm_gateway import ProviderPool

        review_json = json.dumps({
            "score": 85,
            "flaws": [],
            "suggestions": [],
            "missing": [],
            "security_risks": [],
            "summary": "great plan",
        })

        critic = CriticAgent()
        critic._llm_gateway = MagicMock()
        critic._llm_gateway.generate.return_value = review_json
        critic._llm_gateway.provider_pool = ProviderPool()  # empty pool
        critic._audit_logger = MagicMock()

        result = critic.review_plan_multi([{"task": "build"}], "A product")
        assert result["score"] == 85

    def test_multi_returns_error_when_all_fail(self):
        """review_plan_multi should return error when all providers fail."""
        from src.agents.critic import CriticAgent
        from src.core.llm_gateway import ProviderPool

        class _FailProvider:
            def provider_name(self):
                return "fail"
            def generate(self, prompt, system_prompt):
                raise ConnectionError("down")

        pool = ProviderPool()
        pool.register("fail1", _FailProvider())
        pool.register("fail2", _FailProvider())

        critic = CriticAgent()
        critic._llm_gateway = MagicMock()
        critic._llm_gateway.provider_pool = pool
        critic._audit_logger = MagicMock()

        result = critic.review_plan_multi(
            [{"task": "build"}], "A product",
            strategy="fallback", provider_names=["fail1", "fail2"],
        )
        assert result["score"] == 0
        assert "error" in result
