"""Tests for src.core.project_loader helpers."""
from pathlib import Path

from src.core.project_loader import list_solutions


def test_list_solutions_returns_dirs_with_project_yaml(tmp_path):
    (tmp_path / "solutions" / "a").mkdir(parents=True)
    (tmp_path / "solutions" / "a" / "project.yaml").write_text("name: a\n")
    (tmp_path / "solutions" / "b").mkdir()
    (tmp_path / "solutions" / "b" / "SKILL.md").write_text("# b\n")
    (tmp_path / "solutions" / "README.md").write_text("readme")
    (tmp_path / "solutions" / "org.yaml").write_text("orgs: []")
    (tmp_path / "solutions" / "bare").mkdir()

    result = list_solutions(tmp_path)
    names = [r["name"] for r in result]
    assert names == ["a", "b"]
    assert result[0]["has_sage_dir"] is False
    assert Path(result[0]["path"]).name == "a"


def test_list_solutions_detects_sage_dir(tmp_path):
    (tmp_path / "solutions" / "a").mkdir(parents=True)
    (tmp_path / "solutions" / "a" / "project.yaml").write_text("name: a\n")
    (tmp_path / "solutions" / "a" / ".sage").mkdir()

    result = list_solutions(tmp_path)
    assert result[0]["has_sage_dir"] is True


def test_list_solutions_missing_dir_returns_empty(tmp_path):
    assert list_solutions(tmp_path) == []


def test_list_solutions_sorted_alphabetically(tmp_path):
    for n in ["zeta", "alpha", "mu"]:
        d = tmp_path / "solutions" / n
        d.mkdir(parents=True)
        (d / "project.yaml").write_text("name: x\n")

    names = [r["name"] for r in list_solutions(tmp_path)]
    assert names == ["alpha", "mu", "zeta"]


def test_list_solutions_skips_dotfiles(tmp_path):
    (tmp_path / "solutions" / ".hidden").mkdir(parents=True)
    (tmp_path / "solutions" / ".hidden" / "project.yaml").write_text("x")
    assert list_solutions(tmp_path) == []
