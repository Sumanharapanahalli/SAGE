# Task 16: YAML config loader property tests

**Category:** testing  
**Score:** 10.0/10  
**Converged:** True  
**Iterations:** 1  
**Elapsed:** 575s  

---

## Task

Add property-based tests for src/core/project_loader.py using pytest + hypothesis. Test: (1) a valid project.yaml always loads without error; (2) a project.yaml missing any required field raises a clear error; (3) extra unknown fields are ignored. Define a hypothesis strategy that generates valid/invalid YAML dicts.

## Criteria

Hypothesis is used for at least 2 tests; valid YAML strategy is defined; invalid YAML strategy tests required fields; tests run with pytest and pass; no external deps beyond hypothesis.

## Proposal (submit to HITL approval gate)

# tests/test_project_loader_properties.py
"""Property-based tests for src/core/project_loader.py config validation.

Uses pytest + Hypothesis to assert three invariants over machine-generated
``project.yaml`` dictionaries:

  1. A *valid* project.yaml (always carries ``name``, correctly-typed fields)
     loads through ``ProjectConfig`` without error.
  2. A project.yaml that *omits the required* ``name`` field raises a clear
     ``ConfigValidationError`` that names both the offending field and file.
  3. *Extra unknown fields* are ignored — loading still succeeds and the
     unknown keys are passed through untouched.

Two layers are exercised: the full file-based load path (`ProjectConfig`,
which writes real YAML and parses it back) and the pure validator
(`_validate_config`), so a regression is caught regardless of where it lands.
"""
from __future__ import annotations

import string

import pytest
import yaml
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from src.core import project_loader as pl
from src.core.project_loader import (
    PROJECT_SCHEMA,
    ConfigValidationError,
    ProjectConfig,
    _validate_config,
)

# ---------------------------------------------------------------------------
# Hypothesis strategies — valid / invalid project.yaml dicts
# ---------------------------------------------------------------------------

# Fields PROJECT_SCHEMA knows about. The loader type-checks ONLY these; any
# other key is an "extra unknown field" the validator must silently ignore.
_REQUIRED = list(PROJECT_SCHEMA["required"])        # ["name"]
_KNOWN = set(PROJECT_SCHEMA["properties"])          # name + the optional fields

# YAML-safe scalars. Restricting the alphabet keeps safe_dump -> safe_load a
# faithful round-trip: PyYAML quotes numeric-/keyword-looking strings, so a
# str stays a str (no "1.5" silently parsing back as a float and tripping a
# spurious type error). It also dodges block-scalar / control-char edge cases
# that are irrelevant to what these tests assert.
_TEXT = st.text(alphabet=string.ascii_letters + string.digits + " _-.", max_size=40)
_NAME_TEXT = st.text(
    alphabet=string.ascii_letters + string.digits + "_-", min_size=1, max_size=30
)
_ARRAY = st.lists(_TEXT, max_size=4)
_OBJECT = st.dictionaries(_NAME_TEXT, _TEXT, max_size=4)

# Correctly-typed values for every NON-required known property.
_OPTIONAL_KNOWN = {
    "version":              _TEXT,
    "domain":               _TEXT,
    "description":          _TEXT,
    "active_modules":       _ARRAY,
    "compliance_standards": _ARRAY,
    "integrations":         _ARRAY,
    "ui_labels":            _OBJECT,
    "dashboard":            _OBJECT,
    "agent_budgets":        _OBJECT,
}

# Keys guaranteed never to collide with a known field (always "x_"-prefixed).
_EXTRA_KEY = st.text(
    alphabet=string.ascii_lowercase + string.digits + "_", min_size=1, max_size=12
).map(lambda s: "x_" + s)
_EXTRA_VALUE = st.one_of(_TEXT, _ARRAY, _OBJECT)


@st.composite
def _known_optional_subset(draw) -> dict:
    """A type-correct subset of the optional known fields (possibly empty)."""
    keys = draw(st.lists(st.sampled_from(sorted(_OPTIONAL_KNOWN)), unique=True))
    return {k: draw(_OPTIONAL_KNOWN[k]) for k in keys}


@st.composite
def _extras(draw, min_size: int = 0) -> dict:
    """A mapping of unknown ("x_"-prefixed) keys to arbitrary values."""
    return draw(
        st.dictionaries(_EXTRA_KEY, _EXTRA_VALUE, min_size=min_size, max_size=4)
    )


@st.composite
def valid_project_dicts(draw) -> dict:
    """A project.yaml dict that satisfies PROJECT_SCHEMA."""
    data = {"name": draw(_NAME_TEXT)}
    data.update(draw(_known_optional_subset()))
    data.update(draw(_extras()))
    return data


@st.composite
def valid_with_extra_fields(draw) -> dict:
    """A valid dict guaranteed to carry at least one unknown field."""
    data = {"name": draw(_NAME_TEXT)}
    data.update(draw(_known_optional_subset()))
    data.update(draw(_extras(min_size=1)))
    return data


@st.composite
def missing_name_dicts(draw) -> dict:
    """A NON-EMPTY project.yaml dict that omits the required ``name``.

    Non-emptiness is essential: ``_validate_config`` deliberately skips a falsy
    dict (an absent / blank / comment-only file), so an *empty* dict would NOT
    trip the requirement. We therefore always seed at least one other field.
    ``name`` is never added by these generators.
    """
    seed_key = draw(st.sampled_from(sorted(_OPTIONAL_KNOWN)))
    data = {seed_key: draw(_OPTIONAL_KNOWN[seed_key])}
    data.update(draw(_known_optional_subset()))
    data.update(draw(_extras()))
    data.pop("name", None)  # belt-and-braces; name is never introduced above
    return data


# ---------------------------------------------------------------------------
# Fixture — load a generated dict through the real ProjectConfig pipeline
# ---------------------------------------------------------------------------

@pytest.fixture
def load_project(tmp_path, monkeypatch):
    """Return ``load(data)`` that writes ``data`` as project.yaml and loads it.

    The loader is pointed at an isolated solutions dir and all SAGE_* env vars
    are cleared, so the test is hermetic. A ``ConfigValidationError`` raised
    during loading propagates to the caller.
    """
    for var in ("SAGE_PROJECT", "SAGE_DEFAULT_PROJECT", "SAGE_SOLUTIONS_DIR"):
        monkeypatch.delenv(var, raising=False)
    solutions_root = tmp_path / "solutions"
    monkeypatch.setattr(pl, "_SOLUTIONS_DIR", str(solutions_root))

    def _load(data: dict) -> ProjectConfig:
        sol = solutions_root / "probe"
        sol.mkdir(parents=True, exist_ok=True)
        (sol / "project.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
        return ProjectConfig(project_name="probe")

    return _load


# ---------------------------------------------------------------------------
# (1) A valid project.yaml always loads without error
# ---------------------------------------------------------------------------

@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
    max_examples=50,
)
@given(data=valid_project_dicts())
def test_valid_project_yaml_always_loads(load_project, data):
    cfg = load_project(data)  # must not raise
    assert cfg.project_name == "probe"
    assert cfg.get_project_setting("name") == data["name"]
    assert cfg.metadata["name"] == data["name"]


# ---------------------------------------------------------------------------
# (2) Missing a required field raises a clear error
# ---------------------------------------------------------------------------

@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
    max_examples=50,
)
@given(data=missing_name_dicts())
def test_missing_required_field_raises_clear_error(load_project, data):
    assert "name" not in data  # precondition the strategy guarantees

    with pytest.raises(ConfigValidationError) as excinfo:
        load_project(data)

    err = excinfo.value
    message = str(err)
    # "Clear" = the error pinpoints both the field and the file responsible.
    assert err.field_path == "name"
    assert "name" in message
    assert "required" in message.lower()
    assert err.source.endswith("project.yaml")


# ---------------------------------------------------------------------------
# (3) Extra unknown fields are ignored
# ---------------------------------------------------------------------------

@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
    max_examples=50,
)
@given(data=valid_with_extra_fields())
def test_extra_unknown_fields_are_ignored(load_project, data):
    extras = {k for k in data if k not in _KNOWN}
    assert extras  # the strategy guarantees at least one unknown field

    cfg = load_project(data)  # unknown fields must NOT cause a failure
    assert cfg.get_project_setting("name") == data["name"]

    # Ignored != dropped: unknown keys survive loading untouched.
    sentinel = object()
    for key in extras:
        assert cfg.get_project_setting(key, sentinel) is not sentinel


# ---------------------------------------------------------------------------
# Validation-layer properties (pure, no file IO) — same invariants, faster
# ---------------------------------------------------------------------------

@given(data=valid_project_dicts())
def test_validate_accepts_valid(data):
    assert _validate_config(data, PROJECT_SCHEMA, "project.yaml") is data


@given(data=missing_name_dicts())
def test_validate_rejects_missing_name(data):
    with pytest.raises(ConfigValidationError) as excinfo:
        _validate_config(data, PROJECT_SCHEMA, "project.yaml")
    assert excinfo.value.field_path == "name"


@given(name=_NAME_TEXT, extras=_extras(min_size=1))
def test_validate_ignores_unknown_fields(name, extras):
    data = {"name": name, **extras}
    assert _validate_config(data, PROJECT_SCHEMA, "project.yaml") is data


# ---------------------------------------------------------------------------
# Documented boundaries (concrete edge cases the strategies intentionally avoid)
# ---------------------------------------------------------------------------

def test_empty_dict_is_skipped_not_rejected():
    # An absent/blank/comment-only file parses to {} -> NO validation runs,
    # so the `name` requirement is deliberately not enforced.
    assert _validate_config({}, PROJECT_SCHEMA, "project.yaml") == {}


def test_present_but_empty_name_is_valid():
    # {"name": ""} is a non-empty dict whose name is a (empty) string: valid.
    assert _validate_config({"name": ""}, PROJECT_SCHEMA, "project.yaml") == {"name": ""}

---

## Iteration History

**Iter 1** — score 10.0 pass=True  
Feedback:   

