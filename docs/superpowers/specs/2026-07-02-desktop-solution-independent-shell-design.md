# sage-desktop — Solution-Independent Shell Design

**Date:** 2026-07-02
**Status:** Approved — building
**Builds on:** Phase 3a (`2026-04-17-sage-desktop-phase3a-solution-switcher-design.md`) — the
`switchSolution`/`replace_solution` mechanism this design reuses, not rebuilds.

---

## 1. Goal

Make sage-desktop feel like an IDE (VS Code / Claude desktop): open the app first, pick or switch
a solution ("project") from inside it, at any time — instead of the app being launched already
bound to one solution via CLI args, with switching buried as a secondary control in Settings.

## 2. Non-goals

- **Chat.** Deferred to its own design cycle. Note for that cycle: an action-aware, HITL-preserving
  chat design already exists and is implemented for the **web** UI (`POST /chat`, `src/interface/api.py:5493`,
  specs `2026-03-20-contextual-chat-window.md` + `2026-03-20-action-aware-chat-design.md`). The desktop
  chat cycle should port that design over RPC rather than design from scratch.
- **Running multiple solutions simultaneously.** Still one sidecar, one active solution at a time —
  the single-lane model from Phase 3a is unchanged. This is a *presentation* change (how you get to
  the switch), not an architecture change.
- **Removing Settings' existing solution picker.** It stays as a harmless secondary path; Home is
  the new primary one.
- **Touching the desktop launcher's CLI menu** (`launch_sage.py`). It still works unmodified as a
  fast power-user path that pre-selects a solution before the app even opens.

## 3. User experience

- **First launch ever:** no solution loaded → app opens on a **Home** screen: a list of solutions
  (cards: name, path, `.sage/` presence indicator), a text filter box (the real solutions directory
  already has 17+ entries across two roots — a flat unfiltered list won't scale), a "＋ New solution"
  tile linking to the existing Onboarding wizard, loading/empty/error states via the existing patterns.
- **Subsequent launches:** the app auto-reopens the **last solution used** (persisted in
  `localStorage`, frontend-only) — no Home detour every time, matching VS Code / Claude desktop.
  Home is always one click away via the sidebar.
- **Switching:** clicking the current-solution row in the sidebar navigates to Home (reused as the
  switch surface — no second solution-list UI). The current solution keeps running underneath until
  a new one is actually picked, so browsing Home doesn't tear anything down. Picking a solution calls
  the existing switch mutation; on success you're navigated into the new solution.
- **No solution loaded and you try a solution-scoped route directly** (e.g. a stale deep link):
  redirected to Home.

## 4. Architecture

### 4.1 Boot

Today: sidecar always spawned with `--solution-name`/`--solution-path`. Going forward: the default
launch path omits them **unless** `localStorage` has a remembered last solution, in which case the
frontend immediately calls the same switch mutation on mount to load it. The sidecar's existing
**minimal mode** (`app.py` — `if not solution_path: ... return`, already wires handshake, solutions
list, onboarding, org, then stops) is the boot state whenever no solution is active. No sidecar
changes needed here — this mode already exists and is tested.

### 4.2 Components

- **New `Home.tsx`** page: solution list (reusing `useSolutions()`/`useSwitchSolution()`), "Recent"
  section sourced from the `localStorage` list above "All solutions," a text filter box (client-side
  substring match on name — no backend change), a "＋ New solution" tile, loading/empty/error states.
- **`Sidebar.tsx`**: a persistent switcher pinned above the nav list — current solution name + a
  button that navigates to Home. When no solution is loaded, the rest of the nav is hidden (nothing
  to route to yet).
- **`App.tsx`**: a new `<RequireSolution>` wrapper around every solution-scoped route; redirects to
  `/` (Home) if `useCurrentSolution()` is null. Home, Onboarding, and Organization stay reachable
  without a solution loaded.
- **`useSolutions.ts`**: add a small `useLastSolution()` helper (get/set the `localStorage` entry) —
  frontend-only, no backend change.

### 4.3 Targeted backend fix (found during design, not pre-existing scope creep)

`Sidecar::replace_solution` (`sidecar.rs`) tears down the old child **before** attempting to spawn
the new one. If the new spawn fails, the function returns `Err` via `?` without touching `self.conn`
— which still holds the **old**, now-dead connection. `is_online()` then incorrectly reports `true`
for a process that no longer exists. This was a low-probability edge case while switching was a
buried Settings action; it becomes much more likely once switching is the primary interaction. Fix:
on spawn failure inside `replace_solution`, explicitly set `self.conn = None` so the existing
`SidecarStatusBanner`/crash-recovery UI reflects reality instead of the app silently hanging on a
phantom connection.

## 5. Error handling & testing

Reuses established patterns: `ErrorBanner` for `useSolutions()`/switch failures, loading state on
Home while the list fetches, empty state (zero solutions found) with the "＋ New solution" tile
front and center. New tests: `Home.test.tsx` (list/search/empty/error/switch-success),
`RequireSolution` redirect test, `Sidebar` switcher-button test, `useLastSolution` get/set test, and
a Rust test extending the existing `replace_solution` suite in `sidecar.rs` for the spawn-failure fix.
