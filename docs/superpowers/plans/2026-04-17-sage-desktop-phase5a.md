# sage-desktop Phase 5a — Evolution UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship an `/evolution` page in sage-desktop that shows the gym leaderboard, lets the user trigger a training round, and displays recent history — all via 4 new NDJSON RPCs wrapping `AgentGym` + `GymDB` directly (no HTTP).

**Architecture:** Sidecar handlers reuse `src.core.agent_gym.AgentGym` through the same "lazy-import on wire, swap module-level `_fn`" pattern that Phase 3c onboarding uses. Tauri commands are thin proxies. React uses a single `/evolution` page with one `useQuery` per read RPC and a `useMutation` for train.

**Tech Stack:** Python 3.12 (sidecar), Rust (Tauri), TypeScript + React 18 + TanStack Query (web), Vitest (unit), Playwright (pixel-diff).

---

### Task 1: Sidecar handler — `evolution.leaderboard`

**Files:**
- Create: `sage-desktop/sidecar/handlers/evolution.py`
- Create: `sage-desktop/sidecar/tests/test_evolution.py`

- [ ] **Step 1: Write failing test for leaderboard happy path**

Add to `sage-desktop/sidecar/tests/test_evolution.py`:

```python
"""Tests for the sidecar evolution handler."""
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import handlers.evolution as evo  # noqa: E402
from rpc import RpcError  # noqa: E402


class _FakeGym:
    """Minimal AgentGym stub for handler tests."""

    def __init__(self, leaderboard=None, history=None, analytics=None, train_result=None, train_exc=None):
        self._leaderboard = leaderboard or []
        self._history = history or []
        self._analytics = analytics or {}
        self._train_result = train_result
        self._train_exc = train_exc

    def get_leaderboard(self):
        return list(self._leaderboard)

    def get_history(self, limit=50):
        return list(self._history[:limit])

    def analytics(self, role="", skill=""):
        return {"role": role, "skill": skill, **self._analytics}

    def train(self, role, difficulty="", skill_name="", exercise_id="", enable_peer_review=False):
        if self._train_exc is not None:
            raise self._train_exc
        return self._train_result


def test_leaderboard_happy_path(monkeypatch):
    rows = [
        {"agent_role": "developer", "rating": 1215.3, "rating_deviation": 92.1,
         "wins": 14, "losses": 6, "win_rate": 0.70, "sessions": 20,
         "streak": 3, "best_score": 94.0},
    ]
    monkeypatch.setattr(evo, "_gym", _FakeGym(leaderboard=rows))
    out = evo.leaderboard({})
    assert out["leaderboard"][0]["agent_role"] == "developer"
    assert out["leaderboard"][0]["rating"] == 1215.3
    assert out["stats"]["total_agents"] == 1
    assert out["stats"]["total_sessions"] == 20
```

- [ ] **Step 2: Run the test — it must fail at import**

Run from `C:/System-Team-repos/SAGE/sage-desktop`:

```
../.venv/Scripts/python.exe -m pytest sidecar/tests/test_evolution.py::test_leaderboard_happy_path -v
```

Expected: collection error (handlers.evolution not found) or RpcError-like failure.

- [ ] **Step 3: Implement minimum handler + `_gym` hook**

Create `sage-desktop/sidecar/handlers/evolution.py`:

```python
"""Handler for agent-gym (evolution) RPCs.

Thin wrapper over ``src.core.agent_gym.AgentGym``. The gym does the
heavy lifting (Glicko-2 updates, SQLite persistence, LLM-driven training).
We validate inputs, forward kwargs, and map gym exceptions to JSON-RPC
error codes.

Error mapping:
    RuntimeError (LLM unavailable)    → ``RPC_SIDECAR_ERROR``  (-32000)
    ValueError   (bad role/difficulty) → ``RPC_INVALID_PARAMS`` (-32602)
"""
from typing import Any, Optional

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError

# Wired at startup by app._wire_handlers (None when the framework import fails).
_gym: Optional[Any] = None


def _require_gym() -> Any:
    if _gym is None:
        raise RpcError(
            RPC_SIDECAR_ERROR,
            "evolution handlers are not wired (AgentGym import failed)",
        )
    return _gym


def leaderboard(params: Any):
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    gym = _require_gym()
    rows = list(gym.get_leaderboard())
    total_sessions = sum(int(r.get("sessions", 0)) for r in rows)
    total_agents = len(rows)
    avg_rating = (
        sum(float(r.get("rating", 0.0)) for r in rows) / total_agents
        if total_agents
        else 0.0
    )
    return {
        "leaderboard": rows,
        "stats": {
            "total_agents": total_agents,
            "total_sessions": total_sessions,
            "avg_rating": round(avg_rating, 2),
        },
    }
```

- [ ] **Step 4: Run the test — it must pass**

Same command. Expected: `1 passed`.

- [ ] **Step 5: Commit**

```
git add sage-desktop/sidecar/handlers/evolution.py sage-desktop/sidecar/tests/test_evolution.py
git commit -m "feat(sidecar): evolution.leaderboard handler"
```

---

### Task 2: Sidecar handler — `evolution.history` + `evolution.analytics`

**Files:**
- Modify: `sage-desktop/sidecar/handlers/evolution.py`
- Modify: `sage-desktop/sidecar/tests/test_evolution.py`

- [ ] **Step 1: Write failing tests for history + analytics**

Append to `test_evolution.py`:

```python
def test_history_default_limit(monkeypatch):
    sessions = [{"session_id": f"s{i}", "score": 50.0 + i} for i in range(60)]
    monkeypatch.setattr(evo, "_gym", _FakeGym(history=sessions))
    out = evo.history({})
    assert len(out["sessions"]) == 50
    assert out["sessions"][0]["session_id"] == "s0"


def test_history_respects_custom_limit(monkeypatch):
    sessions = [{"session_id": f"s{i}"} for i in range(20)]
    monkeypatch.setattr(evo, "_gym", _FakeGym(history=sessions))
    out = evo.history({"limit": 5})
    assert len(out["sessions"]) == 5


def test_analytics_forwards_role_and_skill(monkeypatch):
    monkeypatch.setattr(evo, "_gym", _FakeGym(analytics={"weakness_map": []}))
    out = evo.analytics({"role": "developer", "skill": "openswe"})
    assert out["role"] == "developer"
    assert out["skill"] == "openswe"
    assert out["weakness_map"] == []


def test_analytics_unknown_role_returns_whatever_gym_returns(monkeypatch):
    monkeypatch.setattr(evo, "_gym", _FakeGym(analytics={"score_trend": []}))
    out = evo.analytics({"role": "not_a_real_role"})
    assert out["score_trend"] == []
```

- [ ] **Step 2: Run the 4 tests — they must fail**

```
../.venv/Scripts/python.exe -m pytest sidecar/tests/test_evolution.py -v
```

Expected: 4 failures with `AttributeError: module 'handlers.evolution' has no attribute 'history'`.

- [ ] **Step 3: Implement `history` + `analytics`**

Append to `handlers/evolution.py`:

```python
def history(params: Any):
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    limit_raw = params.get("limit", 50)
    try:
        limit = int(limit_raw)
    except (TypeError, ValueError):
        raise RpcError(RPC_INVALID_PARAMS, "limit must be an integer")
    if limit <= 0:
        raise RpcError(RPC_INVALID_PARAMS, "limit must be positive")
    gym = _require_gym()
    return {"sessions": list(gym.get_history(limit=limit))}


def analytics(params: Any):
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    role = params.get("role", "")
    skill = params.get("skill", "")
    if role is not None and not isinstance(role, str):
        raise RpcError(RPC_INVALID_PARAMS, "role must be a string")
    if skill is not None and not isinstance(skill, str):
        raise RpcError(RPC_INVALID_PARAMS, "skill must be a string")
    gym = _require_gym()
    return gym.analytics(role=role or "", skill=skill or "")
```

- [ ] **Step 4: Run the 5 tests — they must all pass**

Expected: `5 passed`.

- [ ] **Step 5: Commit**

```
git add sage-desktop/sidecar/handlers/evolution.py sage-desktop/sidecar/tests/test_evolution.py
git commit -m "feat(sidecar): evolution.history + evolution.analytics"
```

---

### Task 3: Sidecar handler — `evolution.train`

**Files:**
- Modify: `sage-desktop/sidecar/handlers/evolution.py`
- Modify: `sage-desktop/sidecar/tests/test_evolution.py`

- [ ] **Step 1: Write failing tests for train**

Append to `test_evolution.py`:

```python
def test_train_requires_role(monkeypatch):
    monkeypatch.setattr(evo, "_gym", _FakeGym())
    with pytest.raises(RpcError) as e:
        evo.train({})
    assert e.value.code == -32602


def test_train_happy_path(monkeypatch):
    session = {
        "session_id": "2026-04-17T12:00:00",
        "agent_role": "developer",
        "status": "completed",
        "grade": {"score": 78.0, "passed": True},
        "elo_before": 1215.3,
        "elo_after": 1228.9,
        "reflection": "Missed the empty-input edge case.",
        "improvement_plan": ["write guard clause"],
        "duration_s": 14.2,
    }
    monkeypatch.setattr(evo, "_gym", _FakeGym(train_result=session))
    out = evo.train({"role": "developer", "difficulty": "beginner"})
    assert out["status"] == "completed"
    assert out["elo_after"] == 1228.9


def test_train_llm_unavailable_maps_to_sidecar_down(monkeypatch):
    monkeypatch.setattr(
        evo,
        "_gym",
        _FakeGym(train_exc=RuntimeError("LLM down")),
    )
    with pytest.raises(RpcError) as e:
        evo.train({"role": "developer"})
    assert e.value.code == -32000
```

- [ ] **Step 2: Run the 3 new tests — they must fail**

```
../.venv/Scripts/python.exe -m pytest sidecar/tests/test_evolution.py -v
```

Expected: `AttributeError ... no attribute 'train'` for all 3 new tests.

- [ ] **Step 3: Implement `train`**

Append to `handlers/evolution.py`:

```python
def train(params: Any):
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    role = params.get("role")
    if not isinstance(role, str) or not role.strip():
        raise RpcError(RPC_INVALID_PARAMS, "role is required")
    difficulty = params.get("difficulty") or ""
    skill_name = params.get("skill_name") or ""
    exercise_id = params.get("exercise_id") or ""
    gym = _require_gym()
    try:
        session = gym.train(
            role=role,
            difficulty=difficulty,
            skill_name=skill_name,
            exercise_id=exercise_id,
        )
    except ValueError as e:
        raise RpcError(RPC_INVALID_PARAMS, f"invalid training params: {e}") from e
    except RuntimeError as e:
        raise RpcError(RPC_SIDECAR_ERROR, f"gym unavailable: {e}") from e
    if hasattr(session, "to_dict"):
        session = session.to_dict()
    return session
```

- [ ] **Step 4: Run the 8 tests — they must all pass**

Expected: `8 passed`.

- [ ] **Step 5: Commit**

```
git add sage-desktop/sidecar/handlers/evolution.py sage-desktop/sidecar/tests/test_evolution.py
git commit -m "feat(sidecar): evolution.train handler"
```

---

### Task 4: Register handlers + wire `AgentGym` into sidecar

**Files:**
- Modify: `sage-desktop/sidecar/app.py`

- [ ] **Step 1: Add import + dispatcher registrations**

In `sage-desktop/sidecar/app.py`, edit the `from handlers import (...)` tuple to add `evolution`:

```python
from handlers import (
    agents,
    approvals,
    audit,
    backlog,
    builds,
    evolution,
    handshake,
    llm,
    onboarding,
    queue,
    solutions,
    status,
    yaml_edit,
)
```

In `_build_dispatcher()`, add:

```python
    d.register("evolution.leaderboard", evolution.leaderboard)
    d.register("evolution.history", evolution.history)
    d.register("evolution.analytics", evolution.analytics)
    d.register("evolution.train", evolution.train)
```

- [ ] **Step 2: Wire `AgentGym` into `evolution._gym`**

In `_wire_handlers(...)`, after the `onboarding._generate_fn` wire block, add:

```python
    try:
        from src.core.agent_gym import AgentGym, GymDB

        _db_path = ".gym_data.db"
        if solution_path:
            _db_path = str(solution_path / ".sage" / "gym_data.db")
        evolution._gym = AgentGym(GymDB(_db_path))
    except Exception as e:  # noqa: BLE001
        logging.warning("AgentGym unavailable: %s", e)
```

- [ ] **Step 3: Verify app loads cleanly**

Run full sidecar test suite to check nothing regressed:

```
../.venv/Scripts/python.exe -m pytest sidecar/tests -q
```

Expected: all green (190+ tests).

- [ ] **Step 4: Commit**

```
git add sage-desktop/sidecar/app.py
git commit -m "feat(sidecar): register evolution.* handlers + wire AgentGym"
```

---

### Task 5: Rust — Tauri proxy commands

**Files:**
- Create: `sage-desktop/src-tauri/src/commands/evolution.rs`
- Modify: `sage-desktop/src-tauri/src/commands/mod.rs`
- Modify: `sage-desktop/src-tauri/src/lib.rs`

- [ ] **Step 1: Create the 4 proxy commands**

Create `sage-desktop/src-tauri/src/commands/evolution.rs`:

```rust
//! Evolution (Agent Gym) — proxies to `evolution.*` on the sidecar.
//!
//! `evolution_train` is long-running (full gym training round) but the
//! sidecar already serializes through its own stdin/stdout mutex, so a
//! read-lock on the Tauri side is sufficient.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn evolution_leaderboard(
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar.read().await.call("evolution.leaderboard", json!({})).await
}

#[tauri::command]
pub async fn evolution_history(
    limit: Option<u32>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("evolution.history", json!({"limit": limit.unwrap_or(50)}))
        .await
}

#[tauri::command]
pub async fn evolution_analytics(
    role: Option<String>,
    skill: Option<String>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "evolution.analytics",
            json!({
                "role": role.unwrap_or_default(),
                "skill": skill.unwrap_or_default(),
            }),
        )
        .await
}

#[tauri::command]
pub async fn evolution_train(
    role: String,
    difficulty: Option<String>,
    skill_name: Option<String>,
    exercise_id: Option<String>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "evolution.train",
            json!({
                "role": role,
                "difficulty": difficulty.unwrap_or_default(),
                "skill_name": skill_name.unwrap_or_default(),
                "exercise_id": exercise_id.unwrap_or_default(),
            }),
        )
        .await
}
```

- [ ] **Step 2: Add module declaration**

In `sage-desktop/src-tauri/src/commands/mod.rs`, add:

```rust
pub mod evolution;
```

- [ ] **Step 3: Register handlers**

In `sage-desktop/src-tauri/src/lib.rs`, find the `.invoke_handler(tauri::generate_handler![...])` block and add the 4 new commands (preserve existing entries, add after onboarding_generate):

```rust
            commands::evolution::evolution_leaderboard,
            commands::evolution::evolution_history,
            commands::evolution::evolution_analytics,
            commands::evolution::evolution_train,
```

- [ ] **Step 4: Compile-check**

```
cd sage-desktop/src-tauri && cargo check --no-default-features
```

Expected: compiles clean (warnings are OK).

- [ ] **Step 5: Commit**

```
git add sage-desktop/src-tauri/src/commands/evolution.rs sage-desktop/src-tauri/src/commands/mod.rs sage-desktop/src-tauri/src/lib.rs
git commit -m "feat(desktop-rs): evolution_* Tauri proxy commands"
```

---

### Task 6: React — types + API client

**Files:**
- Modify: `sage-desktop/src/api/types.ts`
- Modify: `sage-desktop/src/api/client.ts`

- [ ] **Step 1: Add types**

Append to `sage-desktop/src/api/types.ts`:

```typescript
// ── Evolution (Agent Gym) ─────────────────────────────────────────────────

export interface LeaderboardEntry {
  agent_role: string;
  rating: number;
  rating_deviation: number;
  wins: number;
  losses: number;
  win_rate: number;
  sessions: number;
  streak?: number;
  best_score?: number;
}

export interface LeaderboardResult {
  leaderboard: LeaderboardEntry[];
  stats: {
    total_agents: number;
    total_sessions: number;
    avg_rating: number;
  };
}

export interface HistorySession {
  session_id: string;
  agent_role: string;
  exercise_id?: string;
  score?: number;
  passed?: boolean;
  timestamp?: string;
}

export interface HistoryResult {
  sessions: HistorySession[];
}

// Analytics is a loose bag of sub-reports; typed as a record so the UI
// can render whichever slices the framework happens to include.
export type AnalyticsResult = Record<string, unknown>;

export interface TrainParams {
  role: string;
  difficulty?: string;
  skill_name?: string;
  exercise_id?: string;
}

export interface TrainResult {
  session_id: string;
  agent_role: string;
  status: string;
  grade?: { score: number; passed: boolean };
  elo_before?: number;
  elo_after?: number;
  reflection?: string;
  improvement_plan?: string[];
  duration_s?: number;
}
```

- [ ] **Step 2: Add client functions**

In `sage-desktop/src/api/client.ts`, extend the imports block:

```typescript
  LeaderboardResult,
  HistoryResult,
  AnalyticsResult,
  TrainParams,
  TrainResult,
```

Add a new section before the re-exports tail:

```typescript
// ── Evolution (Agent Gym) ─────────────────────────────────────────────────

export const evolutionLeaderboard = () =>
  call<LeaderboardResult>("evolution_leaderboard");

export const evolutionHistory = (limit?: number) =>
  call<HistoryResult>("evolution_history", { limit });

export const evolutionAnalytics = (role?: string, skill?: string) =>
  call<AnalyticsResult>("evolution_analytics", { role, skill });

export const evolutionTrain = (params: TrainParams) =>
  call<TrainResult>("evolution_train", params);
```

Also add the 5 new types to the re-export block at the end.

- [ ] **Step 3: Vitest sanity**

Run:

```
cd sage-desktop && npx vitest run src/api --reporter=dot
```

Expected: any existing api tests still green (or collection-only pass if no api tests exist).

- [ ] **Step 4: Commit**

```
git add sage-desktop/src/api/types.ts sage-desktop/src/api/client.ts
git commit -m "feat(desktop-web): types + client for evolution.*"
```

---

### Task 7: React — `useEvolution` hooks

**Files:**
- Create: `sage-desktop/src/hooks/useEvolution.ts`
- Create: `sage-desktop/src/__tests__/hooks/useEvolution.test.ts`

- [ ] **Step 1: Write failing hook tests**

Create `sage-desktop/src/__tests__/hooks/useEvolution.test.ts`:

```typescript
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import * as client from "@/api/client";
import {
  useLeaderboard,
  useHistory,
  useAnalytics,
  useTrainAgent,
  leaderboardKey,
  historyKey,
} from "@/hooks/useEvolution";

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return {
    qc,
    Wrapper: ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    ),
  };
}

describe("useLeaderboard", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("returns leaderboard data", async () => {
    vi.spyOn(client, "evolutionLeaderboard").mockResolvedValue({
      leaderboard: [
        { agent_role: "developer", rating: 1200, rating_deviation: 90,
          wins: 10, losses: 5, win_rate: 0.66, sessions: 15 },
      ],
      stats: { total_agents: 1, total_sessions: 15, avg_rating: 1200 },
    });
    const { Wrapper } = makeWrapper();
    const { result } = renderHook(() => useLeaderboard(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.leaderboard[0].agent_role).toBe("developer");
  });
});

describe("useHistory", () => {
  it("passes limit through to client", async () => {
    const spy = vi
      .spyOn(client, "evolutionHistory")
      .mockResolvedValue({ sessions: [] });
    const { Wrapper } = makeWrapper();
    renderHook(() => useHistory(25), { wrapper: Wrapper });
    await waitFor(() => expect(spy).toHaveBeenCalledWith(25));
  });
});

describe("useAnalytics", () => {
  it("only runs when a role is selected", async () => {
    const spy = vi
      .spyOn(client, "evolutionAnalytics")
      .mockResolvedValue({ score_trend: [] });
    const { Wrapper } = makeWrapper();
    const { rerender } = renderHook(
      ({ role }: { role: string }) => useAnalytics(role),
      { wrapper: Wrapper, initialProps: { role: "" } },
    );
    // No fetch yet
    expect(spy).not.toHaveBeenCalled();
    rerender({ role: "developer" });
    await waitFor(() => expect(spy).toHaveBeenCalledWith("developer", undefined));
  });
});

describe("useTrainAgent", () => {
  it("invalidates leaderboard and history on success", async () => {
    vi.spyOn(client, "evolutionTrain").mockResolvedValue({
      session_id: "s1",
      agent_role: "developer",
      status: "completed",
      elo_before: 1200,
      elo_after: 1220,
    });
    const { qc, Wrapper } = makeWrapper();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useTrainAgent(), { wrapper: Wrapper });
    await act(async () => {
      await result.current.mutateAsync({ role: "developer" });
    });
    // Must invalidate both queries
    const keys = invalidateSpy.mock.calls.map((c) => c[0]?.queryKey);
    expect(keys).toContainEqual(leaderboardKey);
    expect(keys).toContainEqual(historyKey);
  });
});
```

- [ ] **Step 2: Run tests — they must fail (module missing)**

```
cd sage-desktop && npx vitest run src/__tests__/hooks/useEvolution.test.ts
```

Expected: `Failed to resolve import "@/hooks/useEvolution"`.

- [ ] **Step 3: Implement the hooks**

Create `sage-desktop/src/hooks/useEvolution.ts`:

```typescript
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  evolutionAnalytics,
  evolutionHistory,
  evolutionLeaderboard,
  evolutionTrain,
} from "@/api/client";
import type {
  AnalyticsResult,
  DesktopError,
  HistoryResult,
  LeaderboardResult,
  TrainParams,
  TrainResult,
} from "@/api/types";

export const leaderboardKey = ["evolution", "leaderboard"] as const;
export const historyKey = ["evolution", "history"] as const;
export const analyticsKey = (role: string, skill = "") =>
  ["evolution", "analytics", role, skill] as const;

export function useLeaderboard() {
  return useQuery<LeaderboardResult, DesktopError>({
    queryKey: leaderboardKey,
    queryFn: () => evolutionLeaderboard(),
  });
}

export function useHistory(limit = 50) {
  return useQuery<HistoryResult, DesktopError>({
    queryKey: [...historyKey, limit],
    queryFn: () => evolutionHistory(limit),
  });
}

export function useAnalytics(role: string, skill?: string) {
  return useQuery<AnalyticsResult, DesktopError>({
    queryKey: analyticsKey(role, skill ?? ""),
    queryFn: () => evolutionAnalytics(role, skill),
    enabled: Boolean(role),
  });
}

/**
 * Trigger a gym training round. On success the leaderboard + history
 * auto-refetch so the UI reflects the new rating and the new session.
 */
export function useTrainAgent() {
  const qc = useQueryClient();
  return useMutation<TrainResult, DesktopError, TrainParams>({
    mutationFn: (p) => evolutionTrain(p),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: leaderboardKey });
      qc.invalidateQueries({ queryKey: historyKey });
    },
  });
}
```

- [ ] **Step 4: Run the 4 tests — they must pass**

Expected: `4 passed`.

- [ ] **Step 5: Commit**

```
git add sage-desktop/src/hooks/useEvolution.ts sage-desktop/src/__tests__/hooks/useEvolution.test.ts
git commit -m "feat(desktop-web): useLeaderboard/useHistory/useAnalytics/useTrainAgent hooks"
```

---

### Task 8: React — `Leaderboard` component

**Files:**
- Create: `sage-desktop/src/components/domain/Leaderboard.tsx`
- Create: `sage-desktop/src/__tests__/components/Leaderboard.test.tsx`

- [ ] **Step 1: Write failing component tests**

Create `sage-desktop/src/__tests__/components/Leaderboard.test.tsx`:

```typescript
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Leaderboard } from "@/components/domain/Leaderboard";

const rows = [
  { agent_role: "developer", rating: 1215.3, rating_deviation: 92.1,
    wins: 14, losses: 6, win_rate: 0.7, sessions: 20 },
  { agent_role: "analyst", rating: 1102.7, rating_deviation: 118,
    wins: 5, losses: 7, win_rate: 0.42, sessions: 12 },
];

describe("Leaderboard", () => {
  it("renders one row per entry", () => {
    render(<Leaderboard rows={rows} selectedRole={null} onSelect={() => {}} />);
    expect(screen.getByText("developer")).toBeInTheDocument();
    expect(screen.getByText("analyst")).toBeInTheDocument();
  });

  it("calls onSelect with the clicked role", () => {
    const onSelect = vi.fn();
    render(<Leaderboard rows={rows} selectedRole={null} onSelect={onSelect} />);
    fireEvent.click(screen.getByText("developer"));
    expect(onSelect).toHaveBeenCalledWith("developer");
  });

  it("renders empty-state when rows is empty", () => {
    render(<Leaderboard rows={[]} selectedRole={null} onSelect={() => {}} />);
    expect(screen.getByText(/no agents yet/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests — they must fail**

```
cd sage-desktop && npx vitest run src/__tests__/components/Leaderboard.test.tsx
```

Expected: import error or no such component.

- [ ] **Step 3: Implement the component**

Create `sage-desktop/src/components/domain/Leaderboard.tsx`:

```typescript
import clsx from "clsx";

import type { LeaderboardEntry } from "@/api/types";

export interface LeaderboardProps {
  rows: LeaderboardEntry[];
  selectedRole: string | null;
  onSelect: (role: string) => void;
}

export function Leaderboard({ rows, selectedRole, onSelect }: LeaderboardProps) {
  if (rows.length === 0) {
    return (
      <div className="rounded border border-sage-100 bg-white p-6 text-sm text-slate-500">
        No agents yet. Run a training round to see ratings appear here.
      </div>
    );
  }
  return (
    <table className="w-full border-separate border-spacing-0 text-sm">
      <thead className="text-left text-xs uppercase text-sage-600">
        <tr>
          <th className="border-b border-sage-100 px-3 py-2">Role</th>
          <th className="border-b border-sage-100 px-3 py-2">Rating</th>
          <th className="border-b border-sage-100 px-3 py-2">RD</th>
          <th className="border-b border-sage-100 px-3 py-2">Wins</th>
          <th className="border-b border-sage-100 px-3 py-2">Losses</th>
          <th className="border-b border-sage-100 px-3 py-2">Win %</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr
            key={r.agent_role}
            className={clsx(
              "cursor-pointer hover:bg-sage-50",
              selectedRole === r.agent_role && "bg-sage-100",
            )}
            onClick={() => onSelect(r.agent_role)}
          >
            <td className="border-b border-sage-50 px-3 py-2 font-medium">
              {r.agent_role}
            </td>
            <td className="border-b border-sage-50 px-3 py-2">
              {r.rating.toFixed(1)}
            </td>
            <td className="border-b border-sage-50 px-3 py-2">
              {r.rating_deviation.toFixed(1)}
            </td>
            <td className="border-b border-sage-50 px-3 py-2">{r.wins}</td>
            <td className="border-b border-sage-50 px-3 py-2">{r.losses}</td>
            <td className="border-b border-sage-50 px-3 py-2">
              {Math.round(r.win_rate * 100)}%
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 4: Run tests — they must pass**

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```
git add sage-desktop/src/components/domain/Leaderboard.tsx sage-desktop/src/__tests__/components/Leaderboard.test.tsx
git commit -m "feat(desktop-web): Leaderboard component"
```

---

### Task 9: React — `TrainPanel` component

**Files:**
- Create: `sage-desktop/src/components/domain/TrainPanel.tsx`
- Create: `sage-desktop/src/__tests__/components/TrainPanel.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `sage-desktop/src/__tests__/components/TrainPanel.test.tsx`:

```typescript
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TrainPanel } from "@/components/domain/TrainPanel";

describe("TrainPanel", () => {
  it("disables Train until a role is chosen", () => {
    render(
      <TrainPanel
        roles={["developer", "analyst"]}
        onTrain={() => {}}
        isPending={false}
        error={null}
        lastResult={null}
      />,
    );
    const btn = screen.getByRole("button", { name: /train/i });
    expect(btn).toBeDisabled();
  });

  it("passes role + difficulty to onTrain", () => {
    const onTrain = vi.fn();
    render(
      <TrainPanel
        roles={["developer"]}
        onTrain={onTrain}
        isPending={false}
        error={null}
        lastResult={null}
      />,
    );
    fireEvent.change(screen.getByLabelText(/role/i), {
      target: { value: "developer" },
    });
    fireEvent.change(screen.getByLabelText(/difficulty/i), {
      target: { value: "beginner" },
    });
    fireEvent.click(screen.getByRole("button", { name: /train/i }));
    expect(onTrain).toHaveBeenCalledWith({
      role: "developer",
      difficulty: "beginner",
    });
  });

  it("renders elo delta panel on successful result", () => {
    render(
      <TrainPanel
        roles={["developer"]}
        onTrain={() => {}}
        isPending={false}
        error={null}
        lastResult={{
          session_id: "s1",
          agent_role: "developer",
          status: "completed",
          grade: { score: 78, passed: true },
          elo_before: 1215.3,
          elo_after: 1228.9,
        }}
      />,
    );
    // Show a delta with the + sign for positive movement
    expect(screen.getByText(/\+13\.6/)).toBeInTheDocument();
    expect(screen.getByText(/1215\.3/)).toBeInTheDocument();
    expect(screen.getByText(/1228\.9/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests — they must fail**

```
cd sage-desktop && npx vitest run src/__tests__/components/TrainPanel.test.tsx
```

Expected: import error.

- [ ] **Step 3: Implement the component**

Create `sage-desktop/src/components/domain/TrainPanel.tsx`:

```typescript
import { useState } from "react";

import type { DesktopError, TrainParams, TrainResult } from "@/api/types";

export interface TrainPanelProps {
  roles: string[];
  onTrain: (p: TrainParams) => void;
  isPending: boolean;
  error: DesktopError | null;
  lastResult: TrainResult | null;
}

const DIFFICULTIES = ["", "beginner", "intermediate", "advanced", "expert"];

export function TrainPanel({
  roles,
  onTrain,
  isPending,
  error,
  lastResult,
}: TrainPanelProps) {
  const [role, setRole] = useState("");
  const [difficulty, setDifficulty] = useState("");

  const canSubmit = Boolean(role) && !isPending;

  const delta =
    lastResult && typeof lastResult.elo_before === "number" &&
    typeof lastResult.elo_after === "number"
      ? lastResult.elo_after - lastResult.elo_before
      : null;

  return (
    <div className="rounded border border-sage-100 bg-white p-4 text-sm">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col">
          <span className="text-xs text-sage-600">Role</span>
          <select
            aria-label="Role"
            className="rounded border border-sage-200 px-2 py-1"
            value={role}
            onChange={(e) => setRole(e.target.value)}
          >
            <option value="">— choose —</option>
            {roles.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col">
          <span className="text-xs text-sage-600">Difficulty</span>
          <select
            aria-label="Difficulty"
            className="rounded border border-sage-200 px-2 py-1"
            value={difficulty}
            onChange={(e) => setDifficulty(e.target.value)}
          >
            {DIFFICULTIES.map((d) => (
              <option key={d || "auto"} value={d}>
                {d || "auto"}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="rounded bg-sage-600 px-4 py-2 text-white hover:bg-sage-700 disabled:cursor-not-allowed disabled:bg-sage-300"
          disabled={!canSubmit}
          onClick={() => onTrain({ role, difficulty })}
        >
          {isPending ? "Training…" : "Train"}
        </button>
      </div>

      {error && (
        <div className="mt-3 rounded border border-red-200 bg-red-50 p-3 text-red-900">
          Training failed: {error.kind}
        </div>
      )}

      {lastResult && delta !== null && (
        <div className="mt-3 rounded border border-green-200 bg-green-50 p-3 text-green-900">
          ✓ Trained {lastResult.agent_role} · score{" "}
          {lastResult.grade?.score?.toFixed(1) ?? "—"} · rating{" "}
          {lastResult.elo_before?.toFixed(1)} →{" "}
          {lastResult.elo_after?.toFixed(1)} (
          {delta >= 0 ? "+" : ""}
          {delta.toFixed(1)})
          {lastResult.reflection && (
            <div className="mt-2 text-xs text-green-800">
              Reflection: {lastResult.reflection}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests — they must pass**

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```
git add sage-desktop/src/components/domain/TrainPanel.tsx sage-desktop/src/__tests__/components/TrainPanel.test.tsx
git commit -m "feat(desktop-web): TrainPanel component"
```

---

### Task 10: React — `RecentHistory` component

**Files:**
- Create: `sage-desktop/src/components/domain/RecentHistory.tsx`
- Create: `sage-desktop/src/__tests__/components/RecentHistory.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `sage-desktop/src/__tests__/components/RecentHistory.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RecentHistory } from "@/components/domain/RecentHistory";

describe("RecentHistory", () => {
  it("renders empty-state when no sessions", () => {
    render(<RecentHistory sessions={[]} />);
    expect(screen.getByText(/no training sessions yet/i)).toBeInTheDocument();
  });

  it("renders one row per session", () => {
    render(
      <RecentHistory
        sessions={[
          { session_id: "s1", agent_role: "developer",
            exercise_id: "openswe_x_ab", score: 78, passed: true,
            timestamp: "2026-04-17T12:00:00Z" },
          { session_id: "s2", agent_role: "analyst",
            exercise_id: "openml_y_cd", score: 62, passed: false,
            timestamp: "2026-04-17T11:00:00Z" },
        ]}
      />,
    );
    expect(screen.getByText("s1")).toBeInTheDocument();
    expect(screen.getByText("s2")).toBeInTheDocument();
    expect(screen.getByText("developer")).toBeInTheDocument();
    expect(screen.getByText("analyst")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests — they must fail**

```
cd sage-desktop && npx vitest run src/__tests__/components/RecentHistory.test.tsx
```

- [ ] **Step 3: Implement the component**

Create `sage-desktop/src/components/domain/RecentHistory.tsx`:

```typescript
import type { HistorySession } from "@/api/types";

export interface RecentHistoryProps {
  sessions: HistorySession[];
}

export function RecentHistory({ sessions }: RecentHistoryProps) {
  if (sessions.length === 0) {
    return (
      <div className="rounded border border-sage-100 bg-white p-6 text-sm text-slate-500">
        No training sessions yet.
      </div>
    );
  }
  return (
    <table className="w-full border-separate border-spacing-0 text-sm">
      <thead className="text-left text-xs uppercase text-sage-600">
        <tr>
          <th className="border-b border-sage-100 px-3 py-2">Session</th>
          <th className="border-b border-sage-100 px-3 py-2">Role</th>
          <th className="border-b border-sage-100 px-3 py-2">Exercise</th>
          <th className="border-b border-sage-100 px-3 py-2">Score</th>
          <th className="border-b border-sage-100 px-3 py-2">Passed</th>
          <th className="border-b border-sage-100 px-3 py-2">When</th>
        </tr>
      </thead>
      <tbody>
        {sessions.map((s) => (
          <tr key={s.session_id}>
            <td className="border-b border-sage-50 px-3 py-2 font-mono text-xs">
              {s.session_id}
            </td>
            <td className="border-b border-sage-50 px-3 py-2">{s.agent_role}</td>
            <td className="border-b border-sage-50 px-3 py-2 font-mono text-xs">
              {s.exercise_id ?? "—"}
            </td>
            <td className="border-b border-sage-50 px-3 py-2">
              {s.score !== undefined ? s.score.toFixed(1) : "—"}
            </td>
            <td className="border-b border-sage-50 px-3 py-2">
              {s.passed ? "✓" : "✗"}
            </td>
            <td className="border-b border-sage-50 px-3 py-2 text-xs text-sage-600">
              {s.timestamp ?? "—"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 4: Run tests — they must pass**

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```
git add sage-desktop/src/components/domain/RecentHistory.tsx sage-desktop/src/__tests__/components/RecentHistory.test.tsx
git commit -m "feat(desktop-web): RecentHistory component"
```

---

### Task 11: React — `Analytics` component (minimal)

**Files:**
- Create: `sage-desktop/src/components/domain/Analytics.tsx`

- [ ] **Step 1: Implement the component (no test — smoke-covered by page test in Task 12)**

Create `sage-desktop/src/components/domain/Analytics.tsx`:

```typescript
import type { AnalyticsResult } from "@/api/types";

export interface AnalyticsProps {
  role: string;
  data: AnalyticsResult | undefined;
  isLoading: boolean;
}

export function Analytics({ role, data, isLoading }: AnalyticsProps) {
  if (isLoading) {
    return (
      <div className="rounded border border-sage-100 bg-white p-4 text-sm text-slate-500">
        Loading analytics for {role}…
      </div>
    );
  }
  if (!data) {
    return null;
  }
  // Render as three collapsible subsections for the most commonly present keys.
  return (
    <div className="space-y-3 rounded border border-sage-100 bg-white p-4 text-sm">
      <h3 className="text-sm font-semibold text-sage-800">
        Analytics — {role}
      </h3>
      {Object.entries(data).map(([key, value]) => (
        <details key={key} className="rounded bg-sage-50 px-3 py-2">
          <summary className="cursor-pointer text-xs uppercase tracking-wide text-sage-600">
            {key}
          </summary>
          <pre className="mt-2 max-h-60 overflow-auto text-[11px] text-sage-800">
            {JSON.stringify(value, null, 2)}
          </pre>
        </details>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

```
cd sage-desktop && npx tsc --noEmit -p tsconfig.json
```

Expected: no new errors.

- [ ] **Step 3: Commit**

```
git add sage-desktop/src/components/domain/Analytics.tsx
git commit -m "feat(desktop-web): Analytics component (collapsible JSON panels)"
```

---

### Task 12: React — `Evolution` page + route + nav

**Files:**
- Create: `sage-desktop/src/pages/Evolution.tsx`
- Create: `sage-desktop/src/__tests__/pages/Evolution.test.tsx`
- Modify: `sage-desktop/src/App.tsx`
- Modify: `sage-desktop/src/components/layout/Sidebar.tsx`
- Modify: `sage-desktop/src/components/layout/Header.tsx`

- [ ] **Step 1: Write failing integration test**

Create `sage-desktop/src/__tests__/pages/Evolution.test.tsx`:

```typescript
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as client from "@/api/client";
import Evolution from "@/pages/Evolution";

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Evolution />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Evolution page", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("renders Leaderboard, TrainPanel, and RecentHistory", async () => {
    vi.spyOn(client, "evolutionLeaderboard").mockResolvedValue({
      leaderboard: [
        { agent_role: "developer", rating: 1200, rating_deviation: 90,
          wins: 5, losses: 3, win_rate: 0.625, sessions: 8 },
      ],
      stats: { total_agents: 1, total_sessions: 8, avg_rating: 1200 },
    });
    vi.spyOn(client, "evolutionHistory").mockResolvedValue({ sessions: [] });
    renderPage();

    await waitFor(() =>
      expect(screen.getByText("developer")).toBeInTheDocument(),
    );
    expect(
      screen.getByRole("button", { name: /train/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/no training sessions yet/i),
    ).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test — must fail on missing page**

```
cd sage-desktop && npx vitest run src/__tests__/pages/Evolution.test.tsx
```

- [ ] **Step 3: Create the page**

Create `sage-desktop/src/pages/Evolution.tsx`:

```typescript
import { useState } from "react";

import { Analytics } from "@/components/domain/Analytics";
import { Leaderboard } from "@/components/domain/Leaderboard";
import { RecentHistory } from "@/components/domain/RecentHistory";
import { TrainPanel } from "@/components/domain/TrainPanel";
import {
  useAnalytics,
  useHistory,
  useLeaderboard,
  useTrainAgent,
} from "@/hooks/useEvolution";

export default function Evolution() {
  const [selectedRole, setSelectedRole] = useState<string | null>(null);

  const board = useLeaderboard();
  const history = useHistory(50);
  const train = useTrainAgent();
  const analytics = useAnalytics(selectedRole ?? "");

  const roles = board.data?.leaderboard.map((e) => e.agent_role) ?? [];

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-6">
      <div>
        <h2 className="text-lg font-semibold">Evolution</h2>
        <p className="text-sm text-gray-600">
          Agent ratings, training triggers, and recent sessions. Click a
          leaderboard row to see analytics for that role.
        </p>
      </div>

      {board.isError && (
        <div
          role="alert"
          className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-900"
        >
          Could not load leaderboard: {board.error?.kind ?? "unknown error"}
        </div>
      )}

      <section>
        <h3 className="mb-2 text-sm font-semibold text-sage-700">Leaderboard</h3>
        <Leaderboard
          rows={board.data?.leaderboard ?? []}
          selectedRole={selectedRole}
          onSelect={(r) => setSelectedRole(r === selectedRole ? null : r)}
        />
      </section>

      <section>
        <h3 className="mb-2 text-sm font-semibold text-sage-700">Train</h3>
        <TrainPanel
          roles={roles}
          isPending={train.isPending}
          error={train.error ?? null}
          lastResult={train.data ?? null}
          onTrain={(p) => train.mutate(p)}
        />
      </section>

      {selectedRole && (
        <section>
          <Analytics
            role={selectedRole}
            data={analytics.data}
            isLoading={analytics.isLoading}
          />
        </section>
      )}

      <section>
        <h3 className="mb-2 text-sm font-semibold text-sage-700">
          Recent history
        </h3>
        <RecentHistory sessions={history.data?.sessions ?? []} />
      </section>
    </div>
  );
}
```

- [ ] **Step 4: Wire the route in `App.tsx`**

Add import:

```typescript
import Evolution from "@/pages/Evolution";
```

Add route inside the `<Route element={<Layout />}>` block, before `settings`:

```tsx
<Route path="evolution" element={<Evolution />} />
```

- [ ] **Step 5: Add Sidebar nav entry**

In `sage-desktop/src/components/layout/Sidebar.tsx`, add to `NAV_ITEMS` between `audit` and `status`:

```typescript
  { to: "/evolution", label: "Evolution" },
```

- [ ] **Step 6: Add Header title mapping**

In `sage-desktop/src/components/layout/Header.tsx`, add to `TITLE_MAP`:

```typescript
  "/evolution": "Evolution",
```

- [ ] **Step 7: Run the page test — must pass**

```
cd sage-desktop && npx vitest run src/__tests__/pages/Evolution.test.tsx
```

Expected: `1 passed`.

- [ ] **Step 8: Run full vitest — all green**

```
cd sage-desktop && npm test -- --run
```

Expected: previous count + 14 new tests (4 hooks + 3 leaderboard + 3 train + 2 history + 1 page + 1 sidebar drift if it auto-picks the new nav — or manual sidebar test update in Task 13).

- [ ] **Step 9: Commit**

```
git add sage-desktop/src/pages/Evolution.tsx sage-desktop/src/__tests__/pages/Evolution.test.tsx sage-desktop/src/App.tsx sage-desktop/src/components/layout/Sidebar.tsx sage-desktop/src/components/layout/Header.tsx
git commit -m "feat(desktop-web): /evolution page + route + sidebar link"
```

---

### Task 13: Update drift-guard + sidebar test + e2e config test

**Files:**
- Modify: `sage-desktop/src/__tests__/components/Sidebar.test.tsx`
- Modify: `sage-desktop/src/__tests__/e2e-config.test.ts`
- Create: `sage-desktop/e2e/specs/evolution.spec.mjs`

- [ ] **Step 1: Update the Sidebar test to cover the new nav entry**

In `Sidebar.test.tsx`, the existing test `"renders the four Phase 1 nav entries"` (or whatever its current name is) is now stale — read the current assertions and add `Evolution` to whichever list the test checks against. If the test counts items, bump the expected count by 1.

Run:

```
cd sage-desktop && npx vitest run src/__tests__/components/Sidebar.test.tsx
```

Expected: still green.

- [ ] **Step 2: Update e2e-config.test.ts primary-route list**

In `sage-desktop/src/__tests__/e2e-config.test.ts`, find the array containing `/approvals`, `/agents`, `/audit`, `/status`, `/backlog`, `/builds`, `/onboarding`, `/settings` and add `/evolution`.

- [ ] **Step 3: Add per-page E2E smoke spec**

Look at the existing pattern in `sage-desktop/e2e/specs/approvals.spec.mjs` and copy to `evolution.spec.mjs`, replacing "approvals" with "evolution" in the `a[href="/evolution"]` selector, wait-for text, and description.

Also update `test_e2e_config.test.ts` loop over page names to include `evolution`.

- [ ] **Step 4: Run e2e-config test**

```
cd sage-desktop && npx vitest run src/__tests__/e2e-config.test.ts
```

Expected: green.

- [ ] **Step 5: Commit**

```
git add sage-desktop/src/__tests__/components/Sidebar.test.tsx sage-desktop/src/__tests__/e2e-config.test.ts sage-desktop/e2e/specs/evolution.spec.mjs
git commit -m "test(desktop): cover /evolution in sidebar + e2e drift guards"
```

---

### Task 14: Playwright snapshot for `/evolution`

**Files:**
- Modify: `sage-desktop/playwright/fixtures/mock-sidecar.ts`
- Create: `sage-desktop/playwright/evolution.spec.ts`

NOTE: This task only applies if the target branch already has Phase 4.7 Playwright infrastructure. On `feature/sage-desktop-phase5a` (off main), the `playwright/` directory may not exist yet because Phase 4.7 is unmerged. If so, SKIP this task and note it in the PR for resolution when Phase 4 merges.

- [ ] **Step 1: Check whether `sage-desktop/playwright/` exists**

If absent → skip this task (comment in PR description).
If present → continue.

- [ ] **Step 2: Extend mock-sidecar fixture**

In `sage-desktop/playwright/fixtures/mock-sidecar.ts`, add canned responses for the 4 new commands inside the `installSidecarMock` invoke handler — all returning empty shapes.

- [ ] **Step 3: Create spec**

Create `sage-desktop/playwright/evolution.spec.ts`:

```typescript
import { expect, test } from "@playwright/test";
import { installSidecarMock } from "./fixtures/mock-sidecar";

test("evolution page empty state", async ({ page }) => {
  await installSidecarMock(page);
  await page.goto("/evolution");
  await expect(page.getByText("Evolution")).toBeVisible();
  await expect(page).toHaveScreenshot("evolution-empty.png");
});
```

- [ ] **Step 4: Generate baseline** (non-blocking, runs in CI)

- [ ] **Step 5: Commit**

```
git add sage-desktop/playwright/evolution.spec.ts sage-desktop/playwright/fixtures/mock-sidecar.ts
git commit -m "test(desktop): Playwright pixel-diff for /evolution"
```

---

### Task 15: Docs — CLAUDE.md + desktop-gui.md

**Files:**
- Modify: `.claude/docs/interfaces/desktop-gui.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Append a Phase 5a section to `desktop-gui.md`**

```markdown
## Phase 5a — Evolution UI

`/evolution` route surfaces the Agent Gym loop: leaderboard (Glicko-2
ratings), train panel (pick role + difficulty → spinner → rating delta
card), and recent history. Four NDJSON RPCs back it:

| RPC | Purpose |
|---|---|
| `evolution.leaderboard` | Full leaderboard + roll-up stats |
| `evolution.history` | Recent training sessions (limit param) |
| `evolution.analytics` | Per-role score trend, weakness map, improvement rate |
| `evolution.train` | Trigger a training round; returns the TrainingSession dict |

The sidecar reuses `AgentGym(GymDB(...))` as a module-level singleton,
pointed at `<solution>/.sage/gym_data.db` (or `.gym_data.db` in repo
root when no solution is active). Training blocks the sidecar mutex
for the duration of the round — same as `onboarding.generate`.
```

- [ ] **Step 2: Update `CLAUDE.md` one-liner**

In the paragraph describing sage-desktop phases, append:

```
Phase 5a adds the /evolution route + `evolution.{leaderboard,history,analytics,train}` RPC so the gym's compounding loop is visible from inside the app.
```

- [ ] **Step 3: Commit**

```
git add .claude/docs/interfaces/desktop-gui.md CLAUDE.md
git commit -m "docs(desktop): Phase 5a Evolution UI"
```

---

### Task 16: Full verification

- [ ] **Step 1: Full sidecar test suite**

```
cd sage-desktop && ../.venv/Scripts/python.exe -m pytest sidecar/tests -q
```

Expected: all green.

- [ ] **Step 2: Cargo check**

```
cd sage-desktop/src-tauri && cargo check --no-default-features
```

Expected: compiles.

- [ ] **Step 3: Full vitest**

```
cd sage-desktop && npm test -- --run
```

Expected: previous count + 14 new tests.

- [ ] **Step 4: TypeScript type-check**

```
cd sage-desktop && npx tsc --noEmit -p tsconfig.json
```

Expected: no new errors.

- [ ] **Step 5: Final commit (if any stragglers)** — otherwise mark plan complete.
