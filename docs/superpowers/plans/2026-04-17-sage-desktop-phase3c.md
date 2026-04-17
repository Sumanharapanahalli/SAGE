# sage-desktop Phase 3c — Onboarding Wizard Implementation Plan

**Goal:** Wire `src.core.onboarding.generate_solution` into the sidecar +
a 3-step React wizard so users can create yoga / dance / medical apps
without FastAPI.

**Architecture:** sidecar handler → Tauri proxy command →
React useMutation. New solution lands on disk via the same
framework code that today drives `/onboarding/generate`.

**Tech Stack:** Python (sidecar), Rust (Tauri), React + TanStack Query.

---

## Task 1: Sidecar `onboarding.generate` handler (TDD)

**Files:**
- Create: `sage-desktop/sidecar/handlers/onboarding.py`
- Create: `sage-desktop/sidecar/tests/test_onboarding.py`

- [ ] **Step 1: Write failing tests**

```python
# test_onboarding.py
import sys, pytest
from pathlib import Path
_H = Path(__file__).resolve().parents[1]
if str(_H) not in sys.path:
    sys.path.insert(0, str(_H))
import handlers.onboarding as onb
from rpc import RpcError

def test_generate_requires_description(monkeypatch):
    monkeypatch.setattr(onb, "_generate_fn", lambda **kw: {})
    with pytest.raises(RpcError) as e:
        onb.generate({"solution_name": "x"})
    assert e.value.code == -32602

def test_generate_requires_solution_name(monkeypatch):
    monkeypatch.setattr(onb, "_generate_fn", lambda **kw: {})
    with pytest.raises(RpcError) as e:
        onb.generate({"description": "yoga app"})
    assert e.value.code == -32602

def test_generate_happy_path(monkeypatch):
    monkeypatch.setattr(onb, "_generate_fn", lambda **kw: {
        "solution_name": "yoga", "status": "created",
        "path": "/abs/yoga", "files": {"project.yaml": "a: 1"},
        "suggested_routes": [], "message": "ok",
    })
    out = onb.generate({"description": "yoga app thirty chars long",
                        "solution_name": "yoga"})
    assert out["status"] == "created"
    assert out["files"]["project.yaml"] == "a: 1"

def test_generate_wraps_llm_failure_as_sidecar_error(monkeypatch):
    def boom(**kw): raise RuntimeError("LLM down")
    monkeypatch.setattr(onb, "_generate_fn", boom)
    with pytest.raises(RpcError) as e:
        onb.generate({"description": "x" * 40, "solution_name": "y"})
    assert e.value.code == -32000

def test_generate_wraps_validation_error_as_invalid_params(monkeypatch):
    def boom(**kw): raise ValueError("bad yaml")
    monkeypatch.setattr(onb, "_generate_fn", boom)
    with pytest.raises(RpcError) as e:
        onb.generate({"description": "x" * 40, "solution_name": "y"})
    assert e.value.code == -32602

def test_generate_missing_generate_fn_returns_sidecar_error():
    import handlers.onboarding as m
    m._generate_fn = None
    with pytest.raises(RpcError) as e:
        m.generate({"description": "x" * 40, "solution_name": "y"})
    assert e.value.code == -32000
```

- [ ] **Step 2: Run tests — expect ImportError / fails**

```
cd sage-desktop/sidecar && ../../.venv/Scripts/python.exe -m pytest tests/test_onboarding.py -v
```

- [ ] **Step 3: Implement handler**

```python
# sage-desktop/sidecar/handlers/onboarding.py
"""Handler for solution onboarding via the SAGE onboarding wizard."""
from typing import Any, Optional

from rpc import RpcError, RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR

# Wired at startup by app._wire_handlers
_generate_fn: Optional[Any] = None


def generate(params: Any):
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    description = params.get("description")
    solution_name = params.get("solution_name")
    if not isinstance(description, str) or len(description.strip()) < 1:
        raise RpcError(RPC_INVALID_PARAMS, "description is required")
    if not isinstance(solution_name, str) or not solution_name.strip():
        raise RpcError(RPC_INVALID_PARAMS, "solution_name is required")
    if _generate_fn is None:
        raise RpcError(RPC_SIDECAR_ERROR, "onboarding.generate is not wired (SAGE import failed)")

    try:
        return _generate_fn(
            description=description,
            solution_name=solution_name,
            compliance_standards=params.get("compliance_standards") or [],
            integrations=params.get("integrations") or [],
            parent_solution=params.get("parent_solution") or "",
        )
    except ValueError as e:
        raise RpcError(RPC_INVALID_PARAMS, f"invalid onboarding input: {e}")
    except RuntimeError as e:
        raise RpcError(RPC_SIDECAR_ERROR, f"LLM unavailable: {e}")
```

- [ ] **Step 4: Run tests — all pass**

- [ ] **Step 5: Commit**

```bash
git add sage-desktop/sidecar/handlers/onboarding.py sage-desktop/sidecar/tests/test_onboarding.py
git commit -m "feat(sidecar): onboarding.generate handler (wraps framework)"
```

---

## Task 2: Register handler in `app.py`

**Files:**
- Modify: `sage-desktop/sidecar/app.py`

- [ ] **Step 1: Add import + registration**

In imports:
```python
from handlers import agents, approvals, audit, backlog, handshake, llm, onboarding, queue, solutions, status
```

In `_build_dispatcher()`:
```python
d.register("onboarding.generate", onboarding.generate)
```

In `_wire_handlers(...)` (inside the `try` blocks, pattern-match the
others):
```python
try:
    from src.core.onboarding import generate_solution
    onboarding._generate_fn = generate_solution
except Exception as e:
    logging.warning("onboarding.generate wiring unavailable: %s", e)
```

- [ ] **Step 2: Add an e2e smoke test**

In `sage-desktop/sidecar/tests/test_main.py`:

```python
def test_onboarding_wires_to_handler(monkeypatch):
    """onboarding.generate should reach the handler and return
    InvalidParams when called with empty params."""
    out = _drive(_req("o1", "onboarding.generate", {}) + "\n")
    assert out[0]["id"] == "o1"
    assert "error" in out[0]
    assert out[0]["error"]["code"] == -32602
```

- [ ] **Step 3: Run full sidecar tests — all pass**

```
cd sage-desktop/sidecar && ../../.venv/Scripts/python.exe -m pytest tests/ -v
```

- [ ] **Step 4: Commit**

```bash
git add sage-desktop/sidecar/app.py sage-desktop/sidecar/tests/test_main.py
git commit -m "feat(sidecar): register onboarding.generate + wire framework fn"
```

---

## Task 3: Tauri proxy command `onboarding_generate`

**Files:**
- Create: `sage-desktop/src-tauri/src/commands/onboarding.rs`
- Modify: `sage-desktop/src-tauri/src/commands/mod.rs`
- Modify: `sage-desktop/src-tauri/src/lib.rs`

- [ ] **Step 1: Create the command**

```rust
//! Onboarding wizard — proxy to `onboarding.*` on the sidecar.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn onboarding_generate(
    description: String,
    solution_name: String,
    compliance_standards: Option<Vec<String>>,
    integrations: Option<Vec<String>>,
    parent_solution: Option<String>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "onboarding.generate",
            json!({
                "description": description,
                "solution_name": solution_name,
                "compliance_standards": compliance_standards.unwrap_or_default(),
                "integrations": integrations.unwrap_or_default(),
                "parent_solution": parent_solution.unwrap_or_default(),
            }),
        )
        .await
}
```

- [ ] **Step 2: Register in `mod.rs`**

```rust
pub mod onboarding;
```

- [ ] **Step 3: Register in `lib.rs`** — add to the `generate_handler!` list:

```rust
crate::commands::onboarding::onboarding_generate,
```

- [ ] **Step 4: Build + run tests**

```
cd sage-desktop/src-tauri && cargo build && cargo test --lib --no-default-features
```

- [ ] **Step 5: Commit**

```bash
git add sage-desktop/src-tauri/src/commands/onboarding.rs sage-desktop/src-tauri/src/commands/mod.rs sage-desktop/src-tauri/src/lib.rs
git commit -m "feat(desktop-rs): onboarding_generate Tauri command"
```

---

## Task 4: Frontend types + client

**Files:**
- Modify: `sage-desktop/src/api/types.ts`
- Modify: `sage-desktop/src/api/client.ts`

- [ ] **Step 1: Add types**

```ts
// types.ts — add near the bottom
export interface OnboardingParams {
  description: string;
  solution_name: string;
  compliance_standards?: string[];
  integrations?: string[];
  parent_solution?: string;
}

export interface OnboardingResult {
  solution_name: string;
  path: string;
  status: "created" | "exists";
  files: Record<string, string>;
  suggested_routes: string[];
  message: string;
}
```

- [ ] **Step 2: Add client fn**

```ts
// client.ts — import + export
import type {
  …,
  OnboardingParams,
  OnboardingResult,
} from "./types";

export const onboardingGenerate = (params: OnboardingParams) =>
  call<OnboardingResult>("onboarding_generate", params);

// Re-export
export type { …, OnboardingParams, OnboardingResult };
```

- [ ] **Step 3: Commit**

```bash
git add sage-desktop/src/api/types.ts sage-desktop/src/api/client.ts
git commit -m "feat(desktop-web): types + client for onboarding.generate"
```

---

## Task 5: `useOnboarding` hook (TDD)

**Files:**
- Create: `sage-desktop/src/hooks/useOnboarding.ts`
- Create: `sage-desktop/src/__tests__/hooks/useOnboarding.test.ts`

- [ ] **Step 1: Write failing tests**

```ts
import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  onboardingGenerate: vi.fn(),
}));

import * as client from "@/api/client";
import { useOnboardingGenerate } from "@/hooks/useOnboarding";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

describe("useOnboardingGenerate", () => {
  beforeEach(() => vi.clearAllMocks());

  it("passes params through and invalidates solutions on success", async () => {
    vi.mocked(client.onboardingGenerate).mockResolvedValue({
      solution_name: "yoga", path: "/abs/yoga", status: "created",
      files: { "project.yaml": "x" }, suggested_routes: [], message: "ok",
    });
    const qc = createTestQueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useOnboardingGenerate(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate({ description: "x".repeat(30), solution_name: "yoga" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.onboardingGenerate).toHaveBeenCalled();
    expect(spy).toHaveBeenCalled();
  });

  it("surfaces InvalidParams as a typed error", async () => {
    vi.mocked(client.onboardingGenerate).mockRejectedValue({
      kind: "InvalidParams", detail: { message: "bad name" },
    });
    const { result } = renderHook(() => useOnboardingGenerate(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    result.current.mutate({ description: "x".repeat(30), solution_name: "Bad Name" });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.kind).toBe("InvalidParams");
  });

  it("surfaces SidecarDown when LLM is unavailable", async () => {
    vi.mocked(client.onboardingGenerate).mockRejectedValue({
      kind: "SidecarDown", detail: { message: "LLM unavailable" },
    });
    const { result } = renderHook(() => useOnboardingGenerate(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    result.current.mutate({ description: "x".repeat(30), solution_name: "yoga" });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.kind).toBe("SidecarDown");
  });
});
```

- [ ] **Step 2: Run — fails (no hook yet)**

- [ ] **Step 3: Implement**

```ts
// sage-desktop/src/hooks/useOnboarding.ts
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { onboardingGenerate } from "@/api/client";
import type {
  DesktopError,
  OnboardingParams,
  OnboardingResult,
} from "@/api/types";
import { solutionsKey } from "@/hooks/useSolutions";

export function useOnboardingGenerate() {
  const qc = useQueryClient();
  return useMutation<OnboardingResult, DesktopError, OnboardingParams>({
    mutationFn: (p) => onboardingGenerate(p),
    onSuccess: (data) => {
      if (data.status === "created") {
        qc.invalidateQueries({ queryKey: solutionsKey });
      }
    },
  });
}
```

- [ ] **Step 4: Tests pass**

- [ ] **Step 5: Commit**

```bash
git add sage-desktop/src/hooks/useOnboarding.ts sage-desktop/src/__tests__/hooks/useOnboarding.test.ts
git commit -m "feat(desktop-web): useOnboardingGenerate hook"
```

---

## Task 6: OnboardingWizard component (TDD)

**Files:**
- Create: `sage-desktop/src/components/domain/OnboardingWizard.tsx`
- Create: `sage-desktop/src/__tests__/components/OnboardingWizard.test.tsx`

- [ ] **Step 1: Write failing tests**

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { OnboardingWizard } from "@/components/domain/OnboardingWizard";

describe("OnboardingWizard", () => {
  it("disables Generate until name + description are valid", () => {
    const onGenerate = vi.fn();
    render(
      <OnboardingWizard
        isPending={false}
        error={null}
        result={null}
        onGenerate={onGenerate}
        onSwitch={() => {}}
        onClose={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: /generate/i })).toBeDisabled();
  });

  it("rejects names with spaces or caps", () => {
    render(
      <OnboardingWizard
        isPending={false} error={null} result={null}
        onGenerate={() => {}} onSwitch={() => {}} onClose={() => {}}
      />,
    );
    fireEvent.change(screen.getByLabelText(/solution name/i), {
      target: { value: "Bad Name" },
    });
    fireEvent.change(screen.getByLabelText(/description/i), {
      target: { value: "x".repeat(40) },
    });
    expect(screen.getByRole("button", { name: /generate/i })).toBeDisabled();
    expect(screen.getByText(/snake_case/i)).toBeInTheDocument();
  });

  it("calls onGenerate with trimmed params", () => {
    const onGenerate = vi.fn();
    render(
      <OnboardingWizard
        isPending={false} error={null} result={null}
        onGenerate={onGenerate} onSwitch={() => {}} onClose={() => {}}
      />,
    );
    fireEvent.change(screen.getByLabelText(/solution name/i), {
      target: { value: "yoga" },
    });
    fireEvent.change(screen.getByLabelText(/description/i), {
      target: { value: "yoga instructor assistant with thirty chars plus" },
    });
    fireEvent.click(screen.getByRole("button", { name: /generate/i }));
    expect(onGenerate).toHaveBeenCalledWith(
      expect.objectContaining({ solution_name: "yoga" })
    );
  });

  it("shows a 'Switch to it' button on created success", () => {
    const onSwitch = vi.fn();
    render(
      <OnboardingWizard
        isPending={false} error={null}
        result={{
          solution_name: "yoga", path: "/abs/yoga", status: "created",
          files: { "project.yaml": "x" }, suggested_routes: [], message: "ok",
        }}
        onGenerate={() => {}} onSwitch={onSwitch} onClose={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /switch to/i }));
    expect(onSwitch).toHaveBeenCalledWith("yoga", "/abs/yoga");
  });

  it("renders typed error panels", () => {
    render(
      <OnboardingWizard
        isPending={false}
        error={{ kind: "SidecarDown", detail: { message: "down" } }}
        result={null}
        onGenerate={() => {}} onSwitch={() => {}} onClose={() => {}}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/sidecar/i);
  });
});
```

- [ ] **Step 2: Run — all fail**

- [ ] **Step 3: Implement**

```tsx
// sage-desktop/src/components/domain/OnboardingWizard.tsx
import { useState } from "react";
import type { DesktopError, OnboardingParams, OnboardingResult } from "@/api/types";

const NAME_RE = /^[a-z][a-z0-9_]*$/;
const MIN_DESC = 30;

interface Props {
  isPending: boolean;
  error: DesktopError | null;
  result: OnboardingResult | null;
  onGenerate: (p: OnboardingParams) => void;
  onSwitch: (name: string, path: string) => void;
  onClose: () => void;
}

export function OnboardingWizard({ isPending, error, result, onGenerate, onSwitch, onClose }: Props) {
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [standards, setStandards] = useState("");
  const [integrations, setIntegrations] = useState("");

  const nameOk = NAME_RE.test(name);
  const descOk = desc.trim().length >= MIN_DESC;
  const canSubmit = nameOk && descOk && !isPending;

  if (result) {
    return (
      <div className="space-y-3" data-testid="onboarding-result">
        {result.status === "created" ? (
          <>
            <div className="rounded border border-green-200 bg-green-50 p-4 text-sm">
              <div className="font-semibold">Created '{result.solution_name}'</div>
              <div className="mt-1">{result.path}</div>
              <div className="mt-1 text-xs text-green-800/80">
                {Object.keys(result.files).join(", ")}
              </div>
            </div>
            <div className="flex gap-2">
              <button
                className="rounded bg-sage-600 px-4 py-2 text-white"
                onClick={() => onSwitch(result.solution_name, result.path)}
              >
                Switch to it
              </button>
              <button className="rounded border px-4 py-2" onClick={onClose}>
                Stay on current
              </button>
            </div>
          </>
        ) : (
          <div className="rounded border border-yellow-200 bg-yellow-50 p-4 text-sm">
            <div className="font-semibold">Already exists</div>
            <div className="mt-1">{result.message}</div>
            <button className="mt-3 rounded border px-4 py-2" onClick={onClose}>
              OK
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (!canSubmit) return;
        onGenerate({
          description: desc.trim(),
          solution_name: name.trim(),
          compliance_standards: standards.split(",").map((s) => s.trim()).filter(Boolean),
          integrations: integrations.split(",").map((s) => s.trim()).filter(Boolean),
        });
      }}
    >
      <label className="block">
        <span className="block text-sm font-medium">Solution name</span>
        <input
          className="mt-1 block w-full rounded border border-gray-300 p-2 font-mono"
          placeholder="e.g. yoga"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        {name && !nameOk && (
          <span className="text-xs text-red-700">Must be snake_case.</span>
        )}
      </label>
      <label className="block">
        <span className="block text-sm font-medium">Description</span>
        <textarea
          className="mt-1 block w-full rounded border border-gray-300 p-2"
          rows={4}
          placeholder="A short description of the domain and what the solution should do."
          value={desc}
          onChange={(e) => setDesc(e.target.value)}
        />
        <span className="text-xs text-gray-500">
          {desc.trim().length}/{MIN_DESC} chars minimum
        </span>
      </label>
      <div className="grid grid-cols-2 gap-3">
        <label className="block">
          <span className="block text-sm font-medium">Compliance (comma-separated)</span>
          <input
            className="mt-1 block w-full rounded border border-gray-300 p-2"
            placeholder="ISO 9001, IEC 62304"
            value={standards}
            onChange={(e) => setStandards(e.target.value)}
          />
        </label>
        <label className="block">
          <span className="block text-sm font-medium">Integrations</span>
          <input
            className="mt-1 block w-full rounded border border-gray-300 p-2"
            placeholder="gitlab, slack"
            value={integrations}
            onChange={(e) => setIntegrations(e.target.value)}
          />
        </label>
      </div>
      {error && (
        <div role="alert" className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-900">
          {error.kind === "InvalidParams" || error.kind === "SidecarDown"
            ? `${error.kind}: ${error.detail.message}`
            : `Generation failed (${error.kind}).`}
        </div>
      )}
      <button
        type="submit"
        disabled={!canSubmit}
        className="rounded bg-sage-600 px-4 py-2 text-white disabled:opacity-50"
      >
        {isPending ? "Asking LLM…" : "Generate"}
      </button>
    </form>
  );
}
```

- [ ] **Step 4: Tests pass**

- [ ] **Step 5: Commit**

```bash
git add sage-desktop/src/components/domain/OnboardingWizard.tsx sage-desktop/src/__tests__/components/OnboardingWizard.test.tsx
git commit -m "feat(desktop-web): OnboardingWizard component"
```

---

## Task 7: Onboarding page + routing

**Files:**
- Create: `sage-desktop/src/pages/Onboarding.tsx`
- Modify: `sage-desktop/src/App.tsx`
- Modify: `sage-desktop/src/components/layout/Sidebar.tsx`
- Modify: `sage-desktop/src/components/layout/Header.tsx` (if titles are mapped)
- Modify: `sage-desktop/src/__tests__/App.test.tsx`

- [ ] **Step 1: Create the page**

```tsx
// sage-desktop/src/pages/Onboarding.tsx
import { useNavigate } from "react-router-dom";

import { OnboardingWizard } from "@/components/domain/OnboardingWizard";
import { useOnboardingGenerate } from "@/hooks/useOnboarding";
import { useSwitchSolution } from "@/hooks/useSolutions";

export default function Onboarding() {
  const nav = useNavigate();
  const gen = useOnboardingGenerate();
  const swap = useSwitchSolution();

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <h2 className="text-lg font-semibold">New solution</h2>
      <p className="text-sm text-gray-600">
        Describe what you're building. The wizard asks the LLM to draft
        project.yaml, prompts.yaml, and tasks.yaml for you.
      </p>
      <OnboardingWizard
        isPending={gen.isPending}
        error={gen.error ?? null}
        result={gen.data ?? null}
        onGenerate={(p) => gen.mutate(p)}
        onSwitch={(name, path) => {
          swap.mutate({ name, path }, {
            onSuccess: () => nav("/status"),
          });
        }}
        onClose={() => nav(-1)}
      />
    </div>
  );
}
```

- [ ] **Step 2: App.tsx route**

Add `import Onboarding from "@/pages/Onboarding";` and the route inside
`<Route element={<Layout />}>`:

```tsx
<Route path="onboarding" element={<Onboarding />} />
```

- [ ] **Step 3: Sidebar link** — above the solution footer:

```tsx
<div className="mt-4">
  <NavLink
    to="/onboarding"
    className="block rounded border border-dashed border-sage-400 px-3 py-2 text-center text-sm text-sage-700 hover:bg-sage-100"
  >
    + New solution
  </NavLink>
</div>
```

- [ ] **Step 4: Update App.test.tsx** — add `onboardingGenerate` to the
      mock client stub.

- [ ] **Step 5: Run vitest — all green**

```
cd sage-desktop && npx vitest run
```

- [ ] **Step 6: Commit**

```bash
git add sage-desktop/src/pages/Onboarding.tsx sage-desktop/src/App.tsx sage-desktop/src/components/layout/Sidebar.tsx sage-desktop/src/__tests__/App.test.tsx
git commit -m "feat(desktop-web): onboarding route + sidebar link"
```

---

## Task 8: Docs + CLAUDE.md

**Files:**
- Modify: `.claude/docs/interfaces/desktop-gui.md`
- Modify: `CLAUDE.md`

- [ ] Add a "Phase 3c — Onboarding wizard" section under the Phase 3a
      section documenting the new RPC, the wizard flow, and the
      acceptance criteria from the spec.
- [ ] Update the CLAUDE.md bullet to mention Phase 3c.
- [ ] Commit:

```bash
git add .claude/docs/interfaces/desktop-gui.md CLAUDE.md
git commit -m "docs(desktop): Phase 3c onboarding wizard"
```

---

## Task 9: Full verification

- [ ] `pytest tests/test_project_loader.py` — still 5/5
- [ ] `pytest sage-desktop/sidecar/tests/` — previous + 6-7 new
- [ ] `cargo test --lib --no-default-features` — 20/20 (unchanged)
- [ ] `npx vitest run` — 84 + 3 hook + 5 component = 92+
- [ ] `npx vite build` — clean
- [ ] Merge to main.

---

## Self-review checklist

- [x] Every requirement in the spec has a task (handler, Tauri proxy,
      hook, component, page, routing, docs).
- [x] Types referenced in later tasks (`OnboardingParams`,
      `OnboardingResult`) are defined in Task 4.
- [x] No placeholders / TODOs.
- [x] No new error codes (reuses InvalidParams + SidecarDown).
- [x] Tests are concrete — no "similar to above" skips.
