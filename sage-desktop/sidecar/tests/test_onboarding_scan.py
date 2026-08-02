"""Tests for onboarding.scan_folder / onboarding.save_solution.

Import an EXISTING codebase as a solution: scan the folder, have the LLM draft
the YAML triad, then write it. Scanning deliberately does not touch disk — the
drafts come back for review, and `save_solution` is the separate write step.

The load-bearing assertion here is ``test_scan_folder_calls_generate_with_prompt``.
The web endpoints this ports (api.py:4081 scan-folder, api.py:4125 refine) call
``llm.generate(system_prompt=..., user_prompt=...)``, but
``LLMGateway.generate`` is ``generate(prompt, system_prompt=..., ...)`` with no
``user_prompt`` parameter and no ``**kwargs``. Those calls raise TypeError
every time, get swallowed by a bare ``except Exception``, and are reported to
the user as HTTP 503 "Could not reach the LLM" — so both web endpoints are dead
on arrival. FakeLLM below mirrors the REAL signature, so a regression to
``user_prompt=`` fails loudly here instead of silently degrading.
"""

from __future__ import annotations

import json
import os

import pytest

from handlers import onboarding as onb
from rpc import RpcError

INVALID_PARAMS = -32602
SIDECAR_ERROR = -32000

GENERATED = {
    "project.yaml": "name: imported\ndescription: an imported codebase\n",
    "prompts.yaml": "roles: {}\n",
    "tasks.yaml": "task_types:\n  - name: REVIEW\n    description: review it\n",
}


class FakeLLM:
    """Mirrors LLMGateway.generate's real signature — no `user_prompt`, no
    **kwargs, so an unexpected keyword raises TypeError like the real one."""

    def __init__(self, response: str = ""):
        self.response = response or json.dumps(GENERATED)
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
    """A scannable folder, a fake LLM, a fake audit logger, and a solutions
    dir redirected into tmp so nothing is written into the repo."""
    src = tmp_path / "codebase"
    src.mkdir()
    (src / "main.py").write_text("def run():\n    return 42\n", encoding="utf-8")
    (src / "README.md").write_text("# Demo\nA demo project.\n", encoding="utf-8")

    solutions = tmp_path / "solutions"
    solutions.mkdir()

    llm = FakeLLM()
    logger = FakeLogger()
    monkeypatch.setattr(onb, "_llm", llm)
    monkeypatch.setattr(onb, "_logger", logger)
    monkeypatch.setattr(onb, "_solutions_dir_override", str(solutions))
    return {
        "src": src,
        "solutions": solutions,
        "llm": llm,
        "logger": logger,
    }


# ---------- scan_folder ----------


def test_scan_folder_calls_generate_with_prompt(wired):
    """Regression guard for the web bug: `user_prompt=` is not a parameter of
    LLMGateway.generate, so calling it that way raises TypeError -> 503."""
    onb.scan_folder(
        {
            "folder_path": str(wired["src"]),
            "intent": "import this",
            "solution_name": "imported",
        }
    )
    call = wired["llm"].calls[0]
    assert call["prompt"], "the scanned content must go in as `prompt`"
    assert "main.py" in call["prompt"] or "run" in call["prompt"]
    assert call["system_prompt"], "system_prompt must still be set"


def test_scan_folder_returns_the_yaml_triad_and_a_summary(wired):
    out = onb.scan_folder(
        {
            "folder_path": str(wired["src"]),
            "intent": "import this",
            "solution_name": "imported",
        }
    )
    assert out["solution_name"] == "imported"
    assert set(out["files"]) == {"project.yaml", "prompts.yaml", "tasks.yaml"}
    assert out["summary"]["name"] == "imported"
    assert out["summary"]["task_types"][0]["name"] == "REVIEW"


def test_scan_folder_writes_nothing_to_disk(wired):
    """Scanning is a draft step — the write is save_solution's job (and the
    operator's decision)."""
    onb.scan_folder(
        {
            "folder_path": str(wired["src"]),
            "intent": "import this",
            "solution_name": "imported",
        }
    )
    assert os.listdir(wired["solutions"]) == []


def test_scan_folder_strips_a_markdown_fence(wired, monkeypatch):
    """LLMs wrap JSON in ``` fences — the web helper strips them, so must this."""
    monkeypatch.setattr(
        onb, "_llm", FakeLLM("```json\n" + json.dumps(GENERATED) + "\n```")
    )
    out = onb.scan_folder(
        {
            "folder_path": str(wired["src"]),
            "intent": "x",
            "solution_name": "imported",
        }
    )
    assert out["files"]["prompts.yaml"].strip() == "roles: {}"


def test_scan_folder_rejects_a_missing_folder(wired):
    with pytest.raises(RpcError) as e:
        onb.scan_folder(
            {
                "folder_path": str(wired["src"] / "nope"),
                "intent": "x",
                "solution_name": "imported",
            }
        )
    assert e.value.code == INVALID_PARAMS


def test_scan_folder_rejects_an_empty_folder(wired, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(RpcError) as e:
        onb.scan_folder(
            {
                "folder_path": str(empty),
                "intent": "x",
                "solution_name": "imported",
            }
        )
    assert e.value.code == INVALID_PARAMS


def test_scan_folder_requires_folder_path_and_solution_name(wired):
    for params in (
        {"intent": "x", "solution_name": "imported"},
        {"folder_path": str(wired["src"]), "intent": "x"},
    ):
        with pytest.raises(RpcError) as e:
            onb.scan_folder(params)
        assert e.value.code == INVALID_PARAMS


def test_scan_folder_maps_llm_failure_to_sidecar_error(wired, monkeypatch):
    class Boom:
        def generate(self, prompt, system_prompt="", **_):
            raise RuntimeError("provider down")

    monkeypatch.setattr(onb, "_llm", Boom())
    with pytest.raises(RpcError) as e:
        onb.scan_folder(
            {
                "folder_path": str(wired["src"]),
                "intent": "x",
                "solution_name": "imported",
            }
        )
    assert e.value.code == SIDECAR_ERROR


def test_scan_folder_logs_an_audit_event(wired):
    onb.scan_folder(
        {
            "folder_path": str(wired["src"]),
            "intent": "import this",
            "solution_name": "imported",
        }
    )
    assert wired["logger"].events[0]["action_type"] == "ONBOARDING_SCAN"


# ---------- save_solution ----------


def test_save_solution_writes_the_triad(wired):
    out = onb.save_solution({"solution_name": "imported", "files": GENERATED})
    target = wired["solutions"] / "imported"

    assert out["status"] == "saved"
    assert sorted(os.listdir(target)) == [
        "project.yaml",
        "prompts.yaml",
        "tasks.yaml",
    ]
    assert (target / "prompts.yaml").read_text(encoding="utf-8") == "roles: {}\n"


def test_save_solution_ignores_files_outside_the_triad(wired):
    """A whitelist, not a blacklist — the LLM decides these key names."""
    onb.save_solution(
        {
            "solution_name": "imported",
            "files": {**GENERATED, "../evil.yaml": "x", "notes.txt": "y"},
        }
    )
    target = wired["solutions"] / "imported"
    assert sorted(os.listdir(target)) == [
        "project.yaml",
        "prompts.yaml",
        "tasks.yaml",
    ]
    assert not (wired["solutions"] / "evil.yaml").exists()


@pytest.mark.parametrize(
    "name", ["", "has space", "../escape", "a/b", "x" * 65, "dots.name"]
)
def test_save_solution_rejects_unsafe_names(wired, name):
    with pytest.raises(RpcError) as e:
        onb.save_solution({"solution_name": name, "files": GENERATED})
    assert e.value.code == INVALID_PARAMS


def test_save_solution_requires_files(wired):
    with pytest.raises(RpcError) as e:
        onb.save_solution({"solution_name": "imported", "files": {}})
    assert e.value.code == INVALID_PARAMS


def test_save_solution_logs_an_audit_event(wired):
    onb.save_solution({"solution_name": "imported", "files": GENERATED})
    assert wired["logger"].events[0]["action_type"] == "ONBOARDING_COMPLETE"


# ---------- save_solution: YAML validity ----------
# Item 4d makes the drafted files editable in the review panel, so a hand-edit
# can now introduce a syntax error. Writing that to disk produces a solution
# the framework cannot load, and the failure surfaces much later and far from
# the cause — so validate at the boundary.


def test_save_solution_rejects_unparseable_yaml(wired):
    with pytest.raises(RpcError) as e:
        onb.save_solution(
            {
                "solution_name": "imported",
                "files": {**GENERATED, "project.yaml": "name: [unclosed\n"},
            }
        )
    assert e.value.code == INVALID_PARAMS
    # The operator has three files open; the message must say which one.
    assert "project.yaml" in str(e.value.message)


def test_save_solution_writes_nothing_when_one_file_is_invalid(wired):
    """All-or-nothing: a half-written solution is worse than none."""
    with pytest.raises(RpcError):
        onb.save_solution(
            {
                "solution_name": "imported",
                "files": {**GENERATED, "tasks.yaml": "task_types: [oops\n"},
            }
        )
    assert not (wired["solutions"] / "imported").exists()


def test_save_solution_accepts_valid_edited_yaml(wired):
    edited = {**GENERATED, "project.yaml": "name: imported\ndescription: edited\n"}
    out = onb.save_solution({"solution_name": "imported", "files": edited})
    assert out["status"] == "saved"
    written = (wired["solutions"] / "imported" / "project.yaml").read_text(
        encoding="utf-8"
    )
    assert "edited" in written
