"""Onboarding org templates are loaded from config/org_templates.yaml (data),
not hardcoded in src/ — keeps the framework domain-blind (SOUL.md). See #35."""

import yaml


def test_org_templates_yaml_exists_and_parses():
    import src.interface.api as api

    path = api.os.path.join(
        api.os.path.dirname(
            api.os.path.dirname(api.os.path.dirname(api.os.path.abspath(api.__file__)))
        ),
        "config",
        "org_templates.yaml",
    )
    data = yaml.safe_load(open(path))
    assert "templates" in data
    assert isinstance(data["templates"], list) and data["templates"]


def test_loader_returns_templates_with_expected_shape():
    from src.interface.api import _get_org_templates

    templates = _get_org_templates()
    assert len(templates) >= 1
    for t in templates:
        assert "id" in t and "name" in t and "roles" in t
    # 'starter' is the domain-neutral baseline template and must always ship.
    assert any(t["id"] == "starter" for t in templates)


def test_endpoint_serves_the_loaded_templates(api_client):
    resp = api_client.get("/onboarding/org-templates")
    assert resp.status_code == 200
    body = resp.json()
    assert "templates" in body
    ids = {t["id"] for t in body["templates"]}
    assert "starter" in ids
