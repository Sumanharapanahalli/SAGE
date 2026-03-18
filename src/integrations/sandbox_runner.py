"""
sandbox_runner.py — Isolated execution sandbox for the SWE agent.
Provides repo cloning, shell execution, and file operations in a workspace.

Adapted from open-swe (https://github.com/langchain-ai/open-swe) for SAGE's
agent-first architecture. Supports local subprocess execution with Docker
extension path.
"""
import os
import subprocess
import logging
import shutil
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)


class SandboxRunner:
    """Repo-level execution sandbox for the SWE agent.

    Provides:
    - Repository cloning into an isolated workspace directory
    - Shell command execution inside the workspace
    - File read/write in the workspace
    - AGENTS.md auto-loading (open-swe pattern)
    """

    def clone_repo(self, repo_url: str, workspace_dir: Optional[str] = None) -> dict:
        """Clone a git repository into a temp workspace.
        Returns: {workspace_dir, success, error}
        """
        try:
            if workspace_dir is None:
                workspace_dir = tempfile.mkdtemp(prefix="sage-swe-")
            result = subprocess.run(
                ["git", "clone", "--depth=1", repo_url, workspace_dir],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                return {"success": False, "error": result.stderr, "workspace_dir": workspace_dir}
            return {"success": True, "workspace_dir": workspace_dir, "error": None}
        except Exception as e:
            return {"success": False, "error": str(e), "workspace_dir": workspace_dir or ""}

    def execute(self, command: str, workspace_dir: str, timeout: int = 300) -> dict:
        """Execute a shell command in the workspace directory.
        Returns: {stdout, stderr, returncode, success}
        """
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=workspace_dir,
                timeout=timeout,
            )
            stdout = result.stdout
            stderr = result.stderr
            return {
                "stdout": stdout[-4000:] if len(stdout) > 4000 else stdout,
                "stderr": stderr[-2000:] if len(stderr) > 2000 else stderr,
                "returncode": result.returncode,
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": "Command timed out", "returncode": -1, "success": False}
        except Exception as e:
            return {"stdout": "", "stderr": str(e), "returncode": -1, "success": False}

    def read_file(self, path: str, workspace_dir: str) -> dict:
        """Read a file from the workspace (path relative to workspace_dir)."""
        full_path = os.path.join(workspace_dir, path)
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return {"content": content, "success": True, "path": path}
        except FileNotFoundError:
            return {"content": None, "success": False, "error": f"File not found: {path}"}
        except Exception as e:
            return {"content": None, "success": False, "error": str(e)}

    def write_file(self, path: str, content: str, workspace_dir: str) -> dict:
        """Write a file in the workspace."""
        full_path = os.path.join(workspace_dir, path)
        try:
            os.makedirs(os.path.dirname(full_path) or workspace_dir, exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"success": True, "path": path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_diff(self, workspace_dir: str) -> dict:
        """Get git diff of all uncommitted changes."""
        return self.execute("git diff HEAD", workspace_dir)

    def read_agents_md(self, workspace_dir: str) -> Optional[str]:
        """Read AGENTS.md from workspace root if present (open-swe pattern).
        AGENTS.md contains repo-specific conventions for the SWE agent.
        """
        result = self.read_file("AGENTS.md", workspace_dir)
        return result["content"] if result["success"] else None

    def cleanup(self, workspace_dir: str):
        """Remove the workspace directory."""
        try:
            shutil.rmtree(workspace_dir, ignore_errors=True)
        except Exception as e:
            logger.warning("Failed to cleanup workspace %s: %s", workspace_dir, e)


sandbox_runner = SandboxRunner()
