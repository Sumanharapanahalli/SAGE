"""Tests for onboarding.refine — the conversational refine loop.

Hand the LLM the current drafts plus feedback, get revised drafts back. Like
scan_folder this writes NOTHING; refining is a draft step and `save_solution`
remains the only write.

Same fatal web bug as scan-folder applies here: api.py:4125 calls
``llm.generate(system_prompt=..., user_prompt=...)`` but ``LLMGateway.generate``
takes ``prompt`` and has no ``**kwargs``, so `/onboarding/refine` raises
TypeError on every call and reports it as 503 "Could not reach the LLM". It has
never worked. FakeLLM mirrors the real signature so a regression to
``user_prompt=`` fails loudly here.
"""

from __future__ import annotations

import json
import os

import pytest

from handlers import onboarding as onb
from rpc import RpcError

INVALID_PARAMS = -32602
SIDECAR_ERROR = -32000

CURRENT = {
    "project.yaml": "name: imported\ndescription: old description\n",
    "prompts.yaml": "roles: {}\n",
    "tasks.yaml": "task_types: []\n",
}

REVISED = {
    "project.yaml": "name: imported\ndescription: a much better description\n",
    "prompts.yaml": "roles: {}\n",
    "tasks.yaml": "task_types:\n  - name: REVIEW\n    description: review it\n",
}


class FakeLLM:
    """Mirrors LLMGateway.generate's real signature — no `user_prompt`, no
    **kwargs, so an unexpected keyword raises TypeError like the real one."""

    def __init__(self, response: str = ""):
        self.response = response or json.dumps(REVISED)
        self.calls: list[dict] = []

    def generate(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful AI assistant.",
        trace_name: str = "llm_generate",
        metadata: dict | None = None,
        trace_id: str = "",
        agent_name: str = "",
        request_id: str = "",
    ) -> str:
        self.calls.append({"prompt": prompt, "system_prompt": system_prompt})
        return self.response


class FakeLogger:
    def __init__(self):
        self.events: list[dict] = []

    def log_event(self, **kw):
        self.events.append(kw)


@pytest.fixture
def wired(tmp_path, monkeypatch):
    solutions = tmp_path / "solutions"
    solutions.mkdir()
    llm = FakeLLM()
    logger = FakeLogger()
    monkeypatch.setattr(onb, "_llm", llm)
    monkeypatch.setattr(onb, "_logger", logger)
    monkeypatch.setattr(onb, "_solutions_dir_override", str(solutions))
    return {"llm": llm, "logger": logger, "solutions": solutions}


def _refine(**overrides):
    params = {
        "solution_name": "imported",
        "current_files": CURRENT,
        "feedback": "make the description better",
    }
    params.update(overrides)
    return onb.refine(params)


def test_refine_calls_generate_with_prompt(wired):
    """Regression guard for the web bug at api.py:4125."""
    _refine()
    call = wired["llm"].calls[0]
    assert call["prompt"], "drafts + feedback must go in as `prompt`"
    assert call["system_prompt"]


def test_refine_sends_the_feedback_and_the_current_files(wired):
    _refine(feedback="add a REVIEW task type")
    prompt = wired["llm"].calls[0]["prompt"]

    assert "add a REVIEW task type" in prompt
    # The LLM cannot revise what it cannot see.
    assert "old description" in prompt
    assert "project.yaml" in prompt


def test_refine_returns_the_revised_triad_and_summary(wired):
    out = _refine()

    assert out["solution_name"] == "imported"
    assert "much better description" in out["files"]["project.yaml"]
    assert out["summary"]["task_types"][0]["name"] == "REVIEW"


def test_refine_writes_nothing(wired):
    """Refining is a draft step — save_solution stays the only write."""
    _refine()
    assert os.listdir(wired["solutions"]) == []


def test_refine_strips_a_markdown_fence(wired, monkeypatch):
    monkeypatch.setattr(
        onb, "_llm", FakeLLM("```json\n" + json.dumps(REVISED) + "\n```")
    )
    out = _refine()
    assert "much better description" in out["files"]["project.yaml"]


def test_refine_is_iterable(wired):
    """The loop in 'refine loop': the output of one pass must be valid input
    to the next, so the operator can keep going until satisfied."""
    first = _refine()
    second = onb.refine(
        {
            "solution_name": "imported",
            "current_files": first["files"],
            "feedback": "now add another task type",
        }
    )
    assert second["files"]
    assert "now add another task type" in wired["llm"].calls[1]["prompt"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"solution_name": ""},
        {"feedback": ""},
        {"current_files": {}},
        {"current_files": "not a dict"},
    ],
)
def test_refine_rejects_bad_input(wired, overrides):
    with pytest.raises(RpcError) as e:
        _refine(**overrides)
    assert e.value.code == INVALID_PARAMS


def test_refine_maps_llm_failure_to_sidecar_error(wired, monkeypatch):
    class Boom:
        def generate(self, prompt, system_prompt="", **_):
            raise RuntimeError("provider down")

    monkeypatch.setattr(onb, "_llm", Boom())
    with pytest.raises(RpcError) as e:
        _refine()
    assert e.value.code == SIDECAR_ERROR


def test_refine_logs_an_audit_event(wired):
    _refine(feedback="tighten it up")
    event = wired["logger"].events[0]
    assert event["action_type"] == "ONBOARDING_REFINE"
    assert event["input_context"] == "tighten it up"
