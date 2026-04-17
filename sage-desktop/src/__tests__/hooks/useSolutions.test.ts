import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
