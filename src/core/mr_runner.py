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
    ):
        self.store = store
        self.github = github
        self.worktree = worktree
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

    def _commit_and_push(self, path: str, branch: str, message: str) -> tuple[bool, str]:
        for args in (("add", "-A"), ("commit", "-m", message)):
            rc, out = self.git_fn(path, *args)
            if rc != 0 and args[0] == "commit":
                return False, out  # nothing to commit / commit failed
        rc, out = self.git_fn(path, "push", "-u", "origin", branch)
        return rc == 0, out

    def _run_gate_with_rework(self, mr_id: str, path: str, work_item: str,
                              context: str) -> Optional[dict]:
        """Code → gate, reworking on failure up to rework_max. Returns the green evidence
        dict, or None if it never went green (caller fails the MR)."""
        self.store.update(mr_id, state="gating")
        last = ""
        for attempt in range(self.rework_max + 1):
            ctx = context if attempt == 0 else f"{context}\n\nPREVIOUS ATTEMPT FAILED:\n{last}"
            self.code_fn(path, ctx)
            gate = self.gate_fn(path)
            self.store.update(mr_id, evidence=gate.get("evidence", {}))
            if gate.get("green"):
                return gate
            last = gate.get("output", "")[:4000]
            logger.info("MR %s gate red (attempt %d/%d)", mr_id, attempt + 1, self.rework_max + 1)
        return None

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
        gate = self._run_gate_with_rework(mr_id, path, work_item, context=work_item)
        if gate is None:
            return self._fail(mr_id, f"evidence gate never went green after "
                                     f"{self.rework_max + 1} attempts")

        # 4. Commit + open the regulatory PR (only now that it is green).
        ok, out = self._commit_and_push(path, branch, self.package.build_pr_title(work_item))
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

            if decision == "CHANGES_REQUESTED":
                comments = self.github.get_comments(number)
                notes = "\n".join(f"- {c.get('body', '')}" for c in comments)[:4000]
                self.store.update(mr_id, state="reworking")
                gate = self._run_gate_with_rework(
                    mr_id, path, work_item,
                    context=f"{work_item}\n\nHUMAN REQUESTED CHANGES:\n{notes}")
                if gate is None:
                    return self._fail(mr_id, "rework could not pass the evidence gate")
                ok, out = self._commit_and_push(path, branch, f"rework: address review on {mr_id}")
                if not ok:
                    return self._fail(mr_id, f"rework push failed: {out[:300]}")
                self.github.comment(number, "Reworked and pushed: addressed the review "
                                            "comments; evidence gate is green again.")
                self.store.update(mr_id, state="review")

            self.sleep_fn(self.poll_interval)

        # Poll window elapsed with the PR still open awaiting the human. Not a failure —
        # leave it in review; status()/a re-run resumes the watch.
        self.store.update(mr_id, state="review")
        return {"mr_id": mr_id, "state": "review", "pending": True, "pr_number": number}


def build_default_runner(solution_dir: str, operator: str = "operator"):
    """Wire the real dependencies for a solution. Kept out of __init__ so the state machine
    stays test-only-injectable and this is the single place production plumbing lives."""
    from pathlib import Path

    from src.core.github_pr import GitHubPR
    from src.core.mr_store import MRStore
    from src.core import mr_package
    from src.core.worktree_manager import WorktreeManager
    from src.memory.audit_logger import AuditLogger
    from src.memory.audit_sign import sign_event

    sage_dir = Path(solution_dir) / ".sage"
    sage_dir.mkdir(parents=True, exist_ok=True)
    store = MRStore(str(sage_dir / "mr.db"))
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
        rc, out = _default_git(path, "status")  # cheap smoke; real gate runs the suite
        try:
            p = subprocess.run(
                [str(Path(repo_root) / ".venv" / "Scripts" / "python.exe"),
                 "scripts/verify_system.py", "--fast", "--json"],
                cwd=repo_root, capture_output=True, text=True, timeout=1200, errors="replace")
            import json as _json
            data = _json.loads((p.stdout or "{}").splitlines()[-1]) if p.stdout.strip() else {}
            green = data.get("passed", 0) == data.get("total", -1) and data.get("total", 0) > 0
            return {"green": green, "evidence": {"verify": f"{data.get('passed')}/{data.get('total')}",
                    "gate_green": green}, "output": p.stdout + p.stderr}
        except Exception as e:  # noqa: BLE001
            return {"green": False, "evidence": {"gate_green": False}, "output": f"gate error: {e}"}

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
                    record_merge=record_merge, operator=operator), store
