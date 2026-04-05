"""
GitHub Connector
=================

Fetches issues, PRs, and commits from a GitHub repository.
Uses the gh CLI or GitHub REST API.
"""

import json
import logging
import subprocess

from src.connectors.base import BaseConnector

logger = logging.getLogger(__name__)


class GitHubConnector(BaseConnector):
    """Fetches issues, PRs, and commits from GitHub."""

    connector_type = "github"

    def connect(self, config: dict) -> bool:
        repo = config.get("repo", "")
        if not repo or "/" not in repo:
            self._connected = False
            return False
        self._config = config
        self._connected = True
        return True

    def fetch(self, **kwargs) -> list[dict]:
        if not self._connected:
            return []
        repo = self._config["repo"]
        resource = kwargs.get("resource", "issues")
        limit = kwargs.get("limit", 30)

        try:
            if resource == "issues":
                return self._fetch_issues(repo, limit)
            elif resource == "pulls":
                return self._fetch_pulls(repo, limit)
            elif resource == "commits":
                return self._fetch_commits(repo, limit)
            return []
        except Exception as e:
            logger.error("GitHub fetch failed: %s", e)
            return []

    def _fetch_issues(self, repo: str, limit: int) -> list[dict]:
        result = subprocess.run(
            ["gh", "issue", "list", "--repo", repo, "--limit", str(limit), "--json",
             "number,title,state,body,labels,createdAt"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            logger.warning("gh issue list failed: %s", result.stderr)
            return []
        return json.loads(result.stdout or "[]")

    def _fetch_pulls(self, repo: str, limit: int) -> list[dict]:
        result = subprocess.run(
            ["gh", "pr", "list", "--repo", repo, "--limit", str(limit), "--json",
             "number,title,state,body,createdAt"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return []
        return json.loads(result.stdout or "[]")

    def _fetch_commits(self, repo: str, limit: int) -> list[dict]:
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}/commits", "--jq",
             f".[:{limit}] | [.[] | {{sha: .sha, message: .commit.message, date: .commit.author.date}}]"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return []
        return json.loads(result.stdout or "[]")

    def sync(self) -> dict:
        issues = self.fetch(resource="issues", limit=50)
        pulls = self.fetch(resource="pulls", limit=20)
        return {
            "synced_issues": len(issues),
            "synced_pulls": len(pulls),
            "repo": self._config.get("repo", ""),
        }
