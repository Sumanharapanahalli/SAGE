"""
Tests: OrgLoader wired into ProjectConfig — agents see merged task types from parent chain.
"""
import os
import pytest
import yaml
from unittest.mock import patch


def test_get_task_types_includes_parent_types(tmp_path, monkeypatch):
    """When a parent solution defines REVIEW_MR, child should see it via get_task_types()."""
    monkeypatch.setenv("SAGE_SOLUTIONS_DIR", str(tmp_path))

    (tmp_path / "parent_sol").mkdir()
    (tmp_path / "parent_sol" / "project.yaml").write_text("name: parent_sol\n")
    (tmp_path / "parent_sol" / "tasks.yaml").write_text(
        "task_types:\n  - ANALYZE_LOG\n  - REVIEW_MR\n"
        "task_descriptions:\n  ANALYZE_LOG: 'A'\n  REVIEW_MR: 'R'\n"
    )
    (tmp_path / "parent_sol" / "prompts.yaml").write_text("")

    (tmp_path / "child_sol").mkdir()
    (tmp_path / "child_sol" / "project.yaml").write_text(
        "name: child_sol\nparent: parent_sol\n"
    )
    (tmp_path / "child_sol" / "tasks.yaml").write_text(
        "task_types:\n  - ANALYZE_LOG\ntask_descriptions:\n  ANALYZE_LOG: 'Child A'\n"
    )
    (tmp_path / "child_sol" / "prompts.yaml").write_text("")

    org = {"org": {"name": "x", "root_solution": "parent_sol", "knowledge_channels": {}}}
    (tmp_path / "org.yaml").write_text(yaml.dump(org))

    from src.core.org_loader import OrgLoader
    mock_loader = OrgLoader(str(tmp_path))

    with patch("src.core.project_loader._get_org_loader", return_value=mock_loader):
        from src.core.project_loader import ProjectConfig
        pc = ProjectConfig("child_sol")
        types = pc.get_task_types()

    assert "REVIEW_MR" in types
    assert "ANALYZE_LOG" in types


def test_get_task_descriptions_merges_parent(tmp_path, monkeypatch):
    """Child inherits parent's task descriptions; child key overrides parent."""
    monkeypatch.setenv("SAGE_SOLUTIONS_DIR", str(tmp_path))

    (tmp_path / "parent_sol").mkdir()
    (tmp_path / "parent_sol" / "project.yaml").write_text("name: parent_sol\n")
    (tmp_path / "parent_sol" / "tasks.yaml").write_text(
        "task_types:\n  - ANALYZE_LOG\n  - REVIEW_MR\n"
        "task_descriptions:\n  ANALYZE_LOG: 'Parent A'\n  REVIEW_MR: 'R'\n"
    )
    (tmp_path / "parent_sol" / "prompts.yaml").write_text("")

    (tmp_path / "child_sol").mkdir()
    (tmp_path / "child_sol" / "project.yaml").write_text(
        "name: child_sol\nparent: parent_sol\n"
    )
    (tmp_path / "child_sol" / "tasks.yaml").write_text(
        "task_types:\n  - ANALYZE_LOG\ntask_descriptions:\n  ANALYZE_LOG: 'Child A'\n"
    )
    (tmp_path / "child_sol" / "prompts.yaml").write_text("")

    org = {"org": {"name": "x", "root_solution": "parent_sol", "knowledge_channels": {}}}
    (tmp_path / "org.yaml").write_text(yaml.dump(org))

    from src.core.org_loader import OrgLoader
    mock_loader = OrgLoader(str(tmp_path))

    with patch("src.core.project_loader._get_org_loader", return_value=mock_loader):
        from src.core.project_loader import ProjectConfig
        pc = ProjectConfig("child_sol")
        descs = pc.get_task_descriptions()

    # Child overrides ANALYZE_LOG description
    assert descs["ANALYZE_LOG"] == "Child A"
    # Parent's REVIEW_MR description is inherited
    assert descs["REVIEW_MR"] == "R"


def test_no_org_falls_back_to_flat_tasks(tmp_path, monkeypatch):
    """Without org.yaml (org_name is None), get_task_types() returns the solution's own types only."""
    monkeypatch.setenv("SAGE_SOLUTIONS_DIR", str(tmp_path))

    (tmp_path / "solo_sol").mkdir()
    (tmp_path / "solo_sol" / "project.yaml").write_text("name: solo_sol\n")
    (tmp_path / "solo_sol" / "tasks.yaml").write_text(
        "task_types:\n  - ANALYZE_LOG\ntask_descriptions:\n  ANALYZE_LOG: 'Solo A'\n"
    )
    (tmp_path / "solo_sol" / "prompts.yaml").write_text("")

    from src.core.org_loader import OrgLoader
    # OrgLoader with no org.yaml — org_name will be None
    mock_loader = OrgLoader(str(tmp_path))

    with patch("src.core.project_loader._get_org_loader", return_value=mock_loader):
        from src.core.project_loader import ProjectConfig
        pc = ProjectConfig("solo_sol")
        types = pc.get_task_types()

    assert "ANALYZE_LOG" in types
    assert "REVIEW_MR" not in types
