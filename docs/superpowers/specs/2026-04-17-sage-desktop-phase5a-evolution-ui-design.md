# sage-desktop Phase 5a — Evolution UI

**Status:** design
**Branch:** `feature/sage-desktop-phase5a` (off main)
**Goal:** Surface the Agent Gym's learning loop inside sage-desktop so
the user can watch agent ratings move in real time and trigger a
training round without leaving the desktop app.

---

## 1. Why this phase

SOUL.md's third law is "compounding intelligence over cold-start
lookup." The gym already runs — it grades agents, updates Glicko-2
ratings, stores reflections in vector memory — but sage-desktop's user
has no window into any of that. They install the app, approve a few
proposals, and the learning feedback loop is invisible.

Phase 5a closes that loop visibly. One page, three sections: a
leaderboard, a train panel, and a recent history. The user picks a
role + difficulty, clicks **Train**, watches the spinner, and sees the
matching row's rating tick up (or down). That's the whole product.

It is deliberately a thin slice. Exercise catalog browsing, curriculum
views, batch training, and tree-search stay in Phase 5b. The point of
5a is to prove the RPC family works end-to-end and ship a visible
compounding loop — not to port every gym feature.

---

## 2. Scope

**In scope:**
- `evolution.leaderboard`, `evolution.history`, `evolution.analytics`,
  `evolution.train` RPCs in the sidecar (no HTTP, no FastAPI)
- Corresponding Tauri proxy commands
- React `/evolution` page with Leaderboard, TrainPanel, RecentHistory
  components; Analytics sub-panel appears only when a leaderboard row
  is selected
- Typed error handling: gym-unavailable, invalid-role, training-failed
- Sidebar entry: "Evolution" (between "Agents" and "Audit")
- One Playwright snapshot (`/evolution` empty-state)

**Out of scope:**
- Exercise catalog browser / per-exercise runs → Phase 5b
- Curriculum editor and difficulty progression UI → Phase 5b
- Batch training (`train/batch`) → Phase 5b
- Tree-search / MCTS UI → Phase 5b
- Catalog generation RPC → Phase 5b
- Streaming training progress (single spinner for now)
- Writes to the gym DB beyond what `AgentGym.train()` already does

---

## 3. Architecture

```
React /evolution page
  ├─ <Leaderboard rows={data} onSelect={setRole} />
  │     useLeaderboard()                        → evolution.leaderboard
  │
  ├─ <TrainPanel onTrained={refetch} />
  │     useTrainAgent()            (useMutation)→ evolution.train
  │
  ├─ <RecentHistory limit=50 />
  │     useHistory(50)                          → evolution.history
  │
  └─ <Analytics role={selected} />   (conditional)
        useAnalytics(role)                      → evolution.analytics

Tauri commands/evolution.rs
  evolution_leaderboard | evolution_history | evolution_analytics | evolution_train
       │
       ▼
sidecar/handlers/evolution.py
  thin wrappers over AgentGym + GymDB from src.core.agent_gym
```

### Single-process gym reuse

The sidecar already imports `src.core` modules (for onboarding,
backlog, solutions). We reuse `AgentGym(GymDB(".gym_data.db"))`
initialised once at sidecar boot and held as a module-level singleton.
This matches how `onboarding.generate_solution` is wired.

### Error surface (no new codes)

| Python | JSON-RPC code | DesktopError |
|---|---|---|
| `KeyError` (no such role in ratings) | `-32602` `RPC_INVALID_PARAMS` | `InvalidParams` |
| `RuntimeError` (LLM unavailable) | `-32000` `RPC_SIDECAR_ERROR` | `SidecarDown` |
| `ValueError` (invalid difficulty) | `-32602` `RPC_INVALID_PARAMS` | `InvalidParams` |
| Unhandled | `-32603` `RPC_INTERNAL_ERROR` | `Internal` |

---

## 4. File structure

### Sidecar
- **New:** `sage-desktop/sidecar/handlers/evolution.py`
  - `leaderboard() -> {leaderboard: [...], stats: {...}}`
  - `history(limit=50) -> {sessions: [...]}`
  - `analytics(role, skill="") -> {global_stats, leaderboard, score_trend, weakness_map, ...}`
  - `train(role, difficulty="", skill_name="", exercise_id="") -> session.to_dict()`
- **New:** `sage-desktop/sidecar/tests/test_evolution.py` (8 tests)
- **Modify:** `sage-desktop/sidecar/app.py` — register 4 handlers

### Rust
- **New:** `sage-desktop/src-tauri/src/commands/evolution.rs` with 4 commands
- **Modify:** `sage-desktop/src-tauri/src/commands/mod.rs` (`pub mod evolution;`)
- **Modify:** `sage-desktop/src-tauri/src/lib.rs` — register handlers

### React
- **New:** `sage-desktop/src/api/types.evolution.ts` (or append to
  `src/api/types.ts`) — `LeaderboardEntry`, `HistorySession`,
  `AnalyticsResult`, `TrainParams`, `TrainResult`
- **Modify:** `sage-desktop/src/api/client.ts` — add 4 functions
- **New:** `sage-desktop/src/hooks/useEvolution.ts` — 4 hooks
- **New:** `sage-desktop/src/components/domain/Leaderboard.tsx`
- **New:** `sage-desktop/src/components/domain/TrainPanel.tsx`
- **New:** `sage-desktop/src/components/domain/RecentHistory.tsx`
- **New:** `sage-desktop/src/components/domain/Analytics.tsx`
- **New:** `sage-desktop/src/pages/Evolution.tsx`
- **Modify:** `sage-desktop/src/App.tsx` — add `/evolution` route
- **Modify:** `sage-desktop/src/components/layout/Sidebar.tsx` — nav entry
- **Modify:** `sage-desktop/src/components/layout/Header.tsx` — title mapping

### Tests
- `sidecar/tests/test_evolution.py` (8 tests, mocked `AgentGym`)
- Vitest hooks: `__tests__/hooks/useEvolution.test.ts` (4 tests)
- Vitest components: `__tests__/components/{Leaderboard,TrainPanel,RecentHistory}.test.tsx` (6 tests)
- Vitest page: `__tests__/pages/Evolution.test.tsx` (1 integration test)
- Playwright: `playwright/evolution.spec.ts` (1 empty-state snapshot)

### Docs
- `.claude/docs/interfaces/desktop-gui.md` — Phase 5a section
- `CLAUDE.md` — one-line update noting `/evolution` route

---

## 5. UI flow

### Layout (single page, stacked)

```
┌─────────────────────────────────────────────────────────────┐
│  Evolution                                                  │
├─────────────────────────────────────────────────────────────┤
│  Leaderboard                                                │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Role      │ Rating │ RD   │ Wins │ Losses │ Win %   │  │
│  │ developer │ 1215.3 │ 92.1 │  14  │   6    │  70 %   │  │
│  │ analyst   │ 1102.7 │ 118  │   5  │   7    │  42 %   │  │
│  │ …                                                     │  │
│  └───────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  Train                                                      │
│  Role [developer ▼]  Difficulty [beginner ▼]  [ Train ]     │
│                                                             │
│  ↓ after click                                              │
│  Training developer @ beginner…  (spinner)                  │
│                                                             │
│  ↓ on success                                               │
│  ✓ Trained: score 78 · rating 1215.3 → 1228.9  (+13.6)      │
│    Reflection: "Missed the edge case on empty input…"       │
├─────────────────────────────────────────────────────────────┤
│  Recent history  (last 50)                                  │
│  Timestamp │ Role │ Exercise │ Score │ Passed               │
└─────────────────────────────────────────────────────────────┘
```

When a leaderboard row is clicked, an `<Analytics>` panel slides in
below it showing score trend, weakness map, and improvement rate for
that role. (Plain tables — no charts in Phase 5a.)

### Train flow details

1. User picks `role` (required) and `difficulty` (optional, defaults
   to current curriculum level for that role).
2. **Train** button disabled while mutation pending.
3. On success: green panel with `score`, `elo_before → elo_after
   (±delta)`, and the reflection. Leaderboard + history auto-refetch.
4. On error: red panel with `DesktopError.message`, **Try again**
   button, no refetch.

---

## 6. Wire contract

### `evolution.leaderboard` request / result
```json
// request
{}

// result
{
  "leaderboard": [
    {"agent_role": "developer", "rating": 1215.3, "rating_deviation": 92.1,
     "wins": 14, "losses": 6, "win_rate": 0.70, "sessions": 20,
     "streak": 3, "best_score": 94.0}
  ],
  "stats": {"total_agents": 5, "total_sessions": 112, "avg_rating": 1084.2}
}
```

### `evolution.history` request / result
```json
// request
{"limit": 50}

// result
{
  "sessions": [
    {"session_id": "2026-04-17T12:34:56", "agent_role": "developer",
     "exercise_id": "openswe_fizzbuzz_ab12cd", "score": 78.0, "passed": true,
     "timestamp": "2026-04-17T12:34:56Z"}
  ]
}
```

### `evolution.analytics` request / result
```json
// request
{"role": "developer", "skill": ""}

// result (from AgentGym.analytics — pass-through)
{
  "global_stats": {...},
  "leaderboard": [...],
  "score_trend": [...],
  "weakness_map": [...],
  "improvement_rate": {...},
  "difficulty_breakdown": {...},
  "critic_agreement": {...}
}
```

### `evolution.train` request / result
```json
// request
{"role": "developer", "difficulty": "beginner",
 "skill_name": "", "exercise_id": ""}

// result (TrainingSession.to_dict pass-through)
{
  "session_id": "…", "agent_role": "developer",
  "skill_name": "openswe", "exercise_id": "openswe_…",
  "status": "completed",
  "grade": {"score": 78.0, "passed": true, ...},
  "elo_before": 1215.3, "elo_after": 1228.9,
  "reflection": "…", "improvement_plan": [...],
  "duration_s": 14.2
}
```

---

## 7. Testing targets

| Layer | New tests | What they cover |
|---|---|---|
| Sidecar pytest | 8 | leaderboard happy, leaderboard empty, history default limit, history custom limit, analytics role scope, analytics unknown role returns empty sections, train happy, train RuntimeError → SidecarDown |
| Rust cargo | 0 | proxy-only — matches Phase 3c convention |
| Vitest hooks | 4 | one per hook (useLeaderboard, useHistory, useAnalytics, useTrainAgent) |
| Vitest components | 6 | Leaderboard (row render + click selects role), TrainPanel (disabled without role, submit pass-through, shows delta panel), RecentHistory (limit respected, empty state) |
| Vitest page | 1 | Evolution page renders all 3 primary sections |
| Playwright | 1 | empty-state snapshot at `/evolution` (mock returns empty leaderboard + history) |

**Total new tests: 20.** Drift guard already covers `/evolution` once
we add it to the nav + the e2e-config test.

---

## 8. Acceptance criteria

- `/evolution` loads with leaderboard rendered (real rows from
  `.gym_data.db` if present; empty-state card otherwise).
- Selecting role=developer, difficulty=beginner and clicking **Train**
  runs a real `AgentGym.train(...)` round and shows the delta card
  with `elo_before → elo_after`.
- After training, the corresponding leaderboard row's rating matches
  `elo_after`, and the session appears as the top row in Recent
  history.
- Clicking a leaderboard row reveals an Analytics panel for that role
  populated from `AgentGym.analytics`.
- With the gym DB absent: page shows empty leaderboard + history, no
  uncaught errors, Train button still renders (disabled until role
  chosen).
- With LLM unavailable: Train returns a red `SidecarDown` panel, no
  leaderboard corruption.
- All 5 test layers green (framework-side unchanged, sidecar pytest,
  cargo check, vitest, Playwright pixel-diff — visual snapshot
  accepted as baseline on first run).

---

## 9. Risk + mitigations

| Risk | Mitigation |
|---|---|
| Gym training blocks sidecar mutex for the whole training duration | Accepted — matches onboarding.generate behaviour; spinner in UI is enough. User can't train and approve simultaneously, which is correct. |
| `.gym_data.db` not present on a fresh install | `GymDB` auto-creates tables; handlers return empty leaderboard + empty history gracefully. |
| `AgentGym` pulls in heavy transitive imports that slow sidecar startup | Lazy-import inside the handler entry points — matches the pattern used in `onboarding.py`. |
| Glicko-2 update is non-deterministic across runs (volatility drift) | Tests mock `AgentGym.train` entirely; we never assert on real delta values. |
| Training a role that has no runner wired up (e.g. a custom domain) | `AgentGym.train` raises; we map to `InvalidParams` so the UI gives a clear error. |

---

## 10. Plan link

`docs/superpowers/plans/2026-04-17-sage-desktop-phase5a.md` — bite-sized
TDD plan follows.
