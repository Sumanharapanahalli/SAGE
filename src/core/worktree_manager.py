"""
SAGE Worktree Manager — per-proposal git worktree isolation.

Creates a git worktree for each code_diff proposal so the main working
tree is never dirtied by in-flight proposals.

Worktree layout:  <repo_root>/.sage_worktrees/<trace_id>/
"""

import logging
import os
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


class WorktreeManager:
    """Manages git worktrees keyed by proposal trace_id."""

    def __init__(self, repo_root: str = ""):
        if not repo_root:
            repo_root = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
        self._root = repo_root
        self._wt_base = os.path.join(repo_root, ".sage_worktrees")
        os.makedirs(self._wt_base, exist_ok=True)
        self._worktrees: dict = {}  # trace_id -> path

    def create(self, trace_id: str) -> str:
        """
        Create a new worktree for *trace_id* and return its path.
        The worktree is a checkout of the current HEAD on a new branch.
        """
        wt_path = os.path.join(self._wt_base, trace_id)
        branch  = f"proposal/{trace_id[:8]}"
        try:
            subprocess.run(
                ["git", "worktree", "add", "-b", branch, wt_path, "HEAD"],
                cwd=self._root, check=True, capture_output=True, timeout=15,
            )
            self._worktrees[trace_id] = wt_path
            logger.info("Worktree created: %s -> %s", trace_id, wt_path)
            return wt_path
        except subprocess.CalledProcessError as exc:
            logger.error("git worktree add failed: %s", exc.stderr.decode() if exc.stderr else exc)
            raise

    def remove(self, trace_id: str) -> None:
        """Remove the worktree and its branch for *trace_id*."""
        wt_path = self._worktrees.pop(trace_id, os.path.join(self._wt_base, trace_id))
        try:
            subprocess.run(
                ["git", "worktree", "remove", "--force", wt_path],
                cwd=self._root, check=True, capture_output=True, timeout=15,
            )
            branch = f"proposal/{trace_id[:8]}"
            subprocess.run(
                ["git", "branch", "-D", branch],
                cwd=self._root, capture_output=True, timeout=10,
            )
            logger.info("Worktree removed: %s", trace_id)
        except subprocess.CalledProcessError as exc:
            logger.warning("git worktree remove failed: %s", exc.stderr.decode() if exc.stderr else exc)

    def get_path(self, trace_id: str) -> Optional[str]:
        """Return the worktree path for *trace_id*, or None if not found."""
        path = self._worktrees.get(trace_id)
        if path and os.path.isdir(path):
            return path
        disk_path = os.path.join(self._wt_base, trace_id)
        return disk_path if os.path.isdir(disk_path) else None

    def list_worktrees(self) -> list:
        """Return list of active worktrees as dicts with trace_id and path."""
        result = []
        try:
            out = subprocess.check_output(
                ["git", "worktree", "list", "--porcelain"],
                cwd=self._root, timeout=10, text=True,
            )
            current_path = ""
            for line in out.splitlines():
                if line.startswith("worktree "):
                    current_path = line.split(" ", 1)[1]
                    if ".sage_worktrees" in current_path:
                        trace_id = os.path.basename(current_path)
                        result.append({"trace_id": trace_id, "path": current_path})
        except Exception as exc:
            logger.warning("git worktree list failed: %s", exc)
        return result
