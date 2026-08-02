/**
 * Picking a solution on Home.
 *
 * Measured cost of the thing this button triggers, on this machine:
 *
 *   sidecar boot, no solution (minimal mode)   0.2 s
 *   sidecar boot, real solution, HF cached     5.5 s
 *   sidecar boot, real solution, network up    8.8 s
 *
 * The gap is `_wire_handlers` eagerly constructing `VectorMemory` — ChromaDB
 * plus a sentence-transformers model load, plus ~3.3 s of HuggingFace
 * metadata HEAD requests. `switch_solution` holds the sidecar write lock
 * across all of it (respawn, then a blocking `handshake`), so a pick costs
 * ~10 s during which every other RPC in the app is queued behind it.
 *
 * Before this test, the only feedback over that span was
 * `disabled:opacity-50` on the button: no spinner, no text, and a sidebar
 * still reading "Pick a solution…" with no nav items. It looks like a dead
 * button, which is exactly how it was reported. A "Reopening…" branch did
 * exist but was gated on `triedAutoLoad.current`, so it only fired for the
 * auto-reopen path — never for a manual click, i.e. never on first run.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  listSolutions: vi.fn(),
  getCurrentSolution: vi.fn(),
  switchSolution: vi.fn(),
  unloadSolution: vi.fn(),
  removeSolution: vi.fn(),
  toDesktopError: (e: unknown) => e,
}));

import * as client from "@/api/client";
import { RequireSolution } from "@/components/layout/RequireSolution";
import { useCurrentSolution } from "@/hooks/useSolutions";
import Home from "@/pages/Home";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";
import type { SolutionRef } from "@/api/types";

const STARTER: SolutionRef = {
  name: "starter",
  path: "/solutions/starter",
  has_sage_dir: true,
};

/**
 * Stand-in for the real `Sidebar`, which calls `useCurrentSolution()` from
 * inside `Layout` — outside the routed area, so it stays mounted across
 * navigations and keeps that query from being garbage-collected. Without a
 * persistent observer the test helper's `gcTime: 0` drops the cache entry
 * when Home unmounts and the guard below refetches from scratch, which is
 * not the caching the app actually has.
 */
function PersistentObserver() {
  useCurrentSolution();
  return null;
}

/** Home at /home, plus a guarded page standing in for /approvals. */
function renderApp() {
  const client = createTestQueryClient();
  client.setDefaultOptions({
    queries: { retry: false, gcTime: 5 * 60_000, staleTime: 0 },
    mutations: { retry: false },
  });
  const QueryWrapper = wrapperWith(client);
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={["/home"]}>
        <QueryWrapper>{children}</QueryWrapper>
      </MemoryRouter>
    );
  }
  return render(
    <>
      <PersistentObserver />
      <Routes>
        <Route path="/home" element={<Home />} />
        <Route element={<RequireSolution />}>
          <Route path="/approvals" element={<div>APPROVALS PAGE</div>} />
        </Route>
      </Routes>
    </>,
    { wrapper: Wrapper },
  );
}

/** The pick button's accessible name starts with the solution name; its
 *  sibling delete button's is "Remove <name>". Anchor so both don't match. */
const pickButton = () => screen.findByRole("button", { name: /^starter/ });

describe("Home → solution pick", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("tells the operator the switch is in flight, naming the solution", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    vi.mocked(client.listSolutions).mockResolvedValue([STARTER]);
    let release: (v: { name: string; path: string }) => void = () => {};
    vi.mocked(client.switchSolution).mockImplementation(
      () => new Promise((res) => (release = res)),
    );

    renderApp();
    await userEvent.click(await pickButton());

    // A live region, so a screen reader announces it too — the button that
    // was just clicked has been removed from the page.
    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent(/starter/);
    // And it must frame this as slow, not stuck.
    expect(status).toHaveTextContent(/second/i);

    release({ name: STARTER.name, path: STARTER.path });
  });

  it("says 'Reopening' on the auto-reopen path, not 'Loading'", async () => {
    localStorage.setItem(
      "sage-desktop:last-solution",
      JSON.stringify({ name: STARTER.name, path: STARTER.path }),
    );
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    vi.mocked(client.listSolutions).mockResolvedValue([STARTER]);
    vi.mocked(client.switchSolution).mockImplementation(
      () => new Promise(() => {}), // never settles: hold the pending state
    );

    renderApp();
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(/reopening/i),
    );
  });

  it("lands on the guarded page rather than bouncing back to the picker", async () => {
    // Regression guard for the Home + RequireSolution seam, which no
    // per-page test covers. `useCurrentSolution` caches `null` while nothing
    // is loaded and RequireSolution redirects on a falsy value whenever
    // isLoading is false — so if the post-switch cache update ever lands
    // after Home's navigate, the operator is thrown back to the picker.
    let loaded: { name: string; path: string } | null = null;
    vi.mocked(client.getCurrentSolution).mockImplementation(
      () => new Promise((res) => setTimeout(() => res(loaded), 0)),
    );
    vi.mocked(client.listSolutions).mockResolvedValue([STARTER]);
    vi.mocked(client.switchSolution).mockImplementation(
      (name, path) =>
        new Promise((res) =>
          setTimeout(() => {
            loaded = { name, path };
            res({ name, path });
          }, 0),
        ),
    );

    renderApp();
    await userEvent.click(await pickButton());

    await waitFor(() =>
      expect(screen.getByText("APPROVALS PAGE")).toBeInTheDocument(),
    );
  });
});
