"""
Tests for the SAGE Constitution System
=======================================
Per-solution "blue book" — immutable principles, constraints, voice, and
decision rules that agents must follow.

TDD: tests written first, implementation follows.
"""

import os
import json
import copy
import tempfile
import threading
import pytest
import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_constitution(tmp, solution="test_sol", content=None):
    """Write a constitution.yaml into a temp solutions dir and return its path."""
    sol_dir = os.path.join(tmp, solution)
    os.makedirs(sol_dir, exist_ok=True)
    path = os.path.join(sol_dir, "constitution.yaml")
    if content is None:
        content = _SAMPLE_CONSTITUTION
    with open(path, "w") as fh:
        yaml.dump(content, fh, default_flow_style=False)
    return path


_SAMPLE_CONSTITUTION = {
    "meta": {
        "name": "Test Constitution",
        "version": 1,
        "last_updated": "2026-04-05",
        "updated_by": "founder",
    },
    "principles": [
        {
            "id": "safety-first",
            "text": "Patient safety overrides all other priorities.",
            "weight": 1.0,
        },
        {
            "id": "lean-iteration",
            "text": "Prefer smallest working increment.",
            "weight": 0.8,
        },
    ],
    "constraints": [
        "Never modify files in /critical/ without approval",
        "All API changes must be backward compatible",
    ],
    "voice": {
        "tone": "precise, clinical",
        "avoid": ["marketing speak", "vague estimates"],
    },
    "decisions": {
        "default_approval_tier": "human",
        "auto_approve_categories": ["docs", "tests"],
        "escalation_keywords": ["safety", "regulatory"],
    },
    "knowledge": {
        "primary_sources": ["IEC 62304"],
        "trusted_repos": [],
    },
}


# ===========================================================================
# Test: Constitution Loader
# ===========================================================================

class TestConstitutionLoader:
    """Tests for loading and parsing constitution.yaml files."""

    def test_load_valid_constitution(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "mysol")
        c = Constitution(solutions_dir=str(tmp_path), solution="mysol")
        assert c.name == "Test Constitution"
        assert c.version == 1
        assert len(c.principles) == 2
        assert len(c.constraints) == 2

    def test_load_missing_file_returns_empty(self, tmp_path):
        from src.core.constitution import Constitution
        os.makedirs(os.path.join(str(tmp_path), "empty_sol"))
        c = Constitution(solutions_dir=str(tmp_path), solution="empty_sol")
        assert c.name == ""
        assert c.principles == []
        assert c.constraints == []
        assert c.is_empty

    def test_load_malformed_yaml_returns_empty(self, tmp_path):
        from src.core.constitution import Constitution
        sol_dir = os.path.join(str(tmp_path), "bad")
        os.makedirs(sol_dir)
        with open(os.path.join(sol_dir, "constitution.yaml"), "w") as fh:
            fh.write("{{not valid yaml:::}")
        c = Constitution(solutions_dir=str(tmp_path), solution="bad")
        assert c.is_empty

    def test_load_partial_constitution(self, tmp_path):
        """Constitution with only principles — other sections default."""
        from src.core.constitution import Constitution
        partial = {
            "meta": {"name": "Partial"},
            "principles": [{"id": "p1", "text": "Do good", "weight": 1.0}],
        }
        _make_constitution(str(tmp_path), "partial", partial)
        c = Constitution(solutions_dir=str(tmp_path), solution="partial")
        assert c.name == "Partial"
        assert len(c.principles) == 1
        assert c.constraints == []
        assert c.voice == {}
        assert c.decisions == {}

    def test_reload_picks_up_changes(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "reloadsol")
        c = Constitution(solutions_dir=str(tmp_path), solution="reloadsol")
        assert c.name == "Test Constitution"

        # Write updated version
        updated = copy.deepcopy(_SAMPLE_CONSTITUTION)
        updated["meta"]["name"] = "Updated Constitution"
        updated["meta"]["version"] = 2
        _make_constitution(str(tmp_path), "reloadsol", updated)
        c.reload()
        assert c.name == "Updated Constitution"
        assert c.version == 2


# ===========================================================================
# Test: Principle Accessors
# ===========================================================================

class TestPrinciples:

    def test_get_all_principles(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        assert len(c.principles) == 2
        assert c.principles[0]["id"] == "safety-first"

    def test_get_principle_by_id(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        p = c.get_principle("safety-first")
        assert p is not None
        assert p["weight"] == 1.0

    def test_get_principle_not_found(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        assert c.get_principle("nonexistent") is None

    def test_non_negotiable_principles(self, tmp_path):
        """Principles with weight 1.0 are non-negotiable."""
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        nn = c.get_non_negotiable_principles()
        assert len(nn) == 1
        assert nn[0]["id"] == "safety-first"

    def test_principles_sorted_by_weight(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        sorted_p = c.get_principles_by_priority()
        assert sorted_p[0]["weight"] >= sorted_p[1]["weight"]


# ===========================================================================
# Test: Prompt Injection
# ===========================================================================

class TestPromptInjection:
    """Constitution principles and constraints injected into agent prompts."""

    def test_build_preamble(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        preamble = c.build_prompt_preamble()
        assert "Patient safety" in preamble
        assert "Never modify files" in preamble
        assert "CONSTITUTION" in preamble or "Constitution" in preamble

    def test_preamble_empty_constitution(self, tmp_path):
        from src.core.constitution import Constitution
        os.makedirs(os.path.join(str(tmp_path), "empty"))
        c = Constitution(solutions_dir=str(tmp_path), solution="empty")
        assert c.build_prompt_preamble() == ""

    def test_preamble_includes_voice(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        preamble = c.build_prompt_preamble()
        assert "precise" in preamble or "clinical" in preamble

    def test_preamble_includes_constraints(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        preamble = c.build_prompt_preamble()
        assert "backward compatible" in preamble

    def test_inject_into_system_prompt(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        original = "You are a helpful analyst."
        injected = c.inject_into_prompt(original)
        assert injected.startswith(c.build_prompt_preamble())
        assert "You are a helpful analyst." in injected


# ===========================================================================
# Test: Constraint Checking
# ===========================================================================

class TestConstraintChecking:

    def test_check_action_no_violations(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        result = c.check_action("Update the README with new docs")
        assert result["allowed"] is True
        assert result["violations"] == []

    def test_check_action_detects_constraint_violation(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        result = c.check_action("Modify files in /critical/ to fix a bug")
        assert result["allowed"] is False
        assert len(result["violations"]) > 0

    def test_check_action_empty_constitution_allows_all(self, tmp_path):
        from src.core.constitution import Constitution
        os.makedirs(os.path.join(str(tmp_path), "empty"))
        c = Constitution(solutions_dir=str(tmp_path), solution="empty")
        result = c.check_action("Do anything")
        assert result["allowed"] is True

    def test_escalation_keywords_detected(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        result = c.check_escalation("This involves patient safety concerns")
        assert result["should_escalate"] is True
        assert "safety" in result["matched_keywords"]

    def test_no_escalation_for_normal_text(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        result = c.check_escalation("Update the color of the button")
        assert result["should_escalate"] is False

    def test_auto_approve_category(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        assert c.can_auto_approve("docs") is True
        assert c.can_auto_approve("tests") is True
        assert c.can_auto_approve("code") is False


# ===========================================================================
# Test: CRUD Operations
# ===========================================================================

class TestConstitutionCRUD:

    def test_update_principle(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        c.update_principle("safety-first", text="Updated safety text", weight=0.95)
        p = c.get_principle("safety-first")
        assert p["text"] == "Updated safety text"
        assert p["weight"] == 0.95

    def test_add_principle(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        c.add_principle(id="new-rule", text="Always write tests", weight=0.9)
        assert len(c.principles) == 3
        assert c.get_principle("new-rule") is not None

    def test_add_duplicate_principle_raises(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        with pytest.raises(ValueError, match="already exists"):
            c.add_principle(id="safety-first", text="Duplicate", weight=1.0)

    def test_remove_principle(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        c.remove_principle("lean-iteration")
        assert len(c.principles) == 1
        assert c.get_principle("lean-iteration") is None

    def test_remove_nonexistent_principle_raises(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        with pytest.raises(ValueError, match="not found"):
            c.remove_principle("nonexistent")

    def test_add_constraint(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        c.add_constraint("No deployments on Friday")
        assert "No deployments on Friday" in c.constraints

    def test_remove_constraint(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        c.remove_constraint("All API changes must be backward compatible")
        assert len(c.constraints) == 1

    def test_update_voice(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        c.update_voice(tone="friendly, casual", avoid=["jargon"])
        assert c.voice["tone"] == "friendly, casual"
        assert c.voice["avoid"] == ["jargon"]

    def test_update_decisions(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        c.update_decisions(default_approval_tier="auto", auto_approve_categories=["docs", "tests", "formatting"])
        assert c.decisions["default_approval_tier"] == "auto"
        assert "formatting" in c.decisions["auto_approve_categories"]


# ===========================================================================
# Test: Save / Persist
# ===========================================================================

class TestConstitutionPersistence:

    def test_save_writes_yaml(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        c.add_principle(id="new-one", text="Be kind", weight=0.5)
        c.save()

        # Reload from disk
        c2 = Constitution(solutions_dir=str(tmp_path), solution="sol")
        assert c2.get_principle("new-one") is not None
        assert c2.version == 2  # auto-increments on save

    def test_save_updates_timestamp(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        old_date = c._data["meta"]["last_updated"]
        c.add_principle(id="x", text="x", weight=0.1)
        c.save()
        assert c._data["meta"]["last_updated"] != old_date

    def test_save_empty_constitution_creates_file(self, tmp_path):
        from src.core.constitution import Constitution
        sol_dir = os.path.join(str(tmp_path), "newsol")
        os.makedirs(sol_dir)
        c = Constitution(solutions_dir=str(tmp_path), solution="newsol")
        assert c.is_empty
        c.add_principle(id="first", text="First principle", weight=1.0)
        c.save()
        assert os.path.exists(os.path.join(sol_dir, "constitution.yaml"))

    def test_version_history_tracked(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        c.add_principle(id="v2", text="v2 rule", weight=0.5)
        c.save(changed_by="alice")
        c.add_constraint("New constraint")
        c.save(changed_by="bob")
        history = c.get_version_history()
        assert len(history) >= 2
        assert history[-1]["changed_by"] == "bob"

    def test_to_dict_roundtrip(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        d = c.to_dict()
        assert d["meta"]["name"] == "Test Constitution"
        assert len(d["principles"]) == 2
        assert len(d["constraints"]) == 2


# ===========================================================================
# Test: Validation
# ===========================================================================

class TestConstitutionValidation:

    def test_validate_valid_constitution(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        errors = c.validate()
        assert errors == []

    def test_validate_principle_missing_id(self, tmp_path):
        from src.core.constitution import Constitution
        bad = copy.deepcopy(_SAMPLE_CONSTITUTION)
        bad["principles"][0].pop("id")
        _make_constitution(str(tmp_path), "sol", bad)
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        errors = c.validate()
        assert any("id" in e.lower() for e in errors)

    def test_validate_principle_missing_text(self, tmp_path):
        from src.core.constitution import Constitution
        bad = copy.deepcopy(_SAMPLE_CONSTITUTION)
        bad["principles"][0].pop("text")
        _make_constitution(str(tmp_path), "sol", bad)
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        errors = c.validate()
        assert any("text" in e.lower() for e in errors)

    def test_validate_weight_out_of_range(self, tmp_path):
        from src.core.constitution import Constitution
        bad = copy.deepcopy(_SAMPLE_CONSTITUTION)
        bad["principles"][0]["weight"] = 1.5
        _make_constitution(str(tmp_path), "sol", bad)
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        errors = c.validate()
        assert any("weight" in e.lower() for e in errors)

    def test_validate_duplicate_principle_ids(self, tmp_path):
        from src.core.constitution import Constitution
        bad = copy.deepcopy(_SAMPLE_CONSTITUTION)
        bad["principles"].append({"id": "safety-first", "text": "Dupe", "weight": 0.5})
        _make_constitution(str(tmp_path), "sol", bad)
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        errors = c.validate()
        assert any("duplicate" in e.lower() for e in errors)

    def test_validate_empty_is_valid(self, tmp_path):
        from src.core.constitution import Constitution
        os.makedirs(os.path.join(str(tmp_path), "empty"))
        c = Constitution(solutions_dir=str(tmp_path), solution="empty")
        errors = c.validate()
        assert errors == []


# ===========================================================================
# Test: Thread Safety
# ===========================================================================

class TestThreadSafety:

    def test_concurrent_reads(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        results = []

        def read_principles():
            for _ in range(50):
                results.append(len(c.principles))

        threads = [threading.Thread(target=read_principles) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert all(r == 2 for r in results)

    def test_concurrent_writes(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        errors = []

        def add_principle(i):
            try:
                c.add_principle(id=f"rule-{i}", text=f"Rule {i}", weight=0.5)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=add_principle, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert len(c.principles) == 12  # 2 original + 10 added


# ===========================================================================
# Test: Singleton / get_constitution
# ===========================================================================

class TestSingleton:

    def test_get_constitution_returns_instance(self):
        from src.core.constitution import get_constitution
        c = get_constitution()
        assert c is not None

    def test_get_constitution_same_instance(self):
        from src.core.constitution import get_constitution
        c1 = get_constitution()
        c2 = get_constitution()
        assert c1 is c2


# ===========================================================================
# Test: Stats
# ===========================================================================

class TestStats:

    def test_get_stats(self, tmp_path):
        from src.core.constitution import Constitution
        _make_constitution(str(tmp_path), "sol")
        c = Constitution(solutions_dir=str(tmp_path), solution="sol")
        stats = c.get_stats()
        assert stats["principle_count"] == 2
        assert stats["constraint_count"] == 2
        assert stats["non_negotiable_count"] == 1
        assert stats["has_voice"] is True
        assert stats["has_decisions"] is True
        assert stats["version"] == 1

    def test_stats_empty(self, tmp_path):
        from src.core.constitution import Constitution
        os.makedirs(os.path.join(str(tmp_path), "empty"))
        c = Constitution(solutions_dir=str(tmp_path), solution="empty")
        stats = c.get_stats()
        assert stats["principle_count"] == 0
        assert stats["is_empty"] is True
