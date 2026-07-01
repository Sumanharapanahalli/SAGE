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

**Two distinct namespaces, not one.** The frontend calls a flat-named
Tauri **command** (`invoke("list_pending_approvals", ...)`); that Rust
command proxies to a namespaced sidecar **RPC method**
(`approvals.list_pending`) over the NDJSON pipe. The two names are
usually related but never identical — the table below gives both, so
neither layer is ambiguous.

| Tauri command (React → Rust) | Sidecar RPC method (Rust → Python) | Purpose |
|---|---|---|
| `handshake` | `handshake` | Sidecar version / SAGE version / solution handshake |
| `get_status` | `status.get` | Health, LLM provider/model, pending-approvals count |
| `list_pending_approvals` | `approvals.list_pending` | Returns pending `Proposal[]` |
| `get_approval` | `approvals.get` | Fetch one proposal by `trace_id` |
| `approve_proposal` | `approvals.approve` | Mark approved; optional `decided_by`, `feedback` |
| `reject_proposal` | `approvals.reject` | Mark rejected; optional `decided_by`, `feedback` |
| `batch_approve` | `approvals.batch_approve` | Per-item outcome list; never aborts on one failure |
| `list_audit_events` | `audit.list` | Paginated audit events, filterable by `action_type` / `trace_id` |
| `get_audit_by_trace` | `audit.get_by_trace` | All events sharing a `trace_id` |
| `audit_stats` | `audit.stats` | Totals + `by_action_type` histogram |
| `list_agents` | `agents.list` | Core + custom roles with enrichment (event_count, last_active) |
| `get_agent` | `agents.get` | Single agent by name |
| `get_llm_info` | `llm.get_info` | Current provider name, model, and list of available providers |
| `switch_llm` | `llm.switch` | Runtime provider/model swap (framework control — no HITL) |
| `list_feature_requests` | `backlog.list` | List solution or framework feature requests, filterable by status/scope |
| `submit_feature_request` | `backlog.submit` | Create a new feature request; validates priority + scope |
| `update_feature_request` | `backlog.update` | Approve / reject / complete an existing request |
| `get_queue_status` | `queue.get_status` | Pending / in-progress / done / failed / blocked counts + parallel config |
| `list_queue_tasks` | `queue.list_tasks` | Paginated task list (≤50 by default), optional status filter |
| `analyze_run` | `analyze.run` | SURFACE → PROPOSE trigger (Phase 5d) — runs AnalystAgent, creates a real proposal |
| `switch_solution` | *(none — Rust-side action)* | Closes stdin, respawns the sidecar with `--solution-name`/`--solution-path`, re-handshakes; only the read side (`list_solutions`/`get_current_solution`) is a real RPC |

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

## Phase 5a — Collective Intelligence Browser (landed on `feature/sage-desktop-phase5a`)

**Route:** `/collective`
**RPC namespace:** `collective.*` (12 methods)
**Sidecar module:** `sidecar/handlers/collective.py`
**Python surface:** `src/core/collective_memory.py`

Three-tab page surfacing the git-backed cross-solution knowledge
sharing repo:

- **Learnings** — browse/search/publish/validate entries with
  solution/topic/tag filters. Pagination via `< Prev / Next >`.
- **Help Requests** — Open/Closed toggle, expertise filter;
  Claim / Respond / Close actions per card. Close requires a
  two-click confirm.
- **Stats** — counters (learnings, open help, closed help) plus
  topic and contributor histograms.

**Law 1 positioning:** operator validate/claim/respond/close/create
bypass the proposal queue (human-in-the-UI IS the approval).
`publish_learning` respects the framework's `require_approval`
flag: gated publishes return `{ gated: true, trace_id }` and the
UI displays "Submitted as proposal `<trace_id>`" instead of
"Published." Agent-authored publishes use the same gated path via
the existing `collective_publish` proposal kind.

**Git offline:** when the `CollectiveMemory` singleton reports
`_git_available = false`, the header shows "git: offline" in amber
and the Sync button is disabled. All other operations still work —
the Python layer writes YAML directly and skips the commit step.

**RPC methods:**
`list_learnings`, `get_learning`, `search_learnings`,
`publish_learning`, `validate_learning`, `list_help_requests`,
`create_help_request`, `claim_help_request`,
`respond_to_help_request`, `close_help_request`, `sync`, `stats`.

---

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

## Phase 5d — Analyze (the SURFACE -> PROPOSE trigger)

Prior phases let a desktop operator DECIDE (approvals) and COMPOUND
(knowledge, collective) but gave them no way to make an agent PROPOSE
something in the first place — `builds.start` / `onboarding.generate`
were the only work-creating RPCs, and neither writes to
`ProposalStore`, so the Approvals inbox had nothing an operator could
feed it. `analyze.run` closes that gap.

Unlike the legacy web `POST /analyze` — which stashes its result in an
in-memory `_pending_proposals` dict that only its own
`POST /approve/{trace_id}` branch reads, a second pending-item
mechanism disconnected from `ProposalStore` — the sidecar handler
wraps `AnalystAgent.analyze_log()` and persists the result as a REAL
`ProposalStore` proposal (`action_type="analysis"`,
`risk_class=INFORMATIONAL`). It flows through the already-verified
`approvals.list_pending` / `approve` / `reject` RPCs and the Approvals
page with no new inbox to build. A Python exception, or the analyst's
own `{"error": ...}` failure shape, raises `RPC_SIDECAR_ERROR` and
creates no proposal — no partial/garbage entries.

- One sidecar handler in `handlers/analyze.py`: `analyze.run`. Takes
  `{log_entry}`, requires non-empty. `_store` (the same `ProposalStore`
  instance `approvals.py` uses) and `_analyst_factory` (defaults to the
  real `AnalystAgent`, overridable for tests) are injected by
  `_wire_handlers`.
- One Tauri command, `analyze_run` — proxy-only, same
  `State<RwLock<Sidecar>>` read-lock pattern as every other command.
- React: `useAnalyzeLog` mutation hook (invalidates `["approvals"]` on
  success so the inbox refreshes immediately). The `Analyze` page is a
  plain button + multi-line textarea — deliberately not a
  `<form onSubmit>`, since Enter in a multi-line field should insert a
  newline, not submit. Shows the resulting proposal's description and a
  "View in Approvals" link on success.
- Route `/analyze`, Sidebar "Analyze" entry (first in the nav — it's
  the lean loop's SURFACE step, ahead of Approvals' DECIDE step),
  Header title map updated.

**Law 1 note.** `analyze.run` only *creates* a pending proposal — it
never executes or auto-approves anything. The human still approves or
rejects via the unchanged `approvals.*` RPCs.

### Testing delta
- Python: +7 unit tests (`handlers/analyze`) — 221 sidecar tests total.
- Rust: proxy-only command, no new tests; `cargo check` (full
  `desktop` feature build) verifies the wiring compiles.
- Web: +2 `useAnalyzeLog` hook tests, +3 `Analyze` page, +1 Sidebar
  entry — 183 vitest tests total.

## Phase 5e — Crash recovery (the documented-but-dead `respawn_with_backoff`, wired)

Previously: if the sidecar child process crashed mid-session (not via a
solution switch — an actual unexpected exit), the reader task drained
pending callers with `SidecarDown` and stopped. `respawn_with_backoff()`
already existed (1s/3s/9s policy) but had zero callers — the app stayed
permanently down until the operator switched solutions or restarted.

- `sidecar.rs` gained a `CrashHook = Arc<dyn Fn() + Send + Sync>`,
  deliberately Tauri-free so the module stays unit-testable under
  `cargo test --no-default-features`. `Sidecar::spawn_with_hook(cfg,
  Some(hook))` arms it; plain `Sidecar::spawn(cfg)` still passes `None`
  (unchanged for every existing caller/test). The reader task fires the
  hook exactly once, only when the child exits WITHOUT going through
  `replace_solution` first — an `Arc<AtomicBool>` (`shutting_down`) is
  set by `replace_solution` right before it closes stdin, so an
  intentional solution-switch respawn is never mistaken for a crash.
  `respawn_with_backoff` now threads the hook through so a *recovered*
  sidecar keeps the same crash-detection wired (single-shot: a second
  crash immediately after a successful recovery is not auto-retried —
  re-arming would need a self-referential `Arc<dyn Fn>`, not worth it
  for a double-fault edge case).
- The actual Tauri wiring — `make_crash_hook(handle, cfg)` — lives only
  in `lib.rs`'s `desktop`-feature-gated module: on crash it emits
  `sidecar-status: {online:false, reason}`, calls
  `respawn_with_backoff`, and on success swaps the fresh `Sidecar` into
  the managed `RwLock<Sidecar>` state (looked up lazily via
  `AppHandle::try_state`, so no chicken-and-egg with `handle.manage`
  happening after `Sidecar::spawn_with_hook` returns) and emits
  `{online:true}`. On backoff exhaustion it emits a final
  `{online:false, exhausted:true}` — the app stays *usable* even then,
  since every command already surfaces a recoverable `SidecarDown`; the
  operator just needs a manual solution switch or app restart.
- React: `useAppEvents` now also listens for `sidecar-status` and
  writes the payload into the `["sidecarStatus"]` query-cache slot
  (`useSidecarStatus` — a `useQuery` with `staleTime: Infinity` and no
  real fetch, purely an event-driven cache read so any component
  re-renders on a cache write). `SidecarStatusBanner` renders nothing
  while online, an amber "attempting to reconnect…" banner mid-backoff,
  and a red "restart the app or switch solutions" banner once
  exhausted. Mounted in `Layout.tsx`, always visible above the routed
  page content.

### Testing delta
- Rust: +3 tests in `sidecar.rs` (`on_crash_hook_fires_when_child_dies_unexpectedly`,
  `on_crash_hook_does_not_fire_during_replace_solution`, both against a
  REAL subprocess — force-killed directly vs. torn down via
  `replace_solution`) — 27 pure-Rust tests total. The `lib.rs`
  Tauri-wiring half (`make_crash_hook`, the event emission, the state
  swap) is `desktop`-feature-gated and verified via `cargo check`
  (compiles clean) rather than a unit test, matching this codebase's
  established precedent for Tauri-runtime-dependent code (Phase 1's
  `SAGE_ROOT`/spawn-failure fixes used the same split).
- Web: +2 `useSidecarStatus`, +1 `useAppEvents` (sidecar-status
  caching), +3 `SidecarStatusBanner` — 189 vitest tests total.

## Phase 5f — Compliance (the regulated-industry persona blocker)

The audit LOG (`audit.*`) was already on desktop — the tamper-evident
record of what happened. What was missing was periodic ASSESSMENT
tooling: domain checklists and gap analysis against IEC 62304 / 21 CFR
Part 11 / ISO 26262 / etc. Without it, a compliance operator could store
evidence but not check conformance — a blocker specifically for the
regulated-industry persona `desktop-gui.md`'s own rationale cites.

- Four sidecar handlers in `handlers/compliance.py`: `compliance.domains`,
  `compliance.flags`, `compliance.checklist`, `compliance.gap_assessment`.
  Unlike every other handler, `src.core.compliance_flags` is a pure,
  stateless module (a static domain → requirements dict + pure
  functions) — there is no store/instance to wire at startup, so these
  import it directly at call time. `risk_level` defaults to `"HIGH"`
  where the FastAPI route does the same; unknown domains raise
  `RPC_INVALID_PARAMS` with the valid-domains list.
- Four Tauri commands (`compliance_{domains,flags,checklist,gap_assessment}`)
  — proxy-only, same pattern as every other command.
- React: `useComplianceDomains` / `useComplianceChecklist` (query,
  `enabled` gated on a non-empty domain) / `useAssessComplianceGap`
  (mutation). The `Compliance` page: domain + risk-level selects
  (risk levels sourced from the selected domain's own `risk_levels`),
  the checklist's `required_task` items as checkboxes, and an "Assess
  conformance" button that strips the `TASK-` id prefix
  (`generate_compliance_checklist` builds ids as `f"TASK-{task}"`) back
  to the raw task-type strings `gap_assessment` expects, then shows the
  resulting compliance percentage and any blocking (HIL-required) gaps.
- Route `/compliance`, Sidebar "Compliance" entry, Header title map
  updated.

**Scope note.** `compliance_flags` computes against a *caller-supplied*
`completed_tasks` list (checked locally in the UI) — it is not wired to
automatically infer completion from the audit log. A future pass could
cross-reference `audit.list`/`audit.get_by_trace` to pre-check tasks the
audit trail already shows as done; out of scope for this pass.

### Testing delta
- Python: +11 unit tests (`handlers/compliance`) — 232 sidecar tests total.
- Rust: proxy-only commands, no new tests; `cargo check` verifies the wiring.
- Web: +4 `useCompliance` hook tests, +2 `Compliance` page, +1 Sidebar
  entry — 196 vitest tests total.

## Phase 5g–5k — the remaining SHOULD-tier roadmap items

Five more features landed together, built in parallel (five independent
agents, each producing only its own new leaf files — handler, Rust
command, hook, page — explicitly barred from touching the shared
registration files: `app.py`, `lib.rs`, `commands/mod.rs`, `App.tsx`,
`Sidebar.tsx`) and then wired into those five shared files sequentially
by hand afterward, verified with a fresh full `make test-desktop` run
at the end (312 sidecar / 26 Rust / 239 vitest, all green). `client.ts`
and `types.ts` were each edited concurrently by all five agents — every
agent re-read before writing and appended in a collision-safe spot;
`tsc --noEmit` came out clean (only the pre-existing, unrelated
`BuildRunDetailView.tsx` error) with no manual reconciliation needed.

### Phase 5g — Costs
`costs.{summary,daily,set_budget}` over `src.core.cost_tracker` +
`config.yaml`'s `llm.budgets.per_solution`. Route `/costs`, page shows
spend summary, a daily breakdown, and a budget-setting form.

### Phase 5h — Workflows
`workflow.{list_workflows,run,resume,status}` over
`src.integrations.langgraph_runner`. Route `/workflows` — list
available workflows, run one with an optional JSON initial-state
textarea (client-validated), track the most recent run's status with a
manual refresh, and resume a run paused at `awaiting_approval` with a
JSON feedback textarea. Deliberately excludes the Mermaid-diagram
discovery endpoints (`GET /workflows`, `GET /workflows/{solution}/{name}`
— a separate, lower-value visualization feature).

### Phase 5i — Skills & Tools
`skills.{list,set_visibility,reload}` + `mcp.tools` (kept in the `mcp.*`
namespace, not `skills.*`, since `mcp_registry` is a distinct singleton
from `skill_registry` — mirrors the web API's separate `/skills` vs
`/mcp` REST namespaces) over `src.core.skill_loader` and
`src.integrations.mcp_registry`. Route `/skills` — list skills with
inline visibility toggles (public/private/disabled), a reload button,
and a read-only MCP tools list. Framework control, not HITL-gated
(matches the web API's own "no approval needed" docstrings). Excludes
`POST /mcp/invoke` (arbitrary tool invocation — higher risk, a
follow-up) and the narrower `/skills/{name}`, `/skills/role/`,
`/skills/runner/`, `/skills/search`, `/runners*` endpoints.

### Phase 5j — Organization
`org.{get,update,reload}` over org.yaml. Route `/organization` — edit
identity fields (name/mission/vision/core_values) and view the
cross-team routes org.yaml is enriched with, read-only. Operator's own
direct action (same rationale as Phase 3b/5b), bypasses ProposalStore.
**Known gap, documented in the handler's own module docstring:**
`org.py` resolves org.yaml as `<SAGE_ROOT>/solutions/org.yaml`,
matching the web API's *default* (`_get_solutions_dir()`) but not
honoring a `SAGE_SOLUTIONS_DIR` env override the way the web API does —
the sidecar has no equivalent env-var wiring today. Excludes
channel/solution/route CRUD (`/org/channels`, `/org/solutions`,
`/org/routes` — 5-6 more endpoints, a follow-up).

### Phase 5k — Backlog planning
Extends the *existing* `/backlog` page rather than adding a new route.
New `backlog.plan` RPC: a SAGE-scope feature request opens a GitHub
issue (no LLM call, matches the web API's branch exactly); a
solution-scope request runs `PlannerAgent.create_plan()` and — like
Phase 5d's `analyze.run` — creates a REAL `ProposalStore` proposal
(`action_type="implementation_plan"`, `risk_class=STATEFUL`), so it
shows up immediately in Approvals. The "Generate Plan" button lives on
`FeatureRequestRow` (not `Backlog.tsx` itself), since each row needs
its own independent mutation/result state.

### Testing delta (all five, Phase 5g–5k combined)
- Python: costs +26, workflow +19, skills +10, org +18, backlog +7 —
  **312 sidecar tests total**.
- Rust: five new proxy-only command files (`costs.rs`, `workflow.rs`,
  `skills.rs`, `org.rs`, plus `plan_feature_request` added to the
  existing `backlog.rs`), no new tests; `cargo check` (full `desktop`
  feature) verifies the wiring — **26 pure-Rust tests total**
  (unchanged; none of this phase's logic is pure-Rust-testable).
- Web: costs +6, workflows +12, skills +9, org +8, backlog +4,
  Sidebar +4 nav-entry tests — **239 vitest tests total**.

## Phase 5l — Queue solution-isolation (last NICE-tier item; packaging deliberately deferred)

`get_task_queue(solution_name)` cached `TaskQueue` instances by name
alone, and every instance defaulted to the shared framework-global
`_DB_PATH` (`<repo>/data/audit_log.db`) — the opposite of
`ProposalStore` / `AuditLogger` / `FeatureRequestStore`, which all take
a real per-solution path. Two solutions' sidecar/web processes running
concurrently on one host would see each other's queued tasks.

`TaskQueue.__init__` already accepted a `db_path` constructor arg — the
bug was purely that `get_task_queue` never passed one through. Added an
optional `db_path` parameter (default `None` → unchanged behavior for
existing callers, e.g. api.py's cross-team task-routing path, which
intentionally wants the shared framework queue). The desktop sidecar's
`_wire_handlers` now passes `db_path=str(sage_dir / "queue.db")`, the
same `.sage/`-scoping pattern as everything else it wires. **Web API
untouched** — its general queue-status endpoints read the module-level
`task_queue` singleton directly, not `get_task_queue`, so this was a
desktop-only fix with zero risk to the FastAPI interface.

### Testing delta
- Python (framework): +3 tests in `tests/test_queue_manager.py`
  (`get_task_queue` — explicit db_path, no-path backward compat, and a
  direct two-solution isolation proof: submit to A, assert B sees 0).
- Python (sidecar): +1 end-to-end wiring test in `test_main.py`,
  verified genuinely red-then-green by reverting the one-line fix and
  re-running before restoring it — asserts driving the sidecar for a
  solution creates that solution's own `.sage/queue.db` — **313
  sidecar tests total**.

## Phase 5m — Monitor, Goals, Agent Performance (a scoped slice of the peripheral tail)

Rather than build the entire "monitoring/streaming/peripheral tail" NICE
item in one pass (it bundles ~8 unrelated subsystems), this picks the
three that fit the desktop's existing RPC/page pattern cleanly. Deferred,
with reasons: Eval/HIL (a whole substantial subsystem — suites, runs,
history, HIL sessions — deserves its own round), Integrations/Connectors
(Composio's OAuth-redirect connect flow doesn't map onto a plain
request/response desktop RPC), Distillation (niche), Auth (already
flagged correctly low-priority in the original review — desktop is
single-operator), and streaming (`/logs/stream` etc — the most
architecturally different piece; already an accepted Phase-1 limitation
per this doc).

**Monitor** (`/monitor` route, `monitor.status` + `monitor.scheduler_status`
RPC): ports `GET /monitor/status` and `GET /scheduler/status`. Both
degrade gracefully on any exception — mirroring the web API's own
behavior — returning `{"running": false, "error": ...}` rather than an
RpcError, since an idle monitor/scheduler is a normal desktop state, not
a failure; the page renders that as a plain "Not active" line, not an
error banner.

**Goals** (`/goals` route, `goals.{list,create,get,update,delete}` RPC):
ports the `/goals` CRUD. **Scope note, deliberate divergence from the web
API**: the web API's `_get_goals_store()` resolves `goals.db` next to the
shared framework-global audit-log path; the sidecar instead wires
`goals.db` inside this solution's own `.sage/` directory, matching every
other per-solution store (the same reasoning as Phase 5l's queue fix).
Single-operator desktop, so `user_id` defaults to `"desktop-operator"`
consistently across create/list so goals don't become invisible to the
default list query (`GoalsStore.list()` filters on exact `user_id`
equality, no "unset = match all").

**Agent Performance** (extends the existing `/agents` page and
`agents.*` RPC namespace — no new route): adds `agents.performance`,
porting `GET /agents/{role_key}/performance`'s exact query and
approve/reject classification over `compliance_audit_log`, including its
graceful degrade-to-zero-stats-on-query-failure behavior. `AgentCard`
gained an optional `onSelect`/`selected` prop rather than fetching its
own data, since its existing test file renders it with no query client.

### Testing delta
- Python (sidecar): monitor +8, goals +19, agents +4 — **344 sidecar
  tests total**.
- Rust: `monitor.rs` (2 commands), `goals.rs` (5 commands), one addition
  to the existing `agents.rs` — proxy-only, no new tests; `cargo check`
  (full `desktop` feature) verifies the wiring — **26 pure-Rust tests
  total** (unchanged).
- Web: `useMonitor`+`Monitor` +9, `useGoals`+`Goals` +9, `useAgents`+
  `Agents` +5, Sidebar +2 nav-entry tests — **264 vitest tests total**.

## Phase 5n — Eval (Agent Gym suite runner)

Ports `GET /eval/suites`, `POST /eval/run`, `GET /eval/history` — score
agent quality against the active solution's `evals/*.yaml` catalog
without leaving the app. `/eval` route, `eval.{list_suites,run,history}`
RPC. HIL (Hardware-in-the-Loop) was explicitly split off, not built here
— it connects to real physical transports (serial/J-Link/CAN/OpenOCD),
generates regulatory evidence reports, and deserves its own deliberately
scoped round rather than being rushed through the same pattern as a
routine CRUD/read port.

Same per-solution-isolation pattern as Phase 5l (queue) / 5m (goals):
`EvalRunner` already accepted a `db_path` constructor arg, so
`eval_runs.db` is wired inside this solution's own `.sage/` directory
rather than the framework-shared `data/eval_results.db` the web API's
global `eval_runner` singleton uses.

**A real correctness bug found and fixed along the way, not just a
scope note**: `eval_runner._get_evals_dir()` (and, it turns out,
`langgraph_runner._get_workflows_dir()`) read the framework-*global*
`src.core.project_loader.project_config` singleton directly — not an
injectable instance like the `ProjectConfig(solution_name)` that
`agents.py`/`status.py` already receive. That singleton is constructed
at import time from `SAGE_PROJECT`/auto-discovery, never from this
sidecar's `--solution-name`, so eval suite listing (and workflow
listing) was silently resolving whatever solution happened to be
auto-discovered — not necessarily the sidecar's actual active solution.
Fixed by having `_wire_handlers` call `project_config.reload(solution_name)`
in addition to constructing the locally-injected `ProjectConfig` — safe,
since each sidecar process serves exactly one solution for its whole
lifetime. This incidentally fixed workflow listing too (Phase 5h),
which had the identical latent bug; `test_workflow.py`'s
"no workflows loaded" test previously passed only by accident (no test
in the suite had ever correctly reloaded the global singleton) and
needed updating to force a known-nonexistent solution name rather than
relying on incidental global state.

### Testing delta
- Python (sidecar): eval +11, plus 1 new end-to-end wiring test in
  `test_main.py` proving `project_config.reload()` fires correctly —
  **356 sidecar tests total**.
- Rust: `eval.rs` (3 commands), proxy-only, no new tests; `cargo check`
  (full `desktop` feature) verifies the wiring — **26 pure-Rust tests
  total** (unchanged).
- Web: `useEval` +3, `Eval` page +5, Sidebar +1 nav-entry test — **273
  vitest tests total**.

## Phase 5o — HIL (Hardware-in-the-Loop)

Ports `GET /hil/status`, `POST /hil/connect`, `POST /hil/run-suite`,
`GET /hil/report/{session_id}` — connect to real hardware transports
(serial/J-Link/CAN/OpenOCD/mock), run test suites against them, and
generate regulatory evidence reports (IEC 62304 / DO-178C / EN 50128 /
ISO 26262 / IEC 62443). `/hil` route, `hil.{status,connect,run_suite,
report}` RPC.

**Scope, deliberately narrower than the runner class**:
`HILRunner.flash_firmware()` exists in `src/integrations/hil_runner.py`
but has no endpoint anywhere in the web API either — not ported here,
for the same reason every other feature in this session mirrors the
existing API surface rather than inventing a new one. Firmware flashing
stays unreachable from both interfaces. Reading the runner also showed
the real-hardware execution path (`_execute_on_hardware`) is only
implemented for serial and CAN — J-Link/OpenOCD `connect()` runs a real
but read-only subprocess probe, and `run_suite` against those two
transports reports BLOCKED rather than touching hardware. The actual
risk surface for this port is "send a test-trigger command over
serial/CAN and read the response" — the normal, intended shape of a HIL
test, not a uniquely dangerous action needing guardrails beyond what
the web API itself already has (none).

**Safety-by-construction, not a bolt-on**: connecting to a transport
that can spawn a subprocess (JLinkExe/openocd) or open a real
serial/CAN handle is always an explicit operator action — `hil.status`
is the only auto-firing query; `connect`, `run_suite`, and `report` are
all gated behind a button click (mutations never auto-fire under
TanStack Query; the report query is additionally gated on a
`reportRequested` flag set only by its own button). The transport
selector conditionally renders only the config fields that transport
actually uses (port/baud for serial; device/serial-number/speed for
J-Link; interface/channel/bitrate for CAN; a single config-file path
for OpenOCD) rather than one generic JSON blob, since — unlike
Workflows' single opaque initial-state object — these are five
genuinely different, well-known config shapes worth surfacing as real
fields.

### Testing delta
- Python (sidecar): hil +12 (module-level singleton pattern like
  workflow.py/compliance.py — `_hil_runner` reset around every test to
  avoid cross-test leakage) — **368 sidecar tests total**.
- Rust: `hil.rs` (4 commands), proxy-only, no new tests; `cargo check`
  (full `desktop` feature) verifies the wiring — **26 pure-Rust tests
  total** (unchanged).
- Web: `useHil` +5, `Hil` page +6, Sidebar +1 nav-entry test — **285
  vitest tests total**.

