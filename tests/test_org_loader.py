import os
import pytest
import yaml

from src.core.org_loader import OrgLoader, OrgLoaderError


@pytest.fixture
def solutions_dir(tmp_path):
    (tmp_path / "company_base").mkdir()
    (tmp_path / "company_base" / "project.yaml").write_text("name: company_base\n")
    (tmp_path / "company_base" / "prompts.yaml").write_text(
        "analyst_system: 'You are company analyst'\nshared_key: 'from_company'\n"
    )
    (tmp_path / "company_base" / "tasks.yaml").write_text(
        "task_types:\n  - ANALYZE_LOG\ntask_descriptions:\n  ANALYZE_LOG: 'Analyze'\n"
    )

    (tmp_path / "product_level").mkdir()
    (tmp_path / "product_level" / "project.yaml").write_text(
        "name: product_level\nparent: company_base\n"
    )
    (tmp_path / "product_level" / "prompts.yaml").write_text(
        "analyst_system: 'You are product analyst'\n"
    )
    (tmp_path / "product_level" / "tasks.yaml").write_text(
        "task_types:\n  - ANALYZE_LOG\n  - REVIEW_MR\n"
        "task_descriptions:\n  ANALYZE_LOG: 'Analyze'\n  REVIEW_MR: 'Review'\n"
    )

    (tmp_path / "team_fw").mkdir()
    (tmp_path / "team_fw" / "project.yaml").write_text(
        "name: team_fw\nparent: product_level\n"
        "cross_team_routes:\n  - target: team_hw\n"
    )
    (tmp_path / "team_fw" / "prompts.yaml").write_text(
        "analyst_system: 'You are firmware analyst'\n"
    )
    (tmp_path / "team_fw" / "tasks.yaml").write_text(
        "task_types:\n  - ANALYZE_LOG\ntask_descriptions:\n  ANALYZE_LOG: 'FW analyze'\n"
    )

    (tmp_path / "team_hw").mkdir()
    (tmp_path / "team_hw" / "project.yaml").write_text(
        "name: team_hw\nparent: product_level\n"
    )
    (tmp_path / "team_hw" / "prompts.yaml").write_text("analyst_system: 'HW analyst'\n")
    (tmp_path / "team_hw" / "tasks.yaml").write_text(
        "task_types:\n  - ANALYZE_LOG\ntask_descriptions:\n  ANALYZE_LOG: 'HW analyze'\n"
    )

    org = {
        "org": {
            "name": "test_org",
            "root_solution": "company_base",
            "knowledge_channels": {
                "hw-fw": {"producers": ["team_hw"], "consumers": ["team_fw"]}
            },
        }
    }
    (tmp_path / "org.yaml").write_text(yaml.dump(org))
    return tmp_path


def test_loads_org_yaml(solutions_dir):
    loader = OrgLoader(str(solutions_dir))
    assert loader.org_name == "test_org"
    assert loader.root_solution == "company_base"


def test_no_org_yaml_returns_none():
    loader = OrgLoader("/tmp/no_org_here_xyz")
    assert loader.org_name is None


def test_get_parent_chain(solutions_dir):
    loader = OrgLoader(str(solutions_dir))
    chain = loader.get_parent_chain("team_fw")
    assert chain == ["team_fw", "product_level", "company_base"]


def test_cycle_detection_raises(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "project.yaml").write_text("name: a\nparent: b\n")
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "project.yaml").write_text("name: b\nparent: a\n")
    org = {"org": {"name": "x", "root_solution": "a", "knowledge_channels": {}}}
    (tmp_path / "org.yaml").write_text(yaml.dump(org))
    with pytest.raises(OrgLoaderError, match="cycle"):
        OrgLoader(str(tmp_path))


def test_merged_prompts_child_wins(solutions_dir):
    loader = OrgLoader(str(solutions_dir))
    merged = loader.get_merged_prompts("team_fw")
    assert merged["analyst_system"] == "You are firmware analyst"
    assert merged["shared_key"] == "from_company"


def test_merged_tasks_child_wins(solutions_dir):
    loader = OrgLoader(str(solutions_dir))
    merged = loader.get_merged_tasks("team_fw")
    assert "FW analyze" in merged.get("task_descriptions", {}).get("ANALYZE_LOG", "")
    assert "REVIEW_MR" in merged.get("task_types", [])


def test_channel_normalization(solutions_dir):
    loader = OrgLoader(str(solutions_dir))
    names = loader.get_channel_collection_names("team_fw")
    assert "channel_hw_fw" in names


def test_cross_team_routes_allowed(solutions_dir):
    loader = OrgLoader(str(solutions_dir))
    assert loader.is_route_allowed("team_fw", "team_hw") is True
    assert loader.is_route_allowed("team_fw", "company_base") is False


def test_no_org_is_route_allowed_returns_false():
    loader = OrgLoader("/tmp/no_org_here_xyz")
    assert loader.is_route_allowed("any", "other") is False
