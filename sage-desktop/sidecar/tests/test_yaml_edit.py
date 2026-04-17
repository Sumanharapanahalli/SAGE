"""Tests for the YAML authoring handler.

Covers:
- read: happy path, missing file → InvalidParams, bad file name → InvalidParams.
- write: validates YAML syntax before touching disk; rejects bad file name.
- missing solution path → SidecarDown.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import handlers.yaml_edit as yaml_edit  # noqa: E402
from rpc import RpcError  # noqa: E402


@pytest.fixture
def wired_solution(tmp_path, monkeypatch):
    (tmp_path / "project.yaml").write_text(
        "name: demo\nversion: 1\n", encoding="utf-8"
    )
    (tmp_path / "prompts.yaml").write_text("agents: []\n", encoding="utf-8")
    monkeypatch.setattr(yaml_edit, "_solution_path", tmp_path)
    monkeypatch.setattr(yaml_edit, "_solution_name", "demo")
    return tmp_path


def test_read_returns_existing_file(wired_solution):
    out = yaml_edit.read({"file": "project"})
    assert out["file"] == "project"
    assert out["solution"] == "demo"
    assert "name: demo" in out["content"]


def test_read_rejects_invalid_file_name(wired_solution):
    with pytest.raises(RpcError) as e:
        yaml_edit.read({"file": "secrets"})
    assert e.value.code == -32602


def test_read_rejects_missing_file(wired_solution):
    with pytest.raises(RpcError) as e:
        yaml_edit.read({"file": "tasks"})
    assert e.value.code == -32602
    assert "tasks.yaml" in e.value.message


def test_read_fails_when_solution_unwired(monkeypatch):
    monkeypatch.setattr(yaml_edit, "_solution_path", None)
    with pytest.raises(RpcError) as e:
        yaml_edit.read({"file": "project"})
    assert e.value.code == -32000


def test_write_happy_path(wired_solution):
    new_content = "name: demo\nversion: 2\nlang: en\n"
    out = yaml_edit.write({"file": "project", "content": new_content})
    assert out["file"] == "project"
    assert out["bytes"] == len(new_content.encode("utf-8"))
    assert (wired_solution / "project.yaml").read_text(encoding="utf-8") == new_content


def test_write_rejects_invalid_yaml(wired_solution):
    with pytest.raises(RpcError) as e:
        yaml_edit.write({"file": "project", "content": "{: unbalanced ["})
    assert e.value.code == -32602
    # Original content is untouched
    assert "name: demo\nversion: 1" in (
        wired_solution / "project.yaml"
    ).read_text(encoding="utf-8")


def test_write_rejects_invalid_file_name(wired_solution):
    with pytest.raises(RpcError) as e:
        yaml_edit.write({"file": "../evil", "content": "ok: true\n"})
    assert e.value.code == -32602


def test_write_rejects_non_string_content(wired_solution):
    with pytest.raises(RpcError) as e:
        yaml_edit.write({"file": "project", "content": 42})
    assert e.value.code == -32602


def test_write_creates_file_when_missing(wired_solution):
    out = yaml_edit.write({"file": "tasks", "content": "tasks: []\n"})
    assert out["file"] == "tasks"
    assert (wired_solution / "tasks.yaml").exists()


def test_write_fails_when_solution_unwired(monkeypatch):
    monkeypatch.setattr(yaml_edit, "_solution_path", None)
    with pytest.raises(RpcError) as e:
        yaml_edit.write({"file": "project", "content": "x: 1\n"})
    assert e.value.code == -32000
