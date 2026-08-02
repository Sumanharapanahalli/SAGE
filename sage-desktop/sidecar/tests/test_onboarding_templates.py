"""Tests for onboarding.org_templates and the org_context passthrough.

Pre-built team structures the wizard can start from. The templates are DATA in
config/org_templates.yaml, deliberately outside src/ so the framework stays
domain-blind (SOUL.md) — adding one is a YAML edit, not a code change.

Note what this ports: web has both the `/onboarding/org-templates` endpoint and
a 263-line `OrgStructureChooser.tsx`, but **nothing imports that component** —
the chooser was never wired into the web wizard, so there is no reference for
how a chosen template should reach generation. Desktop routes it through
`generate_solution(org_context=...)`, which the framework already documents as
"prepended to description before LLM generation". No framework change needed.
"""

from __future__ import annotations

import pytest

from handlers import onboarding as onb
from rpc import RpcError

INVALID_PARAMS = -32602


@pytest.fixture(autouse=True)
def clear_cache():
    onb._org_templates_cache = None
    yield
    onb._org_templates_cache = None


# ---------- org_templates ----------


def test_org_templates_loads_the_bundled_yaml():
    out = onb.org_templates({})
    templates = out["templates"]

    assert templates, "config/org_templates.yaml should ship templates"
    ids = {t["id"] for t in templates}
    assert "starter" in ids


def test_org_templates_entries_carry_roles_and_compliance():
    starter = next(
        t for t in onb.org_templates({})["templates"] if t["id"] == "starter"
    )
    assert starter["name"]
    assert isinstance(starter["compliance_standards"], list)
    role_keys = {r["key"] for r in starter["roles"]}
    assert "analyst" in role_keys


def test_org_templates_is_cached(monkeypatch):
    first = onb.org_templates({})["templates"]
    # Point the loader at a path that does not exist; a cached result must
    # still come back rather than re-reading and returning [].
    monkeypatch.setattr(onb, "_org_templates_path", lambda: "/nonexistent.yaml")
    second = onb.org_templates({})["templates"]
    assert second == first


def test_org_templates_degrades_to_empty_when_the_file_is_missing(monkeypatch):
    """A missing templates file must not break onboarding — the wizard still
    works without a template, so return [] rather than raising."""
    monkeypatch.setattr(onb, "_org_templates_path", lambda: "/nonexistent.yaml")
    assert onb.org_templates({})["templates"] == []


def test_org_templates_accepts_no_params():
    assert "templates" in onb.org_templates(None)


# ---------- generate passes org_context through ----------


def test_generate_forwards_org_context(monkeypatch):
    """The chosen template's role brief reaches the LLM via org_context, which
    generate_solution prepends to the description."""
    seen = {}

    def fake_generate(**kw):
        seen.update(kw)
        return {"solution_name": kw["solution_name"], "status": "created"}

    monkeypatch.setattr(onb, "_generate_fn", fake_generate)
    onb.generate(
        {
            "description": "drone inspection",
            "solution_name": "drones",
            "org_context": "Team roles:\n- analyst: Signal Analyst",
        }
    )
    assert seen["org_context"] == "Team roles:\n- analyst: Signal Analyst"


def test_generate_defaults_org_context_to_empty(monkeypatch):
    seen = {}

    def fake_generate(**kw):
        seen.update(kw)
        return {"solution_name": kw["solution_name"], "status": "created"}

    monkeypatch.setattr(onb, "_generate_fn", fake_generate)
    onb.generate({"description": "d", "solution_name": "s"})
    assert seen["org_context"] == ""


def test_generate_rejects_a_non_string_org_context(monkeypatch):
    monkeypatch.setattr(onb, "_generate_fn", lambda **kw: {})
    with pytest.raises(RpcError) as e:
        onb.generate(
            {"description": "d", "solution_name": "s", "org_context": ["nope"]}
        )
    assert e.value.code == INVALID_PARAMS
