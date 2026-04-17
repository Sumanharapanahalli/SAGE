"""Tests for the sidecar evolution handler."""
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import handlers.evolution as evo  # noqa: E402
from rpc import RpcError  # noqa: E402


class _FakeGym:
    """Minimal AgentGym stub for handler tests."""

    def __init__(
        self,
        leaderboard=None,
        history=None,
        analytics=None,
        train_result=None,
        train_exc=None,
    ):
        self._leaderboard = leaderboard or []
        self._history = history or []
        self._analytics = analytics or {}
        self._train_result = train_result
        self._train_exc = train_exc

    def get_leaderboard(self):
        return list(self._leaderboard)

    def get_history(self, limit=50):
        return list(self._history[:limit])

    def analytics(self, role="", skill=""):
        return {"role": role, "skill": skill, **self._analytics}

    def train(
        self,
        role,
        difficulty="",
        skill_name="",
        exercise_id="",
        enable_peer_review=False,
    ):
        if self._train_exc is not None:
            raise self._train_exc
        return self._train_result


def test_leaderboard_happy_path(monkeypatch):
    rows = [
        {
            "agent_role": "developer",
            "rating": 1215.3,
            "rating_deviation": 92.1,
            "wins": 14,
            "losses": 6,
            "win_rate": 0.70,
            "sessions": 20,
            "streak": 3,
            "best_score": 94.0,
        },
    ]
    monkeypatch.setattr(evo, "_gym", _FakeGym(leaderboard=rows))
    out = evo.leaderboard({})
    assert out["leaderboard"][0]["agent_role"] == "developer"
    assert out["leaderboard"][0]["rating"] == 1215.3
    assert out["stats"]["total_agents"] == 1
    assert out["stats"]["total_sessions"] == 20


def test_leaderboard_empty(monkeypatch):
    monkeypatch.setattr(evo, "_gym", _FakeGym(leaderboard=[]))
    out = evo.leaderboard({})
    assert out["leaderboard"] == []
    assert out["stats"]["total_agents"] == 0
    assert out["stats"]["total_sessions"] == 0
    assert out["stats"]["avg_rating"] == 0.0


def test_leaderboard_rejects_non_dict():
    with pytest.raises(RpcError) as e:
        evo.leaderboard([])
    assert e.value.code == -32602


def test_leaderboard_without_wired_gym_raises_sidecar_down(monkeypatch):
    monkeypatch.setattr(evo, "_gym", None)
    with pytest.raises(RpcError) as e:
        evo.leaderboard({})
    assert e.value.code == -32000


def test_history_default_limit(monkeypatch):
    sessions = [{"session_id": f"s{i}", "score": 50.0 + i} for i in range(60)]
    monkeypatch.setattr(evo, "_gym", _FakeGym(history=sessions))
    out = evo.history({})
    assert len(out["sessions"]) == 50
    assert out["sessions"][0]["session_id"] == "s0"


def test_history_respects_custom_limit(monkeypatch):
    sessions = [{"session_id": f"s{i}"} for i in range(20)]
    monkeypatch.setattr(evo, "_gym", _FakeGym(history=sessions))
    out = evo.history({"limit": 5})
    assert len(out["sessions"]) == 5


def test_history_rejects_non_positive_limit(monkeypatch):
    monkeypatch.setattr(evo, "_gym", _FakeGym(history=[]))
    with pytest.raises(RpcError) as e:
        evo.history({"limit": 0})
    assert e.value.code == -32602


def test_analytics_forwards_role_and_skill(monkeypatch):
    monkeypatch.setattr(evo, "_gym", _FakeGym(analytics={"weakness_map": []}))
    out = evo.analytics({"role": "developer", "skill": "openswe"})
    assert out["role"] == "developer"
    assert out["skill"] == "openswe"
    assert out["weakness_map"] == []


def test_analytics_unknown_role_returns_whatever_gym_returns(monkeypatch):
    monkeypatch.setattr(evo, "_gym", _FakeGym(analytics={"score_trend": []}))
    out = evo.analytics({"role": "not_a_real_role"})
    assert out["score_trend"] == []


def test_train_requires_role(monkeypatch):
    monkeypatch.setattr(evo, "_gym", _FakeGym())
    with pytest.raises(RpcError) as e:
        evo.train({})
    assert e.value.code == -32602


def test_train_happy_path(monkeypatch):
    session = {
        "session_id": "2026-04-17T12:00:00",
        "agent_role": "developer",
        "status": "completed",
        "grade": {"score": 78.0, "passed": True},
        "elo_before": 1215.3,
        "elo_after": 1228.9,
        "reflection": "Missed the empty-input edge case.",
        "improvement_plan": ["write guard clause"],
        "duration_s": 14.2,
    }
    monkeypatch.setattr(evo, "_gym", _FakeGym(train_result=session))
    out = evo.train({"role": "developer", "difficulty": "beginner"})
    assert out["status"] == "completed"
    assert out["elo_after"] == 1228.9


def test_train_llm_unavailable_maps_to_sidecar_down(monkeypatch):
    monkeypatch.setattr(
        evo,
        "_gym",
        _FakeGym(train_exc=RuntimeError("LLM down")),
    )
    with pytest.raises(RpcError) as e:
        evo.train({"role": "developer"})
    assert e.value.code == -32000
