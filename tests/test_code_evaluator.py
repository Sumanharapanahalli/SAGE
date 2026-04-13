# tests/test_code_evaluator.py
import tempfile
import os
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from src.core.evolution.code_evaluator import CodeEvaluator, TestPassEvaluator, CodeCriticEvaluator, ComplexityEvaluator
from src.core.evolution.candidate import Candidate


def test_test_pass_evaluator():
    """Test evaluator that runs pytest on evolved code."""
    import asyncio

    evaluator = TestPassEvaluator()
    assert evaluator.name == "test_pass"

    candidate = Candidate(
        id="test-code", content="def add(a, b): return a + b",
        candidate_type="code", fitness=0.0, parent_ids=[], generation=1,
        metadata={"file_path": "src/utils.py"}, created_at=datetime.now(timezone.utc)
    )

    # Mock test execution result
    mock_test_result = {
        "passed": 8,
        "failed": 2,
        "total": 10,
        "pass_rate": 0.8,
        "duration": 1.5
    }

    with patch.object(evaluator, '_run_tests', return_value=mock_test_result):
        result = asyncio.run(evaluator.evaluate(candidate))

    assert result["score"] == 0.8  # Pass rate maps to score
    assert result["tests_passed"] == 8
    assert result["tests_total"] == 10


def test_code_critic_evaluator():
    """Test evaluator that uses CriticAgent to score code quality."""
    import asyncio

    evaluator = CodeCriticEvaluator()
    assert evaluator.name == "code_critic"

    candidate = Candidate(
        id="test", content="def factorial(n):\n    return 1 if n <= 1 else n * factorial(n-1)",
        candidate_type="code", fitness=0.0, parent_ids=[], generation=1,
        metadata={"language": "python"}, created_at=datetime.now(timezone.utc)
    )

    # Mock CriticAgent response
    mock_critique = {
        "score": 8,  # Out of 10
        "flaws": ["Missing input validation"],
        "suggestions": ["Add type hints", "Handle negative inputs"],
        "summary": "Clean recursive implementation"
    }

    with patch.object(evaluator, '_call_code_critic', new=AsyncMock(return_value=mock_critique)):
        result = asyncio.run(evaluator.evaluate(candidate))

    assert result["score"] == 0.8  # 8/10 → 0.8
    assert "code_quality_score" in result


def test_complexity_evaluator():
    """Test evaluator that measures code complexity."""
    import asyncio

    evaluator = ComplexityEvaluator()
    candidate = Candidate(
        id="test", content="def simple(): return True",
        candidate_type="code", fitness=0.0, parent_ids=[], generation=1,
        metadata={}, created_at=datetime.now(timezone.utc)
    )

    result = asyncio.run(evaluator.evaluate(candidate))

    # Simple code should have good complexity score
    assert "score" in result
    assert 0.0 <= result["score"] <= 1.0
    assert "cyclomatic_complexity" in result


def test_code_evaluator_ensemble():
    """Test that CodeEvaluator combines test pass, critic, and complexity scores."""
    import asyncio

    candidate = Candidate(
        id="test", content="def hello(): return 'world'",
        candidate_type="code", fitness=0.0, parent_ids=[], generation=1,
        metadata={"file_path": "test.py"}, created_at=datetime.now(timezone.utc)
    )

    evaluator = CodeEvaluator()

    # Mock individual evaluator results per spec weights:
    # Test pass rate: 0.4, Critic quality: 0.3, Spec correctness: 0.2, Complexity: 0.1
    with patch.object(evaluator.test_evaluator, 'evaluate', new=AsyncMock(return_value={"score": 0.9, "details": "90% pass"})):
        with patch.object(evaluator.critic_evaluator, 'evaluate', new=AsyncMock(return_value={"score": 0.8, "details": "Good quality"})):
            with patch.object(evaluator.spec_evaluator, 'evaluate', new=AsyncMock(return_value={"score": 0.7, "details": "Meets spec"})):
                with patch.object(evaluator.complexity_evaluator, 'evaluate', new=AsyncMock(return_value={"score": 0.7, "details": "Low complexity"})):
                    result = asyncio.run(evaluator.evaluate(candidate))

    # Should be weighted combination: 0.9*0.4 + 0.8*0.3 + 0.7*0.2 + 0.7*0.1 = 0.36 + 0.24 + 0.14 + 0.07 = 0.81
    assert abs(result["fitness"] - 0.81) < 0.01
    assert "breakdown" in result


def test_test_runner_integration():
    """Test integration with pytest execution."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a simple test file
        test_file = os.path.join(tmpdir, "test_sample.py")
        with open(test_file, "w") as f:
            f.write("""
def test_addition():
    assert 1 + 1 == 2

def test_subtraction():
    assert 3 - 1 == 2
""")

        evaluator = TestPassEvaluator()

        # Test should find and run the test file
        result = evaluator._run_tests(tmpdir)
        assert "passed" in result
        assert "total" in result


def test_spec_correctness_evaluator():
    """Test evaluator that checks spec compliance."""
    import asyncio

    evaluator = CodeEvaluator()

    candidate = Candidate(
        id="test", content="def compute(x): return x * 2",
        candidate_type="code", fitness=0.0, parent_ids=[], generation=1,
        metadata={"spec": "Function should double the input"}, created_at=datetime.now(timezone.utc)
    )

    result = asyncio.run(evaluator.evaluate(candidate))

    # Should return valid score and breakdown
    assert "fitness" in result
    assert 0.0 <= result["fitness"] <= 1.0
    assert "breakdown" in result
