# SAGE Desktop — Phase 2 Design Spec

**Date:** 2026-04-17
**Branch:** `feature/sage-desktop-phase2` (off `feature/sage-desktop-phase1`)
**Predecessor:** Phase 1 shipped operator console — Approvals, Agents, Audit, Status.
**Scope:** Phase 2 of a 4-phase rebuild. Later phases have their own specs.

---

## 1. Goal

Extend the no-sockets Tauri + Python-sidecar desktop app with the three
most load-bearing *operator actions* that don't exist in Phase 1: changing
the LLM provider at runtime, logging a feature request into the solution's
backlog, and inspecting the task queue.

All three exist in the FastAPI Web UI today. Phase 2 brings them to the
port-restricted corporate environment without opening any sockets.

## 2. Phase 2 feature set

| Feature | Sidecar method(s) | UI |
|---|---|---|
| **LLM provider switch** | `get_llm_info`, `switch_llm` | New **Settings** page |
| **Feature request submission** | `list_feature_requests`, `submit_feature_request`, `update_feature_request` | New **Backlog** page |
| **Queue / monitor status** | `get_queue_status`, `list_queue_tasks` | New section on **Status** page |

Each feature is a vertical slice: Python handler → Rust command → React
hook → React page, with tests at every layer.

## 3. Non-goals (Phase 2)

- **Chat / Analyze** — requires streaming over NDJSON. Deferred to Phase 2b.
- **Solution switcher** — requires sidecar restart; non-trivial state transition. Phase 2b.
- **Product Owner backlog wizard** — larger UX workflow. Phase 2b.
- **Build Console** — runs long-lived builds. Phase 3.
- **Packaging polish** — Phase 4.
- **Push / websocket** — polling remains sufficient; same cadence as Phase 1.

## 4. Cross-cutting change: extract `FeatureRequestStore`

The feature-requests table is currently defined inline inside
`src/interface/api.py` (lines 427–459, 1896–…). To let the sidecar reuse
the exact same SQLite schema without importing FastAPI, extract a small
module:

```
src/core/feature_request_store.py
    class FeatureRequest:              dataclass
    class FeatureRequestStore:         __init__(db_path), init_schema(),
                                        submit(req), list(status=None, scope=None),
                                        get(id), update(id, action, note)
```

`src/interface/api.py` switches to `FeatureRequestStore(_get_db_path())` —
no behaviour change, same SQLite file, same columns. This extraction is
task 1 of Phase 2 so every later task builds on the new module.

## 5. Architecture

Unchanged from Phase 1 — same stdin/stdout NDJSON JSON-RPC, same
`SidecarManager` + `RpcClient`, same `.sage/audit_log.db` shared state.
Phase 2 only adds handlers and commands; no core infra change.

```
┌──────────────────────────────────────────────────────────────┐
│ sage-desktop.exe  (unchanged wrapper)                        │
│                                                              │
│  React UI (adds Settings + Backlog pages + Status queue tile)│
│     │                                                        │
│     ▼                                                        │
│  Rust (adds 7 #[tauri::command] wrappers)                    │
│     │                                                        │
│     ▼ NDJSON JSON-RPC (unchanged)                            │
│                                                              │
│  Python sidecar                                              │
│   handlers/llm.py        ← new                               │
│   handlers/backlog.py    ← new                               │
│   handlers/queue.py      ← new                               │
│                                                              │
│  Imports (new):                                              │
│   src.core.llm_gateway.LLMGateway                            │
│   src.core.feature_request_store.FeatureRequestStore         │
│   src.core.queue_manager.get_task_queue                      │
│   src.core.proposal_executor._execute_llm_switch             │
└──────────────────────────────────────────────────────────────┘
```

## 6. RPC contract — Phase 2 methods

### 6.1 LLM

```
get_llm_info() → {
  provider: "gemini" | "claude-code" | "ollama" | "local" | "claude" | "generic-cli",
  model: string,
  provider_name: string,              # e.g. "GeminiCLIProvider"
  available_providers: string[]
}

switch_llm(provider: string, model?: string, save_as_default?: bool) → {
  provider: string,
  provider_name: string,
  saved_as_default: bool
}
```

`switch_llm` is framework control (no HITL approval) per CLAUDE.md Law 1:
"Framework control executes immediately". The handler delegates to the
existing `_execute_llm_switch` function by building a synthetic `Proposal`,
matching the Web UI's behaviour exactly.

### 6.2 Backlog

```
list_feature_requests(status?: string, scope?: string) → FeatureRequest[]

submit_feature_request(
  title: string,
  description: string,
  module_id?: string = "general",
  module_name?: string = "General",
  priority?: "low"|"medium"|"high"|"critical" = "medium",
  requested_by?: string = "anonymous",
  scope?: "solution"|"sage" = "solution"
) → FeatureRequest

update_feature_request(
  id: string,
  action: "approve"|"reject"|"complete",
  reviewer_note?: string = ""
) → FeatureRequest
```

Validation lives in `FeatureRequestStore.submit()`; the sidecar translates
`ValueError` → `InvalidParams`, `KeyError` → a new `FeatureRequestNotFound`
error variant.

### 6.3 Queue

```
get_queue_status() → {
  pending: number,
  in_progress: number,
  done: number,
  failed: number,
  blocked: number,
  parallel_enabled: bool,
  max_workers: number
}

list_queue_tasks(status?: string, limit?: number = 50) → Task[]
```

`Task` = `{ id, task_type, status, priority, created_at, started_at?, completed_at?, error? }`.
Full payloads omitted — keeps NDJSON frames small.

## 7. New error variants

Adds to `errors.rs` / `api/types.ts`:

- `FeatureRequestNotFound { feature_id: string }`
- `LlmSwitchFailed { detail: string }`

Existing variants (`InvalidParams`, `SageImportError`, `SidecarDown`, etc.)
handle the rest.

## 8. Test coverage targets

Match Phase 1's bar:

| Layer | Coverage | New tests |
|---|---|---|
| Python sidecar handlers + store | ≥90% | ~40 pytests (store + 3 handlers + dispatcher wiring) |
| Rust commands + error mapping | ≥85% | ~10 cargo tests |
| React hooks + api | ≥95% | ~15 vitests (hooks) |
| React pages + components | ≥75% | ~10 vitests (Settings, Backlog, Status enhancement) |

Plus the e2e smoke gains one method per feature (`switch_llm` noop,
`list_feature_requests`, `get_queue_status`) to guarantee the wire format.

## 9. UI changes

- **Sidebar** gains two entries: `Settings` (gear icon) and `Backlog`
  (stack icon). Existing four pages stay.
- **Status** page gains one `QueueTile` row showing pending / in_progress
  / done / failed / blocked counts, with a "View all tasks" link that
  expands a sub-table.
- **Settings** page: current LLM info card, provider dropdown (enum from
  `available_providers`), model text field, "Save as default" checkbox,
  Apply button. On success, toast + refetch `get_llm_info`.
- **Backlog** page: tabbed by scope (`Solution` | `SAGE Framework`),
  submit form in a collapsible panel, list with status badge, action
  menu per row (approve / reject / complete — only visible to owners; all
  users in Phase 2 since no auth).

## 10. Docs updates (part of Phase 2 deliverables)

- `CLAUDE.md` — Quick Start table gains "Phase 2 operator tools" row.
- `.claude/docs/interfaces/desktop-gui.md` — new "Phase 2" section with
  RPC methods, error variants, and sidebar changes.
- `.claude/docs/architecture.md` — two-backlog section gets a note that
  sage-desktop now submits solution feature requests directly (same DB).
- `docs/superpowers/specs/2026-04-17-sage-desktop-phase2-design.md` — this
  file, committed before implementation starts.

## 11. Acceptance criteria (Phase 2 "done")

Phase 2 is complete when **all** of the following are true:

1. `make test-desktop` passes — target shows **≥ 210** tests total (82 sidecar + 40 new + 17 Rust + 10 new + 50 React + 25 new).
2. `make test-desktop-e2e` round-trips all three new methods.
3. `src/core/feature_request_store.py` exists, `src/interface/api.py`
   uses it exclusively, and the existing FastAPI feature-request tests
   (`tests/test_api.py::test_feature_request*`) still pass unchanged.
4. Settings page lets a user switch from one provider to another and the
   change is visible in the subsequent `get_status` handshake.
5. Backlog page submits a new feature request, and the same record
   appears in the FastAPI Web UI's `/features/list` response — proving
   shared-state parity.
6. Status page shows queue counts and auto-refreshes on the same 5 s
   cadence as the health tile.
7. Docs §10 updates committed.
8. All four existing Phase 1 pages still render and all 149 existing
   tests still pass.

## 12. Out of scope / deferred

- **Phase 2b — Operator UX**: Chat / Analyze, Product Owner wizard,
  solution switcher. Each warrants its own spec once Phase 2 lands.
- **Phase 1.5 — Evolution**: still blocked on `src/core/evolution/`
  merging to `main` (tracked separately).

## 13. Risks

| Risk | Mitigation |
|---|---|
| `_execute_llm_switch` config.yaml rewrite corrupts file on Windows path quirks | Handler catches and maps to `LlmSwitchFailed`; file write already has try/except |
| Extracted `FeatureRequestStore` breaks existing FastAPI tests | Task 1 is the extraction + test migration; nothing else ships until those pass |
| Queue manager isn't initialised when sidecar runs standalone | Handler handles the `RuntimeError` from `get_task_queue` and returns an empty-but-valid status |

## 14. File structure additions

```
src/core/feature_request_store.py       (new — extracted from api.py)
tests/test_feature_request_store.py     (new — ~12 tests)
sage-desktop/sidecar/handlers/llm.py        (new)
sage-desktop/sidecar/handlers/backlog.py    (new)
sage-desktop/sidecar/handlers/queue.py      (new)
sage-desktop/sidecar/tests/test_llm.py
sage-desktop/sidecar/tests/test_backlog.py
sage-desktop/sidecar/tests/test_queue.py
sage-desktop/src-tauri/src/commands/llm.rs
sage-desktop/src-tauri/src/commands/backlog.rs
sage-desktop/src-tauri/src/commands/queue.rs
sage-desktop/src/api/types.ts              (extended)
sage-desktop/src/api/client.ts             (extended)
sage-desktop/src/hooks/useLlm.ts
sage-desktop/src/hooks/useBacklog.ts
sage-desktop/src/hooks/useQueue.ts
sage-desktop/src/pages/Settings.tsx
sage-desktop/src/pages/Backlog.tsx
sage-desktop/src/components/domain/QueueTile.tsx
sage-desktop/src/components/domain/FeatureRequestRow.tsx
sage-desktop/src/components/domain/LlmProviderForm.tsx
```

No files deleted.
