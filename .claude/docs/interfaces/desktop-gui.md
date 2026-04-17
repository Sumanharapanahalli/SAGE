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

---

## Phase 4.5 — Cross-platform packaging

Phase 4.5 extends Phase 4's Windows-only release pipeline to also
produce installable macOS and Linux artifacts from the same source
tree. No feature changes — strictly packaging.

### Deliverables

- **Sidecar target matrix** — `resolve_sidecar_path()` (src-tauri/src/sidecar.rs)
  now probes six candidate filenames before falling back to the dev
  entrypoint:
  - `sage-sidecar-x86_64-pc-windows-msvc.exe`
  - `sage-sidecar-aarch64-pc-windows-msvc.exe`
  - `sage-sidecar-x86_64-apple-darwin`
  - `sage-sidecar-aarch64-apple-darwin`
  - `sage-sidecar-x86_64-unknown-linux-gnu`
  - `sage-sidecar-aarch64-unknown-linux-gnu`
  The per-triple candidate order is driven by `cfg!()` so a native
  build picks its own exe first. `SUPPORTED_SIDECAR_TRIPLES` is a
  public const so the release workflow and drift-guard tests share
  one source of truth.
- **Tauri bundle targets** — `tauri.conf.json.bundle.targets`
  extended from `["msi", "nsis"]` to include `"app"`, `"dmg"`,
  `"appimage"`, `"deb"`. Tauri picks the relevant subset per host at
  build time.
- **Portable build script** — `scripts/build-sidecar.sh` detects the
  host's `.venv` layout (Scripts/ vs bin/) and emits the correct
  extension-less executable on POSIX (Windows still writes `.exe`).
- **Expanded release workflow matrix** —
  `.github/workflows/sage-desktop-release.yml` adds `macos-13`
  (Intel), `macos-latest` (Apple Silicon), and `ubuntu-latest` (x64
  AppImage + .deb) runners alongside the existing Windows job. Each
  runner builds PyInstaller, stages the triple-named sidecar under
  `src-tauri/bin/`, sets the POSIX execute bit, then runs Tauri with
  its own `bundle_targets` set. Linux additionally installs
  `libwebkit2gtk-4.1-dev` + `libappindicator3-dev` + `patchelf` so
  Tauri 2 + AppImage can build on a stock Ubuntu image.
- **Updater manifest cross-arch** — `scripts/generate-latest-json.py`
  now distinguishes `darwin-x86_64` vs `darwin-aarch64` and
  `linux-x86_64` vs `linux-aarch64` by scanning bundle filenames for
  an `aarch64`/`arm64` marker (Tauri embeds the arch into the DMG /
  AppImage stem by default). The Windows key stays `windows-x86_64`
  until a Windows-on-ARM build is added to the matrix.

### Testing delta (on top of Phase 4)

- Rust: +2 tests in `sidecar.rs` (`supported_triples_covers_six_platforms`,
  `sidecar_path_picks_up_native_triple_when_bundled`) guarding the
  target-triple matrix.
- Python: +14 tests in `test_latest_json.py` parametrizing every
  Tauri bundle filename pattern through `_detect_platform()` +
  `build_manifest()`.

### Distribution caveats (Phase 4.5)

- **No trusted-CA code signing yet.** Gatekeeper (macOS) and
  SmartScreen (Windows) both raise a first-launch warning. AppImage
  needs `chmod +x` to run. Trusted signing moves to Phase 4.6.
- **Linux deps.** `.AppImage` is self-contained; `.deb` expects
  `libwebkit2gtk-4.1` to be available via apt.
- **macOS universal binary.** The matrix produces two separate DMGs
  (Intel + Apple Silicon), not a universal binary — that's a Phase
  4.6 optimization.

---

## Phase 4.6 — Code signing hooks + telemetry uploader + background update

Phase 4.6 closes the deferred transport and signing work that Phase 4
and 4.5 explicitly punted on. No new user-visible UI — existing
Settings panels gain new capabilities; everything remains opt-in.

### Deliverables

- **Telemetry HTTPS uploader** — `flush_buffer()` in
  `sidecar/handlers/telemetry.py` reads the local JSONL buffer,
  defensively re-filters every row through the PII allowlist (so a
  tampered buffer file can't smuggle banned keys past the wire), and
  POSTs a `{"events": [...]}` JSON body to
  `$SAGE_TELEMETRY_ENDPOINT`. 2xx → buffer truncated; anything else
  → buffer preserved for retry. Consent is **re-gated at flush
  time** (`if not config.enabled: return opted_out`) so "I opted
  out" always wins the race against in-flight buffered events. No
  destination is hardcoded; the env var is deliberately off-disk so
  a malicious `config.json` can never redirect the feed. Exposed as
  RPC `telemetry.flush` → Tauri command `telemetry_flush` → React
  hook `useFlushTelemetry`.
- **Background update probe on launch** — `lib.rs::setup` spawns a
  second async task (after a 3s warm-up so the sidecar gets first
  crack at the runtime) that calls `probe_update(&AppHandle)` and
  emits the `UpdateStatus` as a `update-check-result` Tauri event.
  The frontend UpdatePanel already knows how to render that status,
  so the only wiring needed is a listener. Opt-out via env var
  `SAGE_SKIP_BG_UPDATE` for CI and offline dev loops. The manual
  `Check for updates` button still works; it now shares the same
  `probe_update` helper.
- **Code-signing scaffolding** — The release workflow now threads
  trusted-CA signing secrets into `tauri build`:
  - Windows: `TAURI_WINDOWS_SIGNING_CERTIFICATE_THUMBPRINT` +
    `WINDOWS_CODESIGN_TOOL` (for EV cert via signtool or Azure
    Code Signing).
  - macOS: `APPLE_CERTIFICATE`, `APPLE_CERTIFICATE_PASSWORD`,
    `APPLE_SIGNING_IDENTITY`, plus `APPLE_ID`, `APPLE_PASSWORD`,
    `APPLE_TEAM_ID` for notarytool.
  When the secrets are missing (PRs from forks, dev tags), the
  build falls back to the Phase 4.5 unsigned path so contributors
  don't need production certs to ship a test release.

### Testing delta

- Python: +9 tests in `test_telemetry.py` covering `flush_buffer`:
  opt-out re-gate, missing endpoint, empty buffer, 2xx truncation,
  non-2xx retention, network-error resilience, defensive re-filter,
  env-var fallback, and the `telemetry.flush` RPC shim.
- Rust: no new tests — `probe_update` shares its logic with
  `check_update` which is already exercised via `update_status.rs`
  tests; the setup hook firing is an integration-only concern.
- Web: +2 tests in `hooks/useTelemetry.test.ts` covering
  `useFlushTelemetry` success and opt-out paths.

### Privacy invariants preserved

- The allowlist is enforced **twice**: at `record()` time (when the
  event lands on disk) and at `flush_buffer()` time (when it leaves
  the device). Adding a key to the allowlist remains the only way
  for a field to reach the wire.
- `session_id` values still never persist in `config.json`;
  `flush_buffer` preserves the ones already stamped on buffered
  events but does not mint new ones.
- Opting out still wipes the local buffer immediately.

---

## Phase 4.7 — Playwright pixel-diff for 4 canonical pages

Phase 4.7 replaces the vitest DOM-snapshot layer from Phase 4 with
actual image-pixel regression for the four high-churn canonical
pages: **Approvals, Builds, Audit, YAML**. DOM snapshots stay as a
fast local check; pixel-diff runs as a nightly CI gate.

### Deliverables

- **Playwright config** — `sage-desktop/playwright.config.ts` runs
  Chromium against `npm run dev` (port 1420), snapshots to
  `playwright/snapshots/`, 0.2% pixel-diff tolerance (accommodates
  font-rendering jitter across CI runners without masking real
  drift).
- **Tauri invoke() mock** — `playwright/fixtures/mock-sidecar.ts`
  stubs `window.__TAURI_INTERNALS__.invoke` so every page renders
  canned, deterministic data without a real sidecar or packaged
  app. Defaults cover status/handshake/queue/audit/approvals/etc;
  individual specs can override per-command.
- **Four canonical specs** — `approvals.spec.ts`, `builds.spec.ts`,
  `audit.spec.ts`, `yaml.spec.ts`. Each loads the route, waits for
  its heading/body text, and calls `toHaveScreenshot(...)`.
- **Drift-guard** — vitest test in
  `src/__tests__/e2e-config.test.ts` asserts the config, the
  fixture, and all four spec files exist + reference
  `toHaveScreenshot` + their route. This runs in the default
  `npm test` so structural breakage fails fast without needing
  Playwright installed locally.
- **CI wiring** — `sage-desktop-mutation.yml` gains a
  `playwright-visual` job that runs `npm run test:visual` on
  ubuntu-latest with a pinned Chromium. Non-blocking: mismatches
  surface as warnings with the full playwright report uploaded as
  an artifact so the PR author can inspect + refresh baselines.

### Running locally

```bash
# One-time: install Chromium into ~/.cache/ms-playwright
npx playwright install chromium

# Run the suite against the dev server
npm run test:visual

# Refresh baselines after an intentional UI change
npm run test:visual:update
```

### Why four pages (not all eight)

The eight primary pages exist, but Approvals/Builds/Audit/YAML are
where the visual churn lives. Status/Agents/Onboarding/Backlog have
barely changed visually since Phase 2 and don't justify the
per-runner screenshot maintenance cost yet. Adding a page is two
new files (`*.spec.ts` + its committed baseline); the infrastructure
is designed to scale to all eight when the churn justifies it.

