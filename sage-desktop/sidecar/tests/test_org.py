"""Tests for the Organization (org.yaml) handler.

org.yaml is a SAGE_ROOT-level file (``<sage_root>/solutions/org.yaml``) —
unlike per-solution YAMLs (constitution.yaml, project.yaml/...), it lives
above any single solution. Tests monkeypatch ``handlers.org._sage_root`` to
an isolated ``tmp_path`` so they never touch the real repo's
``solutions/org.yaml``.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import handlers.org as org  # noqa: E402
from rpc import RpcError  # noqa: E402


@pytest.fixture
def wired_root(tmp_path, monkeypatch) -> Path:
    (tmp_path / "solutions").mkdir()
    monkeypatch.setattr(org, "_sage_root", tmp_path)
    return tmp_path


def _write_org_yaml(root: Path, data: dict) -> None:
    path = root / "solutions" / "org.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f)


# ── get ──────────────────────────────────────────────────────────────────


def test_get_returns_empty_shape_when_file_missing(wired_root):
    out = org.get({})
    assert out == {"org": {}, "routes": []}


def test_get_fails_when_unwired(monkeypatch):
    monkeypatch.setattr(org, "_sage_root", None)
    with pytest.raises(RpcError) as e:
        org.get({})
    assert e.value.code == -32000


def test_get_rejects_non_object_params(wired_root):
    with pytest.raises(RpcError) as e:
        org.get("nope")
    assert e.value.code == -32602


def test_get_reads_existing_org_yaml(wired_root):
    _write_org_yaml(
        wired_root,
        {"org": {"name": "Acme", "mission": "Ship things", "core_values": ["Speed"]}},
    )
    out = org.get({})
    assert out["org"]["name"] == "Acme"
    assert out["org"]["mission"] == "Ship things"
    assert out["org"]["core_values"] == ["Speed"]
    assert out["routes"] == []


def test_get_includes_cross_team_routes(wired_root):
    sol_a = wired_root / "solutions" / "a"
    sol_a.mkdir()
    (sol_a / "project.yaml").write_text(
        "name: a\ncross_team_routes:\n  - target: b\n", encoding="utf-8"
    )
    out = org.get({})
    assert {"source": "a", "target": "b"} in out["routes"]


def test_get_after_prior_write_round_trips_through_handler(wired_root):
    """get() reflects a change made via update() — not just direct disk writes."""
    org.update({"name": "Acme", "mission": "Ship things"})
    out = org.get({})
    assert out["org"]["name"] == "Acme"
    assert out["org"]["mission"] == "Ship things"


# ── update ───────────────────────────────────────────────────────────────


def test_update_rejects_non_dict_params(wired_root):
    with pytest.raises(RpcError) as e:
        org.update("oops")
    assert e.value.code == -32602


def test_update_rejects_non_string_name(wired_root):
    with pytest.raises(RpcError) as e:
        org.update({"name": 5})
    assert e.value.code == -32602


def test_update_rejects_non_list_core_values(wired_root):
    with pytest.raises(RpcError) as e:
        org.update({"core_values": "not-a-list"})
    assert e.value.code == -32602


def test_update_rejects_non_string_core_value_entries(wired_root):
    with pytest.raises(RpcError) as e:
        org.update({"core_values": ["ok", 5]})
    assert e.value.code == -32602


def test_update_fails_when_unwired(monkeypatch):
    monkeypatch.setattr(org, "_sage_root", None)
    with pytest.raises(RpcError) as e:
        org.update({"name": "Acme"})
    assert e.value.code == -32000


def test_update_creates_file_when_missing(wired_root):
    out = org.update({"name": "Acme", "mission": "Ship things"})
    assert out["status"] == "saved"
    assert out["org"]["name"] == "Acme"
    assert out["org"]["mission"] == "Ship things"
    path = wired_root / "solutions" / "org.yaml"
    assert path.is_file()
    on_disk = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert on_disk["org"]["name"] == "Acme"


def test_update_merges_only_supplied_fields(wired_root):
    org.update({"name": "Acme", "mission": "Ship things", "core_values": ["Speed"]})
    out = org.update({"vision": "A better world"})
    assert out["org"]["name"] == "Acme"  # preserved
    assert out["org"]["mission"] == "Ship things"  # preserved
    assert out["org"]["core_values"] == ["Speed"]  # preserved
    assert out["org"]["vision"] == "A better world"  # newly set


def test_update_overwrites_supplied_field(wired_root):
    org.update({"name": "Acme"})
    out = org.update({"name": "New Name"})
    assert out["org"]["name"] == "New Name"


def test_update_clears_core_values_with_empty_list(wired_root):
    org.update({"core_values": ["Speed"]})
    out = org.update({"core_values": []})
    assert out["org"]["core_values"] == []


def test_update_preserves_unmanaged_org_fields(wired_root):
    """Fields this pass doesn't edit (root_solution, knowledge_channels —
    channel/route CRUD is out of scope) must survive an identity-field
    update untouched."""
    _write_org_yaml(
        wired_root,
        {
            "org": {
                "name": "Acme",
                "root_solution": "core",
                "knowledge_channels": {"x": {"producers": ["a"]}},
            }
        },
    )
    out = org.update({"mission": "Ship things"})
    assert out["org"]["name"] == "Acme"
    assert out["org"]["root_solution"] == "core"
    assert out["org"]["knowledge_channels"] == {"x": {"producers": ["a"]}}
    assert out["org"]["mission"] == "Ship things"


# ── reload ───────────────────────────────────────────────────────────────


def test_reload_returns_status(wired_root):
    out = org.reload({})
    assert out == {"status": "reloaded"}


def test_reload_rejects_non_object_params(wired_root):
    with pytest.raises(RpcError) as e:
        org.reload("nope")
    assert e.value.code == -32602
