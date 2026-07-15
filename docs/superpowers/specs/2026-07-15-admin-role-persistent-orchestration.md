# Spec — The Admin Role: Persistent, Cross-Session Orchestration

**Status:** Draft for human review (propose → decide, per Law 1)
**Date:** 2026-07-15
**Author:** SAGE agents
**Related:** [[2026-07-14-merge-gate-governance-design]] (the MR gate this admin role drives)

---

## 1. Why this exists

Today SAGE can open a regulatory MR, run the evidence gate, react to a human's
"request changes", rework, and merge on approval. But the machinery that does
this — the `_watch` loop in `mr_runner.py` — **only lives inside a running
process**. When the operator logs off, closes the desktop app, or the session
ends, the watcher dies. Open MRs stop being watched, in-flight work is dropped,
and a comment left on a PR sits untouched until someone manually relaunches a
runner.

The operator asked for the opposite: **"anything that we work should be between
the sessions — not lost if we log off."** The base interaction model chosen is
*desktop-continuous* (the app watches while open), but it must be extended so
that:

1. **No state is lost across sessions.** Work items, MRs, watcher cursors,
   rework counters, and the audit trail all survive logoff, crash, and reboot.
2. **Work continues without a human present** — a few times a day at minimum,
   even when the desktop app is closed (headless/scheduled), and live while it
   is open.
3. **The human's control surface is richer** — an actual "admin" view of every
   MR, its state, what SAGE did, and the single approval touchpoint.

This spec defines the **Admin Role**: the durable orchestration layer plus the
human control surface that together make the merge-gate loop dependable.

## 2. The Admin Role has two halves

The word "admin" covers two distinct actors. Keeping them separate is essential
(it is the same agents-propose / humans-decide split as the rest of SAGE).

| | **Admin Daemon** (the orchestrator) | **Human Admin** (the operator) |
|---|---|---|
| Who | An always-on **deterministic Python script** | The person (e.g. Harish) |
| Decides | Nothing that lands on `main` | Approves/returns every MR |
| Does | Runs the MR lifecycle, reacts to comments, reworks, keeps state durable, escalates | Reviews, approves, comments, sets cadence, intervenes |
| Runs | 24/7 on a Pi / spare laptop (systemd/Task Scheduler); optionally live in the desktop too | On their own schedule |
| Cost | **$0 while idle** — spends tokens only when it calls the coder to rework | — |

**Rule (unchanged, Law 1a):** the Admin Daemon never approves an MR. Only an
approved MR merges to `main`, and the merge writes a signed audit record. The
daemon's job is to make sure that by the time the human looks, the MR is green,
well-described, and waiting — and to act on the human's comments without
supervision *up to* the approval line.

## 2.1 The daemon is a SCRIPT, not an agent (token economics)

The always-on part must be a **deterministic script**, not an LLM agent — an
agent "thinking" 24/7 would burn tokens for nothing. The design rule:

> **Separate the control loop (deterministic, free) from the intelligence
> (LLM, paid, invoked on demand).** The LLM is a subroutine the daemon calls
> only when there is a concrete code change to make. It is never used to *decide
> whether* to act — that is a string comparison, not a prompt.

| Deterministic — the daemon ($0, idle-safe) | LLM-invoked (the ONLY token spend) |
|---|---|
| Poll GitHub for open MRs (`gh` CLI) | — |
| Detect new human comments (filter the `[Sage]` tag), approvals, merges | — |
| On approval → squash-merge + signed audit record | — |
| Run the evidence gate (pytest — compute, no tokens) | — |
| git branch/commit/push; read/write `watch.db`/`mr.db`; heartbeat; escalation; budget caps | — |
| **When a comment needs a code change** → | **call the coder once** to produce the rework |

Consequence: **token spend is proportional to the number of review comments that
need rework, not to uptime.** The daemon idles at zero cost and spends only when
the human actually engages. A **hard daily token/rework budget** (§4.9) is
enforced deterministically so even a bad loop cannot overspend.

## 3. Hard requirement: durability across sessions

Everything the Admin Agent knows must be reconstructable from disk. On any
restart it reloads open work and resumes exactly where it left off.

### 3.1 Durable stores (all under the solution's `.sage/`)

| Store | File | Holds | Exists? |
|---|---|---|---|
| MR store | `.sage/mr.db` | Every MR: work item, branch, state, PR number, evidence, error | ✅ `mr_store.py` |
| Audit log | `.sage/audit_log.db` | Signed, hash-chained compliance events | ✅ `audit_logger.py` + `audit_sign.py` |
| Work queue | `.sage/queue.db` | Queued / in-progress / done work items | ✅ partial (`queue_manager.py`) |
| **Watcher cursor** | `.sage/watch.db` | Per-MR: last-seen comment id, last review decision, next-poll time, rework count, lease/lock | ❌ **new** |
| **Watcher lease** | `.sage/watch.db` | Which process currently owns the watch (prevents two watchers double-acting) | ❌ **new** |

The only genuinely new persistence is the **watcher cursor + lease**. Every other
store already exists — the gap is that nothing durably records *"MR #13, I have
already seen comment `IC_kw…`, next check at T, 0 reworks done"*, so a restarted
watcher can't tell a new comment from an old one.

### 3.2 Resumability contract

- **Idempotent poll.** Reacting to a comment is keyed on `(mr_id, comment_id)`;
  a comment already in the cursor is never reworked twice. This is what makes
  "restart and resume" safe.
- **Crash-safe writes.** Cursor advances only *after* a rework is pushed and the
  reply is posted — so a crash mid-rework re-does that one rework, never skips it.
- **Single-writer lease.** A watcher takes a short-lived lease (row in
  `watch.db`) before acting on an MR, so the desktop watcher and a scheduled
  headless run can't both rework the same MR. Lease expires → another watcher
  resumes.
- **Reboot recovery.** On startup the Admin Agent lists every MR in state
  `review` / `reworking`, reloads its cursor, and continues.

## 4. What the Admin Daemon must do (capabilities)

1. **Watch open MRs.** For each MR in `review`, poll GitHub for (a) new human
   comments, (b) review decisions, (c) a direct merge. Filter out SAGE's own
   comments using the `[Sage]` tag (already implemented) so it never reacts to
   itself.
2. **React to plain comments — not only "Request changes."** The operator's
   natural action is a plain comment (observed on PR #13). The watcher must treat
   a new, un-tagged human comment as actionable, read its text, and route it to
   rework. (Today only a formal `CHANGES_REQUESTED` review triggers rework — a
   known gap.)
3. **Rework within the gate.** Run coder → evidence gate → push, up to
   `rework_max`, exactly as now — but on the durable branch, with the cursor
   advanced on success.
4. **Reply, tagged and traceable.** Post `[Sage][<role>] : …` summarising what it
   did (already implemented for the rework reply).
5. **Propose new work.** From the gap/feedback backlog, draft new MRs (system
   agent) — still human-approved before merge.
6. **Escalate, don't spin.** When the gate can't go green after `rework_max`, or
   a comment is ambiguous, mark the MR `needs_human` and notify — never loop
   silently.
7. **Keep the human informed.** Emit a durable, readable status per MR (what
   changed, gate result, what's blocked) the desktop and headless runs both write.
8. **Audit everything.** Every action → signed event. This is both compliance
   and the training signal.
9. **Enforce a token/rework budget (§4.9).** A hard, deterministic daily ceiling
   on coder invocations / tokens. When hit, the daemon stops calling the LLM and
   marks affected MRs `budget_paused` until the human lifts it — so a runaway
   loop can never overspend. This is the structural answer to "it can't keep
   consuming tokens."
10. **Heartbeat.** Write "last alive at T / next poll at T" to durable state so
    the human (and the desktop) can see the daemon is running and when it last
    checked — a silent daemon is indistinguishable from a dead one otherwise.

## 5. What the Human Admin needs (control surface)

A desktop **Admin / Merge-Gate** page (extends the existing Workflows/MR views):

- **MR board** — every MR with live state (`coding → gating → review →
  reworking → merged | needs_human | failed`), PR link, last SAGE action, and
  what (if anything) it's waiting on from the human.
- **One-click touchpoints** — Approve, Request changes (with comment), Comment.
  Approve is the only path to `main`.
- **Watcher controls** — Start / Pause / Stop; set cadence (continuous while open;
  every N hours headless); see "last checked / next check".
- **Audit view** — the signed event chain for an MR, exportable for a dossier.
- **Escalations inbox** — MRs marked `needs_human` (gate stuck, ambiguous
  comment), so the scarce human time goes only where it's needed.

Everything on this surface reads from the durable stores, so it shows the true
state after any restart.

## 6. Deployment — daemon on an external Pi / laptop, gate on the backend

The daemon is a small Python process (git + `gh` CLI + the SAGE repo + a venv +
one credential for the coder). It is meant to live on a cheap always-on box — a
Raspberry Pi or a spare laptop — next to the backend server, and run forever.

**Where each piece runs**

| Piece | Host | Why |
|---|---|---|
| **Admin daemon** (poll / state / git / merge) | Pi or spare laptop, 24/7 | Trivial load, deterministic, near-zero power, $0 tokens while idle |
| **Coder invocation** (the one LLM call) | Pi calls the Claude API on demand | A Pi is too weak for a good local coding model; the API is cheap because it fires only on rework |
| **Evidence gate** (full pytest suite) | The **backend server** (the more powerful box) | ~2485 tests, minutes of compute — too heavy for a Pi; the daemon triggers it and waits on the result |
| **Durable state** (`watch.db`, `mr.db`, `audit_log.db`) | The daemon host's disk | Survives reboot; auto-restart resumes every open MR |

**How it stays alive across sessions**

- Runs as a **systemd service** (Linux Pi) or a **Windows service / Task
  Scheduler** entry (laptop): auto-start on boot, auto-restart on crash.
- Between polls the process **sleeps** — near-zero CPU, zero tokens.
- On restart it reloads open MRs + cursors from `watch.db` and continues exactly
  where it left off.

**Optional live mode:** while the desktop app is open it may run the same watcher
in-process for instant reaction; the **single-writer lease** stops it and the Pi
daemon from double-acting.

**Security:** the daemon host holds a GitHub token (it can push and, on your
approval, merge to `main`) and the coder API key. Treat it as a secrets-bearing
box — least-privilege token, standard secret storage.

> Setting up the systemd / Task Scheduler service and placing credentials on the
> Pi is a one-time standing configuration the operator does explicitly.

## 7. Compliance boundaries (unchanged)

- **Only an approved MR merges to `main`** (Law 1a). The Admin Agent never
  approves.
- **Every merge is signed** (HMAC hash-chain) and traceable to the approver.
- **reflect-\* isolation** holds: nothing referencing the proprietary reflect
  repos may enter the SAGE tree, and those repos stay read-only.
- **No silent truncation.** If the watcher bounds its work (max reworks, poll
  window), it records that in the audit + status — never presents partial work
  as complete.

## 8. What exists vs. what's new

| Piece | State |
|---|---|
| MR state machine, evidence gate, signed merge | ✅ built (`mr_runner.py`, `audit_sign.py`) |
| `[Sage][role]` comment tagging (self-vs-human) | ✅ built today |
| React to `CHANGES_REQUESTED` review | ✅ built |
| **React to a plain human comment** | ❌ new (small change in `_watch`) |
| **Read the review-body text, not just conversation comments** | ❌ new (fold `get_reviews` into notes) |
| **Watcher cursor + lease (`watch.db`)** | ❌ new — the core durability piece |
| **Headless scheduled runner + resume-open-MRs** | ❌ new (reuse `build_default_runner`) |
| **Single-writer lease across desktop + headless** | ❌ new |
| **Admin/Merge-Gate desktop page + escalations inbox** | ❌ new (UI) |
| Durable status per MR | ⚠️ partial (state in `mr.db`; add human-readable status) |

## 9. Phased implementation

**Phase 1 — Never lose a comment (durability core).**
`watch.db` cursor + lease; make `_watch` react to plain comments and read review
bodies; advance the cursor idempotently; resume all open MRs on startup.
*Outcome: comment on any open MR → it is worked exactly once, even across logoff.*

**Phase 2 — Runs without the human present.**
Headless entrypoint that opens every open MR's watch and exits; Task Scheduler
setup (operator-approved); lease coordination with the desktop watcher.
*Outcome: the "few times a day" guarantee with the app closed.*

**Phase 3 — Admin control surface.**
Desktop Admin/Merge-Gate page: MR board, approve/request-changes/comment,
watcher start/pause/cadence, audit view, escalations inbox.
*Outcome: the human sees and controls everything from one place.*

**Phase 4 — Proactive admin.**
System agent proposes new MRs from the gap/feedback backlog; escalation policy;
notifications.
*Outcome: SAGE surfaces work, not just reacts.*

## 10. Open decisions for the human

1. **Headless cadence** — every 2 h? 3 h? only on desktop open + one nightly?
2. **Comment trigger scope** — react to *any* new human comment, or only ones
   that @-mention SAGE / carry a keyword? (Broad = responsive; narrow = the
   human can discuss on the PR without triggering reworks.)
3. **Escalation channel** — in-app inbox only, or also email/desktop notification?
4. **Phase order** — is Phase 1 (never-lose-a-comment) the right first slice, or
   is the Admin page (Phase 3) more valuable to you first?
