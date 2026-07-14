# SAGE Merge-Gate Governance — Design

**Date:** 2026-07-14
**Status:** design, pending approval
**Decided with the operator (product owner):** the human approval gate moves from
per-code-change to **per-MR**; agents self-manage the branch; human time is the scarce
resource and is spent only at the top (approve / high-level comment on a
regulatory-complete PR). First delivery is a **vertical slice that pushes to a real GitHub
PR**, dogfooded on SAGE's own repo.

---

## 1. The model (full target, for context)

```
Gap analysis + human feedback + data
        │  system agent prioritizes — DIRECTION is feedback-driven, not agent-chosen
        ▼
  Work backlog ──auto-start top items (concurrency-capped)──▶ Agent branch (isolated worktree)
                                                                 code → EVIDENCE GATE
                                                                 (tests + make verify + feature test)
                                                                 iterate until GREEN — no human
                                                                        ▼
                                                          Regulatory MR package
                                                          (high-level summary FIRST, then dossier)
                                                                        │
                                    HUMAN (high-level only, minutes) ───┤
                                    approve ─▶ signed immutable audit ─▶ merge to main
                                    request changes (high-level) ─▶ agents rework ─▶ back to top
```

**This replaces the broken per-`code_diff` pipeline** (B4/B5/B6 in `docs/GAPS_DEEP_2026-07-14.md`):
the branch is the agent workspace (agents write into a real repo), the MR gate is the
compliance gate (per-change approval is gone), and merge produces the signature that fixes
the unsigned-audit gap. **SOUL.md Law 1 and CLAUDE.md are updated** to make the MR the
gated unit (`code_diff` is no longer a standalone human gate; it is an internal step on the
branch).

Five subsystems: (A) agent workspace + evidence gate, (B) regulatory package assembler,
(C) merge gate + signed audit + GitHub-PR adapter, (D) feedback-driven prioritizer,
(E) high-level review surface. **This spec builds the vertical slice through A+B+C for one
human-picked work item.** D and the full dossier/E follow as their own specs.

## 2. Vertical slice — scope

**One work item → agent branch → green gate → regulatory PR on GitHub → human approves →
signed squash-merge to `main`.** Dogfood target: the SAGE GitHub repo
(`Sumanharapanahalli/SAGE`), because it is the only `gh`-authenticated repo and lets the
operator watch the whole loop on a real gap from today's review.

Human actions in the slice: (1) pick one work item to start; (2) review the PR and either
Approve or leave high-level "request changes" comments. Nothing else.

## 3. Components (small, isolated, testable)

| Module | Responsibility | Reuses |
|---|---|---|
| `src/core/mr_runner.py` | The state machine that drives one MR: create branch → code → gate → assemble package → open PR → watch for review → rework on comments → on approval, merge + sign. Runs as a **background job** (not on the sidecar's NDJSON thread — avoids the freeze in gap M6). | `worktree_manager`, `jobs.py` |
| `src/core/mr_store.py` | Per-solution SQLite record of MRs: `{id, work_item, branch, pr_number, pr_url, state, evidence, created, merged_sha}`. States: `coding → gating → review → reworking → approved → merged / failed`. | `.sage/mr.db` |
| `src/core/mr_package.py` | Assemble the PR body: **high-level summary first** (what/why, system impact, risk assessment, safe-to-merge verdict), then the dossier (diff stat, test/build evidence, traceability to the work item, change summary). Slice = these sections; full dossier (formal risk matrix, doc-diff) is a later spec. | `CriticAgent` for the risk/impact read |
| `src/core/github_pr.py` | Thin adapter over the `gh` CLI: `create(branch, title, body)`, `get_reviews(n)`, `get_comments(n)`, `comment(n, body)`, `merge(n, method="squash")`. **All git/gh side effects live here** so the runner is testable with a fake adapter. | `gh` CLI |
| `src/memory/audit_sign.py` | HMAC-SHA256 signature over each audit row chained to the previous row's hash (`prev_hash`), written on the merge event. Fills the never-populated `verification_signature` column and makes the log tamper-evident. Operator identity comes from `operator.yaml`. | `audit_logger` |
| surface | One RPC/endpoint pair: `mr.start(work_item)` and `mr.status(id)` (desktop) mirrored in `api.py`. The runner does the work in the background; the UI polls status. | dispatcher / api |

**Evidence gate (A):** the runner, inside the worktree, runs the affected tests +
`make verify` (or `verify_system.py --fast`) + the feature's own check. The PR is **not
opened until green**; on failure the coding agent gets the failing output and reworks, up
to a bounded retry count. This is the same evidence-first discipline proven this session.

**Fixes B6 inline:** the worktree is created **before** the coding agent runs, and the
agent's write-root is the worktree — so the branch actually contains the changes (today the
worktree is created after coding and commits empty).

## 4. Data flow (one MR)

1. `mr.start(work_item)` → create `mr.db` row (`coding`), create worktree/branch
   `sage/mr-<id>` off `main`.
2. Coding agent writes into the worktree. Runner runs the evidence gate → on red, feed
   failures back and rework (≤ N); on green, → `gating` passed.
3. `mr_package` builds the body; `github_pr.create` pushes the branch and opens the PR →
   store `pr_number/url`, state `review`.
4. Runner watches the PR (bounded poll, backoff): 
   - **changes requested / comments** → state `reworking`; agent addresses comments in the
     worktree; re-run gate; `github_pr.comment` summarizing the rework; push → back to
     `review`.
   - **approved** → `github_pr.merge(squash)` → `audit_sign` writes the signed, chained
     merge record (approver identity + signature + merged SHA) → state `merged`.
5. `mr.status(id)` surfaces the state + PR URL + evidence for the UI at each step.

## 5. Error handling

- **gh not authed / offline:** `github_pr` probes `gh auth status` first; a failure sets the
  MR `failed` with an actionable reason (never a silent hang).
- **Gate never goes green within N reworks:** MR parked `failed` with the last failing
  output attached — the human sees *why*, no broken PR is ever opened.
- **Merge conflict with `main`** (main moved during review): runner rebases the branch and
  re-runs the gate before merging; unresolvable → `failed` with the conflict surfaced.
- **Nothing destructive:** all agent file writes are confined to the worktree; `main` is
  only ever changed by an approved squash-merge. The old repo-root `git clean -fd` path
  (fixed earlier today) is not used.

## 6. Testing

- `github_pr`: unit-tested against a **fake gh** (no network); asserts argv + parsing.
- `mr_runner`: state-machine tests with a fake adapter + a stub coding agent — green-first,
  red-then-rework, changes-requested-then-approved, gate-never-green, all asserted; **no PR
  is opened while the gate is red**.
- `mr_package`: asserts the high-level summary precedes the dossier and every required
  section is present.
- `audit_sign`: a tampered row breaks the chain; a valid chain verifies; the merge event is
  signed with the operator identity.
- **Acceptance (real):** one end-to-end dogfood run — agents fix a small real gap on a
  branch of the SAGE repo, open a real PR, the operator approves, SAGE squash-merges and
  writes the signed record. This is the demo the operator watches.

## 7. Regulatory alignment

The gate is a **reviewed, signed, traceable merge to a protected `main`** — the standard
regulated-software release control (IEC 62304 / 21 CFR Part 11). Every merge carries: the
approver's identity, an HMAC signature chained to prior records (tamper-evidence), the
traceability link from work item → PR → merged SHA, and the green-evidence precondition. The
human reviews the high-level package and signs; agents produce the evidence.

## 8. Out of scope (later specs)

- (D) The feedback-driven prioritizer that auto-starts work from the gap analysis + approval
  history (slice is human-picked, one item).
- The full formal dossier: quantified risk matrix, automated doc-diff, system-impact graph.
- (E) The rich review UI (slice reviews in GitHub's own PR view).
- External `reflect-*` repos as targets (needs B4 external-repo awareness) — slice dogfoods
  SAGE's own repo.
- git-local (no-PR) mode — slice commits to the GitHub-PR path the operator chose.
