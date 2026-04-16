# SAGE Desktop — Phase 1 Design Spec

**Date:** 2026-04-16
**Author:** Claude (with Suman Harapanahalli)
**Status:** Design — awaiting user sign-off before implementation plan
**Scope:** Phase 1 of a 4-phase rebuild of `sage-desktop/`. Later phases have their own specs.

---

## 1. Goal

Build a native Windows desktop application (`sage-desktop/`) that gives a SAGE operator a full HITL approval workflow **with zero listening sockets, zero open ports, and zero admin privileges** — usable in corporate environments where all network sockets (including loopback) are blocked by endpoint security.

The Phase 1 feature set is a working operator console covering the four most load-bearing SAGE screens available on `main`:

1. **Approvals inbox** — pending proposals sorted by risk class, with approve/reject/batch/undo
2. **Agents roster** — list of agents with role and performance metrics
3. **Audit log viewer** — searchable audit trail from the active solution's `.sage/audit_log.db`
4. **Status dashboard** — component health, solution context, LLM provider info

**Evolution page is deferred** to a short Phase 1.5 that lands after the Phase 7 web/evolution work (currently on `experiments/FDA_CDS_Gap_Analysis.md`) merges to `main`. Phase 1 ships without it. Reason: `src/core/evolution/` does not yet exist on `main`; the desktop sidecar cannot import modules that aren't there.

Phases 2–4 add operator tools, authoring/admin, and packaging respectively. Each is a separate spec.

### 1.1 Relationship to existing `web/src-tauri/`

`main` already contains a thin Tauri wrapper at `web/src-tauri/` that bundles the React web UI into a desktop window and connects to the FastAPI server at `localhost:8000` (see its `tauri.conf.json` CSP: `connect-src http://localhost:8000`). That app **requires port access** and is therefore unusable in restricted corporate environments.

`sage-desktop/` and `web/src-tauri/` are **complementary**, not competing:
- `web/src-tauri/` — for users with loopback port access; zero new Python code; fastest path to a desktop shell.
- `sage-desktop/` — for users in port-restricted environments; embedded Python sidecar; no HTTP at all.

Both continue to ship. Users pick the one that fits their environment.

---

## 2. Non-goals (Phase 1)

- No feature that requires HTTP: LLM switch, onboarding wizard, YAML editor, BuildConsole → all deferred to later phases.
- No push/WebSocket equivalents — polling is sufficient for Phase 1.
- No mobile, macOS, or Linux builds — Windows-only.
- No SSO / remote-identity integration — uses the local Windows user as `decided_by`.
- No packaging/installer polish — that is Phase 4.
- No replacement for the existing web UI or VS Code extension — this is a *third* interface for restricted-environment users. Web and VS Code continue to work for users with port access.

---

## 3. Architecture

### 3.1 Processes

Single user-scope `.exe` (Tauri bundle) containing three processes:

```
┌──────────────────────────────────────────────────────────────┐
│  sage-desktop (Tauri — no admin, no open ports)              │
│                                                              │
│  ┌─────────────────┐      ┌────────────────────────────┐     │
│  │ React UI        │      │ Rust (Tauri core)          │     │
│  │ (webview)       │◄────►│  - SidecarManager          │     │
│  │                 │ IPC  │  - RpcClient (NDJSON)      │     │
│  │                 │      │  - Thin Tauri commands     │     │
│  └─────────────────┘      └──────────────┬─────────────┘     │
│                                          │                   │
│                   stdin/stdout JSON-RPC  │ (no sockets)      │
│                                          ▼                   │
│                          ┌────────────────────────────┐      │
│                          │ Python sidecar             │      │
│                          │ (bundled interpreter)      │      │
│                          │  - imports src/core/*      │      │
│                          │  - imports src/agents/*    │      │
│                          │  - imports src/memory/*    │      │
│                          │  - NO FastAPI              │      │
│                          └────────────────────────────┘      │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 Key properties

- **No sockets, no ports.** All IPC between Rust and Python is stdin/stdout newline-delimited JSON-RPC 2.0.
- **Bypasses FastAPI.** The Python sidecar imports SAGE library modules directly (`src/core/proposal_store.py`, `src/memory/audit_log.py`, agent registry, evolution stores). The existing `src/interface/api.py` is untouched and continues to serve the web UI and VS Code extension for users who can use HTTP.
- **Single source of truth.** Desktop sidecar, FastAPI server, and Python CLI all read/write the **same** SQLite + Chroma files under the active solution's `.sage/` directory. A decision approved in desktop is visible to web UI users and CLI users, and vice versa.
- **Bundled Python.** Tauri's `externalBin` ships the Python interpreter + SAGE dependencies (~350–500 MB installer). Trade-off accepted: size over first-launch UX.
- **One sidecar per solution.** Sidecar is pinned to the active solution at launch. Solution switch (deferred to Phase 2) restarts the sidecar.
- **User-scope installer.** No elevation needed. Installs to `%LOCALAPPDATA%\Programs\sage-desktop\`.

### 3.3 Failure model

If the sidecar crashes, Rust detects closed stdout, marks the app `Offline`, disables write buttons, and restarts the sidecar with exponential backoff (1s → 3s → 9s). After the third failure, the user sees a full-screen recovery panel with copy-pasteable diagnostics. Details in §6.

---

## 4. Components

### 4.1 Rust — `sage-desktop/src-tauri/src/`

| File | Responsibility |
|---|---|
| `main.rs` | Entry point. Builds Tauri app, registers `SidecarManager` in managed state. |
| `sidecar.rs` | Spawns/restarts/health-checks the Python process. Exponential backoff. Emits `sidecar-status` Tauri events to the webview. |
| `rpc.rs` | JSON-RPC 2.0 over NDJSON on stdin/stdout. Correlation IDs (UUID), per-call timeouts, pipelined in-flight requests. Typed with serde. |
| `commands/approvals.rs` | Tauri commands: `get_pending_proposals`, `approve`, `reject`, `batch_approve`, `undo` |
| `commands/agents.rs` | `list_agents`, `get_agent_performance` |
| `commands/audit.rs` | `query_audit_log` (filter by trace_id, date range, agent, decision) |
| `commands/status.rs` | `get_status`, `get_project_config` |
| `errors.rs` | Typed errors: `SidecarCrashed`, `RpcTimeout`, `ProposalExpired`, `RbacDenied`, `ValidationFailed`, `ProposalNotFound`, `AlreadyDecided`, `SolutionUnavailable`, `SageImportError`. Each implements `serde::Serialize` so frontend can pattern-match. |

Commands do no business logic — each is ≤20 lines: marshal args, call `rpc.call(method, params)`, map errors, return. This keeps Rust unit-testable without spawning a real Python process.

### 4.2 React — `sage-desktop/src/`

| Path | Responsibility |
|---|---|
| `api/approvals.ts`, `agents.ts`, `audit.ts`, `status.ts` | Typed Tauri command wrappers. Pure functions. |
| `api/types.ts` | Shared TS types mirroring Rust structs (`Proposal`, `RiskClass`, `AgentInfo`, `AuditEntry`, etc.) — handwritten for Phase 1; codegen deferred. |
| `hooks/useProposals.ts`, `useAgents.ts`, `useAudit.ts`, `useStatus.ts` | React Query wrappers. Handle polling (`refetchInterval`), invalidation on mutations, offline detection. |
| `components/layout/Sidebar.tsx`, `TopBar.tsx`, `OfflineBanner.tsx`, `ErrorBoundary.tsx` | Global layout + error boundary. |
| `components/domain/ProposalCard.tsx`, `RiskBadge.tsx`, `ExpiryCountdown.tsx`, `StatusIndicator.tsx` | Domain UI pieces. |
| `pages/Approvals.tsx`, `Agents.tsx`, `Audit.tsx`, `Status.tsx` | One page per feature. Routed via React Router. |

### 4.3 Python sidecar — `sage-desktop/sidecar/`

| File | Responsibility |
|---|---|
| `__main__.py` | Read NDJSON from stdin; dispatch; write NDJSON to stdout. Clean shutdown on EOF. |
| `rpc.py` | JSON-RPC 2.0 framing, error-code mapping. |
| `dispatcher.py` | Method-name → handler registry. |
| `handlers/approvals.py` | Thin wrapper over `src/core/proposal_store.py` — the same ProposalStore the FastAPI server uses. |
| `handlers/agents.py` | Wraps agent registry. |
| `handlers/audit.py` | Wraps `src/memory/audit_logger.py`. |
| `handlers/status.py` | Project config + component health. |
| `errors.py` | Python exception → JSON-RPC error mapping. |

Sidecar handlers are the **only** new Python code. If a handler needs domain logic, that logic belongs in `src/core/` or `src/agents/`, not in the sidecar. The sidecar is a transport layer, not a business-logic layer.

### 4.4 Contract: shared RPC fixtures

`sage-desktop/tests/fixtures/rpc-contracts/*.json` contains canonical request and response pairs for every method. Both Rust and Python tests load these files and assert serialization round-trips match. This is the authoritative contract — if Rust serializes a shape Python rejects, the test catches it.

---

## 5. Data Flow

### 5.1 Happy path — approve a proposal

1. User clicks Approve on a `ProposalCard`.
2. React calls `api.approveProposal(traceId, feedback?)`.
3. `api.approveProposal` calls `invoke('approve', { traceId, feedback })`.
4. Rust command `commands::approvals::approve` builds `{jsonrpc:"2.0", id:<uuid>, method:"approve", params:{trace_id, feedback, decided_by:"desktop:<local_user>"}}`.
5. `RpcClient.call()` writes NDJSON to sidecar stdin, parks a future on the correlation ID.
6. Python `dispatcher.dispatch` → `handlers/approvals.approve` → `ProposalStore.decide(trace_id, "approved", approver)`. This writes SQLite and appends the audit log.
7. Handler returns the updated proposal. Sidecar writes response NDJSON to stdout.
8. Rust RpcClient reads, matches correlation ID, resolves the future.
9. Tauri command returns `Result<Proposal, DesktopError>`.
10. React `useApproveMutation onSuccess` → `queryClient.invalidateQueries(['proposals','pending'])` → inbox rerenders; approved card disappears.

Warm-sidecar round-trip budget: <150 ms. RPC timeout: 10 s per call.

### 5.2 Startup & handshake

1. Tauri app starts; `SidecarManager.spawn()` resolves the bundled `python.exe` via Tauri's externalBin resolver and launches `python -m sidecar --solution <path>`.
2. Rust sends `{method:"handshake", params:{ui_version}}`.
3. Sidecar responds with `{sidecar_version, sage_version, solution_name, warnings:[...]}` where `warnings` lists any non-fatal missing SAGE modules.
4. On version mismatch, Rust halts startup and surfaces a recovery screen.
5. Rust emits `sidecar-ready` Tauri event; React mounts and initial queries fire.

Handshake timeout: 10 s. Failure → recovery screen with copy-paste diagnostics.

### 5.3 Polling cadence

| Page | Query key | Interval | Invalidated on |
|---|---|---|---|
| Approvals | `['proposals','pending']` | 10 s | approve / reject / batch_approve / undo |
| Agents | `['agents']` | 30 s | manual refresh only |
| Audit | `['audit', filters]` | 30 s | manual refresh only |
| Status | `['status']` | 5 s | manual refresh only |

No push in Phase 1. Push (Tauri events from sidecar) is a Phase 2 option if polling proves costly.

### 5.4 Failure paths

See §6.

---

## 6. Error Handling & Recovery

### 6.1 Error taxonomy

Single error shape crosses all three layers: `code` (machine), `message` (human), `details` (structured).

| JSON-RPC code | Rust enum | UI surface | Retryable? |
|---|---|---|---|
| `-32700` parse error | `RpcProtocolError` | Toast, auto-retry once | Yes (1x) |
| `-32601` method not found | `RpcMethodMissing` | Version-mismatch recovery screen | No |
| `-32602` invalid params | `ValidationFailed{field}` | Inline field error | No |
| `-32000` generic sidecar | `SidecarError{detail}` | Toast | No |
| `-32001` `PROPOSAL_EXPIRED` | `ProposalExpired{trace_id}` | Inline + invalidate list | No |
| `-32002` `RBAC_DENIED` | `RbacDenied{required_role}` | Modal | No |
| `-32003` `PROPOSAL_NOT_FOUND` | `ProposalNotFound{trace_id}` | Inline + list refresh | No |
| `-32004` `SOLUTION_UNAVAILABLE` | `SolutionUnavailable` | Full-screen recovery | No |
| `-32005` `ALREADY_DECIDED` | `AlreadyDecided{status}` | Toast + list refresh | No (reconcile) |
| `-32010` `SAGE_IMPORT_ERROR` | `SageImportError{module}` | Full-screen recovery with diagnostic | Maybe (user) |
| (no response) | `RpcTimeout` | Toast, manual retry button | Yes (manual) |
| (stdout EOF) | `SidecarCrashed` | `OfflineBanner`, auto-restart | Auto (3x) |

### 6.2 Retry policy

| Scope | Policy | Numbers |
|---|---|---|
| Sidecar respawn | Exponential w/ jitter | 1s, 3s, 9s; 3rd failure → manual action required |
| RPC protocol error (transient) | Single auto-retry | Then surface |
| RPC timeout | **No auto-retry** | Prevents double-writes |
| React Query refetch | Linear | 3 retries, 2s spacing, then stale badge |
| Handshake | No retry | Blocks startup |

**Writes (approve, reject, approve_candidate, undo) never auto-retry.** Lost response to an approve could double-decide. Manual retry returns `ALREADY_DECIDED`, reconciled by list invalidation. Net effect: correct and idempotent.

### 6.3 UI surfaces

| Surface | When | Auto-dismiss |
|---|---|---|
| Inline (next to field/card) | Scoped validation, stale proposal | On user edit / list refresh |
| Toast | Transient server error, retry suggestion | 5 s, stacked |
| Modal | RBAC denied, destructive confirm | User dismisses |
| OfflineBanner (top) | Sidecar offline | When sidecar back |
| Full-screen recovery | Handshake failure, import error, missing solution | User action required |

Write buttons are **disabled** (not click-rejected) when sidecar is offline, to prevent queued-up actions firing on reconnect.

### 6.4 Logging

Three log streams, each rotated daily, 14-day retention, in `%APPDATA%\sage-desktop\logs\`:

1. `sidecar-YYYY-MM-DD.log` — sidecar stderr captured by Tauri.
2. `app-YYYY-MM-DD.log` — Rust `tracing` output.
3. Webview console — dev mode only; production suppressed (power-user "Open DevTools" menu deferred to Phase 3).

"Copy diagnostic bundle" button (Phase 3) zips recent logs + handshake output. Phase 1 emits the logs; the UI button comes later.

### 6.5 Graceful degradation

If sidecar boots but a SAGE module fails to import (e.g., `chromadb` missing):

- Handshake returns `warnings:[...]` listing unavailable features.
- Affected pages (Audit, Evolution) render per-page offline state with a "Copy fix command" (`pip install chromadb`).
- Other pages function normally.

This is Phase 1 scope because partial-failure is the most likely early-support headache with bundled Python.

---

## 7. Testing Strategy

TDD is mandatory — every implementation task in the plan starts with a failing test.

### 7.1 Coverage targets

| Layer | Framework | Target | Location |
|---|---|---|---|
| Python sidecar | pytest | 90% | `sage-desktop/sidecar/tests/` |
| Rust core | cargo test | 85% | inline `#[cfg(test)]` + `src-tauri/tests/` |
| React UI | vitest + @testing-library/react | 75% components, 95% hooks+api | colocated + `src/__tests__/integration/` |

### 7.2 Test types

**Python**: handler units (mocked ProposalStore / AuditLog) + integration against temp-dir SQLite + RPC loop tests (dispatcher routing, malformed input, partial frames). Fixture solution at `sage-desktop/tests/fixtures/test-solution/` (minimal project.yaml / prompts.yaml / tasks.yaml). Same fixture reused by Rust integration tests.

**Rust**: unit tests for rpc framing, error mapping, command marshalling. Integration tests under `src-tauri/tests/` spawn a **mock sidecar** — `tests/fixtures/mock_sidecar.py` that replays canned NDJSON responses. Verifies SidecarManager spawn/respawn/health, correlation under concurrent requests, crash-recovery backoff. Full-sidecar tests (real SAGE imports) marked `#[ignore]`, run nightly.

**React**: api wrappers mock `@tauri-apps/api/core#invoke`. Hook tests cover React Query behavior (polling, invalidation, offline cache). Component tests cover state matrix (empty/loading/error/populated/stale) + key interactions. Page integration tests (`__tests__/integration/*.test.tsx`) render full pages with MSW-style invoke mocks — approve happy path, reject with feedback, batch partial failure, offline banner.

**Cross-boundary contract**: `sage-desktop/tests/fixtures/rpc-contracts/*.json` loaded by both Rust and Python tests. Single source of truth for wire shape.

**E2E**: one smoke test in Phase 1 using `tauri-driver` — launch app → handshake → seed fixture with one pending proposal → approve → verify audit log entry on disk. Lives in `sage-desktop/tests/e2e/`. Runs via `make test-desktop-e2e`, not on every unit-test pass. Full E2E suite deferred to Phase 4.

### 7.3 Test-runner scripts

| Command | Runs |
|---|---|
| `cd sage-desktop && npm test` | vitest (React) |
| `cd sage-desktop/src-tauri && cargo test` | Rust unit + integration |
| `cd sage-desktop/sidecar && pytest` | Python |
| `make test-desktop` | All three, fail-fast |
| `make test-desktop-e2e` | E2E smoke |
| `make test-all` (extended) | Existing `test-all` gains `test-desktop` |

### 7.4 Deferred

- Performance/load tests — Phase 2.
- Mutation testing (cargo-mutants / stryker) — Phase 4.
- Visual regression (Playwright screenshots) — Phase 4.
- Accessibility audit (axe-core) — Phase 3.

---

## 8. Development Workflow

Execution uses `superpowers:subagent-driven-development`. Within the plan for this spec:

- One implementer subagent per task, sequentially.
- Two-stage review after each task: spec-compliance reviewer, then code-quality reviewer.
- Failed reviews loop back to the same implementer subagent with specific fixes.
- No parallelism within Phase 1 — foundation code is tightly coupled.

Parallelism appears **between** phases: while Phase 1 is in implementation, background agents brainstorm and spec Phases 2–4. Once Phase 1 merges, Phases 2–4 execute in parallel git worktrees via `superpowers:executing-plans`.

---

## 9. Branching & Cleanup

- **Branch**: `feature/sage-desktop-phase1` off `main` (not off the current `experiments/FDA_CDS_Gap_Analysis.md` branch, which contains unrelated Phase 7 web UI WIP).
- **Phase 7 web UI work** continues on its own branch. The deferred Evolution page (Phase 1.5) consumes its features (via the shared ProposalStore and evolution stores) once both merge to main.
- **Deleted in Phase 1 Task 1**: `my_rust_app/` (confirmed abandoned stub, empty Cargo.toml, no sources).
- **Retained**: `sage-vscode/` unchanged. Noted in docs as "requires `localhost:8000` — not usable in restricted environments."
- **Retained**: `web/src-tauri/` unchanged. Noted in docs as "web-UI desktop wrapper; requires `localhost:8000`; use `sage-desktop/` in port-restricted environments." Both coexist.
- **Replaced**: `sage-desktop/` contents wiped and rebuilt from scratch. The mock-data scaffold is not carried forward.

---

## 10. Docs Updates (part of Phase 1 deliverables)

These are not optional — they are part of the "done" definition for Phase 1:

- **New**: `.claude/docs/interfaces/desktop-gui.md` — architecture, sidecar RPC contract summary, when to use desktop vs. web vs. VS Code.
- **Updated**: `CLAUDE.md` — add `sage-desktop/` to Project Structure section; add `make test-desktop` and related commands to Quick Start.
- **Updated**: `.claude/docs/architecture.md` — add sidecar-as-interface-option paragraph under existing interfaces section; note the shared-state model across interfaces.
- **Updated** (if one exists or newly created): `.claude/docs/setup.md` — desktop build instructions, including bundled-Python prerequisites.

Each is a distinct task in the implementation plan, not a tail afterthought.

---

## 11. Acceptance Criteria (Phase 1 "done")

Phase 1 is complete when **all** of the following are true:

1. `make test-desktop` exits 0. All tests across Python, Rust, React pass.
2. `make test-desktop-e2e` exits 0. The one smoke test passes.
3. Coverage meets the targets in §7.1.
4. The app launches on a fresh Windows 11 install without admin, without any open ports, and shows the Status dashboard.
5. A pending proposal seeded in the fixture solution's `.sage/` appears in the Approvals inbox within 10 s and can be approved; the audit log records the decision with `decided_by:desktop:<user>`.
6. Killing the sidecar process externally causes the OfflineBanner to show within 5 s and auto-recovery to succeed on the first backoff attempt.
7. Docs updates in §10 are committed and reviewed.
8. `my_rust_app/` is deleted; no code depends on it.
9. The four Phase 1 pages (Approvals, Agents, Audit, Status) render without console errors on a freshly built app.
10. Evolution page is **not** required for Phase 1 completion; it lands in Phase 1.5 after Phase 7 merges.

---

## 12. Out-of-scope Phases (for reference only)

- **Phase 1.5 — Evolution page**: Experiment list + candidate approvals. Unblocked once `experiments/FDA_CDS_Gap_Analysis.md` merges to `main` and `src/core/evolution/` is available for import. Small scope — one new page, one handler, one Rust commands module, typed api wrappers + hooks.
- **Phase 2 — Operator tools**: Chat/Analyze, LLM provider switch, project config switch, feature request submission, Product Owner backlog, monitor/queue status.
- **Phase 3 — Authoring & admin**: YAML editor, Onboarding wizard, BuildConsole, solution switcher, full Settings page, accessibility audit, diagnostic bundle UI, dev-tools menu.
- **Phase 4 — Packaging & polish**: Windows MSI without admin, offline cache, full E2E, update mechanism, mutation/visual-regression tests, telemetry.

Each phase has its own brainstorming session, spec, and plan.

---

## 13. Open questions (to be resolved during implementation, not design)

None at this time. All architectural choices (Python bundling, one-sidecar-per-solution, NDJSON framing, polling over push, handwritten types over codegen) are settled in this spec.

Implementation choices that intentionally remain open to the implementer/reviewer (they don't affect the contract):

- Exact Tauri `externalBin` packaging steps on Windows — to be worked out in Task 1 of the plan.
- Rust tracing subscriber configuration (JSON vs pretty format for the log file).
- React Router version (6.x latest).
- Tokio version pin.

---

## 14. Dependencies on existing SAGE code

Phase 1 **reads from and writes to** these existing modules. Any breaking change to their APIs blocks this work.

| Module | Why |
|---|---|
| `src/core/proposal_store.py` | Approvals inbox reads/writes |
| `src/memory/audit_logger.py` | Audit log viewer reads; all writes append |
| Agent registry (exact path to be confirmed in Task 2 of the plan — likely `src/agents/` module discovery) | Agent roster |
| Solution/project loader (exact path to be confirmed in Task 2 of the plan) | Solution context resolution at sidecar startup |

Phase 1 does **not** modify these modules — only imports them. If a shared-store change is needed, it's a separate task, not bundled.

`src/core/evolution/*` — **not yet on `main`**. Phase 1.5 depends on it landing.

---

## 15. Risks

| Risk | Mitigation |
|---|---|
| Bundled-Python size balloons installer >500 MB | Start with bundled, measure, consider thin-install fallback in Phase 4 if needed |
| Tauri externalBin is finicky on Windows AV | Dev-mode sidecar-path override + signed bundle in Phase 4 |
| Python startup latency >2 s hurts UX | Measure at end of Phase 1; if bad, add splash-screen phase or async handshake in Phase 2 |
| NDJSON framing chokes on SAGE logs leaking to stdout | Sidecar `__main__.py` redirects all non-RPC stdout to stderr; tests cover this |
| Corporate AV blocks spawned child processes | Signed binary + user-scope install path + clear installer diagnostics |
| Partial SAGE import (e.g., chromadb) | Graceful-degradation mode covered in §6.5 |

---

## 16. References

- User pain point: corporate environment blocks all listening sockets, including loopback. Established in brainstorming conversation on 2026-04-16.
- Existing port-bound interfaces: `src/interface/api.py` (FastAPI at localhost:8000), `sage-vscode/` extension (polls the FastAPI). Both remain functional for unrestricted users.
- Mocked scaffold at `sage-desktop/` prior to this spec: rebuilt from scratch in this phase.
- SAGE Five Laws (CLAUDE.md): Law 1 mandates HITL for agent proposals. This spec preserves that invariant — all write RPCs go through `ProposalStore.decide`, which is the framework's sole decision path.
