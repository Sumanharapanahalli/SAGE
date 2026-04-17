# sage-desktop Phase 3d — Build Console

**Status:** design
**Branch:** `feature/sage-desktop-phase3d` (off main)
**Goal:** Let the user start, observe, and approve builds driven by
`src.integrations.build_orchestrator` — the pipeline that turns a
product description into working code — entirely from sage-desktop.

---

## 1. Why this phase

Phase 3c lets the user *create* a solution (YAML scaffold). Phase 3d
lets them *run the build pipeline* against that scaffold — decompose
product description → critic review → HITL approve → execute agents →
review → approve deployment.

Today this only works via FastAPI. For yoga / dance / medical app
builders in locked-down environments, the desktop must own the full
0→1→N loop.

---

## 2. Scope

**In scope:**
- `builds.start`, `builds.list`, `builds.get`, `builds.approve` RPCs in
  the sidecar (thin wrappers over existing
  `build_orchestrator.{start,get_status,list_runs,approve_plan,approve_build,reject}`)
- 4 Tauri proxy commands (`start_build`, `list_builds`, `get_build`,
  `approve_build_stage`)
- React `BuildConsole` page at `/builds` with:
  1. Start panel — product description + solution name + hitl level
  2. Runs table (run_id, solution, state, task count, created_at)
  3. Detail drawer — state timeline + plan + critic scores + approve /
     reject buttons
- `useBuildRuns()` / `useBuildRun(id)` queries (polled every 3 s while
  the run is in a non-terminal state)
- `useStartBuild()` / `useApproveBuildStage()` mutations
- Sidebar entry "Builds" between Backlog and Settings
- Typed errors: reuses `InvalidParams`, `SidecarDown`, `Other`; no new
  codes.

**Out of scope:**
- Streaming per-task progress (polling is enough; events = Phase 4)
- Build artifact download (write-access via desktop deferred)
- Re-running a failed run (reject + start a new run is the flow)
- Editing `hitl_level` / `critic_threshold` after start (unsupported by
  orchestrator)

---

## 3. Architecture

```
React BuildConsole
  useBuildRuns (useQuery, poll every 3 s)
  useBuildRun(id) (useQuery, poll every 3 s while non-terminal)
  useStartBuild (useMutation)
  useApproveBuildStage (useMutation)
      │
      ▼
  invoke("start_build"|"list_builds"|"get_build"|"approve_build_stage", ...)
      │
      ▼
Rust commands/builds.rs (4 proxies)
      │
      ▼
sidecar/handlers/builds.py
  build_orchestrator.start / get_status / list_runs / approve_*
```

### Error mapping

The orchestrator returns dicts with `"error"` keys on bad input (e.g.
unknown run id). Handlers convert these to `RpcError(InvalidParams)` so
the UI gets typed `DesktopError::InvalidParams` — identical pattern to
Phase 3c. Python exceptions bubble as `RPC_SIDECAR_ERROR`.

| Orchestrator outcome | Code |
|---|---|
| `{"error": "... not found"}` | `-32602` (`InvalidParams`) |
| `{"error": "Run is not awaiting approval..."}` | `-32602` |
| Python exception (e.g. import failure) | `-32000` (`SidecarDown`) |
| Missing `_orch` module var | `-32000` |

---

## 4. File structure

### Framework (existing — no changes)
- `src/integrations/build_orchestrator.py` — already exposes
  `build_orchestrator` singleton with the needed methods.

### Sidecar
- **New:** `sage-desktop/sidecar/handlers/builds.py`
  - `start(params)`, `list_runs(_)`, `get(params)`, `approve_stage(params)`
- **New:** `sage-desktop/sidecar/tests/test_builds.py`
- **Modify:** `sage-desktop/sidecar/app.py`
  - Register 4 handlers; wire `_orch` lazily.

### Rust
- **New:** `sage-desktop/src-tauri/src/commands/builds.rs`
  - 4 `#[tauri::command]` proxies.
- **Modify:** `sage-desktop/src-tauri/src/commands/mod.rs` (+ `pub mod builds;`)
- **Modify:** `sage-desktop/src-tauri/src/lib.rs` (register 4 handlers)

### React
- **Modify:** `sage-desktop/src/api/types.ts` — add `BuildRun`,
  `BuildRunDetail`, `StartBuildParams`, `ApproveBuildParams`
- **Modify:** `sage-desktop/src/api/client.ts` — add 4 client fns
- **New:** `sage-desktop/src/hooks/useBuilds.ts`
- **New:** `sage-desktop/src/components/domain/StartBuildForm.tsx`
- **New:** `sage-desktop/src/components/domain/BuildRunsTable.tsx`
- **New:** `sage-desktop/src/components/domain/BuildRunDetail.tsx`
- **New:** `sage-desktop/src/pages/BuildConsole.tsx`
- **Modify:** `sage-desktop/src/App.tsx` — `/builds` route
- **Modify:** `sage-desktop/src/components/layout/Sidebar.tsx` — +Builds entry
- **Modify:** `sage-desktop/src/components/layout/Header.tsx` — +title
- **Modify:** `sage-desktop/src/__tests__/App.test.tsx` — +4 mocks

### Tests
- Sidecar pytest: +8 (4 methods × 2 cases each)
- React vitest:
  - `__tests__/hooks/useBuilds.test.ts` (+3)
  - `__tests__/components/StartBuildForm.test.tsx` (+3)
  - `__tests__/components/BuildRunsTable.test.tsx` (+2)
  - `__tests__/components/BuildRunDetail.test.tsx` (+2)

### Docs
- `.claude/docs/interfaces/desktop-gui.md` — Phase 3d section
- `CLAUDE.md` — one-line update

---

## 5. UI flow

### Start panel (top of `/builds`)
- Product description textarea (min 30 chars)
- Solution name input (optional — orchestrator auto-generates if blank)
- HITL level: `minimal | standard | strict` (radio buttons, default
  `standard`)
- Critic threshold slider 0-100, default 70
- "Start build" button; disabled while pending.
- On success: runs table refreshes and the new run is auto-selected.

### Runs table
- Columns: Solution, State (chip), Tasks, Created, Actions.
- Clicking a row opens the detail drawer.
- State chip colors:
  - `awaiting_plan` / `awaiting_build` → yellow
  - `building` / `decomposing` / `critic_plan` → blue
  - `completed` → green
  - `failed` / `rejected` → red

### Detail drawer
- Header: run_id, solution, state, created_at
- Plan table (one row per task: step, task_type, agent_role,
  description, acceptance_criteria)
- Critic reports list (plan / build phase, score, notes)
- Approve / Reject panel (only shown when state is `awaiting_plan` or
  `awaiting_build`):
  - Feedback textarea
  - `Approve` (green) → calls `builds.approve` with `approved=true`
  - `Reject` (red) → calls with `approved=false`

---

## 6. Wire contract

### `builds.start` request
```json
{
  "product_description": "Yoga instructor app with schedule...",
  "solution_name": "yoga",
  "hitl_level": "standard",
  "critic_threshold": 70
}
```

### `builds.start` result
```json
{
  "run_id": "abc-123",
  "solution_name": "yoga",
  "state": "awaiting_plan",
  "plan": [ {"step": 1, "task_type": "...", ...}, ... ],
  "critic_reports": [...],
  "created_at": "2026-04-17T..."
}
```

### `builds.list` result
```json
[
  {"run_id": "abc-123", "solution_name": "yoga",
   "state": "awaiting_plan", "task_count": 12,
   "created_at": "..."}
]
```

### `builds.approve` request
```json
{"run_id": "abc-123", "approved": true, "feedback": ""}
```

Dispatches to `approve_plan` / `approve_build` based on current state,
or `reject` when `approved=false`.

---

## 7. Testing targets

| Layer | New tests | What they cover |
|---|---|---|
| Sidecar pytest | 8 | start missing description, start happy, list empty, list happy, get missing id, get happy, approve routes to plan/build, reject path |
| Rust cargo | 0 | proxy-only, no logic |
| Vitest hook | 3 | queries fetch + poll, start mutation, approve mutation |
| Vitest component | 7 | StartBuildForm (disable/submit/validation), BuildRunsTable (empty/populated), BuildRunDetail (approve/reject visibility) |

Total new: **18** on top of Phase 3c's 92 → ~110.

---

## 8. Acceptance criteria

- Start a build with description + name → runs table shows the new
  entry within 3 s with `state: awaiting_plan`.
- Open detail → see critic score + plan task list.
- Approve plan → state moves to `building` (next poll) then
  `awaiting_build` once agents complete.
- Approve build → state `completed`.
- Reject at any stage with feedback → state `rejected`, feedback
  recorded in critic_reports/audit.
- Start with empty description → typed `InvalidParams` toast.
- All 5 test layers green.

---

## 9. Risk + mitigations

| Risk | Mitigation |
|---|---|
| Long-running orchestrator blocks sidecar's single lane | Accepted — user-visible spinner, polling drives UI. Sidecar already single-user. |
| Orchestrator errors as dict instead of exceptions | Handler inspects `"error"` key and maps to `InvalidParams`. |
| Polling cadence wastes CPU when no build is running | Poll only when there are non-terminal runs. `refetchInterval: 3000` on queries, disabled when all runs are in `completed/failed/rejected`. |
| Large plan payload slows detail drawer | Plan tasks are trimmed client-side to 50 rows with a "Show all" expander. |

---

## 10. Plan link

`docs/superpowers/plans/2026-04-17-sage-desktop-phase3d.md` —
bite-sized TDD plan follows.
