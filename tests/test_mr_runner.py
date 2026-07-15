"""The MR state machine: driven entirely with fakes — no git, no network, no LLM.

Covers the paths that matter for the compliance gate: a PR is never opened while the gate is
red; approval triggers a signed merge; changes-requested reworks then merges; a manual GitHub
merge is detected and recorded; gh-unavailable fails cleanly without creating a worktree.
"""
from __future__ import annotations

import pytest

from src.core.mr_runner import MRRunner
from src.core.mr_store import MRStore

pytestmark = pytest.mark.unit


class FakeGitHub:
    def __init__(self, *, available=True, decisions=None, states=None,
                 create_ok=True, merge_ok=True):
        self._available = available
        self._decisions = list(decisions or [])   # consumed per poll: review_decision values
        self._states = list(states or [])          # consumed per poll: state values (default OPEN)
        self.create_ok = create_ok
        self.merge_ok = merge_ok
        self.created = None
        self.comments = []
        self.merged = False

    def available(self):
        return self._available

    def create(self, branch, title, body, base="main"):
        if not self.create_ok:
            return {"ok": False, "number": None, "url": "", "error": "boom"}
        self.created = {"branch": branch, "title": title, "body": body}
        return {"ok": True, "number": 42, "url": "https://gh/pr/42", "error": ""}

    def state(self, number):
        st = self._states.pop(0) if self._states else "OPEN"
        dec = self._decisions.pop(0) if self._decisions else "REVIEW_REQUIRED"
        return {"state": st, "review_decision": dec, "merged_sha": "sha-manual", "error": ""}

    def get_comments(self, number):
        return [{"author": "harish", "body": "handle the null case", "created": "t"}]

    def comment(self, number, body, role="agent"):
        self.comments.append({"body": body, "role": role})
        return {"ok": True, "error": ""}

    def merge(self, number, method="squash"):
        self.merged = True
        return {"ok": self.merge_ok, "sha": "sha-merged", "error": "" if self.merge_ok else "no"}


class FakeWorktree:
    def __init__(self, tmp):
        self.tmp = str(tmp)
        self.created_for = None

    def create(self, mr_id):
        self.created_for = mr_id
        return self.tmp

    def get_path(self, mr_id):
        return self.tmp

    def remove(self, mr_id):
        pass


class FakePackage:
    @staticmethod
    def build_pr_title(work_item):
        return f"feat: {work_item}"[:72]

    @staticmethod
    def build_pr_body(**kw):
        return "## Summary\nbody"


def _runner(tmp_path, github, *, gate_sequence, merges):
    """gate_sequence: list of bool (green?) consumed per code+gate attempt."""
    store = MRStore(str(tmp_path / "mr.db"))
    seq = list(gate_sequence)

    def code_fn(path, ctx):
        return {"summary": "did work", "written_files": ["a.py"]}

    def gate_fn(path):
        green = seq.pop(0) if seq else True
        return {"green": green, "evidence": {"gate_green": green, "summary": "did work"},
                "output": "FAILED: x" if not green else "ok"}

    def git_fn(path, *args, timeout=30):
        return 0, "1 file changed"

    def record_merge(approver, work_item, mr_id, sha):
        merges.append({"approver": approver, "mr_id": mr_id, "sha": sha})
        return "sig-" + sha

    r = MRRunner(store=store, github=github, worktree=FakeWorktree(tmp_path),
                 code_fn=code_fn, gate_fn=gate_fn, package=FakePackage(),
                 record_merge=record_merge, git_fn=git_fn, sleep_fn=lambda *_: None,
                 rework_max=2, poll_max=5, poll_interval=0)
    return r, store


def test_green_first_then_approved_merges_and_signs(tmp_path):
    merges = []
    gh = FakeGitHub(decisions=["APPROVED"])
    r, store = _runner(tmp_path, gh, gate_sequence=[True], merges=merges)
    mr = store.create("fix the thing", "sage/mr-1")
    res = r.run(mr)
    assert res["state"] == "merged" and res["merged_sha"] == "sha-merged"
    assert gh.created is not None and gh.merged is True
    assert merges == [{"approver": "operator", "mr_id": mr, "sha": "sha-merged"}]


def test_pr_is_not_opened_while_gate_is_red(tmp_path):
    merges = []
    gh = FakeGitHub()
    # rework_max=2 → 3 attempts, all red → fail before any PR.
    r, store = _runner(tmp_path, gh, gate_sequence=[False, False, False], merges=merges)
    mr = store.create("bad change", "sage/mr-2")
    res = r.run(mr)
    assert res["state"] == "failed"
    assert gh.created is None, "no PR may be opened while the gate is red"
    assert store.get(mr)["state"] == "failed"


def test_red_then_green_opens_pr(tmp_path):
    merges = []
    gh = FakeGitHub(decisions=["APPROVED"])
    r, store = _runner(tmp_path, gh, gate_sequence=[False, True], merges=merges)
    mr = store.create("needs one rework", "sage/mr-3")
    res = r.run(mr)
    assert gh.created is not None
    assert res["state"] == "merged"


def test_changes_requested_then_approved(tmp_path):
    merges = []
    # poll 1: CHANGES_REQUESTED → rework; poll 2: APPROVED → merge.
    gh = FakeGitHub(decisions=["CHANGES_REQUESTED", "APPROVED"])
    # gate: initial green (open PR), rework green.
    r, store = _runner(tmp_path, gh, gate_sequence=[True, True], merges=merges)
    mr = store.create("iterate on review", "sage/mr-4")
    res = r.run(mr)
    assert res["state"] == "merged"
    assert gh.comments, "a rework comment should be posted"
    # the rework comment is authored by the dev agent (drives the [Sage][dev] tag)
    assert gh.comments[0]["role"] == "dev"
    assert len(merges) == 1


def test_manual_github_merge_is_detected_and_recorded(tmp_path):
    merges = []
    gh = FakeGitHub(states=["MERGED"])  # human merged in GitHub directly
    r, store = _runner(tmp_path, gh, gate_sequence=[True], merges=merges)
    mr = store.create("manual merge", "sage/mr-5")
    res = r.run(mr)
    assert res["state"] == "merged" and res["merged_sha"] == "sha-manual"
    assert merges[0]["sha"] == "sha-manual"


def test_gh_unavailable_fails_without_worktree(tmp_path):
    merges = []
    gh = FakeGitHub(available=False)
    wt = FakeWorktree(tmp_path)
    store = MRStore(str(tmp_path / "mr.db"))
    r = MRRunner(store=store, github=gh, worktree=wt,
                 code_fn=lambda p, c: {"summary": "", "written_files": []},
                 gate_fn=lambda p: {"green": True, "evidence": {}, "output": ""},
                 package=FakePackage(), record_merge=lambda *a: "s",
                 git_fn=lambda p, *a, timeout=30: (0, ""), sleep_fn=lambda *_: None)
    mr = store.create("x", "sage/mr-6")
    res = r.run(mr)
    assert res["state"] == "failed"
    assert wt.created_for is None, "must not create a worktree when gh is unusable"


def test_review_pending_when_human_does_not_decide(tmp_path):
    merges = []
    gh = FakeGitHub(decisions=[])  # never decides within poll_max
    r, store = _runner(tmp_path, gh, gate_sequence=[True], merges=merges)
    mr = store.create("awaiting", "sage/mr-7")
    res = r.run(mr)
    assert res["state"] == "review" and res.get("pending") is True
    assert not merges


def test_commit_stages_only_the_agents_files_not_add_A(tmp_path):
    """The evidence gate generates runtime artifacts in the worktree; the commit must stage
    ONLY the agent's declared files, never `git add -A` (PR #12 leaked chroma/gym binaries)."""
    from src.core.mr_runner import MRRunner
    from src.core.mr_store import MRStore
    calls = []

    def git_fn(path, *args, timeout=30):
        calls.append(args)
        return 0, "ok"

    r = MRRunner(store=MRStore(str(tmp_path / "mr.db")), github=None, worktree=None,
                 code_fn=lambda p, c: {}, gate_fn=lambda p: {"green": True}, package=None,
                 record_merge=lambda *a: "s", git_fn=git_fn)
    ok, _ = r._commit_and_push("/wt", "sage/mr-x", "msg", files=["CLAUDE.md", "src/x.py"])
    assert ok
    add_args = [a for a in calls if a and a[0] == "add"]
    # Every add is scoped with `--` to a declared file; none is a bare `add -A`.
    assert all("-A" not in a for a in add_args), f"add -A leaked: {add_args}"
    assert ("add", "--", "CLAUDE.md") in calls and ("add", "--", "src/x.py") in calls
