"""Tests for the reflect.* sidecar handlers (reflection engine bridge)."""

from __future__ import annotations

import json

import pytest

from handlers import reflect
from rpc import RpcError


class _FakeLLM:
    """Fake LLM gateway: returns a JSON critique for critic calls, a plain
    answer for generator calls (distinguished by the critic system prompt)."""

    def __init__(self, score: float = 0.95):
        self._score = score
        self.calls = 0

    def generate(self, prompt: str, system_prompt: str) -> str:
        self.calls += 1
        if "strict critic" in system_prompt.lower():
            return json.dumps({"score": self._score, "feedback": "solid answer"})
        return "a candidate answer that is reasonably detailed and helpful to the task"


def test_run_accepts_high_scoring_output(monkeypatch):
    monkeypatch.setattr(reflect, "_llm_factory", lambda: _FakeLLM(score=0.95))
    out = reflect.run({"task": "Summarise the main risk of approach X"})
    assert "reflection_id" in out
    assert out["accepted"] is True
    assert out["iterations"] >= 1
    assert "final_output" in out


def test_run_requires_task():
    with pytest.raises(RpcError):
        reflect.run({"task": "   "})


def test_run_rejects_bad_max_iterations(monkeypatch):
    monkeypatch.setattr(reflect, "_llm_factory", lambda: _FakeLLM())
    with pytest.raises(RpcError):
        reflect.run({"task": "x", "max_iterations": 0})


def test_stats_and_recent_reflect_a_run(monkeypatch):
    monkeypatch.setattr(reflect, "_llm_factory", lambda: _FakeLLM(score=0.9))
    result = reflect.run({"task": "Improve this plan"})
    stats = reflect.stats({})
    assert stats["total_reflections"] >= 1
    recent = reflect.recent({"limit": 5})
    assert recent["count"] >= 1
    ids = {r["reflection_id"] for r in recent["reflections"]}
    assert result["reflection_id"] in ids


def test_recent_rejects_bad_limit():
    with pytest.raises(RpcError):
        reflect.recent({"limit": "lots"})


def test_get_unknown_reflection_raises():
    with pytest.raises(RpcError):
        reflect.get({"reflection_id": "does-not-exist"})


def test_start_and_progress_stream_iterations(monkeypatch):
    import time

    reflect.reset_progress()
    monkeypatch.setattr(reflect, "_llm_factory", lambda: _FakeLLM(score=0.95))
    started = reflect.start({"task": "Draft a rollback plan"})
    run_id = started["run_id"]
    assert started["state"] == "running"

    # Poll until the background job finishes (fast with the fake LLM).
    deadline = time.time() + 5
    prog = reflect.progress({"run_id": run_id})
    while prog["state"] == "running" and time.time() < deadline:
        time.sleep(0.02)
        prog = reflect.progress({"run_id": run_id})

    assert prog["state"] == "succeeded"
    assert len(prog["iterations"]) >= 1
    assert prog["iterations"][0]["score"] == 0.95
    assert prog["result"]["accepted"] is True


def test_progress_unknown_run_id_raises():
    with pytest.raises(RpcError):
        reflect.progress({"run_id": "nope"})


def test_start_requires_task():
    with pytest.raises(RpcError):
        reflect.start({"task": ""})


def test_parse_critique_tolerates_noise():
    score, feedback = reflect._parse_critique(
        'noise {"score": 0.8, "feedback": "ok"} tail'
    )
    assert score == 0.8
    assert feedback == "ok"
    # Unparseable falls back to a heuristic, never raises.
    score2, _ = reflect._parse_critique("not json at all")
    assert 0.0 <= score2 <= 1.0
