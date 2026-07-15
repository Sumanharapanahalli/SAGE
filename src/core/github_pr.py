"""
SAGE Framework — GitHub PR adapter over the ``gh`` CLI.

This is the *single* place where git/gh side effects live. Every other module
that needs to open, inspect, comment on, or merge a pull request goes through
:class:`GitHubPR`, so the rest of the system can be exercised in tests with a
fake ``GitHubPR`` (or, for this module's own tests, a fake ``runner``).

Design rules honoured here:

* All subprocess invocation is funnelled through an injectable ``runner``
  callable — the test seam. The default runner shells out via
  :func:`subprocess.run`.
* PR / comment *bodies* are long markdown and are passed to ``gh`` on **stdin**
  (``--body-file -``), never as positional args — avoids arg-length and shell
  escaping problems.
* No method ever raises on a git/gh failure. Every method returns a structured
  dict/list; failures (non-zero return code, missing executable, timeout,
  malformed JSON) are captured into an ``error`` field.

Runner contract::

    runner(argv: list[str], cwd: str, timeout: int, stdin: str | None = None)
        -> tuple[returncode: int, stdout: str, stderr: str]

``stdin`` is an optional keyword — a superset of the documented
``(argv, cwd, timeout)`` shape — used only to feed ``--body-file -``.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Runner return type alias.
RunResult = tuple  # (returncode: int, stdout: str, stderr: str)

# Timeouts (seconds). A push can be slow; reads/writes are quick.
_PUSH_TIMEOUT = 120
_DEFAULT_TIMEOUT = 60

# Merge method -> gh flag. Anything unrecognised falls back to squash.
_MERGE_FLAGS = {
    "squash": "--squash",
    "merge": "--merge",
    "rebase": "--rebase",
}

# Matches a PR URL like https://github.com/owner/repo/pull/123
_PR_URL_RE = re.compile(r"https?://\S+/pull/\d+")
_PR_NUM_RE = re.compile(r"/pull/(\d+)")


def _default_runner(
    argv: list, cwd: str, timeout: int, stdin: Optional[str] = None
) -> RunResult:
    """Default runner: run *argv* via subprocess and capture stdout/stderr.

    ``text=True`` + ``errors="replace"`` keeps decoding robust across locales.
    ``stdin`` (when given) is fed to the child process' standard input, which is
    how ``--body-file -`` receives the PR/comment body.
    """
    proc = subprocess.run(
        argv,
        cwd=cwd,
        input=stdin,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=timeout,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


class GitHubPR:
    """Thin, fully-testable adapter over the ``gh`` CLI (and ``git push``)."""

    def __init__(
        self, cwd: str, gh_path: str = "gh", runner: Optional[Callable] = None
    ):
        """
        Args:
            cwd: Working directory (a git checkout) all commands run in.
            gh_path: Path/name of the ``gh`` executable. Left as ``gh`` on
                Windows too — the runner resolves it on PATH, no ``.exe``
                assumption.
            runner: Optional callable ``(argv, cwd, timeout, stdin=None) ->
                (rc, stdout, stderr)``. Defaults to a subprocess-based runner.
                Injecting a fake is how tests avoid the network.
        """
        self._cwd = cwd
        self._gh = gh_path
        self._runner = runner or _default_runner

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _run(
        self, argv: list, timeout: int = _DEFAULT_TIMEOUT, stdin: Optional[str] = None
    ) -> RunResult:
        """Invoke the runner, converting *any* exception into an error tuple.

        Guarantees no method built on top of this ever raises because of a
        subprocess/runner failure (missing exe, timeout, custom-runner bug).
        """
        try:
            rc, out, err = self._runner(argv, self._cwd, timeout, stdin=stdin)
        except FileNotFoundError as exc:
            logger.warning("executable not found: %s", exc)
            return 127, "", f"executable not found: {exc}"
        except subprocess.TimeoutExpired as exc:
            logger.warning("command timed out after %ss: %s", timeout, argv)
            return -1, "", f"timeout after {timeout}s: {exc}"
        except Exception as exc:  # noqa: BLE001 - deliberately defensive seam
            logger.warning("runner raised for %s: %s", argv, exc)
            return -1, "", f"runner error: {exc}"
        return int(rc), out or "", err or ""

    @staticmethod
    def _parse_json(stdout: str):
        """Parse gh ``--json`` stdout. Return ``(data, error)``.

        ``error`` is a human-readable string when stdout is empty or not JSON;
        otherwise "". Never raises.
        """
        text = (stdout or "").strip()
        if not text:
            return None, "empty output from gh (expected JSON)"
        try:
            return json.loads(text), ""
        except (ValueError, TypeError) as exc:
            return None, f"could not parse gh JSON output: {exc}"

    @staticmethod
    def _merge_flag(method: str) -> str:
        return _MERGE_FLAGS.get((method or "").lower(), _MERGE_FLAGS["squash"])

    # ------------------------------------------------------------------ #
    # Availability
    # ------------------------------------------------------------------ #
    def available(self) -> bool:
        """True only if ``gh auth status`` succeeds (gh present AND authed)."""
        rc, _out, _err = self._run([self._gh, "auth", "status"])
        return rc == 0

    # ------------------------------------------------------------------ #
    # Create
    # ------------------------------------------------------------------ #
    def create(self, branch: str, title: str, body: str, base: str = "main") -> dict:
        """Push *branch* and open a PR against *base*.

        Returns ``{"ok", "number", "url", "error"}`` on every path.
        """
        result = {"ok": False, "number": None, "url": "", "error": ""}

        # 1. Push the current branch.
        push_rc, _push_out, push_err = self._run(
            ["git", "push", "-u", "origin", branch], timeout=_PUSH_TIMEOUT
        )
        if push_rc != 0:
            result["error"] = push_err.strip() or f"git push failed (rc={push_rc})"
            return result

        # 2. Open the PR; body goes via stdin (--body-file -), never argv.
        create_rc, create_out, create_err = self._run(
            [
                self._gh,
                "pr",
                "create",
                "--base",
                base,
                "--head",
                branch,
                "--title",
                title,
                "--body-file",
                "-",
            ],
            stdin=body,
        )
        if create_rc != 0:
            result["error"] = (
                create_err.strip() or f"gh pr create failed (rc={create_rc})"
            )
            return result

        # 3. Parse url/number from create output.
        url_match = _PR_URL_RE.search(create_out or "")
        if url_match:
            result["url"] = url_match.group(0)
            num_match = _PR_NUM_RE.search(result["url"])
            if num_match:
                result["number"] = int(num_match.group(1))

        # 4. Fall back to `gh pr view` if the output wasn't parseable.
        if result["number"] is None or not result["url"]:
            view_rc, view_out, view_err = self._run(
                [self._gh, "pr", "view", branch, "--json", "number,url"]
            )
            if view_rc == 0:
                data, perr = self._parse_json(view_out)
                if data is not None:
                    if not result["url"]:
                        result["url"] = str(data.get("url", "") or "")
                    if result["number"] is None and data.get("number") is not None:
                        try:
                            result["number"] = int(data["number"])
                        except (ValueError, TypeError):
                            pass
                elif not result["url"] and result["number"] is None:
                    # PR was created but we couldn't determine its identity.
                    result["error"] = perr

        result["ok"] = True
        return result

    # ------------------------------------------------------------------ #
    # State
    # ------------------------------------------------------------------ #
    def state(self, number: int) -> dict:
        """Return ``{"state", "review_decision", "merged_sha", "error"}``."""
        result = {"state": "", "review_decision": "", "merged_sha": "", "error": ""}
        rc, out, err = self._run(
            [
                self._gh,
                "pr",
                "view",
                str(number),
                "--json",
                "state,reviewDecision,mergeCommit",
            ]
        )
        if rc != 0:
            result["error"] = err.strip() or f"gh pr view failed (rc={rc})"
            return result

        data, perr = self._parse_json(out)
        if data is None:
            result["error"] = perr
            return result

        result["state"] = str(data.get("state", "") or "")
        result["review_decision"] = str(data.get("reviewDecision", "") or "")
        merge_commit = data.get("mergeCommit") or {}
        if isinstance(merge_commit, dict):
            result["merged_sha"] = str(merge_commit.get("oid", "") or "")
        return result

    # ------------------------------------------------------------------ #
    # Reviews / comments
    # ------------------------------------------------------------------ #
    def get_reviews(self, number: int) -> list:
        """Return ``[{"state", "author", "body"}, ...]`` (empty on failure)."""
        rc, out, err = self._run(
            [self._gh, "pr", "view", str(number), "--json", "reviews"]
        )
        if rc != 0:
            logger.warning("gh pr view reviews failed (rc=%s): %s", rc, err.strip())
            return []
        data, perr = self._parse_json(out)
        if data is None:
            logger.warning("could not parse reviews JSON: %s", perr)
            return []

        reviews = data.get("reviews") if isinstance(data, dict) else None
        if not isinstance(reviews, list):
            return []

        parsed = []
        for item in reviews:
            if not isinstance(item, dict):
                continue
            author = item.get("author") or {}
            login = author.get("login", "") if isinstance(author, dict) else ""
            parsed.append(
                {
                    "state": str(item.get("state", "") or ""),
                    "author": str(login or ""),
                    "body": str(item.get("body", "") or ""),
                }
            )
        return parsed

    def get_comments(self, number: int) -> list:
        """Return ``[{"author", "body", "created"}, ...]`` (empty on failure)."""
        rc, out, err = self._run(
            [self._gh, "pr", "view", str(number), "--json", "comments"]
        )
        if rc != 0:
            logger.warning("gh pr view comments failed (rc=%s): %s", rc, err.strip())
            return []
        data, perr = self._parse_json(out)
        if data is None:
            logger.warning("could not parse comments JSON: %s", perr)
            return []

        comments = data.get("comments") if isinstance(data, dict) else None
        if not isinstance(comments, list):
            return []

        parsed = []
        for item in comments:
            if not isinstance(item, dict):
                continue
            author = item.get("author") or {}
            login = author.get("login", "") if isinstance(author, dict) else ""
            parsed.append(
                {
                    "author": str(login or ""),
                    "body": str(item.get("body", "") or ""),
                    "created": str(item.get("createdAt", "") or ""),
                }
            )
        return parsed

    # ------------------------------------------------------------------ #
    # Comment
    # ------------------------------------------------------------------ #
    def comment(self, number: int, body: str) -> dict:
        """Post a PR comment (body via stdin). Returns ``{"ok", "error"}``."""
        rc, _out, err = self._run(
            [self._gh, "pr", "comment", str(number), "--body-file", "-"],
            stdin=body,
        )
        if rc != 0:
            return {
                "ok": False,
                "error": err.strip() or f"gh pr comment failed (rc={rc})",
            }
        return {"ok": True, "error": ""}

    # ------------------------------------------------------------------ #
    # Merge
    # ------------------------------------------------------------------ #
    def merge(self, number: int, method: str = "squash") -> dict:
        """Merge the PR and delete the branch. Returns ``{"ok", "sha", "error"}``."""
        flag = self._merge_flag(method)
        rc, _out, err = self._run(
            [self._gh, "pr", "merge", str(number), flag, "--delete-branch"]
        )
        if rc != 0:
            return {
                "ok": False,
                "sha": "",
                "error": err.strip() or f"gh pr merge failed (rc={rc})",
            }

        # Read the resulting merge commit sha via state().
        st = self.state(number)
        return {"ok": True, "sha": st.get("merged_sha", ""), "error": ""}
