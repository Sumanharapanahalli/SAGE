# sage-desktop Phase 3a — Solution Switcher Design

**Date:** 2026-04-17
**Branch:** `feature/sage-desktop-phase3a` off `main`
**Scope:** First of three Phase 3 sub-phases. Others: onboarding wizard (3c), Build Console (3d). YAML authoring (3b) deferred to Phase 4.

---

## 1. Goal

Let a sage-desktop user pick a different solution from the sidebar / Settings and have the desktop reconnect to the new solution's `.sage/` store without relaunching the app.

Why this matters: it is the foundation for 3c (onboarding creates a new solution then switches to it) and 3d (Build Console is per-solution).

## 2. Non-goals

- Running multiple solutions simultaneously (still one sidecar, one active solution — the single-lane model is deliberate).
- Creating new solutions (that is 3c).
- Editing project/prompts/tasks YAML (that is Phase 4).
- Any HTTP.

## 3. User experience

- **Sidebar footer** gains a compact "Solution:" row showing the active name and a chevron dropdown listing all available solutions. Clicking one triggers a switch.
- **Settings page** gains a "Current solution" section at the top with the same picker plus path and last-used timestamp.
- Switch triggers a two-step transition: (a) show a "Reconnecting…" banner, (b) sidebar + page data refetches once the handshake for the new solution succeeds.
- Errors (missing directory, invalid `project.yaml`) surface via the existing `ErrorBanner` with a new `DesktopError` variant `SolutionNotFound { name: string }` (RPC code `-32021`).

## 4. Architecture

### 4.1 Listing solutions

New sidecar method **`solutions.list`** returns `SolutionRef[]` where each entry is:

```json
{ "name": "medtech", "path": "/abs/path/to/solutions/medtech", "has_sage_dir": true }
```

Algorithm: scan `<SAGE_ROOT>/solutions/` for child directories that contain either `project.yaml` **or** `SKILL.md`. Skip dotfiles, README, and `org.yaml`. Sort alphabetically. Pure filesystem read — no LLM, no DB.

No new dependency. Exposed via `call<SolutionRef[]>("solutions.list", {})`.

### 4.2 Switching

New sidecar method **`solutions.get_current`** returns `{ name, path } | null`. Trivially reads the same values that `handshake` returns, exposed separately so the UI can refresh without re-handshaking.

Switching itself happens **Rust-side** — the sidecar is a one-solution process by design. The Rust layer owns a new Tauri command `#[tauri::command] async fn switch_solution(name: String, path: PathBuf) -> Result<HandshakeResult, DesktopError>`:

1. Terminate the current `Sidecar` (close stdin → wait for child exit → timeout kill after 3 s).
2. Spawn a new `Sidecar` with the new `SolutionRef`.
3. Run `handshake`.
4. Update the Tauri-managed `Arc<RwLock<Sidecar>>`.
5. Emit a Tauri event `solution-switched` with the new handshake payload.

**Why a single `RwLock<Sidecar>` instead of a channel queue:** the invariant is "one live sidecar at a time"; readers already await through `.call()`, so taking a write lock briefly during switch is simpler than a hand-rolled swap queue. Every other command path takes a read lock for the duration of its RPC, so an in-flight call blocks the switch until it finishes — a feature, not a bug.

### 4.3 React side

- `useSolutions()` — React Query `["solutions","list"]`, 60 s stale time (filesystem rarely changes mid-session).
- `useCurrentSolution()` — `["solutions","current"]`, invalidated by `solution-switched` event listener.
- `useSwitchSolution()` — `useMutation`, invalidates every query key on success (`["solutions"]`, `["status"]`, `["approvals"]`, `["audit"]`, `["agents"]`, `["backlog"]`, `["queue"]`, `["llm"]`). This is the right hammer: the whole app's data source changed.
- `SolutionPicker` domain component — dropdown with search, shown in both Sidebar footer and Settings.
- Sidebar wiring — add `<SolutionPicker variant="sidebar" />`; Settings — `<SolutionPicker variant="settings" />` plus path + last-used.

### 4.4 Event subscription

The Sidebar and Settings both listen for the Tauri `solution-switched` event to force-invalidate queries. A thin `useAppEvents()` hook registers listeners in `App.tsx` once — avoids duplicate subscriptions.

## 5. Data flow (switch path)

```
User clicks "medtech" in SolutionPicker
  → useSwitchSolution mutation
  → invoke("switch_solution", {name, path})
  → Rust: stop sidecar → spawn new → handshake
  → Rust emits "solution-switched" event
  → React listens, invalidates caches
  → Sidebar + Settings + all pages refetch
```

## 6. Error handling

| Condition | Surface |
|---|---|
| Solution directory missing | `SolutionNotFound { name }` — banner + keep old sidecar running |
| `project.yaml` / `SKILL.md` malformed | `SageImportError` (existing variant) — banner + fallback |
| Handshake to new sidecar times out | `SidecarDown` (existing) — auto-restart old solution |
| Switch called mid-handshake | Previous switch completes before new one starts (RwLock) |

## 7. Testing (TDD)

| Layer | New tests | Count target |
|---|---|---|
| Python framework | Solution listing helper in `src/core/project_loader.py` (`list_solutions(sage_root)`) — dir scan, invalid entries skipped, alphabetical | +5 |
| Python sidecar | `test_solutions.py`: list returns expected shape, malformed skipped, get_current returns wired name/path, None when not wired | +6 |
| Rust | `switch_solution` command terminates old sidecar + spawns new; `SolutionNotFound` variant serializes round-trip; event emitted on success | +4 |
| React hooks | `useSolutions`, `useCurrentSolution`, `useSwitchSolution` — invalidation assertions | +4 |
| React components | `SolutionPicker` — dropdown render, switch action, error state | +3 |
| React pages | `Settings` shows "Current solution" section | +1 |
| E2E smoke | Round-trip `solutions.list` | +1 method |

Target **≥ 24 new tests**, all passing before merge.

## 8. File structure

```
src/core/project_loader.py                  + list_solutions()

sage-desktop/sidecar/handlers/solutions.py  NEW
sage-desktop/sidecar/tests/test_solutions.py NEW
sage-desktop/sidecar/app.py                 register solutions.list / solutions.get_current

sage-desktop/src-tauri/src/errors.rs        + SolutionNotFound variant + code -32021
sage-desktop/src-tauri/src/commands/
    solutions.rs                            NEW — list + get_current wrappers
    switch.rs                               NEW — switch_solution command
sage-desktop/src-tauri/src/sidecar.rs       refactor to support replace()

sage-desktop/src/api/types.ts               + SolutionRef, SolutionNotFound
sage-desktop/src/api/client.ts              + 2 wrappers
sage-desktop/src/hooks/useSolutions.ts      NEW
sage-desktop/src/hooks/useAppEvents.ts      NEW — single listener setup
sage-desktop/src/components/domain/SolutionPicker.tsx NEW
sage-desktop/src/components/layout/Sidebar.tsx        + footer picker
sage-desktop/src/pages/Settings.tsx                   + current-solution section
sage-desktop/src/__tests__/...                        coverage tests
```

## 9. Docs to update

- `.claude/docs/interfaces/desktop-gui.md` — new RPC table rows, new error variant, sidebar screenshot description.
- `CLAUDE.md` — "Phase 3a ships solution switching" one-liner.
- E2E smoke — add `solutions.list` round-trip.

## 10. Acceptance criteria

1. `make test-desktop` — all layers green (≥ 102 sidecar + 18 Rust + existing + ≥ 24 new React).
2. `npm run test:e2e` — six methods round-trip (Phase 1 + 2 + `solutions.list`).
3. Manual: launch desktop with `SAGE_SOLUTION_PATH` unset → sidebar picker lists all `solutions/*` → click `meditation_app` → UI reconnects → pending approvals / audit reflect that solution.
4. Switch → old sidecar exits within 3 s.
5. Bad solution name → banner appears, old solution stays active.

## 11. Out of scope

- Solution creation (Phase 3c).
- "Recent solutions" with history (defer).
- Multi-solution simultaneous view (never — violates single-lane invariant).
