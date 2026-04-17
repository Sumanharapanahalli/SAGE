# sage-desktop Phase 4 — Packaging & Polish

**Date:** 2026-04-17
**Branch:** `feature/sage-desktop-phase4` (off `main`)
**Status:** Design

---

## 1. Why Phase 4

After Phase 1 → 3d, `sage-desktop` is functionally complete: a user can
onboard a new solution, edit its YAML triad, drive the BuildOrchestrator,
and approve/reject proposals — all without FastAPI. The app runs via
`make desktop-dev`, which launches Vite + Rust + spawns Python from source.

Phase 4 is what makes the app **distributable**. Until Phase 4 lands,
the only way to use sage-desktop is to clone the repo, install Python
deps, and run the dev loop. That's acceptable for SAGE contributors
but unusable for the end-user who just wants to ship a yoga app.

Phase 4 delivers a signed, installable binary that anyone on Windows
can install, launch, and auto-update — with no Python, no npm, no
repo clone required. It also hardens the test story (E2E, mutation,
visual regression) so we ship with confidence.

---

## 2. Scope

### 2.1 In-scope

1. **Sidecar bundling** — The Python sidecar (`sage-desktop/sidecar/`)
   plus its framework dependency (`src/`) is packaged as a single
   self-contained executable via **PyInstaller**. The Rust side spawns
   this executable in production; in dev, it still spawns source
   Python via the existing mechanism.

2. **Tauri externalBin wiring** — `tauri.conf.json` declares the
   bundled sidecar as an `externalBin`. The Rust `Sidecar::spawn`
   resolution logic chooses between dev-mode source Python and
   production-mode bundled binary based on `tauri::Env::resource_dir()`
   availability.

3. **Windows MSI installer** — WiX-based MSI, **non-admin** per-user
   install target (`INSTALLSCOPE=perUser`). No elevated prompts. The
   MSI embeds the Tauri binary + sidecar + icons.

4. **NSIS fallback installer** — Same payload as MSI, NSIS target,
   for environments where MSI execution is restricted (some corporate
   Windows policies). NSIS is also non-admin.

5. **Auto-update mechanism** — Tauri updater plugin. Release manifest
   (JSON) published alongside release artifacts; app checks at launch
   + on manual trigger from Settings. **Signed** updates only (TUF-ish
   signature verification via the updater's built-in ed25519 pubkey
   flow).

6. **Offline pip cache** — The bundled sidecar via PyInstaller is
   already offline-capable (no runtime pip needed). But for developer
   onboarding in air-gapped environments, we also ship a
   `sage-desktop/sidecar/wheels/` directory populated by
   `pip download -r requirements.txt`, plus a `make sidecar-wheels`
   target. Not user-facing; infra for contributors.

7. **Full tauri-driver E2E suite** — Expand
   `sage-desktop/tests/e2e/smoke.rs` into a suite covering every Phase
   1–3d page with real sidecar subprocess: approvals approve/reject,
   agent list, audit filter, status tiles, builds start → approve,
   yaml edit round-trip, onboarding wizard submit, backlog row
   promote.

8. **Mutation + visual regression** — `cargo-mutants` for the Rust
   RPC/errors layer, `stryker-mutator` for the TS hooks, Playwright
   snapshot-diff for four canonical pages (Approvals, Builds, Audit,
   YAML). All run in CI on PR but not on every local test pass.

9. **Telemetry (opt-in)** — A minimal event stream (page views,
   command invocations, error codes only — no content, no PII).
   **Disabled by default**; user explicitly opts in from Settings.
   Transport: HTTPS POST to `telemetry.sage.dev/events` (placeholder
   — user configurable). Local disk buffer for offline.

### 2.2 Out of scope

- **macOS / Linux packaging** — Windows is the only target for Phase
  4. macOS .app + notarization and Linux AppImage land as a Phase 4.5
  later if demand materializes.
- **Code signing of the MSI itself** — Requires an EV cert the repo
  doesn't have. Phase 4 ships an **unsigned** MSI with a clear
  README.md caveat ("SmartScreen warning expected; click 'More info'
  → 'Run anyway'"). Code signing lands in Phase 4.6 when a cert is
  procured.
- **Windows Store (MSIX)** — Out of scope.
- **Telemetry backend** — We ship the client only; the backend
  endpoint is left as config. An actual collector is a separate
  project.
- **Internationalization** — English only. i18n is a future phase.
- **Accessibility audit** — ARIA attributes are in place (we've been
  using them since Phase 1) but no formal WCAG audit in Phase 4.

---

## 3. Architecture

### 3.1 Packaging topology

```
sage-desktop/
├── sidecar/                          (source, dev mode)
│   ├── app.py
│   ├── handlers/
│   ├── requirements.txt
│   └── wheels/                       (Phase 4.5 — offline pip cache)
├── src-tauri/
│   ├── bin/
│   │   └── sage-sidecar-x86_64-pc-windows-msvc.exe   (Phase 4.1 artifact)
│   ├── tauri.conf.json               (externalBin + updater config)
│   └── src/sidecar.rs                (dev vs prod path resolution)
├── dist/                             (Vite build output, from npm run build)
└── target/release/bundle/
    ├── msi/SAGE Desktop_0.2.0_x64_en-US.msi    (Phase 4.2 artifact)
    └── nsis/SAGE Desktop_0.2.0_x64-setup.exe   (Phase 4.3 artifact)
```

### 3.2 Sidecar bundling strategy

**Decision: PyInstaller one-file over alternatives.**

Alternatives considered:
- **Nuitka** — true compilation, smaller binary, but Python
  extension-module compat is brittle with ChromaDB/onnxruntime. Rejected.
- **pex** — Python-specific zipapp, requires Python runtime on target.
  Rejected (we're targeting users without Python).
- **shiv** — same as pex, requires Python. Rejected.
- **PyOxidizer** — embeds CPython statically; was a candidate but the
  project is archived (2024-11). Rejected.
- **PyInstaller --onefile** — mature, handles dynamic imports
  correctly if given a `.spec` file, produces single-exe. **Chosen.**

PyInstaller `.spec` file (`sage-desktop/sidecar/sage-sidecar.spec`)
declares hidden imports for SAGE framework modules
(`src.integrations.*`, `src.core.*`, `src.agents.*`) and bundles
YAML + SQLite + requests. Build output: one `.exe` ≈ 40–80 MB.

**Dev vs prod path resolution** (in `src-tauri/src/sidecar.rs`):

```rust
fn sidecar_path(app: &AppHandle) -> PathBuf {
    // Production: Tauri resource dir contains externalBin binary
    if let Ok(dir) = app.path().resource_dir() {
        let exe = dir.join("sage-sidecar-x86_64-pc-windows-msvc.exe");
        if exe.exists() { return exe; }
    }
    // Dev: env override or workspace-relative fallback
    if let Ok(p) = std::env::var("SAGE_SIDECAR_PATH") {
        return PathBuf::from(p);
    }
    PathBuf::from("..").join("sidecar").join("app.py")  // spawned via python
}
```

The `spawn` function branches on whether `sidecar_path` ends in `.py`
(run via python) or `.exe` (run directly).

### 3.3 Auto-update flow

```
Launch
   │
   ▼
check_update() (Settings "Check for updates")
   │
   ▼
HTTP GET <updater_url>/releases/latest.json
   │
   ▼
Response: { version, notes, pub_date, platforms: { "windows-x86_64": { signature, url } } }
   │
   ▼
Compare semver(response.version) vs APP_VERSION
   │
   ├── higher?  → prompt user → download MSI → verify ed25519 sig → replace + restart
   └── same?    → "Up to date"
```

Signing keypair lives out-of-tree; CI signs release artifacts. The
public key is baked into the binary via `tauri.conf.json.plugins.updater.pubkey`.

### 3.4 Telemetry data model

```
Event {
  event_id: uuid4
  timestamp: ISO8601
  session_id: uuid4 (per-launch, not persistent)
  event_type: "page_view" | "command_invoke" | "error"
  payload: {
    // page_view
    path?: string           // "/approvals", "/builds", etc — no query params, no content
    // command_invoke
    command?: string        // "startBuild", "approveProposal" — name only, no args
    duration_ms?: number
    // error
    error_kind?: string     // DesktopError variant, no message
  }
  app_version: string
  os: "windows"
  // NO user identifier, NO solution name, NO file paths, NO proposal content
}
```

Events buffered to `%APPDATA%/SAGE Desktop/telemetry-queue.jsonl`;
flushed via background POST when online. On opt-out, buffer is
deleted immediately.

---

## 4. File Structure

```
sage-desktop/
├── sidecar/
│   ├── sage-sidecar.spec          NEW — PyInstaller spec
│   └── wheels/                    NEW — pip cache (gitignored)
├── src-tauri/
│   ├── Cargo.toml                 MODIFY — add tauri-plugin-updater
│   ├── tauri.conf.json            MODIFY — externalBin, updater, bundle config
│   ├── src/
│   │   ├── sidecar.rs             MODIFY — prod path resolution
│   │   ├── lib.rs                 MODIFY — register updater plugin
│   │   └── commands/
│   │       ├── updates.rs         NEW — check_update / install_update commands
│   │       └── telemetry.rs       NEW — record_event command
│   └── keys/
│       └── sage-desktop.pub       NEW — updater pubkey (committed)
├── src/
│   ├── api/
│   │   ├── types.ts               MODIFY — UpdateStatus, TelemetryConsent types
│   │   └── client.ts              MODIFY — checkUpdate, installUpdate, recordEvent
│   ├── hooks/
│   │   ├── useUpdate.ts           NEW
│   │   └── useTelemetry.ts        NEW
│   ├── pages/
│   │   └── Settings.tsx           MODIFY — add Updates + Telemetry panels
│   ├── components/
│   │   └── domain/
│   │       ├── UpdatePanel.tsx    NEW
│   │       └── TelemetryPanel.tsx NEW
│   └── lib/
│       └── telemetry.ts           NEW — client-side event recorder
├── tests/
│   └── e2e/
│       ├── smoke.rs               MODIFY — split
│       ├── approvals.rs           NEW
│       ├── agents.rs              NEW
│       ├── audit.rs               NEW
│       ├── status.rs              NEW
│       ├── builds.rs              NEW
│       ├── yaml.rs                NEW
│       ├── onboarding.rs          NEW
│       └── backlog.rs             NEW
├── playwright.config.ts           NEW
├── playwright/
│   ├── fixtures/                  NEW — mock sidecar responses
│   └── snapshots/                 NEW — baseline pngs (gitignored binary LFS)
├── .stryker.conf.json             NEW
├── scripts/
│   ├── build-sidecar.sh           NEW — wraps PyInstaller
│   ├── sign-release.sh            NEW — ed25519 sign MSI
│   └── generate-wheels.sh         NEW — pip download
└── README.md                      MODIFY — install instructions, SmartScreen note

Makefile                           MODIFY — desktop-bundle, desktop-msi, test-desktop-mutation
.github/workflows/
└── desktop-release.yml            NEW — CI build + sign + release
```

---

## 5. Task Breakdown

Eight task groups (4.1 → 4.8), each with its own TDD cycle. See the
corresponding plan document for step-by-step detail.

| # | Task | Gate |
|---|---|---|
| 4.1 | PyInstaller sidecar bundle | sidecar binary runs standalone; `.\sage-sidecar.exe` handshakes on stdin/stdout identical to `python app.py` |
| 4.2 | Tauri externalBin + MSI | `make desktop-msi` produces installable .msi; install → launch → pending approvals list renders |
| 4.3 | NSIS fallback | Same binary, NSIS target; install → launch works on a machine with MSI disabled |
| 4.4 | Auto-update | Settings → "Check for updates" hits a fixture release feed, detects newer version, installs, restarts |
| 4.5 | Offline pip cache | `make sidecar-wheels` populates directory; `pip install --no-index --find-links=wheels/ -r requirements.txt` succeeds on an air-gapped machine |
| 4.6 | Full E2E | All 8 E2E modules pass `cargo test --test e2e` in under 5 minutes |
| 4.7 | Mutation + visual CI | `make test-desktop-mutation` runs cargo-mutants + stryker; Playwright visual job green on four pages |
| 4.8 | Telemetry | Default OFF verified in tests; enable → events buffer; disable → buffer cleared |

---

## 6. Testing Strategy

### 6.1 Coverage targets

| Layer | Current | Phase 4 target |
|---|---|---|
| Python sidecar (pytest) | 145 tests | 165+ (update/telemetry handlers + bundle smoke) |
| Rust (cargo test --lib) | 20 tests | 35+ (sidecar path resolution + update commands + telemetry commands) |
| React (vitest) | 119 tests | 150+ (update/telemetry hooks + panels) |
| Rust E2E (cargo test --test e2e) | 1 smoke | 8 modules, ~25 scenarios |
| Mutation (cargo-mutants) | 0 | ≥80% kill rate on `rpc.rs`, `errors.rs`, `sidecar.rs` |
| Mutation (stryker) | 0 | ≥75% kill rate on all `src/hooks/*.ts` |
| Visual (Playwright) | 0 | 4 canonical pages baselined |

### 6.2 CI topology

Two GitHub Actions workflows:
- `test.yml` (existing) — unit + integration, runs on every PR. Fast.
- `desktop-release.yml` (new) — runs on tag push: builds sidecar, builds
  MSI + NSIS, ed25519-signs, creates GitHub release, generates
  `latest.json` for the updater feed.

Mutation + visual regression run on nightly cron, not per-PR, to keep
PR latency low. They post results as a PR comment.

---

## 7. Documentation Updates

1. `.claude/docs/interfaces/desktop-gui.md` — Phase 4 section with
   install/distribute instructions.
2. `CLAUDE.md` — Phase 4 one-liner in the desktop bullet.
3. `sage-desktop/README.md` — end-user install flow, SmartScreen
   caveat, update behavior, telemetry privacy notice.
4. `.claude/docs/setup.md` — developer-facing note on `make desktop-bundle`.
5. `docs/PRIVACY.md` — NEW — what telemetry collects, retention, opt-out.

---

## 8. Acceptance Criteria

Phase 4 is complete when:

1. `make desktop-bundle` produces a standalone sidecar `.exe` that
   passes the existing `tests/test_main.py` e2e tests when swapped
   in for `python app.py`.
2. `make desktop-msi` produces a working installer; installed app
   launches and renders Approvals page with a live sidecar subprocess.
3. `make desktop-nsis` produces an NSIS installer with identical
   behavior.
4. Settings page shows "Check for updates" and "Telemetry" panels.
5. Update check against a mock release feed detects a newer version,
   downloads, verifies signature, installs, and relaunches.
6. Telemetry is OFF by default. Toggling ON persists the consent flag
   in `%APPDATA%/SAGE Desktop/config.json` and causes events to flow.
7. `cargo test --test e2e` passes all 8 modules.
8. `stryker` mutation score ≥75% on hooks; `cargo-mutants` ≥80% on
   the Rust RPC + errors + sidecar layers.
9. Playwright visual regression job green against committed snapshots.
10. All 4 documentation updates landed.
11. 3-layer test delta: sidecar 165+, Rust 35+, React 150+, all green.

---

## 9. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| PyInstaller misses dynamic import → runtime ModuleNotFoundError in prod | Add a post-bundle smoke test that spawns the .exe and runs the full handler round-trip suite against it |
| Bundle size >150 MB triggers GitHub release size limits | Split ChromaDB into optional runtime download; initial bundle targets <100 MB |
| Windows SmartScreen blocks unsigned MSI | README.md walkthrough; prominent notice in release notes; push Phase 4.6 code-signing follow-up |
| Updater misfires and bricks installed app | Sign every release; updater has built-in sig verification; mandatory staging release on a test VM before prod tag |
| Telemetry leaks PII | Strict allowlist in `lib/telemetry.ts`; no content fields; PR review checklist; privacy doc published before first release |
| Playwright snapshot churn on every UI tweak | Baseline only 4 canonical pages; mark all snapshot updates as explicit PR checklist item |
| Mutation testing runtime on CI | Run nightly only; timeout at 30 min; accept partial coverage on first run |

---

## 10. Out-of-band decisions to lock

**Before starting implementation**, two decisions need alignment:
1. **Updater host** — GitHub release feed (simplest, free) vs. custom
   CDN. **Default: GitHub releases.** Configurable later.
2. **Telemetry endpoint** — Placeholder `telemetry.sage.dev` for now.
   No real collector spun up in Phase 4. User configurable.

Both decisions are reversible post-launch via config; not worth
blocking on.
