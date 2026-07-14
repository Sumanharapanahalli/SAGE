"""A code_diff reject must revert ONLY the agent's files — never wipe the working tree.

The prior _revert_code_diff ran `git checkout -- .` + `git clean -fd` at the repo ROOT, so a
single Reject click discarded every uncommitted edit and deleted every untracked file in the
checkout, unrecoverably. These tests build a real throwaway git repo, plant unrelated
uncommitted + untracked operator work beside the agent's files, reject, and assert the
operator's work SURVIVES while the agent's change is undone.
"""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import pytest

from src.core.proposal_executor import _revert_code_diff

pytestmark = pytest.mark.unit


class _Proposal:
    def __init__(self, trace_id, payload):
        self.trace_id = trace_id
        self.payload = payload


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A real git repo whose root is what proposal_executor computes as `root`.

    proposal_executor derives root as three dirnames up from its own file, so point its
    module `os.path` calls at the temp repo by patching the module's __file__-derived root
    is fragile; instead we patch WorktreeManager to return the temp repo for the trace, which
    _revert_code_diff honours as `root`.
    """
    _git(["init"], tmp_path)
    _git(["config", "user.email", "t@t"], tmp_path)
    _git(["config", "user.name", "t"], tmp_path)
    (tmp_path / "app.py").write_text("original\n", encoding="utf-8")
    _git(["add", "-A"], tmp_path)
    _git(["commit", "-m", "base"], tmp_path)

    import src.core.proposal_executor as pe

    class _WT:
        def get_path(self, trace_id):
            return str(tmp_path)

    monkeypatch.setattr(pe, "WorktreeManager", _WT, raising=False)
    # WorktreeManager is imported inside the function from src.core.worktree_manager.
    import src.core.worktree_manager as wm
    monkeypatch.setattr(wm, "WorktreeManager", _WT, raising=False)
    return tmp_path


def test_reject_deletes_only_the_agents_new_file(repo):
    # Agent created a new file; operator has unrelated untracked work beside it.
    (repo / "agent_new.py").write_text("ai wrote this\n", encoding="utf-8")
    (repo / "operator_scratch.txt").write_text("MY UNSAVED WORK\n", encoding="utf-8")
    (repo / "notes").mkdir()
    (repo / "notes" / "todo.md").write_text("do not delete me\n", encoding="utf-8")

    p = _Proposal("t1", {"written_files": ["agent_new.py"]})
    res = asyncio.run(_revert_code_diff(p))

    assert res["reverted"] is True
    assert not (repo / "agent_new.py").exists(), "agent's new file should be removed"
    # The operator's untracked work MUST survive — this is the whole point.
    assert (repo / "operator_scratch.txt").read_text(encoding="utf-8") == "MY UNSAVED WORK\n"
    assert (repo / "notes" / "todo.md").exists()


def test_reject_restores_a_modified_tracked_file_without_touching_others(repo):
    # Agent modified a tracked file; operator has an unrelated uncommitted edit.
    (repo / "app.py").write_text("AI CHANGED THIS\n", encoding="utf-8")
    (repo / "other_tracked.py").write_text("v1\n", encoding="utf-8")
    _git(["add", "other_tracked.py"], repo)
    _git(["commit", "-m", "add other"], repo)
    (repo / "other_tracked.py").write_text("OPERATOR EDIT IN PROGRESS\n", encoding="utf-8")

    p = _Proposal("t2", {"written_files": ["app.py"]})
    res = asyncio.run(_revert_code_diff(p))

    assert res["reverted"] is True
    assert (repo / "app.py").read_text(encoding="utf-8") == "original\n", "agent edit undone"
    # The operator's unrelated uncommitted edit MUST remain.
    assert (repo / "other_tracked.py").read_text(encoding="utf-8") == "OPERATOR EDIT IN PROGRESS\n"


def test_reject_with_no_recorded_files_wipes_nothing(repo):
    (repo / "precious.txt").write_text("keep\n", encoding="utf-8")
    p = _Proposal("t3", {})  # no written_files
    res = asyncio.run(_revert_code_diff(p))

    assert res["reverted"] is False
    assert (repo / "precious.txt").exists(), "empty payload must NOT trigger a tree wipe"


def test_reject_refuses_path_traversal(repo, tmp_path):
    outside = tmp_path.parent / "OUTSIDE_SECRET.txt"
    outside.write_text("must survive\n", encoding="utf-8")
    p = _Proposal("t4", {"written_files": ["../OUTSIDE_SECRET.txt"]})
    res = asyncio.run(_revert_code_diff(p))

    assert outside.exists(), "a path escaping the repo root must never be touched"
    assert "../OUTSIDE_SECRET.txt" in res.get("skipped", [])
