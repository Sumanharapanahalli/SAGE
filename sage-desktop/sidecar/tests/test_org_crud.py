"""Tests for org.* CRUD — knowledge channels, cross-team routes, parents.

The org handler previously supported only viewing the org state and editing
four identity fields; channels, routes and solution parents were read-only.
These add the write half, matching POST/DELETE /org/channels, /org/routes and
/org/solutions on the web API.

Channels live in org.yaml. Routes and parents live in each solution's OWN
project.yaml, so those handlers must resolve the solutions directory — which
is why `SAGE_SOLUTIONS_DIR` support lands here too: without it these would
write to `<sage_root>/solutions/<name>/project.yaml` for a solution mounted
somewhere else entirely, silently creating or missing files.
"""

from __future__ import annotations

import pytest
import yaml as _yaml

from handlers import org as org_handler
from rpc import RpcError

INVALID_PARAMS = -32602


@pytest.fixture
def sage_root(tmp_path, monkeypatch):
    """A SAGE root whose solutions dir holds one solution with a project.yaml."""
    root = tmp_path / "sage"
    solutions = root / "solutions"
    (solutions / "alpha").mkdir(parents=True)
    (solutions / "alpha" / "project.yaml").write_text(
        "name: alpha\ndescription: first\n", encoding="utf-8"
    )
    (solutions / "org.yaml").write_text(
        "org:\n  name: Acme\n  mission: Ship it\n", encoding="utf-8"
    )
    monkeypatch.setattr(org_handler, "_sage_root", root)
    monkeypatch.delenv("SAGE_SOLUTIONS_DIR", raising=False)
    return root


def _project(root, solution="alpha") -> dict:
    path = root / "solutions" / solution / "project.yaml"
    return _yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _org(root) -> dict:
    path = root / "solutions" / "org.yaml"
    return _yaml.safe_load(path.read_text(encoding="utf-8")) or {}


# ---------- knowledge channels ----------


def test_channel_create_writes_producers_and_consumers(sage_root):
    out = org_handler.channel_create(
        {"name": "alerts", "producers": ["alpha"], "consumers": ["beta"]}
    )
    channels = _org(sage_root)["org"]["knowledge_channels"]

    assert out["status"] == "created"
    assert channels["alerts"] == {"producers": ["alpha"], "consumers": ["beta"]}


def test_channel_create_preserves_existing_org_fields(sage_root):
    """A channel write must not clobber identity fields."""
    org_handler.channel_create({"name": "alerts"})
    assert _org(sage_root)["org"]["mission"] == "Ship it"


def test_channel_create_defaults_to_empty_lists(sage_root):
    org_handler.channel_create({"name": "alerts"})
    assert _org(sage_root)["org"]["knowledge_channels"]["alerts"] == {
        "producers": [],
        "consumers": [],
    }


def test_channel_delete_removes_it(sage_root):
    org_handler.channel_create({"name": "alerts"})
    out = org_handler.channel_delete({"name": "alerts"})

    assert out["status"] == "deleted"
    assert "alerts" not in _org(sage_root)["org"].get("knowledge_channels", {})


def test_channel_delete_rejects_an_unknown_channel(sage_root):
    with pytest.raises(RpcError) as e:
        org_handler.channel_delete({"name": "nope"})
    assert e.value.code == INVALID_PARAMS


@pytest.mark.parametrize("params", [{}, {"name": ""}, {"name": "   "}])
def test_channel_create_requires_a_name(sage_root, params):
    with pytest.raises(RpcError) as e:
        org_handler.channel_create(params)
    assert e.value.code == INVALID_PARAMS


def test_channel_create_rejects_non_list_members(sage_root):
    with pytest.raises(RpcError) as e:
        org_handler.channel_create({"name": "alerts", "producers": "alpha"})
    assert e.value.code == INVALID_PARAMS


# ---------- cross-team routes ----------


def test_route_add_appends_to_the_solutions_project_yaml(sage_root):
    out = org_handler.route_add({"solution": "alpha", "target": "beta"})

    assert out["status"] == "added"
    assert _project(sage_root)["cross_team_routes"] == [{"target": "beta"}]


def test_route_add_is_idempotent(sage_root):
    """Adding the same target twice must not duplicate it."""
    org_handler.route_add({"solution": "alpha", "target": "beta"})
    org_handler.route_add({"solution": "alpha", "target": "beta"})
    assert _project(sage_root)["cross_team_routes"] == [{"target": "beta"}]


def test_route_add_preserves_other_project_fields(sage_root):
    org_handler.route_add({"solution": "alpha", "target": "beta"})
    assert _project(sage_root)["name"] == "alpha"


def test_route_delete_removes_only_that_target(sage_root):
    org_handler.route_add({"solution": "alpha", "target": "beta"})
    org_handler.route_add({"solution": "alpha", "target": "gamma"})
    out = org_handler.route_delete({"solution": "alpha", "target": "beta"})

    assert out["status"] == "removed"
    assert _project(sage_root)["cross_team_routes"] == [{"target": "gamma"}]


def test_route_add_rejects_an_unknown_solution(sage_root):
    with pytest.raises(RpcError) as e:
        org_handler.route_add({"solution": "nope", "target": "beta"})
    assert e.value.code == INVALID_PARAMS


def test_route_add_rejects_a_path_traversing_solution_name(sage_root):
    """`solution` becomes a path segment — it must not escape the dir."""
    with pytest.raises(RpcError) as e:
        org_handler.route_add({"solution": "../../etc", "target": "beta"})
    assert e.value.code == INVALID_PARAMS


# ---------- solution parent ----------


def test_solution_set_parent_writes_parent(sage_root):
    out = org_handler.solution_set_parent({"solution": "alpha", "parent": "corp"})

    assert out["status"] == "added"
    assert _project(sage_root)["parent"] == "corp"


def test_solution_clear_parent_removes_it(sage_root):
    org_handler.solution_set_parent({"solution": "alpha", "parent": "corp"})
    out = org_handler.solution_clear_parent({"solution": "alpha"})

    assert out["status"] == "removed"
    assert "parent" not in _project(sage_root)


def test_solution_clear_parent_is_safe_when_absent(sage_root):
    """Clearing an already-parentless solution is a no-op, not an error."""
    out = org_handler.solution_clear_parent({"solution": "alpha"})
    assert out["status"] == "removed"


@pytest.mark.parametrize(
    "params", [{"solution": "alpha"}, {"parent": "corp"}, {"solution": "", "parent": "c"}]
)
def test_solution_set_parent_requires_both(sage_root, params):
    with pytest.raises(RpcError) as e:
        org_handler.solution_set_parent(params)
    assert e.value.code == INVALID_PARAMS


# ---------- SAGE_SOLUTIONS_DIR (item 6) ----------


def test_solutions_dir_honours_the_env_override(tmp_path, monkeypatch):
    """A solution mounted outside the framework checkout must be reachable.

    Without this the handler writes to `<sage_root>/solutions/<name>/`, which
    for an externally-mounted solution is either missing or — worse — a
    different file than the one the rest of the app reads.
    """
    external = tmp_path / "external"
    (external / "alpha").mkdir(parents=True)
    (external / "alpha" / "project.yaml").write_text("name: alpha\n", encoding="utf-8")
    monkeypatch.setattr(org_handler, "_sage_root", tmp_path / "sage")
    monkeypatch.setenv("SAGE_SOLUTIONS_DIR", str(external))

    org_handler.route_add({"solution": "alpha", "target": "beta"})

    written = _yaml.safe_load(
        (external / "alpha" / "project.yaml").read_text(encoding="utf-8")
    )
    assert written["cross_team_routes"] == [{"target": "beta"}]


def test_org_yaml_also_honours_the_env_override(tmp_path, monkeypatch):
    external = tmp_path / "external"
    external.mkdir()
    (external / "org.yaml").write_text("org:\n  name: External Co\n", encoding="utf-8")
    monkeypatch.setattr(org_handler, "_sage_root", tmp_path / "sage")
    monkeypatch.setenv("SAGE_SOLUTIONS_DIR", str(external))

    assert org_handler.get({})["org"]["name"] == "External Co"
