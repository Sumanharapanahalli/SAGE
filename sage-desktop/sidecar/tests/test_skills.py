"""Tests for the skills handler.

Like compliance.py, skill_registry and mcp_registry are module-level
singletons with no store to wire at startup — these handlers import them
directly at call time. skill_registry auto-loads the framework's
skills/public/*.yaml on import, so these tests exercise the real registry
rather than a mock. Tests that mutate visibility restore state via
reload() so ordering never matters.
"""

from __future__ import annotations

import pytest

from handlers import skills
from rpc import RpcError


@pytest.fixture(autouse=True)
def _reset_registry():
    """Reload skills from disk before and after each test so visibility
    mutations in one test never leak into another."""
    from src.core.skill_loader import skill_registry

    skill_registry.reload()
    yield
    skill_registry.reload()


def _any_known_skill_name() -> str:
    from src.core.skill_loader import skill_registry

    all_skills = skill_registry.list_all(include_disabled=True)
    assert all_skills, "expected at least one skill to be loaded from skills/public/"
    return all_skills[0].name


def test_list_returns_active_skills_and_stats():
    out = skills.list({})
    assert "skills" in out and "stats" in out
    assert isinstance(out["skills"], list)
    for s in out["skills"]:
        assert s.get("visibility") != "disabled"
    assert out["stats"]["total"] >= len(out["skills"])


def test_list_defaults_include_disabled_to_false():
    out_default = skills.list({})
    out_explicit = skills.list({"include_disabled": False})
    assert len(out_default["skills"]) == len(out_explicit["skills"])


def test_list_with_include_disabled_true_returns_more_or_equal_skills():
    name = _any_known_skill_name()
    from src.core.skill_loader import skill_registry

    skill_registry.set_visibility(name, "disabled")

    without_disabled = skills.list({"include_disabled": False})
    with_disabled = skills.list({"include_disabled": True})

    assert len(with_disabled["skills"]) >= len(without_disabled["skills"])
    names_with = {s["name"] for s in with_disabled["skills"]}
    assert name in names_with


def test_set_visibility_happy_path_updates_the_skill():
    name = _any_known_skill_name()
    out = skills.set_visibility({"name": name, "visibility": "private"})
    assert out == {"status": "updated", "name": name, "visibility": "private"}

    from src.core.skill_loader import skill_registry

    updated = skill_registry.get_including_disabled(name)
    assert updated.visibility == "private"


def test_set_visibility_rejects_invalid_visibility_value():
    name = _any_known_skill_name()
    with pytest.raises(RpcError) as exc_info:
        skills.set_visibility({"name": name, "visibility": "bogus"})
    assert exc_info.value.code == -32602  # RPC_INVALID_PARAMS


def test_set_visibility_rejects_unknown_skill_name():
    with pytest.raises(RpcError) as exc_info:
        skills.set_visibility({"name": "not-a-real-skill", "visibility": "public"})
    assert exc_info.value.code == -32602  # RPC_INVALID_PARAMS
    assert "not found" in str(exc_info.value)


def test_set_visibility_requires_name_param():
    with pytest.raises(RpcError):
        skills.set_visibility({"visibility": "public"})


def test_reload_reloads_skills_from_disk_and_returns_stats():
    out = skills.reload({})
    assert out["status"] == "reloaded"
    assert isinstance(out["skills_loaded"], int)
    assert out["skills_loaded"] > 0
    assert "stats" in out
    assert out["stats"]["total"] == out["skills_loaded"]


def test_reload_resets_a_visibility_change_made_in_memory():
    name = _any_known_skill_name()
    from src.core.skill_loader import skill_registry

    original_visibility = skill_registry.get_including_disabled(name).visibility
    skill_registry.set_visibility(name, "disabled")

    skills.reload({})

    restored = skill_registry.get_including_disabled(name)
    assert restored.visibility == original_visibility


def test_mcp_tools_returns_tools_and_count():
    out = skills.mcp_tools({})
    assert "tools" in out and "count" in out
    assert out["count"] == len(out["tools"])
    for tool in out["tools"]:
        assert "name" in tool
        assert "description" in tool
