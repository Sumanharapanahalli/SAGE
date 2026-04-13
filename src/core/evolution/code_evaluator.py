# src/core/evolution/code_evaluator.py
"""
Code evaluation system for evolved source code candidates.

Evaluators score code on different dimensions:
- TestPassEvaluator: runs pytest and scores based on test pass rate (weight: 0.4)
- CodeCriticEvaluator: uses CriticAgent to score code quality (weight: 0.3)
- SpecCorrectnessEvaluator: evaluates spec compliance (weight: 0.2)
- ComplexityEvaluator: measures cyclomatic complexity (weight: 0.1)

The CodeEvaluator combines these into a composite fitness score.

Based on AlphaEvolve paper: multiple evaluation dimensions are combined with learned
weights to optimize for solution quality.
"""

from __future__ import annotations

import logging
import subprocess
import json
import tempfile
import os
from typing import Dict, Any, Optional
from pathlib import Path

from .candidate import Candidate
from .evaluators import Evaluator, EnsembleEvaluator

logger = logging.getLogger(__name__)


class TestPassEvaluator(Evaluator):
    """
    Evaluates code by running pytest on the evolved code.

    Executes the test suite and scores based on the pass rate.

    Note: Named TestPassEvaluator rather than PassEvaluator to be explicit
    that it evaluates test pass rates, not general pass/fail status.
    """

    def __init__(self):
        super().__init__("test_pass")

    async def evaluate(self, candidate: Candidate) -> dict:
        """Score based on test pass rate."""
        test_result = self._run_tests(self._get_test_directory(candidate))

        pass_rate = test_result.get("pass_rate", 0.0)

        return {
            "score": pass_rate,
            "details": f"Test pass rate: {pass_rate:.1%} ({test_result['passed']}/{test_result['total']})",
            "tests_passed": test_result["passed"],
            "tests_total": test_result["total"],
            "pass_rate": pass_rate,
            "duration": test_result.get("duration", 0.0)
        }

    def _get_test_directory(self, candidate: Candidate) -> str:
        """
        Extract test directory from candidate metadata.

        TODO: Implement logic to determine appropriate test directory.
        For now returns current directory.
        """
        file_path = candidate.metadata.get("file_path", "")
        if file_path:
            return os.path.dirname(file_path)
        return "."

    def _run_tests(self, test_dir: str = ".") -> Dict[str, Any]:
        """
        Run pytest on the specified directory and collect results.

        Args:
            test_dir: Directory to search for tests

        Returns:
            dict with keys: passed, failed, total, pass_rate, duration
        """
        try:
            result = subprocess.run(
                [
                    "python", "-m", "pytest",
                    test_dir,
                    "--tb=short",
                    "-q",
                    "--json-report",
                    "--json-report-file=/tmp/pytest_report.json"
                ],
                capture_output=True,
                text=True,
                timeout=30
            )

            # Try to parse JSON report if available
            json_report_path = "/tmp/pytest_report.json"
            if os.path.exists(json_report_path):
                try:
                    with open(json_report_path) as f:
                        report_data = json.load(f)
                        summary = report_data.get("summary", {})
                        total = summary.get("total", 0)
                        passed = summary.get("passed", 0)
                        failed = summary.get("failed", 0)
                        duration = summary.get("duration", 0.0)
                except Exception as e:
                    logger.warning(f"Could not parse JSON report: {e}")
                    return self._parse_pytest_output(result.stdout, result.stderr)
            else:
                return self._parse_pytest_output(result.stdout, result.stderr)

            pass_rate = passed / total if total > 0 else 0.0

            return {
                "passed": passed,
                "failed": failed,
                "total": total,
                "pass_rate": pass_rate,
                "duration": duration
            }

        except subprocess.TimeoutExpired:
            logger.error("Pytest execution timed out")
            return {
                "passed": 0,
                "failed": 1,
                "total": 1,
                "pass_rate": 0.0,
                "duration": 30.0
            }
        except Exception as e:
            logger.error(f"Error running tests: {e}")
            return {
                "passed": 0,
                "failed": 1,
                "total": 1,
                "pass_rate": 0.0,
                "duration": 0.0
            }

    def _parse_pytest_output(self, stdout: str, stderr: str) -> Dict[str, Any]:
        """
        Parse pytest output when JSON report is not available.

        Extracts pass/fail counts from pytest summary line.
        """
        # Try to parse summary from output
        # Format: "8 passed, 2 failed in 1.23s"
        import re

        output = stdout + stderr

        # Look for pattern like "X passed, Y failed"
        match = re.search(r"(\d+)\s+passed", output)
        passed = int(match.group(1)) if match else 0

        match = re.search(r"(\d+)\s+failed", output)
        failed = int(match.group(1)) if match else 0

        match = re.search(r"in\s+([\d.]+)s", output)
        duration = float(match.group(1)) if match else 0.0

        total = passed + failed

        pass_rate = passed / total if total > 0 else 0.0

        return {
            "passed": passed,
            "failed": failed,
            "total": total,
            "pass_rate": pass_rate,
            "duration": duration
        }


class CodeCriticEvaluator(Evaluator):
    """
    Evaluates code quality using CriticAgent.

    Uses existing CriticAgent infrastructure to score code on:
    - Readability
    - Correctness
    - Maintainability
    - Performance considerations
    """

    def __init__(self):
        super().__init__("code_critic")

    async def evaluate(self, candidate: Candidate) -> dict:
        """Score code quality using CriticAgent."""
        critique = await self._call_code_critic(candidate.content)

        # Convert critic score (0-10) to normalized score (0.0-1.0)
        critic_score = critique.get("score", 5)
        normalized_score = critic_score / 10.0

        return {
            "score": normalized_score,
            "details": f"Code quality score: {critic_score}/10 - {critique.get('summary', 'No summary')}",
            "code_quality_score": critic_score,
            "flaws": critique.get("flaws", []),
            "suggestions": critique.get("suggestions", [])
        }

    async def _call_code_critic(self, code_content: str) -> Dict[str, Any]:
        """
        Call CriticAgent to evaluate code quality.

        TODO: Integrate with actual CriticAgent when available.
        For now returns a placeholder response.
        """
        # Placeholder - would call CriticAgent.review_code() or similar
        # with the code as input

        # Mock response for testing
        return {
            "score": 7,
            "flaws": ["Could add more comments"],
            "suggestions": ["Add type hints", "Consider performance"],
            "summary": "Good code but could be more documented"
        }


class SpecCorrectnessEvaluator(Evaluator):
    """
    Evaluates whether evolved code meets the specification.

    Compares code against the original spec/requirement and scores
    on how well it meets the stated requirements.
    """

    def __init__(self):
        super().__init__("spec_correctness")

    async def evaluate(self, candidate: Candidate) -> dict:
        """Score based on spec compliance."""
        spec = candidate.metadata.get("spec", "")

        if not spec:
            logger.warning(f"Candidate {candidate.id} has no spec, using baseline score")
            return {
                "score": 0.5,
                "details": "No specification provided"
            }

        correctness_score = self._check_spec_compliance(candidate.content, spec)

        return {
            "score": correctness_score,
            "details": f"Spec compliance: {correctness_score:.1%}",
            "spec_compliance": correctness_score
        }

    def _check_spec_compliance(self, code: str, spec: str) -> float:
        """
        Check if code meets the specification.

        TODO: Implement actual spec compliance checking.
        For now returns a baseline score based on code length.
        """
        # Placeholder - would analyze code against spec requirements

        # Simple heuristic: longer code is more likely to be complete
        if len(code) > 200:
            return 0.8
        elif len(code) > 50:
            return 0.6
        else:
            return 0.4


class ComplexityEvaluator(Evaluator):
    """
    Evaluates code complexity using cyclomatic complexity metric.

    Lower complexity is better - simpler code is easier to maintain and test.
    """

    def __init__(self):
        super().__init__("complexity")

    async def evaluate(self, candidate: Candidate) -> dict:
        """Score based on code complexity."""
        complexity = self._calculate_complexity(candidate.content)

        # Convert complexity to score: lower complexity = higher score
        # Assume max acceptable complexity is 10
        # Score = 1.0 - (complexity / 10), clamped to [0, 1]
        complexity_score = max(0.0, min(1.0, 1.0 - (complexity / 10.0)))

        return {
            "score": complexity_score,
            "details": f"Cyclomatic complexity: {complexity} (score: {complexity_score:.2f})",
            "cyclomatic_complexity": complexity
        }

    def _calculate_complexity(self, code: str) -> int:
        """
        Calculate cyclomatic complexity of code.

        Counts decision points: if, elif, else, for, while, except, etc.

        TODO: Implement proper radon-based complexity calculation.
        For now uses a simple heuristic based on keyword count.
        """
        try:
            import ast
            import radon.complexity as cc

            try:
                tree = ast.parse(code)
                # Use radon to calculate actual complexity
                blocks = cc.cc_visit(code)
                if blocks:
                    return max(b.complexity for b in blocks) if blocks else 1
            except SyntaxError:
                logger.warning("Could not parse code for complexity analysis")
                return 1

        except ImportError:
            # Fallback: simple keyword counting
            logger.debug("radon not available, using keyword counting")
            keywords = ["if ", "elif ", "else:", "for ", "while ", "except "]
            count = sum(code.count(kw) for kw in keywords)
            return max(1, count + 1)  # At least 1 for the function itself

        return 1


class CodeEvaluator(EnsembleEvaluator):
    """
    Main code evaluation system combining multiple scoring strategies.

    Weights per spec:
    - Test pass rate: 0.4
    - Code quality (CriticAgent): 0.3
    - Spec correctness: 0.2
    - Code complexity: 0.1
    """

    def __init__(self):
        self.test_evaluator = TestPassEvaluator()
        self.critic_evaluator = CodeCriticEvaluator()
        self.spec_evaluator = SpecCorrectnessEvaluator()
        self.complexity_evaluator = ComplexityEvaluator()

        # Initialize ensemble with weights from spec
        evaluators_with_weights = [
            (self.test_evaluator, 0.4),
            (self.critic_evaluator, 0.3),
            (self.spec_evaluator, 0.2),
            (self.complexity_evaluator, 0.1)
        ]

        super().__init__(evaluators_with_weights)
        self.name = "code_ensemble"

        logger.info("CodeEvaluator initialized with 4 evaluation strategies")
