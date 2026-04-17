# SAGE Desktop (`sage-desktop/`) — Phase 1

A native Windows desktop app that gives a SAGE operator the full HITL
approval workflow **without any listening sockets, ports, or admin
privileges**. Intended for corporate environments where endpoint
security blocks all network access — including loopback.

Phase 1 scope, landed on `feature/sage-desktop-phase1`:

- **Approvals inbox** — pending proposals sorted by risk class, with
  per-item approve/reject and batch approve
- **Agents roster** — core + custom roles with event count and
  last-active timestamp
- **Audit log viewer** — event table with action-type filter; trace
  lookup helper
- **Status dashboard** — health, sidecar version, project, LLM
  provider/model, pending count

Evolution, authoring/admin, LLM switching, and packaging are later
phases — each has its own spec.

---

## When to use which interface

SAGE ships three interfaces to the same data. They are **complementary,
not competing** — a decision approved in one is visible in all three.

| Interface | IPC | Listening ports | Use when |
|---|---|---|---|
| Web UI (`web/` + `src/interface/api.py`) | HTTP to `localhost:8000` | Yes (FastAPI on `:8000`, Vite on `:5173` in dev) | Developer machines, CI dashboards, or any environment with loopback access |
| Web-in-Tauri shell (`web/src-tauri/`) | HTTP to `localhost:8000` | Yes (still needs FastAPI running) | Want a desktop window but can keep HTTP |
| **sage-desktop** (`sage-desktop/`) | stdin/stdout NDJSON JSON-RPC | **None** | Locked-down corporate environments; air-gapped installs; compliance teams that forbid open sockets |

All three read/write the **same** SQLite + Chroma files under the
active solution's `.sage/` dir. There is no sync protocol — single
source of truth by virtue of shared filesystem.

---

## Architecture — one `.exe`, three processes

```
┌──────────────────────────────────────────────────────────────┐
│ sage-desktop.exe  (user-scope install, no admin, no ports)   │
│                                                              │
│  ┌─────────────────┐      ┌────────────────────────────┐     │
│  │ React UI        │      │ Rust (Tauri core)          │     │
│  │ (webview)       │◄────►│  - SidecarManager          │     │
│  │                 │ IPC  │  - RpcClient (NDJSON)      │     │
│  └─────────────────┘      └──────────────┬─────────────┘     │
│                                          │                   │
│                   stdin/stdout JSON-RPC  │ (no sockets)      │
│                                          ▼                   │
│                          ┌────────────────────────────┐      │
│                          │ Python sidecar             │      │
│                          │  - imports src/core/*      │      │
│                          │  - imports src/agents/*    │      │
│                          │  - imports src/memory/*    │      │
│                          │  - NO FastAPI              │      │
│                          └────────────────────────────┘      │
└──────────────────────────────────────────────────────────────┘
```

### Key properties

- **No sockets, no ports.** All Rust↔Python IPC is newline-delimited
  JSON-RPC 2.0 on stdin/stdout.
- **Bypasses FastAPI.** The sidecar imports SAGE library modules
  directly — `src/core/proposal_store.py`, `src/memory/audit_logger.py`,
  the agent registry. `src/interface/api.py` is untouched and still
  serves the web UI / VS Code extension.
- **One sidecar per solution.** Pinned to the active solution at
  launch; solution switch (deferred to Phase 2) restarts the sidecar.
- **Bundled Python.** Tauri `externalBin` ships a Python interpreter +
  SAGE dependencies. Installer size: ~350–500 MB (trade-off accepted —
  size over first-launch UX).
- **User-scope install.** No elevation. Installs to
  `%LOCALAPPDATA%\Programs\sage-desktop\`.

### Failure model

If the sidecar crashes, Rust detects the closed stdout, marks the app
`Offline`, disables write buttons, and restarts the sidecar with
exponential backoff: 1 s → 3 s → 9 s. After the third failure the
user sees a recovery panel with copy-pasteable diagnostics.

---

## RPC contract (Phase 1 methods)

NDJSON frames — one JSON object per line. Every request has
`{ jsonrpc: "2.0", id, method, params }`; every response is either
`{ jsonrpc: "2.0", id, result }` or `{ jsonrpc: "2.0", id, error }`.

| Method | Purpose |
|---|---|
| `handshake` | Sidecar version / SAGE version / solution handshake |
| `get_status` | Health, LLM provider/model, pending-approvals count |
| `list_pending_approvals` | Returns pending `Proposal[]` |
| `get_approval` | Fetch one proposal by `trace_id` |
| `approve_proposal` | Mark approved; optional `decided_by`, `feedback` |
| `reject_proposal` | Mark rejected; optional `decided_by`, `feedback` |
| `batch_approve` | Per-item outcome list; never aborts on one failure |
| `list_audit_events` | Paginated audit events, filterable by `action_type` / `trace_id` |
| `get_audit_by_trace` | All events sharing a `trace_id` |
| `audit_stats` | Totals + `by_action_type` histogram |
| `list_agents` | Core + custom roles with enrichment (event_count, last_active) |
| `get_agent` | Single agent by name |

Error codes mirror the sidecar RPC constants and map to a Rust tagged
enum (`DesktopError`) with eleven variants:

```
ProposalNotFound / ProposalExpired / AlreadyDecided / RbacDenied
SolutionUnavailable / SageImportError / InvalidRequest / InvalidParams
MethodNotFound / SidecarDown / Other
```

The React client (`src/api/types.ts`) mirrors the same tagged union, so
error handling is type-safe end to end.

---

## File layout

```
sage-desktop/
├─ src-tauri/                  Rust side
│  ├─ src/
│  │  ├─ errors.rs             DesktopError tagged enum (11 variants)
│  │  ├─ rpc.rs                NDJSON framing + request/response types
│  │  ├─ sidecar.rs            tokio Child + oneshot correlation
│  │  ├─ commands/             #[tauri::command] wrappers (12 methods)
│  │  ├─ lib.rs                desktop_app::run() — builder + handlers
│  │  └─ main.rs               binary entry point
│  ├─ Cargo.toml               feature-gated desktop build
│  ├─ build.rs                 tauri_build only when CARGO_FEATURE_DESKTOP
│  └─ tauri.conf.json          window / bundle / externalBin config
├─ sidecar/                    Python side
│  ├─ app.py                   dispatcher + NDJSON loop
│  ├─ __main__.py              `python -m sidecar` entry point
│  ├─ rpc.py                   request/response/error types
│  ├─ dispatcher.py            method registry
│  ├─ handlers/                approvals | audit | agents | status | handshake
│  └─ tests/                   pytest (~82 tests)
├─ src/                        React side
│  ├─ api/                     types.ts + client.ts (Tauri invoke wrapper)
│  ├─ hooks/                   React Query hooks per domain
│  ├─ components/layout/       Layout / Sidebar / Header / ErrorBanner
│  ├─ components/domain/       ApprovalCard / AuditTable / AgentCard
│  ├─ pages/                   Approvals / Agents / Audit / Status
│  ├─ App.tsx / main.tsx       routing + root
│  └─ __tests__/               vitest (50 tests)
├─ e2e/                        node smoke test against real sidecar
├─ package.json                vite + vitest + tailwind + react-query
└─ tsconfig*.json              strict TS, @ alias
```

---

## Running in development

```bash
# From repo root
make desktop-install           # One-time npm install in sage-desktop/
make desktop-dev               # Tauri dev — Rust, Vite, and sidecar
```

The dev build reads `SAGE_ROOT` from `std::env::current_exe()` by
default and sidecar imports resolve against it. For an alternate
solution path, set `SAGE_SOLUTION_PATH=/path/to/solutions/<name>`
before launching.

---

## Testing

```bash
make test-desktop              # Sidecar (pytest) + Rust + React
make test-desktop-sidecar      # Python only — 82 tests
make test-desktop-rs           # Rust only — 17 tests
make test-desktop-web          # Vitest — 50 tests
make test-desktop-e2e          # Real sidecar subprocess round-trip
```

All three test layers run without any external services — no FastAPI
server, no network, no admin rights. The Rust tests use
`--no-default-features` so WebView2Loader.dll is not required to run
pure-module tests on Windows.

---

## Limits of Phase 1

Deferred to later phases, either because the feature requires HTTP
today (LLM switch, onboarding wizard, YAML editor, Build Console) or
because the supporting module isn't on `main` yet
(`src/core/evolution/` — tracked to Phase 1.5).

- No push/WebSocket updates — the UI polls via React Query.
- No packaging polish, code signing, or auto-update. Phase 4.
- No SSO / remote identity. `decided_by` defaults to the local Windows
  user.
- No solution switcher in the UI — one sidecar per launch. Phase 2.
