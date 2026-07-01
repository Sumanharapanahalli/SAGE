"""Property-based tests for src.core.project_loader config validation."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import mock

import pytest
import yaml
from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

from src.core import project_loader
from src.core.project_loader import (
    ConfigValidationError,
    PROJECT_SCHEMA,
    ProjectConfig,
)

_safe_text = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126), max_size=20
)
_key_text = st.text(
    alphabet=st.characters(min_codepoint=97, max_codepoint=122),
    min_size=1,
    max_size=12,
)

_VALUE_STRATEGIES = {
    "string": _safe_text,
    "array": st.lists(_safe_text, max_size=4),
    "object": st.dictionaries(_key_text, _safe_text, max_size=4),
}

REQUIRED_FIELDS = list(PROJECT_SCHEMA["required"])

_OPTIONAL_PROPS = {
    key: spec["type"]
    for key, spec in PROJECT_SCHEMA["properties"].items()
    if key not in REQUIRED_FIELDS
}


@st.composite
def valid_project_dicts(draw):
    data = {"name": draw(_safe_text)}
    for key in draw(st.lists(st.sampled_from(sorted(_OPTIONAL_PROPS)), unique=True)):
        data[key] = draw(_VALUE_STRATEGIES[_OPTIONAL_PROPS[key]])
    return data


_unknown_keys = _key_text.filter(lambda k: k not in PROJECT_SCHEMA["properties"])


@st.composite
def project_dicts_with_extras(draw):
    data = draw(valid_project_dicts())
    extras = draw(
        st.dictionaries(
            _unknown_keys,
            st.one_of(_safe_text, st.integers(), st.booleans()),
            min_size=1,
            max_size=4,
        )
    )
    data.update(extras)
    return data, extras


@st.composite
def missing_required_project_dicts(draw):
    data = draw(valid_project_dicts())
    data.pop("name", None)
    if not data:
        data["version"] = draw(_safe_text)
    return data


def _load_via_disk(data: dict) -> ProjectConfig:
    with tempfile.TemporaryDirectory() as td:
        sol_dir = Path(td) / "probe"
        sol_dir.mkdir()
        (sol_dir / "project.yaml").write_text(
            yaml.safe_dump(data, allow_unicode=True), encoding="utf-8"
        )
        with mock.patch.object(project_loader, "_SOLUTIONS_DIR", td):
            return ProjectConfig(project_name="probe")


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@example({"name": ""})
@example({"name": "demo"})
@given(valid_project_dicts())
def test_valid_project_yaml_always_loads(data):
    pc = _load_via_disk(data)
    assert pc.get_project_setting("name") == data["name"]
    assert pc.metadata["name"] == (data["name"] or "probe")


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@example({"version": "1.0.0"})
@given(missing_required_project_dicts())
def test_missing_required_field_raises_clear_error(data):
    assert "name" not in data
    with pytest.raises(ConfigValidationError) as excinfo:
        _load_via_disk(data)

    err = excinfo.value
    assert isinstance(err, ValueError)
    assert err.field_path == "name"
    assert "name" in str(err)
    assert "required" in str(err).lower()
    assert err.source.endswith("project.yaml")


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(project_dicts_with_extras())
def test_extra_unknown_fields_are_ignored(payload):
    data, extras = payload
    pc = _load_via_disk(data)
    assert pc.get_project_setting("name") == data["name"]
    for key, value in extras.items():
        assert key not in PROJECT_SCHEMA["properties"]
        assert pc.get_project_setting(key) == value
