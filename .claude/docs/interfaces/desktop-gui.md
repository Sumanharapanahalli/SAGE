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

---

## Phase 4 — Packaging & Polish (landed on `feature/sage-desktop-phase4`)

Phase 4 makes sage-desktop distributable. Until Phase 4 the only way to
run it was `make desktop-dev`, which assumes the SAGE repo is cloned
locally and Python deps installed. Phase 4 produces a signed,
installable Windows MSI (plus NSIS fallback) so an end-user can go
from "download" to "running" without any clone, Python install, or
admin privileges.

### Deliverables

- **PyInstaller sidecar bundle** — `sage-sidecar-x86_64-pc-windows-msvc.exe`,
  a single self-contained exe that embeds CPython 3.12 + the sidecar +
  every `src/` import it needs. Rust's `sidecar_path` resolution picks
  the bundled exe when the Tauri resource dir exists, otherwise falls
  back to dev-mode `python app.py`. Built via `make desktop-bundle`.
- **Windows MSI** — WiX-based, per-user (`INSTALLSCOPE=perUser`), no
  admin prompt, installs to `%LOCALAPPDATA%\Programs\sage-desktop\`.
  Built via `make desktop-msi`.
- **NSIS fallback** — Same payload as MSI, NSIS target, for
  environments where MSI execution is policy-restricted. Built via
  `make desktop-nsis`.
- **Auto-update** — Tauri updater plugin + ed25519 signed releases.
  Settings → "Application updates" panel: idle / checking / up-to-date
  / available (with release notes) / error. Manual check; background
  check on launch deferred to Phase 4.6. Release manifest
  (`latest.json`) generated by `scripts/generate-latest-json.py`.
- **Offline pip cache** — `scripts/build-offline-cache.sh` +
  `scripts/install-offline.sh` for air-gapped dev onboarding. Wheels
  land under `sage-desktop/offline/wheels/`, install uses
  `pip install --no-index --find-links ...`. Not user-facing.
- **tauri-driver E2E** — WebdriverIO 9 + tauri-driver against the
  packaged `.exe`. 8 spec modules (approvals, agents, audit, status,
  builds, yaml, onboarding, backlog) exercised through the real IPC
  path. Run via `npm run test:e2e:tauri` (requires tauri-driver + the
  built exe; non-blocking in CI).
- **Mutation + visual regression** — `cargo-mutants` on the Rust
  `errors.rs` / `rpc.rs` / `sidecar.rs` / `update_status.rs` layer
  (make target `desktop-mutate-rs`). Stryker on `src/hooks/*.ts` via
  `.stryker.conf.json` (nightly cron, not per-PR). Visual regression
  ships as vitest DOM snapshots (`src/__tests__/visual/snapshots.test.tsx`)
  for four canonical empty-state pages — lightweight drift guard; the
  pixel-diff Playwright layer is scaffolded but not wired to CI yet.
- **Telemetry (opt-in, default OFF)** — A minimal event stream with a
  strict PII allowlist. Two RPCs: `telemetry.get_status` (returns
  `enabled`, anon UUID, allowed events, allowed fields) and
  `telemetry.set_enabled(bool)`. Settings → "Telemetry" panel shows a
  checkbox, the anon ID, and an expandable "What gets sent?" disclosure
  listing the full allowlist. See `docs/PRIVACY.md` for the contract.

### File structure delta

```
sage-desktop/
├── sidecar/
│   ├── sage-sidecar.spec                NEW — PyInstaller spec
│   ├── handlers/telemetry.py            NEW — allowlist + record/filter
│   └── tests/test_telemetry.py          NEW — 11 tests
├── src-tauri/
│   ├── src/update_status.rs             NEW — feature-agnostic enum
│   ├── src/commands/updates.rs          NEW
│   ├── src/commands/telemetry.rs        NEW
│   ├── tauri.conf.json                  MODIFY — externalBin, updater.pubkey
│   └── keys/sage-desktop.pub            NEW — updater pubkey (committed)
├── src/
│   ├── hooks/useUpdate.ts               NEW
│   ├── hooks/useTelemetry.ts            NEW
│   ├── components/domain/UpdatePanel.tsx       NEW
│   ├── components/domain/TelemetryPanel.tsx    NEW
│   ├── pages/Settings.tsx               MODIFY — +Updates, +Telemetry
│   └── __tests__/visual/snapshots.test.tsx     NEW — 4 DOM snapshots
├── e2e/
│   ├── tauri-driver.config.mjs          NEW
│   └── specs/*.spec.mjs                 NEW — 8 modules
├── scripts/
│   ├── build-sidecar.sh                 NEW — PyInstaller wrapper
│   ├── build-offline-cache.sh           NEW — pip download + SHA-256 manifest
│   ├── install-offline.sh               NEW — pip install --no-index
│   ├── generate-keypair.sh              NEW — ed25519 keygen
│   ├── sign-release.sh                  NEW — ed25519 sign MSI/NSIS
│   └── generate-latest-json.py          NEW — updater feed manifest
└── .stryker.conf.json                   NEW

.github/workflows/
├── sage-desktop-release.yml             NEW — tag-triggered release
└── sage-desktop-mutation.yml            NEW — weekly cron + PR

docs/
└── PRIVACY.md                           NEW — telemetry contract
```

### Telemetry contract (strict)

- **Default OFF.** Consent is a local checkbox; no events ever leave the
  device until the user flips it.
- **Allowed events** (frozenset, enforced in `handlers/telemetry.py`):
  `approval.decided`, `build.started`, `build.completed`,
  `solution.switched`, `onboarding.generated`, `update.checked`,
  `update.installed`, `llm.switched`.
- **Allowed fields** (frozenset): `event`, `kind`, `status`,
  `action_type`, `route`, `duration_ms`, `count`, `ok`, `error_kind`.
- **Guaranteed NOT sent**: proposal content, trace_ids, user email,
  solution name, file paths, raw prompts, LLM outputs, stack traces.
  `filter_payload()` builds a fresh dict containing only allowlisted
  keys — unknown keys are dropped by construction.
- **Identifiers**: a persisted anonymous UUID (kept when you opt out so
  re-opting-in isn't counted as a new user) plus a per-launch
  `session_id` UUID that never touches disk.
- **Storage**: `%APPDATA%\sage-desktop\config.json` (consent +
  `anon_id`), `%APPDATA%\sage-desktop\telemetry.ndjson` (event buffer,
  flushed on next online). Opting out clears the buffer.

### Testing delta
- Python: +11 `test_telemetry.py` + +6 `test_offline_cache.py` (1
  skipped on Win32 due to bash path semantics) — 163 sidecar tests.
- Rust: +7 `update_status` + existing stack — 27 tests under
  `cargo test --lib --no-default-features` (no WebView2 required).
- Web: +11 `UpdatePanel`/`useUpdate` + +11 `TelemetryPanel`/`useTelemetry`
  + 4 visual-snapshot + 3 e2e-config drift-guard — 140 vitest tests.
- E2E (WebdriverIO + tauri-driver): 8 spec files; not part of the
  default `npm test` run (requires the packaged exe + tauri-driver).

### Distribution caveats

- **SmartScreen**: Phase 4 ships unsigned installers (EV cert deferred
  to Phase 4.6). First-time users see "Windows protected your PC" — the
  expected flow is "More info" → "Run anyway". The README.md walks
  through this.
- **Updater signatures**: every release is signed with the ed25519 key
  whose `.pub` counterpart is committed at
  `sage-desktop/src-tauri/keys/sage-desktop.pub`. An unsigned or
  wrongly-signed update never installs — the Tauri updater refuses.
- **No backend**: telemetry uploader is not wired in Phase 4. Events
  buffer locally; the HTTPS POST transport is Phase 4.6. That means
  Phase 4 ships *no* network egress from the installed app by default.

