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
| `llm.get_info` | Current provider name, model, and list of available providers |
| `llm.switch` | Runtime provider/model swap (framework control — no HITL) |
| `backlog.list` | List solution or framework feature requests, filterable by status/scope |
| `backlog.submit` | Create a new feature request; validates priority + scope |
| `backlog.update` | Approve / reject / complete an existing request |
| `queue.get_status` | Pending / in-progress / done / failed / blocked counts + parallel config |
| `queue.list_tasks` | Paginated task list (≤50 by default), optional status filter |

### Phase 2 methods

- Shares one SQLite file with the FastAPI Web UI (`/features/list` returns the same rows).
- LLM switch reuses `src/core/proposal_executor._execute_llm_switch` so CLI, Web UI, and
  desktop all land on the same runtime state.
- New error variant: `FeatureRequestNotFound { feature_id: string }` (RPC code `-32020`).

Error codes mirror the sidecar RPC constants and map to a Rust tagged
enum (`DesktopError`) with twelve variants:

```
ProposalNotFound / ProposalExpired / AlreadyDecided / RbacDenied
SolutionUnavailable / SageImportError / InvalidRequest / InvalidParams
MethodNotFound / SidecarDown / FeatureRequestNotFound / Other
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
- YAML authoring, onboarding wizard, and Build Console are deferred to
  Phase 3b/3c/3d.

---

## Phase 3a — Solution switcher (landed on `feature/sage-desktop-phase3a`)

The single-lane invariant stands: one sidecar = one active solution. The
3a work makes that choice a **runtime** one.

- `solutions.list` / `solutions.get_current` RPCs + matching
  `list_solutions` / `get_current_solution` Tauri commands.
- `switch_solution(name, path)` command: closes sidecar stdin, waits up
  to 3 s, force-kills on timeout, respawns with
  `--solution-name/--solution-path`, re-handshakes under a write lock,
  then emits a `solution-switched` Tauri event.
- Sidecar handle moves from `State<Sidecar>` to
  `State<RwLock<Sidecar>>` — read-path commands use `.read().await`;
  the switch takes `.write().await`.
- React: `useSolutions` / `useCurrentSolution` / `useSwitchSolution`
  hooks, a `useAppEvents` listener that invalidates the whole React
  Query cache on `solution-switched`, a `SolutionPicker` component,
  Sidebar footer showing the active solution, Settings page section
  anchored at `/settings#solution`.
- Typed error: `DesktopError::SolutionNotFound { name }` (RPC code
  `-32021`) rendered by `ErrorBanner`.

`src/core/project_loader.py` grew a `list_solutions(sage_root)` helper
(pure function, no framework coupling) which the sidecar wires at
`_wire_handlers` time.

### Testing delta
- Python: +6 unit tests (handlers/solutions) and 2 e2e round-trips in
  `test_main.py`.
- Rust: +1 errors test (`SolutionNotFound`) and +1 sidecar integration
  test (`replace_solution_spawns_fresh_sidecar`).
- Web: +6 `useSolutions`, +2 `useAppEvents`, +7 `SolutionPicker`, +1
  Sidebar footer, +1 Settings picker — 84 vitest tests total.

---

## Phase 3c — Onboarding wizard (landed on `feature/sage-desktop-phase3c`)

Phase 3a made switching possible; 3c makes *creating* possible. A user
can now go from "I want a yoga coach app" to a working solution
directory without leaving sage-desktop and without `POST
/onboarding/generate` on FastAPI.

- `onboarding.generate` RPC in the sidecar — a thin wrapper over
  `src.core.onboarding.generate_solution`. Validates `description` and
  `solution_name`; re-raises framework errors as typed RPC codes:
  `ValueError` → `-32602` (`InvalidParams`), `RuntimeError` (LLM down)
  → `-32000` (`SidecarDown`).
- `onboarding_generate(description, solution_name, compliance_standards?,
  integrations?, parent_solution?)` Tauri command — proxy-only, uses the
  existing `State<RwLock<Sidecar>>` read-lock pattern (the sidecar's own
  stdin mutex serializes the LLM call).
- React: `useOnboardingGenerate` mutation hook invalidates `solutionsKey`
  on `status == "created"` so the Sidebar picker refreshes; an
  `OnboardingWizard` component with client-side validation
  (`^[a-z][a-z0-9_]*$` + min 30-char description) and a typed-error
  alert panel; `/onboarding` page; "+ New solution" link in the Sidebar
  (always visible, above the current-solution footer).
- After a successful `created` result the wizard offers "Switch to it"
  (calls `useSwitchSolution` → navigates to `/status`) or "Stay on
  current". An `exists` status renders a yellow soft-fail panel (no
  Switch button — the solution already existed).

The framework function is untouched — 3c is pure wiring.

### Testing delta
- Python: +7 unit tests (`handlers/onboarding`) and +1 e2e round-trip
  in `test_main.py` — 118 sidecar tests total.
- Rust: proxy-only command, no new tests (the existing 20 still pass
  against the enlarged handler list).
- Web: +3 `useOnboardingGenerate` and +5 `OnboardingWizard` tests — 92
  vitest tests total.

---

## Phase 3d — Build Console (landed on `feature/sage-desktop-phase3d`)

Phase 3c scaffolds a solution; 3d executes the build pipeline against
it. The Builds page drives the `BuildOrchestrator` (decompose → plan →
agent execution → integration) through the same stdin/stdout RPC path,
so a user can go from "start a build of this yoga app" to a completed,
approved run without FastAPI.

- Four sidecar handlers (`builds.start`, `builds.list`, `builds.get`,
  `builds.approve`) wrap `src.integrations.build_orchestrator`. The
  orchestrator's dict-with-`error`-key convention is translated into
  typed `RpcError`s: "not found" / "state not ready" → `-32602`
  (`InvalidParams`), internal exceptions → `-32000` (`SidecarDown`).
  `builds.approve` is a unified gate — it reads the current state and
  routes to `approve_plan`, `approve_build`, or `reject` so the
  frontend doesn't have to know the state machine.
- Four Tauri commands (`start_build`, `list_builds`, `get_build`,
  `approve_build_stage`) — proxy-only, all use the existing
  `State<RwLock<Sidecar>>` read-lock pattern.
- React: `useBuilds` (5 s poll), `useBuild(runId)` (3 s poll only while
  the run is actively executing — paused on `awaiting_*` and terminal
  states), `useStartBuild`, `useApproveBuildStage`. A two-column page
  with `StartBuildForm` (min-30-char product description; defaults
  critic_threshold=70, hitl_level=standard), `BuildRunsTable` (color-
  coded state badges), and `BuildRunDetailView` (shows plan / agent
  results / critic scores; surfaces approval buttons only when the run
  is in `awaiting_plan` or `awaiting_build`).
- Route `/builds`, Sidebar "Builds" entry, Header title map updated.

The BuildOrchestrator itself is untouched — 3d is pure wiring.

### Testing delta
- Python: +13 unit tests (`handlers/builds`) and +2 e2e round-trips in
  `test_main.py` — 133 sidecar tests total.
- Rust: proxy-only commands, no new tests (the existing 20 still pass
  against the enlarged handler list).
- Web: +7 `useBuilds` hook tests, +3 `StartBuildForm`, +3
  `BuildRunsTable`, +6 `BuildRunDetailView`, +1 App route — 112 vitest
  tests total.

## Phase 3b — YAML authoring (landed on `feature/sage-desktop-phase3d-next`)

Closes the last "can't do this without the web UI" gap: editing the
active solution's YAML triad (`project.yaml`, `prompts.yaml`,
`tasks.yaml`) live from the desktop app. The `/yaml` page reads the
current file through the sidecar and writes it back atomically, with
syntax validation before the file is touched.

- Two sidecar handlers (`yaml.read`, `yaml.write`) in
  `handlers/yaml_edit.py`. Only the three allowed filenames pass
  validation; unknown names → `-32602` (`InvalidParams`). The file-name
  check runs *before* the solution-wiring check so invalid params
  surface correctly even when no solution is active. On write,
  `yaml.safe_load` parses the incoming string; parse errors are
  translated to `InvalidParams` with the yaml library's message so the
  UI can render it verbatim.
- Two Tauri commands (`read_yaml`, `write_yaml`) — proxy-only, same
  `State<RwLock<Sidecar>>` read-lock pattern. No file I/O in Rust.
- React: `useReadYaml(file)` and `useWriteYaml()` (invalidates the
  read-query on success so the editor refreshes from disk after a
  save). The `YamlEdit` page has a file dropdown, a controlled
  textarea, and Save/Revert buttons; Save is disabled until the draft
  diverges from the loaded content.
- Route `/yaml`, Sidebar "YAML" entry, Header title map updated.

**Law 1 note.** User-driven edits deliberately bypass `ProposalStore`.
The web UI routes YAML edits through the proposal queue for audit
uniformity, but the desktop trust model treats a human typing in the
editor as the human's own action, not an agent proposal. The sidecar
still validates YAML syntax, so a bad parse can never damage the
solution. If an agent ever *suggests* a YAML change, it'll still go
through the approval path (`yaml_edit` proposal kind, unchanged).

### Testing delta
- Python: +10 unit tests (`handlers/yaml_edit`) and +2 e2e round-trips
  in `test_main.py` — 145 sidecar tests total.
- Rust: proxy-only commands, no new tests (20/20 still green).
- Web: +4 `useYamlEdit` hook tests, +3 `YamlEdit` page tests — 119
  vitest tests total.

## Phase 5b — Constitution authoring (landed on `feature/sage-desktop-phase5b`)

Exposes `src/core/constitution.py` through the sidecar so operators can
author per-solution principles, constraints, voice, and decision rules
without leaving the desktop app. The Constitution is what every agent's
system prompt is prepended with — the single highest-leverage
solution-level configuration in SAGE.

- Four sidecar handlers in `handlers/constitution.py`:
  `constitution.get`, `constitution.update`, `constitution.preamble`,
  `constitution.check_action`. The concrete `Constitution` instance is
  wired at startup by `_wire_handlers`; if the import fails the
  handlers degrade gracefully to typed `SidecarError` responses.
  `update` replaces the full state in memory, runs `validate()` before
  writing to disk, and reloads on failure so in-memory state never
  drifts past a rejected edit.
- Four Tauri commands (`constitution_{get,update,preamble,check_action}`)
  — proxy-only, same `State<RwLock<Sidecar>>` read-lock pattern.
- React: `useConstitution` (query), `useUpdateConstitution` (mutation,
  invalidates the query), `useCheckAction` (on-demand mutation). Seven
  domain components: `PrinciplesEditor`, `ConstraintsEditor`,
  `VoiceEditor`, `DecisionsEditor`, `PreamblePreview`, `ActionChecker`,
  `VersionHistoryList`. The `Constitution` page composes the editors
  left and preview/checker/history right; Save is disabled until the
  draft diverges from the loaded state.
- Route `/constitution`, Sidebar "Constitution" entry, Header title
  map updated.

**Law 1 note.** Operator-authored constitutions bypass the proposal
queue by the same rationale as Phase 3b YAML authoring. When an
*agent* proposes a constitution change, it still flows through the
existing `yaml_edit` proposal kind so the audit trail remains uniform.

### Testing delta
- Python: +13 unit tests (`handlers/constitution`) including a real
  `Constitution` round-trip — 158 sidecar tests total.
- Rust: proxy-only commands, no new tests.
- Web: +4 `useConstitution` hook tests, +5 `PrinciplesEditor`, +4
  `ConstraintsEditor`, +3 `ActionChecker`, +2 `Constitution` page, +1
  Sidebar entry — 133 vitest tests total.

## Phase 5c — Knowledge browser (landed on `feature/sage-desktop-phase5c`)

Exposes the active solution's `VectorMemory` (ChromaDB +
sentence-transformers, or the keyword fallback in minimal mode) through
the sidecar so operators can browse, search, add, and delete entries
without FastAPI. The vector store is SAGE's "compounding intelligence"
surface (Law 3) — making it visible is what turns it from a black box
into an inspectable training signal.

- Five sidecar handlers in `handlers/knowledge.py`:
  `knowledge.list`, `knowledge.search`, `knowledge.add`,
  `knowledge.delete`, `knowledge.stats`. `list` paginates at the
  sidecar (VectorMemory's `list_entries` has no offset) and clamps
  `limit` to `[1, 500]`; `search` clamps `top_k` to `[1, 50]`.
  `stats` reports `{total, collection, backend, solution}` with
  `llamaindex` mapped to `full` for the UI. The `VectorMemory`
  instance is wired at startup by `_wire_handlers`; if the import
  fails every handler degrades to a typed `SidecarError` so the UI
  can render a single disabled state.
- Five Tauri commands (`knowledge_{list,search,add,delete,stats}`) —
  proxy-only, same `State<RwLock<Sidecar>>` read-lock pattern.
- React: `useKnowledgeList` / `useKnowledgeSearch` / `useKnowledgeStats`
  queries plus `useAddKnowledge` / `useDeleteKnowledge` mutations
  (both invalidate `["knowledge"]` on success). Three domain
  components: `KnowledgeEntryRow` (collapse/expand, metadata tags,
  two-click delete confirm), `KnowledgeSearchResults` (ranked list
  with optional score), `AddKnowledgeForm` (textarea + metadata
  key/value pairs). The `Knowledge` page has Browse / Search tabs,
  shows a banner when `backend = minimal`, and keeps the add form
  permanently below the tabs.
- Route `/knowledge`, Sidebar "Knowledge" entry, Header title map
  updated.

**Law 1 note.** Operator-authored add/delete bypass the proposal
queue by the same rationale as Phase 3b YAML authoring and Phase 5b
Constitution. An *agent* that wants to add or delete a memory still
flows through the existing `STATEFUL` / `DESTRUCTIVE` proposal kinds
unchanged. The sidecar audit logger is not wired for this handler
by design: the web UI's approval path already writes to audit, and
the desktop edit is the operator's own action.

### Testing delta
- Python: +18 unit tests (`handlers/knowledge`) including a real
  `VectorMemory` round-trip in `SAGE_MINIMAL=1` mode — 176 sidecar
  tests total.
- Rust: proxy-only commands, no new tests.
- Web: +5 `useKnowledge` hook tests, +3 `KnowledgeEntryRow`, +2
  `AddKnowledgeForm`, +2 `Knowledge` page, +1 Sidebar entry — 152
  vitest tests total.

