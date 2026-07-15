"""
Unit tests for src/core/github_pr.py — the gh CLI adapter.

Every test injects a FAKE runner (a callable returning canned
(rc, stdout, stderr)). No real network, no real gh, no real git.
"""
import json

import pytest

pytestmark = pytest.mark.unit

from src.core.github_pr import GitHubPR


# --------------------------------------------------------------------------- #
# Fake runner
# --------------------------------------------------------------------------- #
class FakeRunner:
    """Records every call and returns a canned (rc, stdout, stderr).

    ``responder(argv) -> (rc, out, err)`` lets a test script per-command
    responses (e.g. merge succeeds, the follow-up `pr view` returns a sha).
    Defaults to a clean success with empty output.
    """

    def __init__(self, responder=None, default=(0, "", "")):
        self._responder = responder
        self._default = default
        self.calls = []  # list of dicts: {argv, cwd, timeout, stdin}

    def __call__(self, argv, cwd, timeout, stdin=None):
        self.calls.append({"argv": list(argv), "cwd": cwd, "timeout": timeout, "stdin": stdin})
        if self._responder is not None:
            resp = self._responder(argv)
            if resp is not None:
                return resp
        return self._default

    # -- convenience lookups ------------------------------------------------ #
    def call_with(self, *needles):
        """Return the first recorded call whose argv contains all *needles*."""
        for c in self.calls:
            if all(n in c["argv"] for n in needles):
                return c
        return None

    @property
    def argvs(self):
        return [c["argv"] for c in self.calls]


def _pr(runner):
    return GitHubPR(cwd="/repo", gh_path="gh", runner=runner)


# --------------------------------------------------------------------------- #
# available()
# --------------------------------------------------------------------------- #
class TestAvailable:
    def test_true_when_auth_status_rc_zero(self):
        runner = FakeRunner(default=(0, "Logged in to github.com", ""))
        assert _pr(runner).available() is True
        call = runner.call_with("auth", "status")
        assert call is not None
        assert call["argv"] == ["gh", "auth", "status"]

    def test_false_when_auth_status_rc_nonzero(self):
        runner = FakeRunner(default=(1, "", "not logged in"))
        assert _pr(runner).available() is False

    def test_false_when_gh_missing_raises(self):
        def boom(argv, cwd, timeout, stdin=None):
            raise FileNotFoundError("gh")

        assert _pr(boom).available() is False


# --------------------------------------------------------------------------- #
# create()
# --------------------------------------------------------------------------- #
class TestCreate:
    def _responder(self, argv):
        if "push" in argv:
            return (0, "", "")
        if "create" in argv:
            return (0, "https://github.com/acme/repo/pull/42\n", "")
        return (0, "", "")

    def test_pushes_then_creates_with_right_base_and_head(self):
        runner = FakeRunner(responder=self._responder)
        out = _pr(runner).create(
            branch="feature/x", title="My title", body="# long body", base="develop"
        )
        assert out == {"ok": True, "number": 42, "url": "https://github.com/acme/repo/pull/42", "error": ""}

        # git push happens first, and before the gh pr create call.
        assert runner.argvs[0] == ["git", "push", "-u", "origin", "feature/x"]
        create = runner.call_with("pr", "create")
        assert create is not None
        argv = create["argv"]
        # base/head wired correctly
        assert argv[argv.index("--base") + 1] == "develop"
        assert argv[argv.index("--head") + 1] == "feature/x"
        assert argv[argv.index("--title") + 1] == "My title"

    def test_body_goes_via_stdin_not_argv(self):
        runner = FakeRunner(responder=self._responder)
        _pr(runner).create(branch="b", title="t", body="# long markdown body")
        create = runner.call_with("pr", "create")
        # body delivered on stdin
        assert create["stdin"] == "# long markdown body"
        # --body-file - present, body text NOT anywhere in argv
        argv = create["argv"]
        assert argv[argv.index("--body-file") + 1] == "-"
        assert "# long markdown body" not in argv

    def test_default_base_is_main(self):
        runner = FakeRunner(responder=self._responder)
        _pr(runner).create(branch="b", title="t", body="x")
        create = runner.call_with("pr", "create")
        argv = create["argv"]
        assert argv[argv.index("--base") + 1] == "main"

    def test_push_failure_returns_error_with_all_keys_no_create(self):
        def responder(argv):
            if "push" in argv:
                return (1, "", "fatal: remote rejected")
            return (0, "", "")

        runner = FakeRunner(responder=responder)
        out = _pr(runner).create(branch="b", title="t", body="x")
        assert out["ok"] is False
        assert out["number"] is None
        assert out["url"] == ""
        assert "remote rejected" in out["error"]
        # gh pr create must NOT have run after a failed push
        assert runner.call_with("pr", "create") is None

    def test_create_failure_returns_ok_false_with_stderr(self):
        def responder(argv):
            if "push" in argv:
                return (0, "", "")
            if "create" in argv:
                return (1, "", "a pull request already exists")
            return (0, "", "")

        runner = FakeRunner(responder=responder)
        out = _pr(runner).create(branch="b", title="t", body="x")
        assert out["ok"] is False
        assert set(out.keys()) == {"ok", "number", "url", "error"}
        assert "already exists" in out["error"]

    def test_falls_back_to_pr_view_when_output_not_parseable(self):
        def responder(argv):
            if "push" in argv:
                return (0, "", "")
            if "create" in argv:
                return (0, "Opening PR in browser...\n", "")  # no URL
            if "view" in argv:
                return (0, json.dumps({"number": 77, "url": "https://gh/acme/repo/pull/77"}), "")
            return (0, "", "")

        runner = FakeRunner(responder=responder)
        out = _pr(runner).create(branch="b", title="t", body="x")
        assert out["ok"] is True
        assert out["number"] == 77
        assert out["url"] == "https://gh/acme/repo/pull/77"


# --------------------------------------------------------------------------- #
# state()
# --------------------------------------------------------------------------- #
class TestState:
    def test_maps_gh_json_to_contract_dict(self):
        payload = {
            "state": "MERGED",
            "reviewDecision": "APPROVED",
            "mergeCommit": {"oid": "abc123def"},
        }
        runner = FakeRunner(default=(0, json.dumps(payload), ""))
        out = _pr(runner).state(42)
        assert out == {
            "state": "MERGED",
            "review_decision": "APPROVED",
            "merged_sha": "abc123def",
            "error": "",
        }
        call = runner.call_with("pr", "view")
        argv = call["argv"]
        assert argv[argv.index("--json") + 1] == "state,reviewDecision,mergeCommit"
        assert "42" in argv

    def test_null_merge_commit_and_review_decision_become_empty(self):
        payload = {"state": "OPEN", "reviewDecision": None, "mergeCommit": None}
        runner = FakeRunner(default=(0, json.dumps(payload), ""))
        out = _pr(runner).state(1)
        assert out["state"] == "OPEN"
        assert out["review_decision"] == ""
        assert out["merged_sha"] == ""
        assert out["error"] == ""

    def test_rc_nonzero_returns_error_with_all_keys(self):
        runner = FakeRunner(default=(1, "", "no pull requests found"))
        out = _pr(runner).state(999)
        assert set(out.keys()) == {"state", "review_decision", "merged_sha", "error"}
        assert out["state"] == ""
        assert "no pull requests found" in out["error"]

    def test_malformed_json_becomes_error_not_exception(self):
        runner = FakeRunner(default=(0, "not json at all", ""))
        out = _pr(runner).state(1)
        assert out["state"] == ""
        assert out["error"] != ""
        assert set(out.keys()) == {"state", "review_decision", "merged_sha", "error"}


# --------------------------------------------------------------------------- #
# get_reviews()
# --------------------------------------------------------------------------- #
class TestGetReviews:
    def test_parses_reviews_array(self):
        payload = {
            "reviews": [
                {"author": {"login": "alice"}, "state": "APPROVED", "body": "LGTM"},
                {"author": {"login": "bob"}, "state": "CHANGES_REQUESTED", "body": "fix this"},
            ]
        }
        runner = FakeRunner(default=(0, json.dumps(payload), ""))
        out = _pr(runner).get_reviews(5)
        assert out == [
            {"state": "APPROVED", "author": "alice", "body": "LGTM"},
            {"state": "CHANGES_REQUESTED", "author": "bob", "body": "fix this"},
        ]
        call = runner.call_with("pr", "view")
        argv = call["argv"]
        assert argv[argv.index("--json") + 1] == "reviews"

    def test_empty_list_when_rc_nonzero(self):
        runner = FakeRunner(default=(1, "", "boom"))
        assert _pr(runner).get_reviews(5) == []

    def test_empty_list_when_malformed_json(self):
        runner = FakeRunner(default=(0, "garbage", ""))
        assert _pr(runner).get_reviews(5) == []


# --------------------------------------------------------------------------- #
# get_comments()
# --------------------------------------------------------------------------- #
class TestGetComments:
    def test_parses_comments_array_with_created_at(self):
        payload = {
            "comments": [
                {"author": {"login": "carol"}, "body": "first", "createdAt": "2026-01-01T00:00:00Z"},
                {"author": {"login": "dan"}, "body": "second", "createdAt": "2026-01-02T00:00:00Z"},
            ]
        }
        runner = FakeRunner(default=(0, json.dumps(payload), ""))
        out = _pr(runner).get_comments(9)
        assert out == [
            {"author": "carol", "body": "first", "created": "2026-01-01T00:00:00Z"},
            {"author": "dan", "body": "second", "created": "2026-01-02T00:00:00Z"},
        ]
        call = runner.call_with("pr", "view")
        argv = call["argv"]
        assert argv[argv.index("--json") + 1] == "comments"

    def test_empty_list_on_failure(self):
        runner = FakeRunner(default=(1, "", "boom"))
        assert _pr(runner).get_comments(9) == []


# --------------------------------------------------------------------------- #
# comment()
# --------------------------------------------------------------------------- #
class TestComment:
    def test_body_via_stdin_and_argv(self):
        runner = FakeRunner(default=(0, "", ""))
        out = _pr(runner).comment(7, "a **markdown** comment", role="dev")
        assert out == {"ok": True, "error": ""}
        call = runner.call_with("pr", "comment")
        argv = call["argv"]
        assert argv[:4] == ["gh", "pr", "comment", "7"]
        assert argv[argv.index("--body-file") + 1] == "-"
        # body is stamped with the SAGE identity tag so humans can tell it apart
        assert call["stdin"] == "[Sage][dev] : a **markdown** comment"
        # body text never appears as an argument
        assert "a **markdown** comment" not in argv

    def test_default_role_when_unspecified(self):
        runner = FakeRunner(default=(0, "", ""))
        _pr(runner).comment(7, "hello")
        assert runner.call_with("pr", "comment")["stdin"] == "[Sage][agent] : hello"

    def test_tag_is_idempotent(self):
        # a body already tagged (e.g. re-posted) is not double-wrapped
        runner = FakeRunner(default=(0, "", ""))
        _pr(runner).comment(7, "[Sage][test] : already tagged", role="dev")
        assert runner.call_with("pr", "comment")["stdin"] == "[Sage][test] : already tagged"

    def test_failure_returns_ok_false_with_stderr(self):
        runner = FakeRunner(default=(1, "", "could not add comment"))
        out = _pr(runner).comment(7, "x")
        assert out["ok"] is False
        assert "could not add comment" in out["error"]
        assert set(out.keys()) == {"ok", "error"}


# --------------------------------------------------------------------------- #
# merge()
# --------------------------------------------------------------------------- #
class TestMerge:
    def test_squash_delete_branch_and_reads_sha_via_state(self):
        def responder(argv):
            if "merge" in argv:
                return (0, "", "")
            if "view" in argv:  # follow-up state() read
                payload = {"state": "MERGED", "reviewDecision": "APPROVED",
                           "mergeCommit": {"oid": "deadbeef"}}
                return (0, json.dumps(payload), "")
            return (0, "", "")

        runner = FakeRunner(responder=responder)
        out = _pr(runner).merge(11)
        assert out == {"ok": True, "sha": "deadbeef", "error": ""}

        merge_call = runner.call_with("pr", "merge")
        argv = merge_call["argv"]
        assert argv[:4] == ["gh", "pr", "merge", "11"]
        assert "--squash" in argv
        assert "--delete-branch" in argv

    def test_method_selects_flag(self):
        runner = FakeRunner(default=(0, "{}", ""))
        _pr(runner).merge(3, method="rebase")
        assert "--rebase" in runner.call_with("pr", "merge")["argv"]

        runner2 = FakeRunner(default=(0, "{}", ""))
        _pr(runner2).merge(3, method="merge")
        assert "--merge" in runner2.call_with("pr", "merge")["argv"]

    def test_failure_returns_ok_false_with_stderr_and_all_keys(self):
        def responder(argv):
            if "merge" in argv:
                return (1, "", "not mergeable: checks failing")
            return (0, "", "")

        runner = FakeRunner(responder=responder)
        out = _pr(runner).merge(11)
        assert out["ok"] is False
        assert out["sha"] == ""
        assert "checks failing" in out["error"]
        assert set(out.keys()) == {"ok", "sha", "error"}
        # merge failed -> no follow-up state read
        assert runner.call_with("pr", "view") is None


# --------------------------------------------------------------------------- #
# Never-raises guarantee (runner exceptions)
# --------------------------------------------------------------------------- #
class TestNeverRaises:
    def test_runner_exception_is_captured_not_raised(self):
        def boom(argv, cwd, timeout, stdin=None):
            raise RuntimeError("network exploded")

        pr = _pr(boom)
        # None of these should raise.
        assert pr.available() is False
        c = pr.create(branch="b", title="t", body="x")
        assert c["ok"] is False and "network exploded" in c["error"]
        s = pr.state(1)
        assert s["error"] != ""
        assert pr.get_reviews(1) == []
        assert pr.get_comments(1) == []
        cm = pr.comment(1, "x")
        assert cm["ok"] is False
        m = pr.merge(1)
        assert m["ok"] is False


# --------------------------------------------------------------------------- #
# cwd + gh_path plumbing
# --------------------------------------------------------------------------- #
class TestPlumbing:
    def test_cwd_and_gh_path_are_passed_through(self):
        runner = FakeRunner(default=(0, "", ""))
        pr = GitHubPR(cwd="/some/repo", gh_path="/custom/gh", runner=runner)
        pr.available()
        call = runner.calls[0]
        assert call["cwd"] == "/some/repo"
        assert call["argv"][0] == "/custom/gh"
