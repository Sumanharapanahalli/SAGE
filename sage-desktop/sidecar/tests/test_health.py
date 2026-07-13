"""Tests for the preflight handler.

The contract that matters: preflight NEVER mutates (no proposal, no audit
event), NEVER crashes on a missing optional dep (warning, not error), and
NEVER blocks the serial dispatch loop on a hung LLM provider.
"""
from __future__ import annotations

import time

import pytest

from handlers import health
from rpc import RpcError


class _FakeLLM:
    def __init__(self, reply="OK", provider="gemini", model="gemini-2.0-flash", exc=None, delay=0.0):
        self._reply, self._provider, self._model = reply, provider, model
        self._exc, self._delay = exc, delay
        self.calls = 0

    def get_provider_name(self):
        return self._provider

    def get_model_info(self):
        return {"model": self._model}

    def generate(self, prompt, system_prompt="", **kwargs):
        self.calls += 1
        if self._delay:
            time.sleep(self._delay)
        if self._exc:
            raise self._exc
        return self._reply


class _FakeVM:
    def __init__(self, mode="full", entries=3, raises=False):
        self.mode = mode
        self._entries = entries
        self._raises = raises

    def list_entries(self, limit=50):
        if self._raises:
            raise RuntimeError("chroma exploded")
        return [{"id": str(i), "text": f"e{i}", "metadata": {}} for i in range(self._entries)]


class _FakeProject:
    project_name = "medtech"

    def get_task_types(self):
        return ["CODE_REVIEW", "LOG_ANALYSIS"]


@pytest.fixture
def solution(tmp_path):
    sol = tmp_path / "medtech"
    sol.mkdir()
    for f in ("project.yaml", "prompts.yaml", "tasks.yaml"):
        (sol / f).write_text("x: 1\n", encoding="utf-8")
    return sol


@pytest.fixture(autouse=True)
def wired(monkeypatch, solution):
    monkeypatch.setattr(health, "_llm", _FakeLLM())
    monkeypatch.setattr(health, "_vm", _FakeVM())
    monkeypatch.setattr(health, "_project", _FakeProject())
    monkeypatch.setattr(health, "_solution_name", "medtech")
    monkeypatch.setattr(health, "_solution_path", solution)


def _by_name(out, name):
    return next(c for c in out["checks"] if c["name"] == name)


def test_all_checks_present_and_shaped():
    out = health.preflight({})
    names = [c["name"] for c in out["checks"]]
    assert names == [
        "Sidecar alive",
        "Solution config",
        "LLM provider",
        "Vector store",
        "Skill registry",
    ]
    for c in out["checks"]:
        assert c["status"] in {"ok", "warning", "error"}
        assert isinstance(c["detail"], str)
        assert isinstance(c["latency_ms"], float)
        assert c["latency_ms"] >= 0
    assert isinstance(out["go"], bool)
    assert out["solution"] == "medtech"


def test_happy_path_is_go():
    out = health.preflight({})
    assert out["go"] is True
    assert out["errors"] == 0
    assert _by_name(out, "Sidecar alive")["status"] == "ok"
    assert _by_name(out, "LLM provider")["status"] == "ok"
    assert _by_name(out, "Solution config")["status"] == "ok"


def test_llm_probe_calls_generate_exactly_once(monkeypatch):
    fake = _FakeLLM()
    monkeypatch.setattr(health, "_llm", fake)
    health.preflight({})
    assert fake.calls == 1


def test_llm_probe_reports_latency():
    out = health.preflight({})
    assert _by_name(out, "LLM provider")["latency_ms"] >= 0


def test_llm_failure_is_an_error_and_blocks_go(monkeypatch):
    monkeypatch.setattr(health, "_llm", _FakeLLM(exc=RuntimeError("429 quota")))
    out = health.preflight({})
    llm = _by_name(out, "LLM provider")
    assert llm["status"] == "error"
    assert "429 quota" in llm["detail"]
    assert out["go"] is False


def test_llm_not_wired_is_an_error(monkeypatch):
    monkeypatch.setattr(health, "_llm", None)
    out = health.preflight({})
    assert _by_name(out, "LLM provider")["status"] == "error"
    assert out["go"] is False


def test_empty_llm_reply_is_a_warning_not_an_error(monkeypatch):
    monkeypatch.setattr(health, "_llm", _FakeLLM(reply="  "))
    out = health.preflight({})
    assert _by_name(out, "LLM provider")["status"] == "warning"
    assert out["go"] is True


def test_hung_llm_times_out_instead_of_wedging_the_dispatch_loop(monkeypatch):
    """A provider that never returns must not block the serial NDJSON loop."""
    monkeypatch.setattr(health, "_llm", _FakeLLM(delay=30.0))
    started = time.perf_counter()
    out = health.preflight({"timeout_ms": 1000})
    elapsed = time.perf_counter() - started
    assert elapsed < 10.0
    llm = _by_name(out, "LLM provider")
    assert llm["status"] == "error"
    assert "did not respond" in llm["detail"]
    assert out["go"] is False


def test_minimal_vector_backend_is_a_warning_not_an_error(monkeypatch):
    monkeypatch.setattr(health, "_vm", _FakeVM(mode="minimal"))
    out = health.preflight({})
    vs = _by_name(out, "Vector store")
    assert vs["status"] == "warning"
    assert "minimal" in vs["detail"]
    assert out["go"] is True  # degraded, still operable
    assert out["warnings"] >= 1


def test_missing_vector_store_is_a_warning(monkeypatch):
    monkeypatch.setattr(health, "_vm", None)
    out = health.preflight({})
    assert _by_name(out, "Vector store")["status"] == "warning"
    assert out["go"] is True


def test_vector_store_reports_backend_and_entry_count():
    out = health.preflight({})
    detail = _by_name(out, "Vector store")["detail"]
    assert "full" in detail and "3 entries" in detail


def test_llamaindex_backend_reported_as_full(monkeypatch):
    monkeypatch.setattr(health, "_vm", _FakeVM(mode="llamaindex"))
    out = health.preflight({})
    assert _by_name(out, "Vector store")["status"] == "ok"
    assert "backend=full" in _by_name(out, "Vector store")["detail"]


def test_vector_store_count_failure_degrades_to_warning(monkeypatch):
    monkeypatch.setattr(health, "_vm", _FakeVM(raises=True))
    out = health.preflight({})
    assert _by_name(out, "Vector store")["status"] == "warning"
    assert out["go"] is True


def test_no_solution_is_an_error(monkeypatch):
    monkeypatch.setattr(health, "_solution_name", "")
    monkeypatch.setattr(health, "_solution_path", None)
    out = health.preflight({})
    assert _by_name(out, "Solution config")["status"] == "error"
    assert out["go"] is False


def test_missing_yaml_triad_member_is_an_error(monkeypatch, solution):
    (solution / "tasks.yaml").unlink()
    out = health.preflight({})
    cfg = _by_name(out, "Solution config")
    assert cfg["status"] == "error"
    assert "tasks.yaml" in cfg["detail"]
    assert out["go"] is False


def test_skill_md_supersedes_the_yaml_triad(monkeypatch, solution):
    for f in ("project.yaml", "prompts.yaml", "tasks.yaml"):
        (solution / f).unlink()
    (solution / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
    out = health.preflight({})
    cfg = _by_name(out, "Solution config")
    assert cfg["status"] == "ok"
    assert "SKILL.md" in cfg["detail"]


def test_unloadable_project_config_is_an_error(monkeypatch):
    monkeypatch.setattr(health, "_project", None)
    out = health.preflight({})
    assert _by_name(out, "Solution config")["status"] == "error"
    assert out["go"] is False


def test_skill_registry_import_failure_degrades_to_warning(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def boom(name, *a, **kw):
        if name == "src.core.skill_loader":
            raise ImportError("no skill_loader")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", boom)
    out = health.preflight({})
    monkeypatch.undo()
    assert _by_name(out, "Skill registry")["status"] == "warning"


def test_rejects_non_integer_timeout():
    with pytest.raises(RpcError):
        health.preflight({"timeout_ms": "soon"})


def test_rejects_out_of_range_timeout():
    with pytest.raises(RpcError):
        health.preflight({"timeout_ms": 1})
    with pytest.raises(RpcError):
        health.preflight({"timeout_ms": 999_999})


def test_none_params_is_accepted():
    out = health.preflight(None)
    assert "checks" in out


def test_preflight_is_non_mutating(monkeypatch):
    """Preflight must never touch the proposal queue — that is its whole reason
    for existing (today the only LLM liveness test is analyze.run)."""
    from handlers import analyze

    monkeypatch.setattr(analyze, "_store", object())  # any use would blow up
    out = health.preflight({})
    assert "proposal_id" not in out
    assert out["checks"]
