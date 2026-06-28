# Phase 3a — Solution Switcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a sage-desktop user pick a different solution from the sidebar/Settings and have the desktop reconnect without relaunching.

**Architecture:** Sidecar exposes `solutions.list` / `solutions.get_current`. Rust owns the single sidecar via `RwLock`; a new `switch_solution` command stops + respawns with the new `SolutionRef` and emits a `solution-switched` Tauri event. React invalidates every query key on success.

**Tech Stack:** Tauri 2, tokio, PyYAML, React Query, vitest, pytest, cargo.

---

## Task 1: Framework helper — list_solutions()

**Files:**
- Modify: `src/core/project_loader.py` (add at end)
- Modify: `tests/test_project_loader.py` (or create if missing)

- [ ] **Step 1: Write failing test**

```python
# tests/test_project_loader.py
import tempfile
from pathlib import Path
from src.core.project_loader import list_solutions


def test_list_solutions_returns_dirs_with_project_yaml(tmp_path):
    (tmp_path / "solutions" / "a").mkdir(parents=True)
    (tmp_path / "solutions" / "a" / "project.yaml").write_text("name: a\n")
    (tmp_path / "solutions" / "b").mkdir()
    (tmp_path / "solutions" / "b" / "SKILL.md").write_text("# b\n")
    (tmp_path / "solutions" / "README.md").write_text("readme")
    (tmp_path / "solutions" / "org.yaml").write_text("orgs: []")
    (tmp_path / "solutions" / "bare").mkdir()

    result = list_solutions(tmp_path)

    names = [r["name"] for r in result]
    assert names == ["a", "b"]
    assert result[0]["path"].endswith("solutions" + str(Path("/")) + "a") or result[0]["path"].endswith("solutions/a")
    assert result[0]["has_sage_dir"] is False


def test_list_solutions_detects_sage_dir(tmp_path):
    (tmp_path / "solutions" / "a").mkdir(parents=True)
    (tmp_path / "solutions" / "a" / "project.yaml").write_text("name: a\n")
    (tmp_path / "solutions" / "a" / ".sage").mkdir()

    result = list_solutions(tmp_path)
    assert result[0]["has_sage_dir"] is True


def test_list_solutions_missing_dir_returns_empty(tmp_path):
    assert list_solutions(tmp_path) == []


def test_list_solutions_sorted_alphabetically(tmp_path):
    for n in ["zeta", "alpha", "mu"]:
        d = tmp_path / "solutions" / n
        d.mkdir(parents=True)
        (d / "project.yaml").write_text("name: x\n")

    names = [r["name"] for r in list_solutions(tmp_path)]
    assert names == ["alpha", "mu", "zeta"]


def test_list_solutions_skips_dotfiles(tmp_path):
    (tmp_path / "solutions" / ".hidden").mkdir(parents=True)
    (tmp_path / "solutions" / ".hidden" / "project.yaml").write_text("x")

    assert list_solutions(tmp_path) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/pytest tests/test_project_loader.py -v`
Expected: FAIL (import error — function does not exist).

- [ ] **Step 3: Implement**

Add to `src/core/project_loader.py`:

```python
def list_solutions(sage_root):
    """Return sorted SolutionRef dicts for each valid solution under <sage_root>/solutions/.

    A valid solution is a non-dotfile directory that contains either
    ``project.yaml`` or ``SKILL.md``.
    """
    from pathlib import Path

    root = Path(sage_root) / "solutions"
    if not root.is_dir():
        return []
    out = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if entry.name.startswith("."):
            continue
        if not entry.is_dir():
            continue
        has_yaml = (entry / "project.yaml").is_file()
        has_skill = (entry / "SKILL.md").is_file()
        if not (has_yaml or has_skill):
            continue
        out.append({
            "name": entry.name,
            "path": str(entry.resolve()),
            "has_sage_dir": (entry / ".sage").is_dir(),
        })
    return out
```

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/Scripts/pytest tests/test_project_loader.py -v`
Expected: all 5 new tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/core/project_loader.py tests/test_project_loader.py
git commit -m "feat(core): list_solutions(sage_root) — scan for valid solution dirs"
```

---

## Task 2: Sidecar handler — solutions.list / solutions.get_current

**Files:**
- Create: `sage-desktop/sidecar/handlers/solutions.py`
- Create: `sage-desktop/sidecar/tests/test_solutions.py`
- Modify: `sage-desktop/sidecar/app.py` (register + wire)

- [ ] **Step 1: Write failing tests**

```python
# sage-desktop/sidecar/tests/test_solutions.py
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import handlers.solutions as solutions


def test_list_calls_framework_helper(monkeypatch, tmp_path):
    calls = []

    def fake(root):
        calls.append(root)
        return [{"name": "x", "path": "/x", "has_sage_dir": False}]

    monkeypatch.setattr(solutions, "_list_fn", fake)
    solutions._sage_root = tmp_path
    assert solutions.list_solutions({}) == [
        {"name": "x", "path": "/x", "has_sage_dir": False}
    ]
    assert calls == [tmp_path]


def test_list_missing_sage_root_returns_empty(monkeypatch):
    solutions._sage_root = None
    assert solutions.list_solutions({}) == []


def test_get_current_returns_wired_values():
    solutions._current_name = "meditation_app"
    solutions._current_path = Path("/abs/meditation_app")
    assert solutions.get_current({}) == {
        "name": "meditation_app",
        "path": str(Path("/abs/meditation_app")),
    }


def test_get_current_returns_none_when_unwired():
    solutions._current_name = ""
    solutions._current_path = None
    assert solutions.get_current({}) is None


def test_get_current_treats_blank_name_as_unwired():
    solutions._current_name = ""
    solutions._current_path = Path("/something")
    assert solutions.get_current({}) is None


def test_list_real_filesystem(tmp_path):
    sols = tmp_path / "solutions"
    sols.mkdir()
    (sols / "yoga").mkdir()
    (sols / "yoga" / "project.yaml").write_text("name: yoga\n")
    solutions._list_fn = None  # force re-import
    solutions._sage_root = tmp_path
    from src.core.project_loader import list_solutions as _lf
    solutions._list_fn = _lf
    out = solutions.list_solutions({})
    assert len(out) == 1
    assert out[0]["name"] == "yoga"
```

- [ ] **Step 2: Run tests — expect FAIL (module does not exist)**

Run: `cd sage-desktop/sidecar && pytest tests/test_solutions.py -v`
Expected: collection error.

- [ ] **Step 3: Implement handler**

Create `sage-desktop/sidecar/handlers/solutions.py`:

```python
"""Handlers for solution listing and current-solution inspection.

The sidecar is a single-solution process. ``solutions.list`` gives the UI
the roster of switchable targets; ``solutions.get_current`` echoes the
values wired at spawn time so the UI can refresh without re-handshaking.
"""
from pathlib import Path
from typing import Any, Optional

# Wired by app._wire_handlers
_sage_root: Optional[Path] = None
_current_name: str = ""
_current_path: Optional[Path] = None
_list_fn = None  # filled by app.py with src.core.project_loader.list_solutions


def list_solutions(_params: Any):
    if _sage_root is None or _list_fn is None:
        return []
    return _list_fn(_sage_root)


def get_current(_params: Any):
    if not _current_name:
        return None
    return {
        "name": _current_name,
        "path": str(_current_path) if _current_path else "",
    }
```

- [ ] **Step 4: Register in dispatcher**

Edit `sage-desktop/sidecar/app.py`:

1. Add `solutions` to the import line: `from handlers import agents, approvals, audit, backlog, handshake, llm, queue, solutions, status`.
2. In `_build_dispatcher()` add:
   ```python
   d.register("solutions.list", solutions.list_solutions)
   d.register("solutions.get_current", solutions.get_current)
   ```
3. In `_wire_handlers()` at the top (after the handshake block) add:
   ```python
   solutions._current_name = solution_name
   solutions._current_path = solution_path
   try:
       from src.core.project_loader import list_solutions as _lf
       solutions._list_fn = _lf
       _sr = os.environ.get("SAGE_ROOT")
       solutions._sage_root = Path(_sr) if _sr else None
   except Exception as e:  # noqa: BLE001
       logging.warning("solutions.list wiring unavailable: %s", e)
   ```

- [ ] **Step 5: Run sidecar tests**

Run: `cd sage-desktop/sidecar && pytest tests/ -v`
Expected: 102 + 6 = 108 passing.

- [ ] **Step 6: Commit**

```bash
git add sage-desktop/sidecar/handlers/solutions.py sage-desktop/sidecar/tests/test_solutions.py sage-desktop/sidecar/app.py
git commit -m "feat(sidecar): solutions.list + solutions.get_current handlers"
```

---

## Task 3: Rust errors — SolutionNotFound

**Files:**
- Modify: `sage-desktop/src-tauri/src/errors.rs`

- [ ] **Step 1: Add failing test**

Append to the `tests` module of `errors.rs`:

```rust
#[test]
fn solution_not_found_extracts_name() {
    let err = DesktopError::from_rpc(
        RPC_SOLUTION_NOT_FOUND,
        "solution not found",
        Some(serde_json::json!({ "name": "yoga" })),
    );
    match err {
        DesktopError::SolutionNotFound { name } => assert_eq!(name, "yoga"),
        other => panic!("expected SolutionNotFound, got {other:?}"),
    }
}
```

- [ ] **Step 2: Add constant and variant**

Near the other RPC codes in `errors.rs`:

```rust
pub const RPC_SOLUTION_NOT_FOUND: i32 = -32021;
```

Add variant to `DesktopError`:

```rust
#[serde(rename_all = "snake_case")]
SolutionNotFound {
    name: String,
},
```

Add match arm in `from_rpc`:

```rust
RPC_SOLUTION_NOT_FOUND => {
    let name = data
        .as_ref()
        .and_then(|v| v.get("name"))
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    DesktopError::SolutionNotFound { name }
}
```

Add display format in `fmt::Display`:

```rust
DesktopError::SolutionNotFound { name } => write!(f, "solution not found: {name}"),
```

- [ ] **Step 3: Run tests**

Run: `cd sage-desktop/src-tauri && cargo test --lib --no-default-features`
Expected: 18 + 1 = 19 passing.

- [ ] **Step 4: Commit**

```bash
git add sage-desktop/src-tauri/src/errors.rs
git commit -m "feat(desktop-rs): SolutionNotFound error variant (-32021)"
```

---

## Task 4: Sidecar manager — replace() primitive

**Files:**
- Modify: `sage-desktop/src-tauri/src/sidecar.rs`

- [ ] **Step 1: Add test**

Append inside `#[cfg(test)] mod tests` in `sidecar.rs`:

```rust
#[tokio::test]
async fn spawn_then_replace_returns_new_handshake() {
    // Skip if python not on PATH
    if which::which("python").is_err() && which::which("python3").is_err() {
        eprintln!("skipping: no python");
        return;
    }
    let sage_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .parent()
        .unwrap()
        .to_path_buf();
    let sidecar_dir = sage_root.join("sage-desktop").join("sidecar");
    let python = which::which("python")
        .or_else(|_| which::which("python3"))
        .unwrap();
    let cfg = SidecarConfig {
        python,
        sidecar_dir,
        solution_name: None,
        solution_path: None,
        sage_root,
    };
    let sc = Sidecar::spawn(cfg.clone()).await.expect("spawn");
    let first: serde_json::Value = sc
        .call("handshake", serde_json::json!({}))
        .await
        .expect("handshake");
    assert!(first.get("sidecar_version").is_some());

    // Replace with a fresh sidecar and handshake again
    let sc2 = sc.replace(cfg).await.expect("replace");
    let second: serde_json::Value = sc2
        .call("handshake", serde_json::json!({}))
        .await
        .expect("second handshake");
    assert!(second.get("sidecar_version").is_some());
}
```

- [ ] **Step 2: Implement replace()**

Add to `impl Sidecar`:

```rust
/// Gracefully shut down this sidecar and return a new one spawned with `cfg`.
///
/// Semantics: closes stdin → waits up to 3 s for the child to exit → kills
/// it if needed → spawns a fresh sidecar. Any in-flight calls on the old
/// sidecar receive `SidecarDown`.
pub async fn replace(self, cfg: SidecarConfig) -> Result<Self, DesktopError> {
    use std::time::Duration;
    // Drop stdin so the sidecar's reader loop hits EOF.
    drop(self.stdin);
    // Wait briefly for graceful exit.
    {
        let mut child = self.child.lock().await;
        let _ = tokio::time::timeout(Duration::from_secs(3), child.wait()).await;
        let _ = child.start_kill();
    }
    Self::spawn(cfg).await
}
```

Also: change `_child` to `child` (public within crate) and derive `Clone` on `SidecarConfig` (add `#[derive(Clone)]`).

- [ ] **Step 3: Run tests**

Run: `cd sage-desktop/src-tauri && cargo test --lib --no-default-features`
Expected: 19 + 1 = 20 passing (or 19 if skipped due to no python).

- [ ] **Step 4: Commit**

```bash
git add sage-desktop/src-tauri/src/sidecar.rs
git commit -m "feat(desktop-rs): Sidecar.replace() for graceful swap"
```

---

## Task 5: Rust command — switch_solution + solutions wrappers

**Files:**
- Create: `sage-desktop/src-tauri/src/commands/solutions.rs`
- Create: `sage-desktop/src-tauri/src/commands/switch.rs`
- Modify: `sage-desktop/src-tauri/src/commands/mod.rs`
- Modify: `sage-desktop/src-tauri/src/lib.rs`

- [ ] **Step 1: Implement solutions.rs**

```rust
use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn solutions_list(
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    let sc = sidecar.read().await;
    sc.call("solutions.list", json!({})).await
}

#[tauri::command]
pub async fn solutions_get_current(
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    let sc = sidecar.read().await;
    sc.call("solutions.get_current", json!({})).await
}
```

- [ ] **Step 2: Implement switch.rs**

```rust
use std::path::PathBuf;

use serde_json::{json, Value};
use tauri::{AppHandle, Manager, State};
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::{Sidecar, SidecarConfig};

#[tauri::command]
pub async fn switch_solution(
    app: AppHandle,
    sidecar: State<'_, RwLock<Sidecar>>,
    name: String,
    path: String,
) -> Result<Value, DesktopError> {
    // Acquire write lock — blocks new reads until swap finishes.
    let mut guard = sidecar.write().await;
    let cfg = guard.spawn_config_with(name.clone(), PathBuf::from(&path));
    // Take the existing sidecar out via mem::replace-on-a-dummy is ugly;
    // instead, do it by value with tokio::sync::OwnedRwLock? Simplest: swap
    // by calling a helper on &mut Sidecar that consumes internals.
    let new_sidecar = guard.consume_and_respawn(cfg).await?;
    *guard = new_sidecar;
    let hs: Value = guard.call("handshake", json!({})).await?;
    let _ = app.emit("solution-switched", &hs);
    Ok(hs)
}
```

And add to `impl Sidecar` in `sidecar.rs`:

```rust
pub fn spawn_config_with(&self, name: String, path: PathBuf) -> SidecarConfig {
    SidecarConfig {
        python: self.cfg_python.clone(),
        sidecar_dir: self.cfg_sidecar_dir.clone(),
        solution_name: Some(name),
        solution_path: Some(path),
        sage_root: self.cfg_sage_root.clone(),
    }
}

pub async fn consume_and_respawn(&mut self, cfg: SidecarConfig) -> Result<Self, DesktopError> {
    // Close stdin on current child to trigger EOF.
    let _ = self.stdin.lock().await.shutdown().await;
    {
        let mut child = self.child.lock().await;
        let _ = tokio::time::timeout(std::time::Duration::from_secs(3), child.wait()).await;
        let _ = child.start_kill();
    }
    Self::spawn(cfg).await
}
```

Requires storing `cfg_python`, `cfg_sidecar_dir`, `cfg_sage_root` on the struct. Add them to `Sidecar`:

```rust
pub struct Sidecar {
    stdin: Arc<Mutex<ChildStdin>>,
    pending: PendingMap,
    child: Arc<Mutex<Child>>,
    cfg_python: PathBuf,
    cfg_sidecar_dir: PathBuf,
    cfg_sage_root: PathBuf,
}
```

Populate them in `spawn()` at return time.

- [ ] **Step 3: Wire in mod.rs + lib.rs**

`commands/mod.rs`:
```rust
pub mod solutions;
pub mod switch;
```

`lib.rs` — extend `tauri::generate_handler![...]` with:
```rust
commands::solutions::solutions_list,
commands::solutions::solutions_get_current,
commands::switch::switch_solution,
```

Also change the state registration from `manage(sidecar)` to `manage(tokio::sync::RwLock::new(sidecar))` (if it was plain before). Update every existing `State<'_, Sidecar>` to `State<'_, RwLock<Sidecar>>` and wrap call sites in `sidecar.read().await`.

- [ ] **Step 4: Run cargo check + tests**

```bash
cd sage-desktop/src-tauri
cargo check
cargo test --lib --no-default-features
```
Expected: build succeeds; 20 tests pass (or close, integration test may skip).

- [ ] **Step 5: Commit**

```bash
git add sage-desktop/src-tauri/src/commands/solutions.rs sage-desktop/src-tauri/src/commands/switch.rs sage-desktop/src-tauri/src/commands/mod.rs sage-desktop/src-tauri/src/lib.rs sage-desktop/src-tauri/src/sidecar.rs
git commit -m "feat(desktop-rs): switch_solution + solutions.list/get_current commands"
```

---

## Task 6: React API types + client wrappers

**Files:**
- Modify: `sage-desktop/src/api/types.ts`
- Modify: `sage-desktop/src/api/client.ts`

- [ ] **Step 1: Extend types.ts**

Add to the `DesktopError` union:

```ts
| { kind: "SolutionNotFound"; detail: { name: string } }
```

Add below existing domain types:

```ts
export interface SolutionRef {
  name: string;
  path: string;
  has_sage_dir: boolean;
}

export interface CurrentSolution {
  name: string;
  path: string;
}
```

- [ ] **Step 2: Extend client.ts**

Add three wrappers near the existing cluster:

```ts
export function listSolutions(): Promise<SolutionRef[]> {
  return call<SolutionRef[]>("solutions_list", {});
}

export function getCurrentSolution(): Promise<CurrentSolution | null> {
  return call<CurrentSolution | null>("solutions_get_current", {});
}

export function switchSolution(name: string, path: string): Promise<unknown> {
  return call<unknown>("switch_solution", { name, path });
}
```

- [ ] **Step 3: Handle FeatureRequestNotFound pattern in ErrorBanner equivalent for SolutionNotFound**

Edit `sage-desktop/src/components/layout/ErrorBanner.tsx` — add case:

```tsx
case "SolutionNotFound":
  return { title: "Solution not found", detail: `name: ${err.detail.name}` };
```

- [ ] **Step 4: Typecheck**

Run: `cd sage-desktop && npm run typecheck`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add sage-desktop/src/api/types.ts sage-desktop/src/api/client.ts sage-desktop/src/components/layout/ErrorBanner.tsx
git commit -m "feat(desktop-web): solutions API types + client wrappers"
```

---

## Task 7: Hooks — useSolutions, useCurrentSolution, useSwitchSolution, useAppEvents

**Files:**
- Create: `sage-desktop/src/hooks/useSolutions.ts`
- Create: `sage-desktop/src/hooks/useAppEvents.ts`
- Create: `sage-desktop/src/__tests__/hooks/useSolutions.test.ts`

- [ ] **Step 1: Tests first**

```ts
// sage-desktop/src/__tests__/hooks/useSolutions.test.ts
import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("@/api/client", () => ({
  listSolutions: vi.fn(),
  getCurrentSolution: vi.fn(),
  switchSolution: vi.fn(),
}));

import * as client from "@/api/client";
import {
  useCurrentSolution,
  useSolutions,
  useSwitchSolution,
} from "@/hooks/useSolutions";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

describe("useSolutions", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists solutions", async () => {
    vi.mocked(client.listSolutions).mockResolvedValue([
      { name: "a", path: "/x/a", has_sage_dir: false },
    ]);
    const { result } = renderHook(() => useSolutions(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([
      { name: "a", path: "/x/a", has_sage_dir: false },
    ]);
  });

  it("returns null when no current solution", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    const { result } = renderHook(() => useCurrentSolution(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBeNull();
  });

  it("switchSolution mutation invalidates caches", async () => {
    vi.mocked(client.switchSolution).mockResolvedValue({});
    const qc = createTestQueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useSwitchSolution(), {
      wrapper: wrapperWith(qc),
    });
    await result.current.mutateAsync({ name: "x", path: "/x" });
    expect(client.switchSolution).toHaveBeenCalledWith("x", "/x");
    expect(spy).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Implement useSolutions.ts**

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getCurrentSolution,
  listSolutions,
  switchSolution,
} from "@/api/client";

export function useSolutions() {
  return useQuery({
    queryKey: ["solutions", "list"],
    queryFn: listSolutions,
    staleTime: 60_000,
  });
}

export function useCurrentSolution() {
  return useQuery({
    queryKey: ["solutions", "current"],
    queryFn: getCurrentSolution,
  });
}

export function useSwitchSolution() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ name, path }: { name: string; path: string }) =>
      switchSolution(name, path),
    onSuccess: () => {
      qc.invalidateQueries();
    },
  });
}
```

- [ ] **Step 3: Implement useAppEvents.ts (stub — real wiring happens in App.tsx)**

```ts
import { useEffect } from "react";
import { listen } from "@tauri-apps/api/event";
import { useQueryClient } from "@tanstack/react-query";

export function useAppEvents() {
  const qc = useQueryClient();
  useEffect(() => {
    const p = listen("solution-switched", () => {
      qc.invalidateQueries();
    });
    return () => {
      p.then((un) => un());
    };
  }, [qc]);
}
```

- [ ] **Step 4: Run tests**

Run: `cd sage-desktop && npm run test -- --run src/__tests__/hooks/useSolutions.test.ts`
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add sage-desktop/src/hooks/useSolutions.ts sage-desktop/src/hooks/useAppEvents.ts sage-desktop/src/__tests__/hooks/useSolutions.test.ts
git commit -m "feat(desktop-web): useSolutions/useCurrentSolution/useSwitchSolution hooks"
```

---

## Task 8: SolutionPicker component

**Files:**
- Create: `sage-desktop/src/components/domain/SolutionPicker.tsx`
- Create: `sage-desktop/src/__tests__/components/SolutionPicker.test.tsx`

- [ ] **Step 1: Test first**

```tsx
// sage-desktop/src/__tests__/components/SolutionPicker.test.tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("@/api/client", () => ({
  listSolutions: vi.fn(),
  getCurrentSolution: vi.fn(),
  switchSolution: vi.fn(),
}));

import * as client from "@/api/client";
import { SolutionPicker } from "@/components/domain/SolutionPicker";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

describe("SolutionPicker", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders current + list", async () => {
    vi.mocked(client.listSolutions).mockResolvedValue([
      { name: "yoga", path: "/p/yoga", has_sage_dir: true },
      { name: "medtech", path: "/p/medtech", has_sage_dir: false },
    ]);
    vi.mocked(client.getCurrentSolution).mockResolvedValue({
      name: "yoga",
      path: "/p/yoga",
    });
    const qc = createTestQueryClient();
    render(<SolutionPicker variant="settings" />, { wrapper: wrapperWith(qc) });
    await waitFor(() => expect(screen.getByText("yoga")).toBeInTheDocument());
    expect(screen.getByText(/medtech/)).toBeInTheDocument();
  });

  it("calls switch on click", async () => {
    vi.mocked(client.listSolutions).mockResolvedValue([
      { name: "yoga", path: "/p/yoga", has_sage_dir: false },
      { name: "dance", path: "/p/dance", has_sage_dir: false },
    ]);
    vi.mocked(client.getCurrentSolution).mockResolvedValue({
      name: "yoga",
      path: "/p/yoga",
    });
    vi.mocked(client.switchSolution).mockResolvedValue({});
    const qc = createTestQueryClient();
    render(<SolutionPicker variant="settings" />, { wrapper: wrapperWith(qc) });
    await waitFor(() => expect(screen.getByText("yoga")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /switch.*dance/i }));
    expect(client.switchSolution).toHaveBeenCalledWith("dance", "/p/dance");
  });

  it("disables the currently-active option", async () => {
    vi.mocked(client.listSolutions).mockResolvedValue([
      { name: "yoga", path: "/p/yoga", has_sage_dir: false },
    ]);
    vi.mocked(client.getCurrentSolution).mockResolvedValue({
      name: "yoga",
      path: "/p/yoga",
    });
    render(<SolutionPicker variant="sidebar" />, {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() =>
      expect(screen.getByText(/yoga.*current/i)).toBeInTheDocument(),
    );
  });
});
```

- [ ] **Step 2: Implement**

```tsx
import { useCurrentSolution, useSolutions, useSwitchSolution } from "@/hooks/useSolutions";

interface Props {
  variant: "sidebar" | "settings";
}

export function SolutionPicker({ variant }: Props) {
  const list = useSolutions();
  const current = useCurrentSolution();
  const switcher = useSwitchSolution();

  const activeName = current.data?.name ?? "";

  return (
    <div
      className={
        variant === "sidebar"
          ? "mt-auto border-t border-sage-100 pt-3"
          : "rounded-md border border-sage-100 bg-white p-4"
      }
    >
      <div className="text-xs uppercase tracking-wide text-sage-500">
        Solution
      </div>
      <div className="mt-1 text-sm font-semibold text-sage-900">
        {activeName || "—"}
      </div>
      {variant === "settings" && current.data?.path ? (
        <div className="mt-0.5 text-xs text-sage-600">{current.data.path}</div>
      ) : null}
      <ul className="mt-3 flex flex-col gap-1">
        {(list.data ?? []).map((s) => {
          const isActive = s.name === activeName;
          const label = isActive ? `${s.name} (current)` : s.name;
          return (
            <li key={s.name}>
              <button
                type="button"
                disabled={isActive || switcher.isPending}
                onClick={() => switcher.mutate({ name: s.name, path: s.path })}
                className={
                  isActive
                    ? "w-full rounded px-2 py-1 text-left text-xs text-sage-500"
                    : "w-full rounded px-2 py-1 text-left text-xs text-sage-900 hover:bg-sage-50"
                }
                aria-label={isActive ? `${s.name} (current)` : `Switch to ${s.name}`}
              >
                {label}
              </button>
            </li>
          );
        })}
      </ul>
      {switcher.isError ? (
        <div className="mt-2 text-xs text-red-700">Switch failed</div>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 3: Run tests**

Run: `cd sage-desktop && npm run test -- --run src/__tests__/components/SolutionPicker.test.tsx`
Expected: 3 tests pass.

- [ ] **Step 4: Commit**

```bash
git add sage-desktop/src/components/domain/SolutionPicker.tsx sage-desktop/src/__tests__/components/SolutionPicker.test.tsx
git commit -m "feat(desktop-web): SolutionPicker component"
```

---

## Task 9: Wire Sidebar footer + Settings section + App event listener

**Files:**
- Modify: `sage-desktop/src/components/layout/Sidebar.tsx`
- Modify: `sage-desktop/src/pages/Settings.tsx`
- Modify: `sage-desktop/src/App.tsx` (attach useAppEvents)
- Modify: `sage-desktop/src/__tests__/App.test.tsx` (mock new client funcs)

- [ ] **Step 1: Sidebar**

Insert `<SolutionPicker variant="sidebar" />` after the NAV_ITEMS list `</ul>` closing tag.

- [ ] **Step 2: Settings**

Insert `<SolutionPicker variant="settings" />` at the top of the Settings page, above the LLM provider section. Wrap the page content in a `space-y-4` div.

- [ ] **Step 3: App.tsx**

Inside the `QueryClientProvider`, above `<Routes>`, add a component that calls `useAppEvents()`:

```tsx
function AppEvents({ children }: { children: ReactNode }) {
  useAppEvents();
  return <>{children}</>;
}
```

Wrap `<Routes>...</Routes>` with `<AppEvents>...</AppEvents>`.

- [ ] **Step 4: App.test.tsx**

Extend the `vi.mock("@/api/client", ...)` block with:
- `listSolutions: vi.fn().mockResolvedValue([])`
- `getCurrentSolution: vi.fn().mockResolvedValue(null)`
- `switchSolution: vi.fn()`

Also stub `@tauri-apps/api/event` at the top:

```ts
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn().mockResolvedValue(() => {}),
}));
```

- [ ] **Step 5: Full suite**

Run: `cd sage-desktop && npm run test -- --run`
Expected: ≥ 66 + ≥ 6 new = 72 tests pass.

- [ ] **Step 6: Typecheck + build**

Run: `cd sage-desktop && npm run typecheck && npm run build`

- [ ] **Step 7: Commit**

```bash
git add sage-desktop/src/components/layout/Sidebar.tsx sage-desktop/src/pages/Settings.tsx sage-desktop/src/App.tsx sage-desktop/src/__tests__/App.test.tsx
git commit -m "feat(desktop-web): sidebar + Settings solution picker + event listener"
```

---

## Task 10: E2E smoke + docs

**Files:**
- Modify: `sage-desktop/e2e/smoke.mjs`
- Modify: `.claude/docs/interfaces/desktop-gui.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add e2e round-trip**

In `smoke.mjs`, extend `expected` with `solutions_list: false` and add an id-6 request for `solutions.list`. Update completion check and success message.

- [ ] **Step 2: Run e2e**

Run: `cd sage-desktop && npm run test:e2e`
Expected: "OK" with six methods.

- [ ] **Step 3: Update docs**

Append to the desktop-gui RPC table:

```
| `solutions.list` | Scan `<SAGE_ROOT>/solutions/` for valid solution directories |
| `solutions.get_current` | Echo the name/path the sidecar was wired with |
```

Add to the Phase 2 section (or new Phase 3a subsection):

```
### Phase 3a additions
- `switch_solution` Tauri command (Rust-side sidecar swap)
- `solution-switched` event emitted after successful handshake on new solution
- `SolutionNotFound { name: string }` error variant (RPC `-32021`)
```

Update `CLAUDE.md` Interfaces bullet to mention solution switching.

- [ ] **Step 4: Commit**

```bash
git add sage-desktop/e2e/smoke.mjs .claude/docs/interfaces/desktop-gui.md CLAUDE.md
git commit -m "docs(phase3a): solution switcher + RPC contract update"
```

---

## Task 11: Full verification

- [ ] **Step 1: Python** — `.venv/Scripts/pytest tests/test_project_loader.py -v` → +5 passing.
- [ ] **Step 2: Sidecar** — `cd sage-desktop/sidecar && pytest tests/ -v` → ≥ 108.
- [ ] **Step 3: Rust** — `cd sage-desktop/src-tauri && cargo test --lib --no-default-features` → ≥ 19.
- [ ] **Step 4: React** — `cd sage-desktop && npm run test -- --run` → ≥ 72.
- [ ] **Step 5: E2E** — `npm run test:e2e` → OK.
- [ ] **Step 6: Build** — `npm run build` → succeeds.
- [ ] **Step 7: Branch clean** — `git status` → nothing tracked.

Acceptance on all green.
