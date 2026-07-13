import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  listSolutions: vi.fn(),
  getCurrentSolution: vi.fn(),
  switchSolution: vi.fn(),
  unloadSolution: vi.fn(),
  removeSolution: vi.fn(),
}));

import * as client from "@/api/client";
import {
  solutionsKey,
  useCurrentSolution,
  useRemoveSolution,
  useSolutions,
  useSwitchSolution,
  useUnloadSolution,
} from "@/hooks/useSolutions";
import {
  createTestQueryClient,
  wrapperWith,
} from "../helpers/queryWrapper";

describe("useSolutions", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists solutions from the sidecar", async () => {
    vi.mocked(client.listSolutions).mockResolvedValue([
      { name: "meditation_app", path: "/abs/meditation_app", has_sage_dir: true },
      { name: "yoga", path: "/abs/yoga", has_sage_dir: false },
    ]);
    const { result } = renderHook(() => useSolutions(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(2);
    expect(result.current.data?.[0].name).toBe("meditation_app");
  });

  it("returns [] when sidecar has no sage_root wired", async () => {
    vi.mocked(client.listSolutions).mockResolvedValue([]);
    const { result } = renderHook(() => useSolutions(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([]);
  });
});

describe("useCurrentSolution", () => {
  beforeEach(() => vi.clearAllMocks());

  it("returns the wired current solution", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue({
      name: "meditation_app",
      path: "/abs/meditation_app",
    });
    const { result } = renderHook(() => useCurrentSolution(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.name).toBe("meditation_app");
  });

  it("returns null when sidecar was spawned without a solution", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    const { result } = renderHook(() => useCurrentSolution(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBeNull();
  });
});

describe("useSwitchSolution", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls switchSolution and invalidates the cache on success", async () => {
    vi.mocked(client.switchSolution).mockResolvedValue({
      name: "yoga",
      path: "/abs/yoga",
    });
    const qc = createTestQueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");

    const { result } = renderHook(() => useSwitchSolution(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate({ name: "yoga", path: "/abs/yoga" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(client.switchSolution).toHaveBeenCalledWith("yoga", "/abs/yoga");
    expect(spy).toHaveBeenCalled();
  });

  it("surfaces SolutionNotFound as a typed error", async () => {
    vi.mocked(client.switchSolution).mockRejectedValue({
      kind: "SolutionNotFound",
      detail: { name: "ghost" },
    });
    const { result } = renderHook(() => useSwitchSolution(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    result.current.mutate({ name: "ghost", path: "/abs/ghost" });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.kind).toBe("SolutionNotFound");
  });
});

describe("useUnloadSolution", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("unloads, forgets the remembered solution, and invalidates the cache", async () => {
    localStorage.setItem(
      "sage-desktop:last-solution",
      JSON.stringify({ name: "yoga", path: "/abs/yoga" }),
    );
    vi.mocked(client.unloadSolution).mockResolvedValue({
      name: null,
      path: null,
    });
    const qc = createTestQueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");

    const { result } = renderHook(() => useUnloadSolution(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate();
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(client.unloadSolution).toHaveBeenCalled();
    // Otherwise Home would immediately auto-reopen what we just unloaded.
    expect(localStorage.getItem("sage-desktop:last-solution")).toBeNull();
    expect(spy).toHaveBeenCalled();
  });

  it("keeps the remembered solution when the unload fails", async () => {
    localStorage.setItem(
      "sage-desktop:last-solution",
      JSON.stringify({ name: "yoga", path: "/abs/yoga" }),
    );
    vi.mocked(client.unloadSolution).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "dead" },
    });
    const { result } = renderHook(() => useUnloadSolution(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    result.current.mutate();
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(localStorage.getItem("sage-desktop:last-solution")).not.toBeNull();
  });
});

describe("useRemoveSolution", () => {
  beforeEach(() => vi.clearAllMocks());

  it("defaults to archive mode", async () => {
    vi.mocked(client.removeSolution).mockResolvedValue({
      name: "yoga",
      mode: "archive",
      path: "/abs/yoga",
      archived_to: "/abs/.archive/yoga-20260713T000000Z",
    });
    const { result } = renderHook(() => useRemoveSolution(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    result.current.mutate({ name: "yoga" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.removeSolution).toHaveBeenCalledWith(
      "yoga",
      "archive",
      undefined,
    );
  });

  it("passes the typed confirmation through for a delete", async () => {
    vi.mocked(client.removeSolution).mockResolvedValue({
      name: "yoga",
      mode: "delete",
      path: "/abs/yoga",
    });
    const qc = createTestQueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useRemoveSolution(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate({ name: "yoga", mode: "delete", confirm: "yoga" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.removeSolution).toHaveBeenCalledWith(
      "yoga",
      "delete",
      "yoga",
    );
    expect(spy).toHaveBeenCalledWith({ queryKey: solutionsKey });
  });
});
