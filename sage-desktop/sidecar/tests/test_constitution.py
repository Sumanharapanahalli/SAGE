"""Tests for the Constitution authoring handler.

Uses a tiny in-memory fake that mirrors the surface of
``src.core.constitution.Constitution`` so the handler layer is tested
without loading the full framework. One happy-path test exercises the
real class against a tmp YAML file to guard the contract.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import handlers.constitution as constitution  # noqa: E402
from rpc import RpcError  # noqa: E402


class _FakeCtx:
    def __init__(self) -> None:
        self._data: dict = {
            "meta": {
                "name": "demo",
                "version": 1,
                "last_updated": "",
                "updated_by": "",
            },
            "principles": [{"id": "p1", "text": "Test first", "weight": 0.8}],
            "constraints": ["Never touch /prod/"],
        }
        self._path = "/tmp/demo/constitution.yaml"
        self.reloaded = 0
        self.saved_with: list[str] = []

    def to_dict(self) -> dict:
        import copy
        return copy.deepcopy(self._data)

    def get_stats(self) -> dict:
        return {
            "is_empty": False,
            "name": self._data["meta"]["name"],
            "version": self._data["meta"]["version"],
            "principle_count": len(self._data.get("principles", [])),
            "constraint_count": len(self._data.get("constraints", [])),
            "non_negotiable_count": sum(
                1 for p in self._data.get("principles", []) if p.get("weight", 0) >= 1.0
            ),
            "has_voice": bool(self._data.get("voice")),
            "has_decisions": bool(self._data.get("decisions")),
            "has_knowledge": bool(self._data.get("knowledge")),
            "history_entries": len(self._data.get("_history", [])),
        }

    def build_prompt_preamble(self) -> str:
        return "## Solution Constitution\n### Guiding Principles (by priority)\n- Test first"

    def get_version_history(self) -> list:
        return list(self._data.get("_history", []))

    def validate(self) -> list[str]:
        errors = []
        for i, p in enumerate(self._data.get("principles", [])):
            if "id" not in p:
                errors.append(f"Principle {i}: missing 'id' field")
        return errors

    def reload(self) -> None:
        self.reloaded += 1

    def save(self, changed_by: str = "system") -> None:
        self.saved_with.append(changed_by)
        self._data["meta"]["version"] += 1

    @property
    def version(self) -> int:
        return self._data["meta"]["version"]

    def check_action(self, desc: str) -> dict:
        return {
            "allowed": "/prod/" not in desc.lower(),
            "violations": ["Never touch /prod/"] if "/prod/" in desc.lower() else [],
        }


@pytest.fixture
def wired(monkeypatch) -> _FakeCtx:
    fake = _FakeCtx()
    monkeypatch.setattr(constitution, "_ctx", fake)
    return fake


def test_get_returns_full_state(wired):
    out = constitution.get({})
    assert out["stats"]["name"] == "demo"
    assert out["stats"]["version"] == 1
    assert out["data"]["principles"][0]["id"] == "p1"
    assert out["preamble"].startswith("## Solution Constitution")
    assert out["errors"] == []
    assert wired.reloaded == 1


def test_get_rejects_non_object_params(wired):
    with pytest.raises(RpcError) as e:
        constitution.get("not a dict")
    assert e.value.code == -32602


def test_get_fails_when_unwired(monkeypatch):
    monkeypatch.setattr(constitution, "_ctx", None)
    with pytest.raises(RpcError) as e:
        constitution.get({})
    assert e.value.code == -32000


def test_update_saves_and_returns_new_stats(wired):
    new_data = {
        "meta": {"name": "demo", "version": 1, "last_updated": "", "updated_by": ""},
        "principles": [
            {"id": "p1", "text": "Test first", "weight": 0.9},
            {"id": "p2", "text": "Ship small", "weight": 0.6},
        ],
        "constraints": ["Never touch /prod/"],
    }
    out = constitution.update({"data": new_data, "changed_by": "alice"})
    assert out["version"] == 2
    assert out["stats"]["principle_count"] == 2
    assert wired.saved_with == ["alice"]


def test_update_defaults_changed_by_to_desktop(wired):
    new_data = wired.to_dict()
    constitution.update({"data": new_data})
    assert wired.saved_with == ["desktop"]


def test_update_rejects_validation_errors_and_reloads(wired):
    bad_data = {
        "meta": {"name": "demo", "version": 1, "last_updated": "", "updated_by": ""},
        "principles": [{"text": "missing id"}],
    }
    before = wired.reloaded
    with pytest.raises(RpcError) as e:
        constitution.update({"data": bad_data})
    assert e.value.code == -32602
    assert "missing 'id'" in e.value.message
    assert wired.saved_with == []  # never saved
    assert wired.reloaded == before + 1  # reloaded to drop the bad data


def test_update_rejects_non_dict_data(wired):
    with pytest.raises(RpcError) as e:
        constitution.update({"data": "not-a-dict"})
    assert e.value.code == -32602


def test_update_rejects_non_dict_params(wired):
    with pytest.raises(RpcError) as e:
        constitution.update("oops")
    assert e.value.code == -32602


def test_preamble_returns_current_text(wired):
    out = constitution.preamble({})
    assert "Solution Constitution" in out["preamble"]


def test_check_action_blocks_constraint_violation(wired):
    out = constitution.check_action({"action_description": "delete /prod/ data"})
    assert out["allowed"] is False
    assert "/prod/" in out["violations"][0]


def test_check_action_allows_safe_description(wired):
    out = constitution.check_action({"action_description": "read staging logs"})
    assert out["allowed"] is True
    assert out["violations"] == []


def test_check_action_rejects_empty_description(wired):
    with pytest.raises(RpcError) as e:
        constitution.check_action({"action_description": "  "})
    assert e.value.code == -32602


def test_real_constitution_roundtrip(tmp_path, monkeypatch):
    """Guard the real Constitution class contract end-to-end."""
    from src.core.constitution import Constitution

    sol = tmp_path / "demo"
    sol.mkdir()
    ctx = Constitution(solutions_dir=str(tmp_path), solution="demo")
    monkeypatch.setattr(constitution, "_ctx", ctx)

    # Empty at first.
    out = constitution.get({})
    assert out["stats"]["is_empty"] is True

    # Populate via update.
    new_data = {
        "meta": {"name": "demo", "version": 0, "last_updated": "", "updated_by": ""},
        "principles": [{"id": "p1", "text": "Be kind", "weight": 0.9}],
        "constraints": ["Never print('bad')"],
    }
    updated = constitution.update({"data": new_data, "changed_by": "tester"})
    assert updated["version"] == 1
    assert updated["stats"]["principle_count"] == 1

    # File now exists on disk.
    assert (sol / "constitution.yaml").is_file()

    # get() round-trips without errors.
    fresh = constitution.get({})
    assert fresh["stats"]["name"] == "demo"
    assert fresh["data"]["principles"][0]["id"] == "p1"
    assert fresh["errors"] == []
