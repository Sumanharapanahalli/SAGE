"""Merge-Gate Governance runner — the state machine for one Merge Request.

Drives a single work item from an isolated agent branch to a signed merge, with the human's
only touchpoints being (1) picking the work item and (2) approving/commenting on the PR:

    coding → gating → review → (reworking → gating → review)* → merged | failed

Design rules, learned the hard way this session:
  * Every dependency is INJECTED (coding, evidence gate, git, GitHub, store, sign) so the
    whole state machine is testable with fakes — no network, no LLM, no real git. The
    production wiring lives in build_default_runner().
  * The worktree is created BEFORE coding and IS the agent's write-root, so the branch
    actually contains the change (the old pipeline created the worktree AFTER coding and
    committed nothing — gap B6).
  * A PR is NEVER opened until the evidence gate is green — no broken MR reaches the human.
  * `main` is only ever changed by an approved squash-merge; agent file writes are confined
    to the worktree; nothing here touches the repo root destructively.
"""
from __future__ import annotations

import logging
import subprocess
import time
from typing import Callable, Optional

from src.core.github_pr import SAGE_COMMENT_TAG

logger = logging.getLogger("MRRunner")


def _default_git(path: str, *args: str, timeout: int = 30):
    p = subprocess.run(["git", *args], cwd=path, capture_output=True, text=True,
                       timeout=timeout, errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


class MRRunner:
    """Advance one MR through its lifecycle. All I/O is injected."""

    def __init__(
        self,
        *,
        store,                       # MRStore
        github,                      # GitHubPR-like
        worktree,                    # WorktreeManager-like: create(id)->path, get_path(id), remove(id)
        code_fn: Callable,           # (worktree_path, context:str) -> {"summary":str,"written_files":[str]}
        gate_fn: Callable,           # (worktree_path) -> {"green":bool,"evidence":dict,"output":str}
        package,                     # module with build_pr_title(work_item), build_pr_body(**kw)
        record_merge: Callable,      # (approver, work_item, mr_id, sha) -> event_id  (logs + signs)
        git_fn: Callable = _default_git,
        sleep_fn: Callable = time.sleep,
        base: str = "main",
        rework_max: int = 3,
        poll_max: int = 60,
        poll_interval: float = 10.0,
        operator: str = "operator",
        watch=None,  # WatchStore — durable, idempotent comment handling (optional)
    ):
        self.store = store
        self.github = github
        self.worktree = worktree
        self.watch = watch
        self.code_fn = code_fn
        self.gate_fn = gate_fn
        self.package = package
        self.record_merge = record_merge
        self.git_fn = git_fn
        self.sleep_fn = sleep_fn
        self.base = base
        self.rework_max = rework_max
        self.poll_max = poll_max
        self.poll_interval = poll_interval
        self.operator = operator

    # -- helpers ------------------------------------------------------------
    def _fail(self, mr_id: str, reason: str) -> dict:
        logger.warning("MR %s failed: %s", mr_id, reason)
        self.store.update(mr_id, state="failed", error=reason)
        return {"mr_id": mr_id, "state": "failed", "error": reason}

    def _commit_and_push(self, path: str, branch: str, message: str,
                         files: list = None) -> tuple[bool, str]:
        # Stage ONLY the files the agent declared — never `git add -A`. The evidence gate
        # runs the test suite in the worktree, which GENERATES runtime artifacts (.sage/
        # dbs, caches); -A swept all of that into the PR (observed: PR #12 carried a dozen
        # chroma/gym binaries alongside the one-line fix). Same class as the executor's
        # add-A bug fixed earlier today.
        if files:
            staged = False
            for rel in files:
                if not rel:
                    continue
                rc, _ = self.git_fn(path, "add", "--", rel)
                staged = staged or rc == 0
            if not staged:
                return False, "none of the agent's written files could be staged"
        else:
            self.git_fn(path, "add", "-A")  # no declared list — last resort
        rc, out = self.git_fn(path, "commit", "-m", message)
        if rc != 0:
            return False, out  # nothing to commit / commit failed
        rc, out = self.git_fn(path, "push", "-u", "origin", branch)
        return rc == 0, out

    def _run_gate_with_rework(self, mr_id: str, path: str, work_item: str,
                              context: str):
        """Code → gate, reworking on failure up to rework_max. Returns
        (green evidence dict | None, written_files) — the file list scopes the commit."""
        self.store.update(mr_id, state="gating")
        last = ""
        written: list = []
        for attempt in range(self.rework_max + 1):
            ctx = context if attempt == 0 else f"{context}\n\nPREVIOUS ATTEMPT FAILED:\n{last}"
            result = self.code_fn(path, ctx)
            if isinstance(result, dict):
                written = result.get("written_files", written) or written
            gate = self.gate_fn(path)
            self.store.update(mr_id, evidence=gate.get("evidence", {}))
            if gate.get("green"):
                return gate, written
            last = gate.get("output", "")[:4000]
            logger.info("MR %s gate red (attempt %d/%d)", mr_id, attempt + 1, self.rework_max + 1)
        return None, written

    # -- the lifecycle ------------------------------------------------------
    def run(self, mr_id: str) -> dict:
        row = self.store.get(mr_id)
        if not row:
            return {"mr_id": mr_id, "state": "failed", "error": "unknown MR"}
        work_item = row["work_item"]
        branch = row["branch"]

        if not self.github.available():
            return self._fail(mr_id, "GitHub CLI not authenticated (gh auth status failed) — "
                                     "cannot open a PR")

        # 1. Isolated workspace (created BEFORE coding; it IS the write-root).
        try:
            path = self.worktree.create(mr_id)
        except Exception as e:  # noqa: BLE001
            return self._fail(mr_id, f"could not create worktree: {e}")

        # 2+3. Code + evidence gate, reworking until green.
        self.store.update(mr_id, state="coding")
        gate, written = self._run_gate_with_rework(mr_id, path, work_item, context=work_item)
        if gate is None:
            return self._fail(mr_id, f"evidence gate never went green after "
                                     f"{self.rework_max + 1} attempts")

        # 4. Commit + open the regulatory PR (only now that it is green).
        ok, out = self._commit_and_push(path, branch, self.package.build_pr_title(work_item),
                                        files=written)
        if not ok:
            return self._fail(mr_id, f"commit/push failed: {out[:300]}")
        body = self.package.build_pr_body(
            work_item=work_item, mr_id=mr_id,
            diff_stat=self.git_fn(path, "diff", "--stat", f"{self.base}...HEAD")[1],
            evidence=gate.get("evidence", {}),
            change_summary=gate.get("evidence", {}).get("summary", work_item),
        )
        pr = self.github.create(branch, self.package.build_pr_title(work_item), body, base=self.base)
        if not pr.get("ok"):
            return self._fail(mr_id, f"could not open PR: {pr.get('error')}")
        self.store.update(mr_id, state="review", pr_number=pr["number"], pr_url=pr.get("url", ""))

        # 5. Watch for the human's decision.
        return self._watch(mr_id, work_item, branch, path, pr["number"])

    def _watch(self, mr_id, work_item, branch, path, number) -> dict:
        for _ in range(self.poll_max):
            st = self.github.state(number)
            if st.get("state") == "MERGED":
                # The human merged in GitHub directly — back-fill the signed record.
                sha = st.get("merged_sha", "")
                self.record_merge(self.operator, work_item, mr_id, sha)
                self.store.update(mr_id, state="merged", merged_sha=sha)
                return {"mr_id": mr_id, "state": "merged", "merged_sha": sha}

            decision = st.get("review_decision", "")
            if decision == "APPROVED":
                self.store.update(mr_id, state="approved")
                m = self.github.merge(number, method="squash")
                if not m.get("ok"):
                    return self._fail(mr_id, f"merge failed after approval: {m.get('error')}")
                sha = m.get("sha", "")
                self.record_merge(self.operator, work_item, mr_id, sha)
                self.store.update(mr_id, state="merged", merged_sha=sha)
                return {"mr_id": mr_id, "state": "merged", "merged_sha": sha}

            # Any NEW human input — a plain comment or a changes-requested review body —
            # triggers a rework. Handled idempotently via the watch store: each comment
            # is acted on exactly once, even across a daemon restart, and SAGE's own
            # [Sage]-tagged comments are skipped so the watcher never reacts to itself.
            notes, keys = self._collect_new_human_input(mr_id, number, decision)
            if notes:
                self.store.update(mr_id, state="reworking")
                gate, written = self._run_gate_with_rework(
                    mr_id, path, work_item,
                    context=f"{work_item}\n\nHUMAN REQUESTED CHANGES:\n{notes}")
                if gate is None:
                    return self._fail(mr_id, "rework could not pass the evidence gate")
                ok, out = self._commit_and_push(path, branch, f"rework: address review on {mr_id}",
                                                files=written)
                if not ok:
                    return self._fail(mr_id, f"rework push failed: {out[:300]}")
                # Mark handled only AFTER a successful push, so a crash mid-rework
                # re-does that one rework rather than dropping the comment.
                if self.watch is not None:
                    for key in keys:
                        self.watch.mark_handled(mr_id, key)
                    self.watch.bump_rework(mr_id)
                    self.watch.set_decision(mr_id, decision)
                self.github.comment(number, "Reworked and pushed: addressed the review "
                                            "comments; evidence gate is green again.",
                                    role="dev")
                self.store.update(mr_id, state="review")

            self.sleep_fn(self.poll_interval)

        # Poll window elapsed with the PR still open awaiting the human. Not a failure —
        # leave it in review; status()/a re-run resumes the watch.
        self.store.update(mr_id, state="review")
        return {"mr_id": mr_id, "state": "review", "pending": True, "pr_number": number}

    def _collect_new_human_input(self, mr_id, number, decision) -> tuple:
        """Gather unhandled human input on the PR and return ``(notes, keys)``.

        ``notes`` is the concatenated bodies to feed the coder; ``keys`` are the
        stable ids to mark handled *after* a successful rework. Plain conversation
        comments plus (on CHANGES_REQUESTED) the review body are included; SAGE's
        own ``[Sage]``-tagged comments and anything already handled are excluded.

        Without a watch store (no persistence), falls back to the original
        behaviour: react only to CHANGES_REQUESTED, once per poll, no dedup.
        """
        if self.watch is None:
            if decision != "CHANGES_REQUESTED":
                return "", []
            comments = self.github.get_comments(number)
            notes = "\n".join(f"- {c.get('body', '')}" for c in comments)[:4000]
            return notes, []

        fresh: list = []  # (handle_key, body)
        for c in self.github.get_comments(number):
            body = (c.get("body") or "").strip()
            if not body or body.startswith(SAGE_COMMENT_TAG):
                continue  # empty, or SAGE's own comment — never react to self
            key = c.get("id") or c.get("created") or body[:60]
            if not self.watch.handled(mr_id, key):
                fresh.append((key, body))

        if decision == "CHANGES_REQUESTED":
            for r in self.github.get_reviews(number):
                if r.get("state") != "CHANGES_REQUESTED":
                    continue
                body = (r.get("body") or "").strip()
                if not body or body.startswith(SAGE_COMMENT_TAG):
                    continue
                key = f"review:{r.get('author', '')}:{body[:60]}"
                if not self.watch.handled(mr_id, key):
                    fresh.append((key, body))

        if not fresh:
            return "", []
        notes = "\n".join(f"- {b}" for _, b in fresh)[:4000]
        return notes, [k for k, _ in fresh]


def build_default_runner(solution_dir: str, operator: str = "operator"):
    """Wire the real dependencies for a solution. Kept out of __init__ so the state machine
    stays test-only-injectable and this is the single place production plumbing lives."""
    from pathlib import Path

    from src.core.github_pr import GitHubPR
    from src.core.mr_store import MRStore
    from src.core.watch_store import WatchStore
    from src.core import mr_package
    from src.core.worktree_manager import WorktreeManager
    from src.memory.audit_logger import AuditLogger
    from src.memory.audit_sign import sign_event

    sage_dir = Path(solution_dir) / ".sage"
    sage_dir.mkdir(parents=True, exist_ok=True)
    store = MRStore(str(sage_dir / "mr.db"))
    watch = WatchStore(str(sage_dir / "watch.db"))
    audit = AuditLogger(db_path=str(sage_dir / "audit_log.db"))
    repo_root = str(Path(__file__).resolve().parent.parent.parent)

    def code_fn(path, context):
        # Point the CodingAgent's write-root at the worktree so the branch holds the change
        # (root injection added to coder.py for exactly this).
        from src.agents.coder import CodingAgent
        agent = CodingAgent(root=path)
        result = agent.implement_step({"description": context})
        return {"summary": result.get("summary", context),
                "written_files": result.get("written_files", [])}

    def gate_fn(path):
        # The gate runs IN THE WORKTREE (so it validates the branch's code) using the MAIN
        # checkout's .venv (a worktree has no .venv / node_modules / cargo target of its own).
        # verify_system.py --fast is wrong here — it needs node/cargo the worktree lacks — so
        # the gate is the pytest suite: does this change break the framework?
        import os as _os
        venv_py = str(Path(repo_root) / ".venv" / "Scripts" / "python.exe")
        if not _os.path.exists(venv_py):
            venv_py = str(Path(repo_root) / ".venv" / "bin" / "python")

        # There must actually be a change to gate — never open an empty PR.
        _, dirty = _default_git(path, "status", "--porcelain")
        if not dirty.strip():
            return {"green": False, "output": "coder produced no file changes",
                    "evidence": {"gate_green": False, "reason": "no changes"}}
        try:
            p = subprocess.run(
                [venv_py, "-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider",
                 "--ignore=tests/system/test_browser_e2e.py"],
                cwd=path, capture_output=True, text=True, timeout=1800, errors="replace")
            green = p.returncode == 0
            out = (p.stdout or "") + (p.stderr or "")
            last = [l for l in (p.stdout or "").splitlines() if l.strip()]
            return {"green": green, "output": out,
                    "evidence": {"tests": last[-1] if last else "", "gate_green": green,
                                 "summary": "framework test suite"}}
        except Exception as e:  # noqa: BLE001
            return {"green": False, "output": f"gate error: {e}",
                    "evidence": {"gate_green": False}}

    def record_merge(approver, work_item, mr_id, sha):
        # Signed, chained audit record of the reviewed merge — the compliance event.
        audit.log_event(actor="operator", action_type="MR_MERGED",
                        input_context=f"work_item={work_item} mr={mr_id}",
                        output_content=f"merged {sha}", approved_by=approver)
        import sqlite3
        conn = sqlite3.connect(audit.db_path)
        eid = conn.execute("SELECT id FROM compliance_audit_log "
                           "ORDER BY timestamp DESC, id DESC LIMIT 1").fetchone()[0]
        conn.close()
        return sign_event(audit.db_path, eid)

    return MRRunner(store=store, github=GitHubPR(cwd=repo_root), worktree=WorktreeManager(),
                    code_fn=code_fn, gate_fn=gate_fn, package=mr_package,
                    record_merge=record_merge, operator=operator, watch=watch), store


def resume_open_mrs(runner) -> list:
    """Resume the watch on every open MR — the daemon's restart hook.

    Lists MRs left in ``review`` / ``reworking`` (a prior watcher stopped, the
    process exited, the laptop slept) and re-enters the watch for each whose
    worktree is still available locally. Idempotent comment handling (the watch
    store) guarantees nothing already actioned is reworked again; the single-writer
    lease guarantees a co-running desktop watcher and this daemon never double-act.

    Returns a list of per-MR result dicts. Recreating a worktree from the remote
    proposal branch on a fresh machine is a Phase-2 daemon concern; here we resume
    the MRs this host can still act on and skip (report) the rest.
    """
    results = []
    open_mrs = runner.store.list("review") + runner.store.list("reworking")
    for row in open_mrs:
        mr_id = row["id"]
        number = row.get("pr_number")
        if not number:
            continue  # never reached review — nothing to watch
        if runner.watch is not None and not runner.watch.acquire(mr_id, runner.operator):
            results.append({"mr_id": mr_id, "state": "skipped",
                            "reason": "watch lease held by another process"})
            continue
        try:
            path = runner.worktree.get_path(mr_id)
        except Exception:  # noqa: BLE001
            path = None
        if not path:
            results.append({"mr_id": mr_id, "state": "skipped",
                            "reason": "worktree not available on this host"})
            continue
        try:
            results.append(runner._watch(mr_id, row["work_item"], row["branch"], path, number))
        finally:
            if runner.watch is not None:
                runner.watch.release(mr_id, runner.operator)
    return results
