"""Tests for the Evaluator-Optimizer loop (mock providers — no live LLMs)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.core.evaluator_optimizer import EvaluatorOptimizerRunner, _extract_json

pytestmark = pytest.mark.unit


class MockOptimizer:
    """Returns 'solution vN'; records the prompts it received."""
    def __init__(self):
        self.prompts = []
    def generate(self, prompt, system_prompt=""):
        self.prompts.append(prompt)
        return f"solution v{len(self.prompts)}"


class MockEvaluator:
    """Replays a fixed list of JSON responses (repeats the last)."""
    def __init__(self, responses):
        self.responses = responses
        self.i = 0
    def generate(self, prompt, system_prompt=""):
        r = self.responses[min(self.i, len(self.responses) - 1)]
        self.i += 1
        return r


def _run(opt, ev, **cfg):
    # mechanics tests use fixed evaluator response sequences, so disable rubric
    # sharpening (which would consume the first response); rubric has its own tests.
    base = {"optimizer_provider": opt, "evaluator_provider": ev,
            "max_iterations": 4, "score_threshold": 8.0, "generate_rubric": False}
    base.update(cfg)
    return EvaluatorOptimizerRunner(base).run("improve the thing", context="current artifact")


def test_converges_when_evaluator_passes():
    ev = MockEvaluator(['{"score": 6, "pass": false, "feedback": "fix the edge case"}',
                        '{"score": 9, "pass": true, "feedback": ""}'])
    r = _run(MockOptimizer(), ev)
    assert r["converged"] is True
    assert r["iterations"] == 2
    assert r["final"] == "solution v2"
    assert r["score"] == 9


def test_threshold_pass_without_explicit_pass_flag():
    # score >= threshold counts as passed even if pass=false
    ev = MockEvaluator(['{"score": 8.5, "pass": false, "feedback": "good enough"}'])
    r = _run(MockOptimizer(), ev)
    assert r["converged"] is True and r["iterations"] == 1


def test_max_iterations_returns_best_candidate():
    ev = MockEvaluator(['{"score": 4, "pass": false, "feedback": "a"}',
                        '{"score": 7, "pass": false, "feedback": "b"}',
                        '{"score": 5, "pass": false, "feedback": "c"}'])
    r = _run(MockOptimizer(), ev, max_iterations=3)
    assert r["converged"] is False
    assert r["iterations"] == 3
    assert r["score"] == 7                       # best of 4/7/5
    assert r["final"] == "solution v2"           # the iteration that scored 7


def test_optimizer_receives_evaluator_feedback():
    opt = MockOptimizer()
    ev = MockEvaluator(['{"score": 5, "pass": false, "feedback": "ADDRESS_THIS_POINT"}',
                        '{"score": 9, "pass": true, "feedback": ""}'])
    _run(opt, ev)
    # iteration 1 prompt has no feedback; iteration 2 prompt must carry it
    assert "ADDRESS_THIS_POINT" not in opt.prompts[0]
    assert "ADDRESS_THIS_POINT" in opt.prompts[1]


def test_extract_json_tolerates_fences_and_prose():
    assert _extract_json('```json\n{"score": 9, "pass": true}\n```')["score"] == 9
    assert _extract_json('Here is my verdict: {"score": 3, "pass": false} done')["score"] == 3
    assert _extract_json("not json at all") is None


def test_missing_providers_returns_error():
    r = EvaluatorOptimizerRunner({"optimizer_provider": None, "evaluator_provider": None}).run("x")
    assert r["converged"] is False and "error" in r


# -- hardening: rubric sharpening, fence stripping, retry, sandbox ----------

class RecordingEvaluator:
    """Records the prompts it received; replays a fixed JSON response list."""
    def __init__(self, responses):
        self.responses = responses
        self.prompts = []
    def generate(self, prompt, system_prompt=""):
        self.prompts.append(prompt)
        r = self.responses[min(len(self.prompts) - 1, len(self.responses) - 1)]
        return r


def test_rubric_is_generated_and_fed_into_evaluation():
    # first evaluator call is the rubric request; it must flow into the eval prompt
    ev = RecordingEvaluator([
        "1. must be correct\n2. must be clear",          # rubric
        '{"score": 9, "pass": true, "feedback": ""}',     # evaluation
    ])
    r = EvaluatorOptimizerRunner(
        {"optimizer_provider": MockOptimizer(), "evaluator_provider": ev,
         "generate_rubric": True}
    ).run("improve the thing")
    assert r["converged"] is True
    # the rubric request came first, then the evaluation carried the sharpened rubric
    assert "scoring rubric" in ev.prompts[0]
    assert "DETAILED RUBRIC" in ev.prompts[1]


def test_strip_fences_unwraps_single_code_block():
    s = EvaluatorOptimizerRunner._strip_fences
    assert s("```tsx\nconst x = 1;\n```") == "const x = 1;"
    assert s("```\nplain\n```") == "plain"
    assert s("no fence here") == "no fence here"        # untouched
    assert s("") == ""


def test_optimizer_retries_once_on_empty():
    class FlakyOptimizer:
        def __init__(self):
            self.calls = 0
        def generate(self, prompt, system_prompt=""):
            self.calls += 1
            return "" if self.calls == 1 else "recovered solution"
    opt = FlakyOptimizer()
    ev = MockEvaluator(['{"score": 9, "pass": true, "feedback": ""}'])
    r = EvaluatorOptimizerRunner(
        {"optimizer_provider": opt, "evaluator_provider": ev, "generate_rubric": False}
    ).run("x")
    assert opt.calls == 2                 # retried after the empty first response
    assert r["final"] == "recovered solution"


def test_sandbox_hardening_applied_to_built_optimizer():
    # when SAGE builds the optimizer itself, it must be tool-restricted + sandboxed
    captured = {}
    def fake_build(cfg):
        captured.update(cfg)
        return MockOptimizer()
    EvaluatorOptimizerRunner(
        {"optimizer": {"provider": "claude-code"}, "evaluator_provider": MockEvaluator(["{}"])},
        build_provider=fake_build,
    )
    assert "Write" in captured.get("disallowed_tools", "")
    assert "Edit" in captured.get("disallowed_tools", "")
    assert captured.get("cwd")            # a throwaway sandbox cwd was assigned
