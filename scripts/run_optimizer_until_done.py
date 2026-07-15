#!/usr/bin/env python3
"""
Drive the SAGE self-improvement optimizer loop to completion.
=============================================================
Wraps `scripts/self_improve.py --resume` in an OUTER loop so a full run survives:

  * provider usage-limit pauses — the runner already waits + retries *per task*
    (--limit-wait-min / --limit-max-retries); this driver adds resilience for
  * process-level failures — a crash, kill, machine sleep, or limit-exhaustion
    just restarts the runner, which resumes from disk (converged proposals are
    skipped, so nothing already done is redone).

It STOPS when every task has converged, or after MAX_NO_PROGRESS consecutive
attempts add nothing new — so a genuine (non-limit) bug cannot spin forever.

The output directory is PINNED to the existing self-improvement folder, so a
date rollover mid-run cannot fork the work into a fresh, empty directory and
re-run everything from scratch.

Usage:
    python scripts/run_optimizer_until_done.py
    python scripts/run_optimizer_until_done.py --out-dir docs/proposals/20260628-self-improvement
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "self_improve.py"

# Substrings that indicate a TRANSIENT provider outage / overload (Opus
# "temporarily unavailable" surfaces from the CLI as rc=1 'Unknown error',
# often preceded by empty/slow returns). When an attempt converges nothing AND
# is dominated by these, it is NOT a stuck task — wait and retry, don't give up.
# Trust / config errors deliberately do NOT appear here (a real 'not been
# trusted' / stale-tool failure must still trip the no-progress guard).
OUTAGE_MARKERS = (
    "unknown error",
    "temporarily unavailable",
    "overloaded",
    "service unavailable",
    "bad gateway",
    "gateway timeout",
    "529",
    "503",
    "502",
    "empty output",
    "timed out",
)

# Load self_improve as a module so we reuse its task list + slug + done-check.
_spec = importlib.util.spec_from_file_location("self_improve", SCRIPT)
si = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(si)


def detect_out_dir() -> Path:
    """Pick the existing *-self-improvement dir with the most proposals already in
    it (so we CONTINUE prior work); fall back to today's dir if none exist."""
    base = ROOT / "docs" / "proposals"
    best, best_n = None, -1
    for d in sorted(base.glob("*-self-improvement")):
        n = len(list(d.glob("task-*.md")))
        if n > best_n:
            best, best_n = d, n
    if best is not None and best_n > 0:
        return best
    return base / f"{datetime.date.today().strftime('%Y%m%d')}-self-improvement"


def convergence(out_dir: Path, threshold: float, only=None):
    """Return (done_ids, todo_ids) by reading the proposal files on disk.

    If `only` (a set of task ids) is given, restrict the accounting to those
    tasks — so a scoped overnight run isn't blocked forever by hard tasks left
    out of scope.
    """
    done, todo = [], []
    for t in si.TASKS:
        if only is not None and t["id"] not in only:
            continue
        f = out_dir / (si.slugify(t["title"], t["id"]) + ".md")
        (done if (f.exists() and si.proposal_is_done(f, threshold)) else todo).append(
            t["id"]
        )
    return done, todo


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run the SAGE optimizer loop until all tasks converge."
    )
    ap.add_argument(
        "--out-dir",
        default="",
        help="Proposal dir to continue (auto-detected if omitted)",
    )
    ap.add_argument(
        "--only-ids",
        default="",
        help="Comma-separated task ids to run (default: all remaining)",
    )
    ap.add_argument("--threshold", type=float, default=8.0)
    ap.add_argument("--max-iterations", type=int, default=3)
    ap.add_argument("--limit-wait-min", type=float, default=30)
    ap.add_argument("--limit-max-retries", type=int, default=12)
    ap.add_argument(
        "--between-min", type=float, default=2, help="Pause between outer attempts"
    )
    ap.add_argument(
        "--max-no-progress",
        type=int,
        default=2,
        help="Stop after this many consecutive attempts that converge nothing new",
    )
    ap.add_argument("--max-attempts", type=int, default=50)
    ap.add_argument(
        "--outage-wait-min",
        type=float,
        default=15,
        help="Minutes to wait when a transient provider outage (mass 'Unknown error') is detected",
    )
    ap.add_argument(
        "--max-outage-waits",
        type=int,
        default=24,
        help="Max outage wait-and-retry cycles before giving up (default 24 ~ 6h of dips)",
    )
    args = ap.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else detect_out_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    only = {int(x) for x in args.only_ids.split(",") if x.strip()} or None
    scope = len(only) if only else len(si.TASKS)

    print(f"[driver] Output pinned to: {out_dir}", flush=True)
    if only:
        print(f"[driver] Scoped to task ids: {sorted(only)}", flush=True)
    done, todo = convergence(out_dir, args.threshold, only)
    print(
        f"[driver] Start: {len(done)}/{scope} converged, {len(todo)} remaining -> {todo}",
        flush=True,
    )

    no_progress = 0
    outage_waits = 0
    attempt = 0
    while todo and attempt < args.max_attempts and no_progress < args.max_no_progress:
        attempt += 1
        print(
            f"\n[driver] === attempt {attempt} | {len(todo)} remaining: {todo} ===",
            flush=True,
        )
        cmd = [
            sys.executable,
            "-u",
            str(SCRIPT),
            "--resume",
            "--out-dir",
            str(out_dir),
            "--threshold",
            str(args.threshold),
            "--max-iterations",
            str(args.max_iterations),
            "--limit-wait-min",
            str(args.limit_wait_min),
            "--limit-max-retries",
            str(args.limit_max_retries),
        ]
        if only:
            cmd += ["--task-ids", ",".join(str(i) for i in sorted(only))]
        # Capture output so we can tell a transient provider outage apart from a
        # genuinely stuck task; still echo it so the driver log keeps everything.
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        print(out, flush=True)
        print(f"[driver] attempt {attempt} exited rc={proc.returncode}", flush=True)

        new_done, todo = convergence(out_dir, args.threshold, only)
        gained = len(new_done) - len(done)
        done = new_done

        if gained > 0:
            no_progress = 0
            outage_waits = 0  # real progress clears the outage counter
            print(
                f"[driver] +{gained} converged this attempt -> {len(done)}/{scope} total",
                flush=True,
            )
            continue

        # Nothing converged. Was it a transient provider outage (wait it out) or
        # tasks that actually ran but scored low (genuine no-progress -> stop)?
        outage_hits = sum(out.lower().count(m) for m in OUTAGE_MARKERS)
        if outage_hits >= 3 and outage_waits < args.max_outage_waits:
            outage_waits += 1
            print(
                f"[driver] transient provider outage detected ({outage_hits} marker hits, "
                f"e.g. 'Unknown error'/overloaded) — waiting {args.outage_wait_min:g} min then "
                f"retrying (outage wait {outage_waits}/{args.max_outage_waits}; NOT a no-progress strike)",
                flush=True,
            )
            time.sleep(args.outage_wait_min * 60)
            continue

        no_progress += 1
        print(
            f"[driver] no new convergence ({no_progress}/{args.max_no_progress}); rc={proc.returncode}",
            flush=True,
        )
        if todo and no_progress < args.max_no_progress:
            print(
                f"[driver] pausing {args.between_min:g} min before retry...", flush=True
            )
            time.sleep(args.between_min * 60)

    if not todo:
        print(
            f"\n[driver] DONE — all {len(si.TASKS)} tasks converged. Proposals in {out_dir}",
            flush=True,
        )
        return 0
    if no_progress >= args.max_no_progress:
        print(
            f"\n[driver] STOPPED — {len(todo)} task(s) made no progress in "
            f"{args.max_no_progress} attempts: {todo}",
            flush=True,
        )
        print(
            "[driver] This looks like a real error (NOT a usage limit, which the runner waits out). "
            "Inspect the last attempt's output above before re-running.",
            flush=True,
        )
        return 2
    print(
        f"\n[driver] STOPPED — hit max attempts ({args.max_attempts}). Remaining: {todo}",
        flush=True,
    )
    return 3


if __name__ == "__main__":
    sys.exit(main())
