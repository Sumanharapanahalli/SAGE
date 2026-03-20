import os
import subprocess
import shutil
import pytest


@pytest.fixture
def git_repo(tmp_path):
    """Create a minimal git repo for testing."""
    if shutil.which("git") is None:
        pytest.skip("git not available")
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True, capture_output=True)
    (tmp_path / "main.py").write_text("# main\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], check=True, capture_output=True)
    return tmp_path


def test_create_and_delete_worktree(git_repo):
    from src.core.worktree_manager import WorktreeManager
    mgr = WorktreeManager(repo_root=str(git_repo))
    wt_path = mgr.create("test-trace-001")
    assert os.path.isdir(wt_path)
    mgr.remove("test-trace-001")
    assert not os.path.isdir(wt_path)


def test_list_worktrees(git_repo):
    from src.core.worktree_manager import WorktreeManager
    mgr = WorktreeManager(repo_root=str(git_repo))
    mgr.create("trace-aaa")
    mgr.create("trace-bbb")
    listed = mgr.list_worktrees()
    trace_ids = [w["trace_id"] for w in listed]
    assert "trace-aaa" in trace_ids
    assert "trace-bbb" in trace_ids
    mgr.remove("trace-aaa")
    mgr.remove("trace-bbb")


def test_get_path_returns_none_for_unknown(git_repo):
    from src.core.worktree_manager import WorktreeManager
    mgr = WorktreeManager(repo_root=str(git_repo))
    assert mgr.get_path("nonexistent") is None
