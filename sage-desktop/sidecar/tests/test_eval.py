from pathlib import Path

import pytest

from handlers import eval as eval_handler
from rpc import RpcError


@pytest.fixture
def runner(tmp_path: Path):
    from src.core.eval_runner import EvalRunner

    return EvalRunner(db_path=str(tmp_path / "eval_runs.db"))


@pytest.fixture(autouse=True)
def inject(runner):
    eval_handler._runner = runner
    yield
    eval_handler._runner = None


# ---------- eval.list_suites ----------


def test_list_suites_not_wired_raises():
    eval_handler._runner = None
    with pytest.raises(RpcError):
        eval_handler.list_suites({})


def test_list_suites_returns_names_and_count(runner, monkeypatch):
    monkeypatch.setattr(runner, "list_suites", lambda: ["smoke", "regression"])
    result = eval_handler.list_suites({})
    assert result == {"suites": ["smoke", "regression"], "count": 2}


def test_list_suites_empty_when_no_evals_dir(runner, monkeypatch):
    monkeypatch.setattr(runner, "list_suites", lambda: [])
    result = eval_handler.list_suites({})
    assert result == {"suites": [], "count": 0}


# ---------- eval.run ----------


def test_run_not_wired_raises():
    eval_handler._runner = None
    with pytest.raises(RpcError):
        eval_handler.run({})


def test_run_passes_suite_through(runner, monkeypatch):
    captured = {}

    def fake_run(suite=None):
        captured["suite"] = suite
        return {
            "run_id": "r1",
            "suite": suite or "all",
            "total_cases": 1,
            "passed_cases": 1,
            "failed_cases": 0,
            "mean_score": 9.0,
            "results": [],
        }

    monkeypatch.setattr(runner, "run", fake_run)
    result = eval_handler.run({"suite": "smoke"})
    assert captured["suite"] == "smoke"
    assert result["run_id"] == "r1"


def test_run_omitted_suite_runs_all(runner, monkeypatch):
    captured = {}

    def fake_run(suite=None):
        captured["suite"] = suite
        return {
            "run_id": "r2",
            "suite": "all",
            "total_cases": 0,
            "passed_cases": 0,
            "failed_cases": 0,
            "mean_score": 0.0,
            "results": [],
        }

    monkeypatch.setattr(runner, "run", fake_run)
    eval_handler.run({})
    assert captured["suite"] is None


def test_run_translates_error_dict_to_invalid_params(runner, monkeypatch):
    monkeypatch.setattr(
        runner, "run", lambda suite=None: {"error": "No eval suites found"}
    )
    with pytest.raises(RpcError) as exc_info:
        eval_handler.run({})
    assert exc_info.value.code == -32602


# ---------- eval.history ----------


def test_history_not_wired_raises():
    eval_handler._runner = None
    with pytest.raises(RpcError):
        eval_handler.history({})


def test_history_returns_list_and_count(runner, monkeypatch):
    rows = [{"run_id": "r1", "suite": "smoke", "mean_score": 9.0}]
    monkeypatch.setattr(runner, "get_history", lambda suite=None, limit=20: rows)
    result = eval_handler.history({})
    assert result == {"history": rows, "count": 1}


def test_history_passes_suite_and_limit_through(runner, monkeypatch):
    captured = {}

    def fake_get_history(suite=None, limit=20):
        captured["suite"] = suite
        captured["limit"] = limit
        return []

    monkeypatch.setattr(runner, "get_history", fake_get_history)
    eval_handler.history({"suite": "smoke", "limit": 5})
    assert captured == {"suite": "smoke", "limit": 5}


def test_history_defaults_limit_to_20(runner, monkeypatch):
    captured = {}

    def fake_get_history(suite=None, limit=20):
        captured["limit"] = limit
        return []

    monkeypatch.setattr(runner, "get_history", fake_get_history)
    eval_handler.history({})
    assert captured["limit"] == 20
