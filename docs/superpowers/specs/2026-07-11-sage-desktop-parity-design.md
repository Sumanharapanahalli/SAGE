# sage-desktop ⇄ web Parity — Design

**Date:** 2026-07-11
**Status:** Approved for implementation
**Branch:** `feat/desktop-parity`

---

## 1. Why

The operator is **desktop-only**: the web portal is blocked by corporate network policy. Every capability absent from `sage-desktop/` is therefore a capability permanently lost, not a deferred convenience. The deliberate deferrals recorded in `CLAUDE.md` (streaming, Integrations, Auth, Distillation) were reasoned against a world where the web UI remained available as a fallback. That world no longer exists for this operator, so each deferral must be re-decided on its merits: either built, or declared genuinely impossible with a stated least-bad alternative.

A verified capability audit (37 web pages traced to their endpoints, every "already covered" claim adversarially re-checked against the actual sidecar handlers and UI controls) produced two findings. The second was expected. The first was not.

## 2. The unexpected finding: the shipped desktop loop is not merely incomplete, it is inaccurate

These are not parity gaps. They are correctness and compliance defects in code that ships today, and several pages *appear* to have parity only because of them. Each was confirmed by direct inspection, not inferred:

- **No approval is ever audit-logged.** There is no `log_event` call anywhere in `sage-desktop/sidecar/` production code. `Approvals.tsx` nonetheless tells the operator "The decision is recorded in the Audit log."
- **Approval does not execute.** `execute_approved_proposal` appears nowhere in `sage-desktop/`. Approving an `implementation_plan` flips a status column and stops — no task queued, no code written. Rejecting a `code_diff` does not call `_revert_code_diff`, so the agent's edits remain on disk.
- **Rejection teaches nothing.** No `learn_from_feedback`, no `add_feedback` in desktop production code. Phase 5 (compounding memory) — Law 3, and the core thesis of the framework — is severed. `ApprovalCard.tsx` claims the opposite in its placeholder copy.
- **The audit log read path is not the write path.** `sidecar.rs` never sets `SAGE_PROJECT`, so `audit_logger` freezes `DB_PATH` at import to `<sage_root>/.sage/`, while `handlers/audit.py` reads `<solution>/.sage/`. In desktop-only operation **the audit log is permanently empty.**

A framework whose product *is* the human approval gate currently ships, on this interface, a gate that records nothing, teaches nothing, and does nothing — while the UI asserts in copy that it does all three. In a regulated context an honest absence would be safer than a false assurance. **Remediating this precedes all new pages.** New pages built atop this core would inherit the same defects.

Nine further cross-cutting defects (hardcoded `Health: ok`; a queue "Done" counter structurally pinned to zero; an `llm.switch` path that silently writes `ollama_model: "gemini-2.5-flash"`; a `yaml.write` that never reloads config; six pages that never refresh; a registered-nowhere `agents.performance` RPC that throws on every click; a `permissive` HITL level that does not exist and silently degrades to `standard` while displaying itself as active) are folded into the same hardening work.

## 3. Principles

1. **Sidecar handlers wrap `src/` modules. They never reimplement domain logic.** Every slice below names the module it wraps.
2. **Port the intended contract, not the current behavior.** Several web pages are themselves partially broken (a backslash-escaped FTA path that 404s; a CodeExecution Execute tab that 400s; a Gym leaderboard that does not exist; an approval gate whose auth URL is handed over before approval). Where web is wrong, desktop is built right, and the divergence is recorded.
3. **Watch the import-time singleton trap.** `project_config`, `audit_logger`, `vector_memory`, `agent_gym`, and `knowledge_syncer`'s default all bind to whatever solution was auto-discovered *at import*, not to `--solution-name`. This class of bug has already been fixed three times (Phases 5l, 5n, 5p). Slice 0 fixes it at the root by exporting `SAGE_PROJECT` before the sidecar imports anything.
4. **Law 1 is preserved exactly.** Agent proposals (`agents.run`, `agents.hire`, `code.plan`, `integrations.connect`, `product_owner.gather_requirements`) route through `ProposalStore` and the HITL queue. Framework control (`operator.set`, `config.set_modules`, `llm.switch`, `skills.set_visibility`, `integrations.set_config`) executes immediately. Where desktop must diverge from web's enforcement, it is a **written decision**, never an accident.
5. **Vertical slices.** Each slice is sidecar RPC + Rust passthrough + client/types/hook + page + tests, shippable with `make test-desktop` green. No "all handlers, then all pages."

## 4. Architecture decisions for the previously-deferred items

**Streaming — feasible, but not on the critical path.** NDJSON is line-delimited, so the sidecar can emit unsolicited `stream.chunk` notification frames on the same stdout pipe, forwarded by the Rust reader task as a Tauri event (mirroring the existing `CrashHook`/`sidecar-status` mechanism). This needs a `FrameWriter` lock and streaming worker threads. **However**, an S-cost polling fallback — `logs.tail(after_seq)` over a bounded deque `logging.Handler` — reproduces every LiveConsole control with zero protocol change, and web's Chat does not truly stream either. **Decision: ship polling first (Slice 5); build true push (Slice 8) only for token-by-token UX, after the worker model is proven.** `llm_gateway`'s single-lane `threading.Lock` is intentional (SOUL.md) and is mitigated in the UI, never removed.

**Integrations — the documented blocker was factually wrong.** No SAGE integration hosts an OAuth callback; Composio's cloud holds the redirect and SAGE merely opens a URL and later polls `get_connected_accounts()`. The real blocker is that the sidecar **never loads `.env`** (only `src/main.py` does), so `api_key_set` reads false on a fully-configured machine. **Decision: build it (Slice 15).** Env bootstrap in `_wire_handlers`, `tauri-plugin-opener` for the system browser, poll for completion, with a copy-the-URL fallback. No port is opened. Because outbound HTTPS to `backend.composio.dev` may also be blocked in this environment, PAT/API-key/webhook integrations (GitLab, Jira, Teams, DB) are the **primary** surface; Composio degrades cleanly to an optional card.

**Auth — do not port; build operator identity instead.** API-key minting and role assignment gate the **FastAPI HTTP surface, which the desktop deliberately does not run**; `user_roles` is consumed in exactly one place, inside `verify_token`'s OIDC branch. A desktop AccessControl page would administer credentials for a deployment the operator cannot reach — pure waste. OIDC login is structurally unreachable from a stdin/stdout pipe (no `Request`, no headers, no redirect). **The real residue is signer identity**, which Slice 0 supplies: a per-solution `operator.yaml` (name, email), resolved **sidecar-side** and written into `approved_by`/`approver_role`/`approver_email` with `approver_provider="desktop-operator"`. The signer field is never accepted as an RPC parameter from the renderer. This satisfies 21 CFR Part 11 §11.50 (signed records) but **not** §11.100 (identity verification), and the UI will say so rather than imply otherwise.

**Docker sandbox (CodeExecution) — graceful degradation, with the local fallback disabled by default.** `autogen_runner`'s `_run_local` executes LLM-generated code as an unsandboxed subprocess. On a server that is a calculated risk; on the operator's own workstation it is materially worse. It becomes explicit opt-in, never a silent fallback.

## 5. Slice order

Compliance-correctness → the broken core loop → highest-value missing pages → long tail.

| # | Slice | Cost | Delivers |
|---|---|---|---|
| **0** | **The sidecar tells the truth** | S | `SAGE_PROJECT` set before import (fixes audit read/write split, and the singleton trap at its root); approvals write real audit events with a real signer; `operator.{get,set}`; real `status.get` health probe; `yaml.write` reloads config; register `agents.performance`; fix queue `done`→`completed`; per-provider model state; refresh intervals on 6 stale hooks |
| **1** | **Compounding memory** | S | Rejection → `learn_from_feedback` → `vector_memory.add_feedback`; trace_id threaded so it resolves in `audit.get_by_trace`; reject gated on non-empty feedback |
| **2** | **Approval actually approves** | L | Sidecar worker thread + `jobs.{status,list}`; `approvals.approve` → `execute_approved_proposal`; reject → `_revert_code_diff`; backlog loop closed; diff renderer, expiry countdown, risk triage, batch approve |
| **3** | Run an agent | M | `agents.{run,hire,analyze_jd}`, `config.get_project` (unblocks 6, 9, 11) |
| **4** | Chat | M | `chat.*`, `conversations.*`; solution-scoped `ChatStore` |
| **5** | Live Console (polling) | S | `logs.tail` — the only way a desktop operator ever sees a traceback |
| **6** | Dashboard + Activity + Queue | M | `queue.list_tasks` rewritten against SQLite (history, payloads, subtasks); live event feed |
| **7** | Preflight | S | `health.preflight` — a non-mutating LLM liveness check (none exists today) |
| **8** | True streaming | XL | `stream.chunk` notification frames + `NotifyHook` (UX only) |
| **9** | Solution config surface | M | `config.{set_modules,patch_theme}`; module toggles, branding, `ui_labels` |
| **10** | Developer / GitLab | M | `mr.{create,review,list_open}` |
| **11** | Regulatory + CDS + Safety | M×3 | Three stateless `src/core/` wrappers |
| **12** | Agent Gym | M | `gym.*`; solution-scoped DB injection |
| **13** | Knowledge sync | S | `knowledge.sync` with explicit vector-store injection |
| **14** | Long tail | S×n | Goals KRs + type reshape, Backlog fields, Audit CSV, MCP invoke, SKILL.md editing, org CRUD, onboarding refine, builds detail, Guide |
| **15** | Integrations | M | `.env` bootstrap; `integrations.*`; approval **before** the auth URL opens |
| **16** | Orchestrator + Workflow viewer + CodeExecution + ProductBacklog | M×4 | Lowest priority; 5 of 9 orchestrator modules have no production call sites and are deferred |

## 6. Explicitly not built

| Item | Reason | Instead |
|---|---|---|
| OIDC login / `GET /auth/me` | No `Request`, no headers, no redirect in a stdin/stdout pipe | `operator.yaml` signer identity (Slice 0); labelled honestly, never as `"oidc"` |
| API-key minting, role assignment | Gate an HTTP surface desktop does not run; enforce nothing locally | Not built. Physical machine access is the desktop trust boundary — **a written decision** |
| OAuth `redirect_url` back into the app | Requires a listening port — the one thing this app exists to avoid | Poll `integrations.status`; Composio's cloud holds the callback |

## 7. Testing

Every slice: pytest (sidecar handler), Rust (`cargo test`) where the Rust layer changes, vitest (hook + page). `make test-desktop` green before the next slice starts. Tests must exercise the **dispatcher**, not call handlers directly — the `agents.performance` defect (built, tested, and unreachable because it was never registered) existed precisely because the tests bypassed registration.

An end-to-end round-trip against a real sidecar subprocess (`make test-desktop-e2e`) covers Slices 0–2, since their whole subject is that the persisted record matches what the UI claims.
