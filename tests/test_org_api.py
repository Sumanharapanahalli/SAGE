from fastapi.testclient import TestClient
from src.interface.api import app

client = TestClient(app)


def test_get_org_returns_200():
    resp = client.get("/org")
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)


def test_get_org_includes_routes_key():
    resp = client.get("/org")
    assert resp.status_code == 200
    assert "routes" in resp.json()


def test_org_reload_returns_reloaded():
    resp = client.post("/org/reload")
    assert resp.status_code == 200
    assert resp.json().get("status") == "reloaded"


def test_org_routes_post_requires_solution_and_target():
    resp = client.post("/org/routes", json={})
    assert resp.status_code == 400


def test_org_routes_delete_requires_solution_and_target():
    resp = client.request("DELETE", "/org/routes", json={})
    assert resp.status_code == 400


def test_org_channels_post_requires_name():
    resp = client.post("/org/channels", json={})
    assert resp.status_code == 400


def test_org_solutions_post_requires_both_fields():
    resp = client.post("/org/solutions", json={"solution": "foo"})
    assert resp.status_code == 400
