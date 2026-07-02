# Solution-Independent Desktop Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make sage-desktop open solution-independent, with a Home screen to pick/switch solutions from inside the app (not just via CLI launch args), reusing the existing Phase 3a `switchSolution`/`replace_solution` mechanism.

**Architecture:** Sidecar already supports a "minimal mode" boot with no solution (no changes needed there). Frontend adds a `Home` page (solution picker/switcher, reused both for first-launch and later manual switching), a `RequireSolution` route guard for solution-scoped pages, a `localStorage`-backed "last solution" helper for auto-reopen-on-launch, and a small Rust fix so a failed switch can't leave the connection state lying about being online.

**Tech Stack:** React 18 + TypeScript + react-router-dom v6 + TanStack Query (frontend, `sage-desktop/src/`); Rust + Tokio (backend shell, `sage-desktop/src-tauri/src/sidecar.rs`). No sidecar (Python) changes.

## Global Constraints

- No new backend RPC — reuse `list_solutions`, `get_current_solution`, `switch_solution` exactly as they exist today (`sage-desktop/src/api/client.ts:265-271`).
- `localStorage` only for "last solution" persistence — no backend/file-based persistence.
- Every existing passing test must still pass; existing tests whose mocks are now insufficient (because a solution being active is a new precondition for solution-scoped UI) get their mocks updated, not their assertions weakened.
- Match existing conventions: `ErrorBanner` + `toDesktopError` for error surfaces, `wrapperWith(createTestQueryClient())` for query-only tests, a local `routerWrapper()` (MemoryRouter + query wrapper) for tests needing `useNavigate`/`Link`.
- Pages own `<h2>` (or no heading) for in-content headings; `<h1>` belongs to the global `Header` component only (established convention — confirmed no page in this codebase renders a competing `<h1>`).

---

### Task 1: Rust fix — `replace_solution` must not leave a dead connection reporting online

**Files:**
- Modify: `sage-desktop/src-tauri/src/sidecar.rs:243-280` (the `replace_solution` method)
- Test: `sage-desktop/src-tauri/src/sidecar.rs` (append to the existing `mod tests` block, after `replace_solution_spawns_fresh_sidecar`)

**Interfaces:**
- Consumes: nothing new — `Sidecar::spawn_with_hook`, `SidecarConfig`, `Sidecar::is_online()` all already exist.
- Produces: no signature changes. `replace_solution`'s behavior on spawn failure changes: `self.conn` becomes `None` (was previously left pointing at the already-torn-down old connection).

- [ ] **Step 1: Write the failing test**

Add this test to the `mod tests` block in `sage-desktop/src-tauri/src/sidecar.rs`, immediately after the existing `replace_solution_spawns_fresh_sidecar` test function:

```rust
    #[tokio::test]
    async fn replace_solution_resets_conn_on_spawn_failure() {
        let root = repo_root();
        let sidecar_dir = root.join("sage-desktop").join("sidecar");
        let cfg = SidecarConfig {
            python: python_exe(),
            sidecar_dir,
            solution_name: None,
            solution_path: None,
            sage_root: root.clone(),
        };
        let mut sidecar = match Sidecar::spawn(cfg).await {
            Ok(s) => s,
            Err(e) => {
                eprintln!("skipping: could not spawn sidecar: {e}");
                return;
            }
        };
        assert!(sidecar.is_online());

        // Point at a nonexistent interpreter so the respawn inside
        // replace_solution fails deterministically.
        sidecar.cfg.python = PathBuf::from("this-binary-does-not-exist-xyz-12345");
        let swap_path = root.join("solutions").join("starter");
        let result = sidecar.replace_solution("starter".into(), swap_path).await;

        assert!(result.is_err(), "spawn with a bad interpreter must fail");
        assert!(
            !sidecar.is_online(),
            "a failed respawn must leave the sidecar reporting offline, \
             not pointing at the old (already-torn-down) connection"
        );
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sage-desktop/src-tauri && cargo test --lib replace_solution_resets_conn_on_spawn_failure -- --nocapture`
Expected: FAIL — `assert!(!sidecar.is_online(), ...)` fails because `is_online()` still returns `true` (the stale `Some(Connection)` from before the failed respawn attempt).

- [ ] **Step 3: Write minimal implementation**

In `sage-desktop/src-tauri/src/sidecar.rs`, find `replace_solution` (starts at line 243). Replace this block:

```rust
        let mut cfg = self.cfg.clone();
        cfg.solution_name = Some(name);
        cfg.solution_path = Some(path);
        // Re-arm the same crash hook for the fresh child.
        let fresh = Self::spawn_with_hook(cfg, self.on_crash.clone()).await?;

        self.conn = fresh.conn;
        self.cfg = fresh.cfg;
        Ok(())
    }
```

with:

```rust
        // The old child (if any) is now dead — reflect that immediately so a
        // failed respawn below can't leave is_online() reporting a stale,
        // already-exited process as still connected.
        self.conn = None;

        let mut cfg = self.cfg.clone();
        cfg.solution_name = Some(name);
        cfg.solution_path = Some(path);
        // Re-arm the same crash hook for the fresh child.
        let fresh = Self::spawn_with_hook(cfg, self.on_crash.clone()).await?;

        self.conn = fresh.conn;
        self.cfg = fresh.cfg;
        Ok(())
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sage-desktop/src-tauri && cargo test --lib replace_solution -- --nocapture`
Expected: PASS — all 4 `replace_solution`-related tests (`on_crash_hook_does_not_fire_during_replace_solution`, `replace_solution_spawns_fresh_sidecar`, and the 2 others in that name family) pass, including the new one.

- [ ] **Step 5: Commit**

```bash
git add sage-desktop/src-tauri/src/sidecar.rs
git commit -m "fix(desktop): reset sidecar conn on a failed replace_solution respawn"
```

---

### Task 2: `lastSolution` — localStorage persistence for auto-reopen

**Files:**
- Create: `sage-desktop/src/lib/lastSolution.ts`
- Test: `sage-desktop/src/__tests__/lib/lastSolution.test.ts`

**Interfaces:**
- Produces: `getLastSolution(): { name: string; path: string } | null`, `setLastSolution(s: { name: string; path: string }): void`. Task 4 (Home) imports both.

- [ ] **Step 1: Write the failing test**

Create `sage-desktop/src/__tests__/lib/lastSolution.test.ts`:

```ts
import { beforeEach, describe, expect, it } from "vitest";

import { getLastSolution, setLastSolution } from "@/lib/lastSolution";

describe("lastSolution", () => {
  beforeEach(() => localStorage.clear());

  it("returns null when nothing is stored", () => {
    expect(getLastSolution()).toBeNull();
  });

  it("round-trips a stored solution", () => {
    setLastSolution({ name: "poseengine", path: "/sol/poseengine" });
    expect(getLastSolution()).toEqual({
      name: "poseengine",
      path: "/sol/poseengine",
    });
  });

  it("returns null for malformed JSON", () => {
    localStorage.setItem("sage-desktop:last-solution", "{not json");
    expect(getLastSolution()).toBeNull();
  });

  it("returns null for a JSON value missing required fields", () => {
    localStorage.setItem(
      "sage-desktop:last-solution",
      JSON.stringify({ name: "x" }),
    );
    expect(getLastSolution()).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sage-desktop && npx vitest run src/__tests__/lib/lastSolution.test.ts`
Expected: FAIL — `Cannot find module '@/lib/lastSolution'`.

- [ ] **Step 3: Write minimal implementation**

Create `sage-desktop/src/lib/lastSolution.ts`:

```ts
const KEY = "sage-desktop:last-solution";

export interface LastSolution {
  name: string;
  path: string;
}

/** Read the last-used solution from localStorage. Returns null if unset or malformed. */
export function getLastSolution(): LastSolution | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (
      parsed &&
      typeof parsed.name === "string" &&
      typeof parsed.path === "string"
    ) {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}

/** Remember a solution as the one to auto-reopen on next launch. */
export function setLastSolution(solution: LastSolution): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(solution));
  } catch {
    // localStorage can throw (quota, disabled) — auto-reopen is a nicety, not critical.
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sage-desktop && npx vitest run src/__tests__/lib/lastSolution.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add sage-desktop/src/lib/lastSolution.ts sage-desktop/src/__tests__/lib/lastSolution.test.ts
git commit -m "feat(desktop): localStorage last-solution helper for auto-reopen"
```

---

### Task 3: `RequireSolution` route guard

**Files:**
- Create: `sage-desktop/src/components/layout/RequireSolution.tsx`
- Test: `sage-desktop/src/__tests__/components/RequireSolution.test.tsx`

**Interfaces:**
- Consumes: `useCurrentSolution()` from `@/hooks/useSolutions` (existing, unchanged — returns `{ data: CurrentSolution | null, isLoading: boolean }`).
- Produces: `RequireSolution` — a React Router layout-route component (renders `<Outlet />` or redirects). Task 7 (App.tsx) wraps solution-scoped routes with it.

- [ ] **Step 1: Write the failing test**

Create `sage-desktop/src/__tests__/components/RequireSolution.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  getCurrentSolution: vi.fn(),
}));

import * as client from "@/api/client";
import { RequireSolution } from "@/components/layout/RequireSolution";

function renderGuarded(initialPath: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/home" element={<div>Home page</div>} />
          <Route element={<RequireSolution />}>
            <Route path="/guarded" element={<div>Guarded content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("RequireSolution", () => {
  it("renders the guarded route when a solution is active", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue({
      name: "starter",
      path: "/solutions/starter",
    });
    renderGuarded("/guarded");
    expect(await screen.findByText("Guarded content")).toBeInTheDocument();
  });

  it("redirects to /home when no solution is active", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    renderGuarded("/guarded");
    expect(await screen.findByText("Home page")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sage-desktop && npx vitest run src/__tests__/components/RequireSolution.test.tsx`
Expected: FAIL — `Cannot find module '@/components/layout/RequireSolution'`.

- [ ] **Step 3: Write minimal implementation**

Create `sage-desktop/src/components/layout/RequireSolution.tsx`:

```tsx
import { Navigate, Outlet } from "react-router-dom";

import { useCurrentSolution } from "@/hooks/useSolutions";

/**
 * Route guard for solution-scoped pages. Redirects to /home when no
 * solution is loaded. Renders nothing while the initial current-solution
 * fetch is in flight, to avoid a flash-redirect before it resolves.
 */
export function RequireSolution() {
  const { data, isLoading } = useCurrentSolution();

  if (isLoading) return null;
  if (!data) return <Navigate to="/home" replace />;
  return <Outlet />;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sage-desktop && npx vitest run src/__tests__/components/RequireSolution.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add sage-desktop/src/components/layout/RequireSolution.tsx sage-desktop/src/__tests__/components/RequireSolution.test.tsx
git commit -m "feat(desktop): RequireSolution route guard"
```

---

### Task 4: `Home` page — solution picker, filter, and auto-reopen

**Files:**
- Create: `sage-desktop/src/pages/Home.tsx`
- Test: `sage-desktop/src/__tests__/pages/Home.test.tsx`

**Interfaces:**
- Consumes: `useCurrentSolution()`, `useSolutions()`, `useSwitchSolution()` (all existing, `@/hooks/useSolutions`), `getLastSolution`/`setLastSolution` (Task 2), `ErrorBanner`/`toDesktopError` (existing), `SolutionRef` type (existing, `@/api/types`).
- Produces: `export default function Home()`. Task 7 (App.tsx) routes `path="home"` to it. Renders no `<h1>`/competing heading (relies on `Header`'s title, wired in Task 5) — content starts with the filter input.

- [ ] **Step 1: Write the failing test**

Create `sage-desktop/src/__tests__/pages/Home.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  listSolutions: vi.fn(),
  getCurrentSolution: vi.fn(),
  switchSolution: vi.fn(),
}));

import * as client from "@/api/client";
import Home from "@/pages/Home";
import {
  createTestQueryClient,
  wrapperWith,
} from "../helpers/queryWrapper";
import type { SolutionRef } from "@/api/types";

function routerWrapper() {
  const QueryWrapper = wrapperWith(createTestQueryClient());
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter>
        <QueryWrapper>{children}</QueryWrapper>
      </MemoryRouter>
    );
  };
}

const sol = (name: string): SolutionRef => ({
  name,
  path: `/solutions/${name}`,
  has_sage_dir: true,
});

describe("Home page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("shows the solution list", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    vi.mocked(client.listSolutions).mockResolvedValue([
      sol("starter"),
      sol("poseengine"),
    ]);
    render(<Home />, { wrapper: routerWrapper() });
    await waitFor(() =>
      expect(screen.getByText("poseengine")).toBeInTheDocument(),
    );
    expect(screen.getByText("starter")).toBeInTheDocument();
  });

  it("shows an empty state when there are no solutions", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    vi.mocked(client.listSolutions).mockResolvedValue([]);
    render(<Home />, { wrapper: routerWrapper() });
    await waitFor(() =>
      expect(screen.getByText(/no solutions found/i)).toBeInTheDocument(),
    );
  });

  it("filters the list by name", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    vi.mocked(client.listSolutions).mockResolvedValue([
      sol("starter"),
      sol("poseengine"),
    ]);
    render(<Home />, { wrapper: routerWrapper() });
    await waitFor(() => screen.getByText("poseengine"));
    await userEvent.type(
      screen.getByPlaceholderText(/filter solutions/i),
      "pose",
    );
    expect(screen.getByText("poseengine")).toBeInTheDocument();
    expect(screen.queryByText("starter")).not.toBeInTheDocument();
  });

  it("switches to the picked solution and remembers it", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    vi.mocked(client.listSolutions).mockResolvedValue([sol("poseengine")]);
    vi.mocked(client.switchSolution).mockResolvedValue({
      name: "poseengine",
      path: "/solutions/poseengine",
    });
    render(<Home />, { wrapper: routerWrapper() });
    await waitFor(() => screen.getByText("poseengine"));
    await userEvent.click(screen.getByText("poseengine"));
    await waitFor(() =>
      expect(client.switchSolution).toHaveBeenCalledWith(
        "poseengine",
        "/solutions/poseengine",
      ),
    );
    await waitFor(() =>
      expect(localStorage.getItem("sage-desktop:last-solution")).toEqual(
        JSON.stringify({ name: "poseengine", path: "/solutions/poseengine" }),
      ),
    );
  });

  it("auto-reopens the remembered solution on mount", async () => {
    localStorage.setItem(
      "sage-desktop:last-solution",
      JSON.stringify({ name: "poseengine", path: "/solutions/poseengine" }),
    );
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    vi.mocked(client.listSolutions).mockResolvedValue([sol("poseengine")]);
    vi.mocked(client.switchSolution).mockResolvedValue({
      name: "poseengine",
      path: "/solutions/poseengine",
    });
    render(<Home />, { wrapper: routerWrapper() });
    await waitFor(() =>
      expect(client.switchSolution).toHaveBeenCalledWith(
        "poseengine",
        "/solutions/poseengine",
      ),
    );
  });

  it("does not auto-reopen when a solution is already active", async () => {
    localStorage.setItem(
      "sage-desktop:last-solution",
      JSON.stringify({ name: "poseengine", path: "/solutions/poseengine" }),
    );
    vi.mocked(client.getCurrentSolution).mockResolvedValue({
      name: "starter",
      path: "/solutions/starter",
    });
    vi.mocked(client.listSolutions).mockResolvedValue([
      sol("starter"),
      sol("poseengine"),
    ]);
    render(<Home />, { wrapper: routerWrapper() });
    await waitFor(() => screen.getByText("poseengine"));
    expect(client.switchSolution).not.toHaveBeenCalled();
  });

  it("shows an error banner when the list fails to load", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    vi.mocked(client.listSolutions).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "dead" },
    });
    render(<Home />, { wrapper: routerWrapper() });
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/sidecar/i),
    );
  });

  it("always shows a + New solution link", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    vi.mocked(client.listSolutions).mockResolvedValue([]);
    render(<Home />, { wrapper: routerWrapper() });
    await waitFor(() =>
      expect(
        screen.getByRole("link", { name: /new solution/i }),
      ).toHaveAttribute("href", "/onboarding"),
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sage-desktop && npx vitest run src/__tests__/pages/Home.test.tsx`
Expected: FAIL — `Cannot find module '@/pages/Home'`.

- [ ] **Step 3: Write minimal implementation**

Create `sage-desktop/src/pages/Home.tsx`:

```tsx
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { toDesktopError } from "@/api/client";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import { getLastSolution, setLastSolution } from "@/lib/lastSolution";
import {
  useCurrentSolution,
  useSolutions,
  useSwitchSolution,
} from "@/hooks/useSolutions";
import type { SolutionRef } from "@/api/types";

const DEFAULT_LANDING = "/approvals";

export default function Home() {
  const navigate = useNavigate();
  const current = useCurrentSolution();
  const solutions = useSolutions();
  const switchSolution = useSwitchSolution();
  const [filter, setFilter] = useState("");
  const triedAutoLoad = useRef(false);

  // Auto-reopen the last used solution once, only if none is active yet.
  useEffect(() => {
    if (triedAutoLoad.current) return;
    if (current.isLoading) return;
    if (current.data) return;
    const last = getLastSolution();
    if (!last) return;
    triedAutoLoad.current = true;
    switchSolution.mutate({ name: last.name, path: last.path });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current.isLoading, current.data]);

  // Leave Home once a switch (auto or manual) succeeds.
  useEffect(() => {
    if (switchSolution.isSuccess && switchSolution.data) {
      setLastSolution({
        name: switchSolution.data.name,
        path: switchSolution.data.path,
      });
      navigate(DEFAULT_LANDING, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [switchSolution.isSuccess, switchSolution.data]);

  const handlePick = (s: SolutionRef) => {
    switchSolution.mutate({ name: s.name, path: s.path });
  };

  const filtered = (solutions.data ?? []).filter((s) =>
    s.name.toLowerCase().includes(filter.toLowerCase()),
  );

  if (triedAutoLoad.current && switchSolution.isPending) {
    const last = getLastSolution();
    return (
      <div className="p-6 text-sm text-slate-500">
        Reopening {last?.name ?? "your last solution"}…
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-6">
      <ErrorBanner
        error={
          solutions.error ??
          (switchSolution.error ? toDesktopError(switchSolution.error) : null)
        }
      />

      <input
        type="text"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder="Filter solutions…"
        className="w-full rounded border border-sage-100 px-3 py-2 text-sm"
      />

      {solutions.isLoading ? (
        <p className="text-sm text-slate-500">Loading solutions…</p>
      ) : filtered.length === 0 ? (
        <div className="rounded border border-sage-100 bg-white p-6 text-center text-sm text-slate-500">
          {solutions.data?.length === 0
            ? "No solutions found."
            : "No solutions match your filter."}
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {filtered.map((s) => (
            <li key={s.path}>
              <button
                type="button"
                onClick={() => handlePick(s)}
                disabled={switchSolution.isPending}
                className="flex w-full flex-col items-start rounded border border-sage-100 bg-white p-3 text-left hover:border-sage-300 hover:bg-sage-50 disabled:opacity-50"
              >
                <span className="font-medium text-sage-900">{s.name}</span>
                <span className="text-xs text-slate-500">{s.path}</span>
                {s.has_sage_dir && (
                  <span className="mt-1 inline-block rounded bg-sage-100 px-1.5 py-0.5 text-[11px] text-sage-700">
                    has data
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}

      <Link
        to="/onboarding"
        className="block rounded border border-dashed border-sage-400 px-3 py-2 text-center text-sm text-sage-700 hover:bg-sage-100"
      >
        + New solution
      </Link>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sage-desktop && npx vitest run src/__tests__/pages/Home.test.tsx`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add sage-desktop/src/pages/Home.tsx sage-desktop/src/__tests__/pages/Home.test.tsx
git commit -m "feat(desktop): Home page — solution picker, filter, auto-reopen"
```

---

### Task 5: `Header` — add the `/home` title

**Files:**
- Modify: `sage-desktop/src/components/layout/Header.tsx`
- Modify: `sage-desktop/src/__tests__/components/Header.test.tsx`

**Interfaces:**
- No new exports. `TITLE_MAP` gains one entry: `"/home": "Solutions"`.

- [ ] **Step 1: Write the failing test**

In `sage-desktop/src/__tests__/components/Header.test.tsx`, add `"/home"` to the existing `it.each` table (find the array that currently starts with `["/analyze", /analyze/i]`):

```ts
  it.each([
    ["/analyze", /analyze/i],
    ["/home", /solutions/i],
    ["/compliance", /compliance/i],
    ["/costs", /costs/i],
    ["/workflows", /workflows/i],
    ["/skills", /skills/i],
    ["/organization", /organization/i],
    ["/monitor", /monitor/i],
    ["/goals", /goals/i],
    ["/eval", /eval/i],
    ["/hil", /hardware-in-the-loop/i],
  ])("shows a real title for %s (not the generic fallback)", (path, re) => {
    renderAt(path);
    const heading = screen.getByRole("heading");
    expect(heading).toHaveTextContent(re);
    expect(heading).not.toHaveTextContent(/sage desktop/i);
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sage-desktop && npx vitest run src/__tests__/components/Header.test.tsx`
Expected: FAIL — the `/home` case fails because `TITLE_MAP` has no entry, so `Header` falls back to "SAGE Desktop".

- [ ] **Step 3: Write minimal implementation**

In `sage-desktop/src/components/layout/Header.tsx`, add `"/home": "Solutions",` to `TITLE_MAP` (place it first, matching the "Approvals" ordering pattern — order doesn't matter functionally, just keep it readable):

```ts
const TITLE_MAP: Record<string, string> = {
  "/home": "Solutions",
  "/analyze": "Analyze",
  "/approvals": "Approvals",
  ...
```

(Keep every existing entry unchanged — only add the new `"/home"` line.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sage-desktop && npx vitest run src/__tests__/components/Header.test.tsx`
Expected: PASS (all cases, including `/home`).

- [ ] **Step 5: Commit**

```bash
git add sage-desktop/src/components/layout/Header.tsx sage-desktop/src/__tests__/components/Header.test.tsx
git commit -m "feat(desktop): Header title for /home"
```

---

### Task 6: `Sidebar` — persistent switcher, hide nav when no solution is active

**Files:**
- Modify: `sage-desktop/src/components/layout/Sidebar.tsx`
- Modify: `sage-desktop/src/__tests__/components/Sidebar.test.tsx` (full replacement — nearly every existing test needs its assertion converted from synchronous `getBy*` to `await findBy*`, because nav rendering now depends on an async `useCurrentSolution()` fetch resolving non-null first)

**Interfaces:**
- Consumes: `useCurrentSolution()`, `useApprovals()` (both existing, unchanged).
- No new exports — `Sidebar` keeps its existing signature. `data-testid="sidebar-solution"` is preserved (moved from the old bottom footer onto the new top switcher) so existing consumers of that test id don't need to change name, only location semantics.

- [ ] **Step 1: Replace the test file (write the failing tests)**

Replace the full contents of `sage-desktop/src/__tests__/components/Sidebar.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  getCurrentSolution: vi
    .fn()
    .mockResolvedValue({ name: "starter", path: "/solutions/starter" }),
  listPendingApprovals: vi.fn().mockResolvedValue([]),
}));

import * as client from "@/api/client";
import { Sidebar } from "@/components/layout/Sidebar";
import type { Proposal } from "@/api/types";

function renderAt(path: string) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <Sidebar />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const fakeProposal = (trace_id: string): Proposal => ({
  trace_id,
  created_at: "2026-04-16T10:00:00Z",
  action_type: "yaml_edit",
  risk_class: "STATEFUL",
  reversible: true,
  proposed_by: "analyst",
  description: "d",
  payload: {},
  status: "pending",
  decided_by: null,
  decided_at: null,
  feedback: null,
  expires_at: null,
  required_role: null,
  approved_by: null,
  approver_role: null,
  approver_email: null,
});

describe("Sidebar", () => {
  it("renders the four Phase 1 nav entries", async () => {
    renderAt("/approvals");
    expect(await screen.findByRole("link", { name: /approvals/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /agents/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /audit/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /status/i })).toBeInTheDocument();
  });

  it("marks the active route with aria-current=page", async () => {
    renderAt("/audit");
    const link = await screen.findByRole("link", { name: /audit/i });
    expect(link).toHaveAttribute("aria-current", "page");
  });

  it("renders the solution switcher", async () => {
    renderAt("/approvals");
    expect(await screen.findByTestId("sidebar-solution")).toHaveTextContent(/solution/i);
  });

  it("the solution switcher links to /home", async () => {
    renderAt("/approvals");
    expect(await screen.findByTestId("sidebar-solution")).toHaveAttribute("href", "/home");
  });

  it("includes the Constitution entry (Phase 5b)", async () => {
    renderAt("/approvals");
    expect(
      await screen.findByRole("link", { name: /constitution/i }),
    ).toHaveAttribute("href", "/constitution");
  });

  it("includes the Knowledge entry (Phase 5c)", async () => {
    renderAt("/approvals");
    expect(
      await screen.findByRole("link", { name: /knowledge/i }),
    ).toHaveAttribute("href", "/knowledge");
  });

  it("includes the Collective entry (Phase 5a)", async () => {
    renderAt("/approvals");
    expect(
      await screen.findByRole("link", { name: /collective/i }),
    ).toHaveAttribute("href", "/collective");
  });

  it("includes the Analyze entry — the SURFACE -> PROPOSE trigger", async () => {
    renderAt("/approvals");
    expect(
      await screen.findByRole("link", { name: /analyze/i }),
    ).toHaveAttribute("href", "/analyze");
  });

  it("includes the Compliance entry (Phase 5f)", async () => {
    renderAt("/approvals");
    expect(
      await screen.findByRole("link", { name: /compliance/i }),
    ).toHaveAttribute("href", "/compliance");
  });

  it("includes the Costs entry", async () => {
    renderAt("/approvals");
    expect(await screen.findByRole("link", { name: /costs/i })).toHaveAttribute(
      "href",
      "/costs",
    );
  });

  it("includes the Workflows entry", async () => {
    renderAt("/approvals");
    expect(
      await screen.findByRole("link", { name: /workflows/i }),
    ).toHaveAttribute("href", "/workflows");
  });

  it("includes the Skills & Tools entry", async () => {
    renderAt("/approvals");
    expect(await screen.findByRole("link", { name: /skills/i })).toHaveAttribute(
      "href",
      "/skills",
    );
  });

  it("includes the Organization entry", async () => {
    renderAt("/approvals");
    expect(
      await screen.findByRole("link", { name: /organization/i }),
    ).toHaveAttribute("href", "/organization");
  });

  it("includes the Monitor entry", async () => {
    renderAt("/approvals");
    expect(await screen.findByRole("link", { name: /monitor/i })).toHaveAttribute(
      "href",
      "/monitor",
    );
  });

  it("includes the Goals entry", async () => {
    renderAt("/approvals");
    expect(await screen.findByRole("link", { name: /goals/i })).toHaveAttribute(
      "href",
      "/goals",
    );
  });

  it("includes the Eval entry", async () => {
    renderAt("/approvals");
    expect(await screen.findByRole("link", { name: /eval/i })).toHaveAttribute(
      "href",
      "/eval",
    );
  });

  it("includes the HIL entry", async () => {
    renderAt("/approvals");
    expect(await screen.findByRole("link", { name: /hil/i })).toHaveAttribute(
      "href",
      "/hil",
    );
  });

  it("shows a pending-approvals badge with the count", async () => {
    vi.mocked(client.listPendingApprovals).mockResolvedValueOnce([
      fakeProposal("a"),
      fakeProposal("b"),
      fakeProposal("c"),
    ]);
    renderAt("/status");
    const badge = await screen.findByTestId("pending-badge");
    expect(badge).toHaveTextContent("3");
  });

  it("hides the badge when nothing is pending", async () => {
    renderAt("/approvals");
    await screen.findByRole("link", { name: /approvals/i });
    expect(screen.queryByTestId("pending-badge")).not.toBeInTheDocument();
  });

  it("hides solution-scoped nav links when no solution is loaded", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValueOnce(null);
    renderAt("/home");
    await screen.findByText(/pick a solution/i);
    expect(screen.queryByRole("link", { name: /^approvals$/i })).not.toBeInTheDocument();
  });

  it("always shows + New solution regardless of solution state", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValueOnce(null);
    renderAt("/home");
    await screen.findByText(/pick a solution/i);
    expect(
      screen.getByRole("link", { name: /new solution/i }),
    ).toHaveAttribute("href", "/onboarding");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sage-desktop && npx vitest run src/__tests__/components/Sidebar.test.tsx`
Expected: FAIL — the two new "hides ... when no solution" tests fail (nav is unconditional today); most other tests still pass since they don't yet depend on the new gating (harmless — they'll continue passing after the implementation step too, just now via `findBy*`).

- [ ] **Step 3: Write minimal implementation**

Replace the full contents of `sage-desktop/src/components/layout/Sidebar.tsx`:

```tsx
import clsx from "clsx";
import { NavLink } from "react-router-dom";

import { useApprovals } from "@/hooks/useApprovals";
import { useCurrentSolution } from "@/hooks/useSolutions";

const NAV_ITEMS = [
  { to: "/analyze", label: "Analyze" },
  { to: "/approvals", label: "Approvals" },
  { to: "/agents", label: "Agents" },
  { to: "/audit", label: "Audit" },
  { to: "/status", label: "Status" },
  { to: "/builds", label: "Builds" },
  { to: "/backlog", label: "Backlog" },
  { to: "/yaml", label: "YAML" },
  { to: "/constitution", label: "Constitution" },
  { to: "/knowledge", label: "Knowledge" },
  { to: "/collective", label: "Collective" },
  { to: "/compliance", label: "Compliance" },
  { to: "/costs", label: "Costs" },
  { to: "/workflows", label: "Workflows" },
  { to: "/skills", label: "Skills & Tools" },
  { to: "/organization", label: "Organization" },
  { to: "/monitor", label: "Monitor" },
  { to: "/goals", label: "Goals" },
  { to: "/eval", label: "Eval" },
  { to: "/hil", label: "HIL" },
  { to: "/settings", label: "Settings" },
] as const;

export function Sidebar() {
  const { data: current } = useCurrentSolution();
  const { data: pending } = useApprovals();
  const pendingCount = pending?.length ?? 0;
  const hasSolution = Boolean(current);

  return (
    <nav className="flex w-56 shrink-0 flex-col overflow-y-auto border-r border-sage-100 bg-sage-50 p-4">
      <div className="mb-4 text-xl font-semibold text-sage-700">SAGE</div>

      <NavLink
        to="/home"
        data-testid="sidebar-solution"
        className="mb-4 block rounded border border-sage-200 bg-white px-3 py-2 text-xs hover:border-sage-400 hover:bg-sage-50"
      >
        <div className="uppercase tracking-wide text-sage-500">Solution</div>
        <div
          className="mt-0.5 truncate font-medium text-sage-900"
          title={current?.name ?? "none"}
        >
          {current?.name ?? "Pick a solution…"}
        </div>
      </NavLink>

      {hasSolution && (
        <ul className="flex flex-col gap-1">
          {NAV_ITEMS.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                className={({ isActive }) =>
                  clsx(
                    "flex items-center rounded px-3 py-2 text-sm transition-colors",
                    isActive
                      ? "bg-sage-500 text-white"
                      : "text-sage-900 hover:bg-sage-100",
                  )
                }
              >
                <span>{item.label}</span>
                {item.to === "/approvals" && pendingCount > 0 && (
                  <span
                    data-testid="pending-badge"
                    className="ml-auto rounded-full bg-red-600 px-2 py-0.5 text-xs font-semibold text-white"
                  >
                    {pendingCount}
                  </span>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-auto pt-4">
        <NavLink
          to="/onboarding"
          className="block rounded border border-dashed border-sage-400 px-3 py-2 text-center text-sm text-sage-700 hover:bg-sage-100"
        >
          + New solution
        </NavLink>
      </div>
    </nav>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sage-desktop && npx vitest run src/__tests__/components/Sidebar.test.tsx`
Expected: PASS (22 tests).

- [ ] **Step 5: Commit**

```bash
git add sage-desktop/src/components/layout/Sidebar.tsx sage-desktop/src/__tests__/components/Sidebar.test.tsx
git commit -m "feat(desktop): persistent sidebar solution switcher, hide nav when unset"
```

---

### Task 7: `App.tsx` — wire Home, IndexRedirect, and RequireSolution

**Files:**
- Modify: `sage-desktop/src/App.tsx`
- Modify: `sage-desktop/src/__tests__/App.test.tsx`

**Interfaces:**
- Consumes: `Home` (Task 4), `RequireSolution` (Task 3), `useCurrentSolution` (existing).
- No new exports — `App` keeps its existing signature.

- [ ] **Step 1: Replace the test file (write the failing tests)**

Replace the full contents of `sage-desktop/src/__tests__/App.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  listPendingApprovals: vi.fn().mockResolvedValue([]),
  getApproval: vi.fn(),
  approveProposal: vi.fn(),
  rejectProposal: vi.fn(),
  batchApprove: vi.fn(),
  listAuditEvents: vi
    .fn()
    .mockResolvedValue({ total: 0, limit: 50, offset: 0, events: [] }),
  getAuditByTrace: vi.fn(),
  auditStats: vi.fn(),
  listAgents: vi.fn().mockResolvedValue([]),
  getAgent: vi.fn(),
  getStatus: vi.fn().mockResolvedValue({
    health: "ok",
    sidecar_version: "0.1.0",
    project: null,
    llm: null,
    pending_approvals: 0,
  }),
  handshake: vi.fn(),
  toDesktopError: (e: unknown) => e,
  getLlmInfo: vi.fn().mockResolvedValue({
    provider_name: "GeminiCLIProvider",
    model: "gemini-2.0",
    available_providers: ["gemini"],
  }),
  switchLlm: vi.fn(),
  listFeatureRequests: vi.fn().mockResolvedValue([]),
  submitFeatureRequest: vi.fn(),
  updateFeatureRequest: vi.fn(),
  getQueueStatus: vi.fn().mockResolvedValue({
    pending: 0, in_progress: 0, done: 0, failed: 0, blocked: 0,
    parallel_enabled: false, max_workers: 0,
  }),
  listQueueTasks: vi.fn().mockResolvedValue([]),
  listSolutions: vi.fn().mockResolvedValue([]),
  getCurrentSolution: vi
    .fn()
    .mockResolvedValue({ name: "starter", path: "/solutions/starter" }),
  switchSolution: vi.fn(),
  onboardingGenerate: vi.fn(),
  startBuild: vi.fn(),
  listBuilds: vi.fn().mockResolvedValue([]),
  getBuild: vi.fn(),
  approveBuildStage: vi.fn(),
  readYaml: vi.fn().mockResolvedValue({
    file: "project",
    solution: "demo",
    content: "",
    path: "",
  }),
  writeYaml: vi.fn(),
}));

vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn().mockResolvedValue(() => {}),
}));

import * as client from "@/api/client";
import { App } from "@/App";

describe("App routing", () => {
  beforeEach(() => vi.clearAllMocks());

  it("redirects / to /approvals when a solution is already active", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue({
      name: "starter",
      path: "/solutions/starter",
    });
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByRole("heading")).toHaveTextContent(/approvals/i),
    );
  });

  it("redirects / to /home when no solution is active", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByRole("heading")).toHaveTextContent(/solutions/i),
    );
  });

  it("redirects a solution-scoped route to /home when no solution is active", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    render(
      <MemoryRouter initialEntries={["/audit"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByRole("heading")).toHaveTextContent(/solutions/i),
    );
  });

  it("renders the Audit route", async () => {
    render(
      <MemoryRouter initialEntries={["/audit"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByRole("heading")).toHaveTextContent(/audit/i),
    );
  });

  it("renders the Status route", async () => {
    render(
      <MemoryRouter initialEntries={["/status"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByRole("heading")).toHaveTextContent(/status/i),
    );
  });

  it("renders the Builds route", async () => {
    render(
      <MemoryRouter initialEntries={["/builds"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
        /builds/i,
      ),
    );
  });

  it("renders Home without redirecting away when a solution is already active", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue({
      name: "starter",
      path: "/solutions/starter",
    });
    render(
      <MemoryRouter initialEntries={["/home"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByRole("heading")).toHaveTextContent(/solutions/i),
    );
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.getByRole("heading")).toHaveTextContent(/solutions/i);
  });

  it("renders Onboarding without a solution loaded", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    render(
      <MemoryRouter initialEntries={["/onboarding"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByRole("heading")).toHaveTextContent(/new solution/i),
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sage-desktop && npx vitest run src/__tests__/App.test.tsx`
Expected: FAIL — the 3 new tests fail (index always redirects to `/approvals` today regardless of solution state; `/audit` never redirects; `/home` doesn't exist). The original 3 route-rendering tests still pass unmodified in intent (their mock already returns a solution now).

- [ ] **Step 3: Write minimal implementation**

Replace the full contents of `sage-desktop/src/App.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PropsWithChildren } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "@/components/layout/Layout";
import { RequireSolution } from "@/components/layout/RequireSolution";
import { useAppEvents } from "@/hooks/useAppEvents";
import { useCurrentSolution } from "@/hooks/useSolutions";
import Analyze from "@/pages/Analyze";
import { Agents } from "@/pages/Agents";
import { Approvals } from "@/pages/Approvals";
import { Audit } from "@/pages/Audit";
import Backlog from "@/pages/Backlog";
import Builds from "@/pages/Builds";
import Collective from "@/pages/Collective";
import Compliance from "@/pages/Compliance";
import Constitution from "@/pages/Constitution";
import Costs from "@/pages/Costs";
import Eval from "@/pages/Eval";
import Goals from "@/pages/Goals";
import Hil from "@/pages/Hil";
import Home from "@/pages/Home";
import Knowledge from "@/pages/Knowledge";
import Monitor from "@/pages/Monitor";
import Onboarding from "@/pages/Onboarding";
import Organization from "@/pages/Organization";
import Settings from "@/pages/Settings";
import SkillsTools from "@/pages/SkillsTools";
import { Status } from "@/pages/Status";
import Workflows from "@/pages/Workflows";
import YamlEdit from "@/pages/YamlEdit";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Sidecar is local; retry lightly on transient errors (e.g. respawn window)
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function AppEvents({ children }: PropsWithChildren) {
  useAppEvents();
  return <>{children}</>;
}

/**
 * Index route: send an already-loaded solution straight to its Approvals
 * inbox (today's behavior, preserved for CLI-launched solutions); send a
 * solution-independent boot to Home to pick one. Renders nothing while the
 * initial current-solution fetch is in flight, to avoid a flash redirect.
 */
function IndexRedirect() {
  const { data, isLoading } = useCurrentSolution();
  if (isLoading) return null;
  return <Navigate to={data ? "/approvals" : "/home"} replace />;
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppEvents>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<IndexRedirect />} />
            <Route path="home" element={<Home />} />
            <Route path="onboarding" element={<Onboarding />} />
            <Route path="organization" element={<Organization />} />
            <Route path="settings" element={<Settings />} />
            <Route element={<RequireSolution />}>
              <Route path="analyze" element={<Analyze />} />
              <Route path="approvals" element={<Approvals />} />
              <Route path="agents" element={<Agents />} />
              <Route path="audit" element={<Audit />} />
              <Route path="status" element={<Status />} />
              <Route path="backlog" element={<Backlog />} />
              <Route path="builds" element={<Builds />} />
              <Route path="yaml" element={<YamlEdit />} />
              <Route path="constitution" element={<Constitution />} />
              <Route path="knowledge" element={<Knowledge />} />
              <Route path="collective" element={<Collective />} />
              <Route path="compliance" element={<Compliance />} />
              <Route path="costs" element={<Costs />} />
              <Route path="workflows" element={<Workflows />} />
              <Route path="skills" element={<SkillsTools />} />
              <Route path="monitor" element={<Monitor />} />
              <Route path="goals" element={<Goals />} />
              <Route path="eval" element={<Eval />} />
              <Route path="hil" element={<Hil />} />
            </Route>
          </Route>
        </Routes>
      </AppEvents>
    </QueryClientProvider>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sage-desktop && npx vitest run src/__tests__/App.test.tsx`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add sage-desktop/src/App.tsx sage-desktop/src/__tests__/App.test.tsx
git commit -m "feat(desktop): wire Home + RequireSolution into App routing"
```

---

### Task 8: Full verification and push

**Files:** none (verification only).

- [ ] **Step 1: Run the full frontend suite**

Run: `cd sage-desktop && npx vitest run`
Expected: all test files pass (baseline before this plan was 74 files / 327 tests — expect that plus the ~5 new/changed files from Tasks 2–7).

- [ ] **Step 2: Typecheck**

Run: `cd sage-desktop && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Run the Rust test suite**

Run: `cd sage-desktop/src-tauri && cargo test --lib`
Expected: all tests pass, including the new `replace_solution_resets_conn_on_spawn_failure`.

- [ ] **Step 4: Run the Python sidecar suite (regression check — no sidecar files were touched, but confirm)**

Run: `cd sage-desktop/sidecar && python -m pytest tests/ -q`
Expected: 369 passed (unchanged from before this plan — this task touches no sidecar code).

- [ ] **Step 5: Push**

```bash
git push origin main
```

If any step in Steps 1–4 fails, fix the regression before pushing — do not push on a red suite.

---

## Post-plan note

This plan builds the shell only. Chat (conversational interaction inside a solution) is a separate design cycle — see `docs/superpowers/specs/2026-07-02-desktop-solution-independent-shell-design.md` §2 for the pointer to the existing, already-implemented web `/chat` design it should port from.
