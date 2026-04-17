import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  startBuild: vi.fn(),
  listBuilds: vi.fn(),
  getBuild: vi.fn(),
  approveBuildStage: vi.fn(),
}));

import * as client from "@/api/client";
import {
  useApproveBuildStage,
  useBuild,
  useBuilds,
  useStartBuild,
} from "@/hooks/useBuilds";
import {
  createTestQueryClient,
  wrapperWith,
} from "../helpers/queryWrapper";

const summary = {
  run_id: "r1",
  solution_name: "yoga",
  state: "completed" as const,
  created_at: "2026-04-17T12:00:00Z",
  task_count: 3,
};

const detail = {
  run_id: "r1",
  solution_name: "yoga",
  state: "awaiting_plan",
  state_description: "waiting for plan approval",
  created_at: "2026-04-17T12:00:00Z",
  updated_at: "2026-04-17T12:00:01Z",
  product_description: "yoga app",
  hitl_level: "standard",
  hitl_gates: [],
  detected_domains: [],
  plan: [],
  task_count: 0,
  critic_scores: [],
  critic_reports: [],
  agent_results: [],
  integration_result: null,
  phase_durations: {},
};

describe("useBuilds", () => {
  beforeEach(() => vi.clearAllMocks());

  it("fetches the list of runs", async () => {
    vi.mocked(client.listBuilds).mockResolvedValue([summary]);
    const { result } = renderHook(() => useBuilds(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.[0].run_id).toBe("r1");
  });
});

describe("useBuild", () => {
  beforeEach(() => vi.clearAllMocks());

  it("skips the fetch when no run_id is supplied", () => {
    const { result } = renderHook(() => useBuild(undefined), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    expect(result.current.fetchStatus).toBe("idle");
    expect(client.getBuild).not.toHaveBeenCalled();
  });

  it("fetches when a run_id is supplied", async () => {
    vi.mocked(client.getBuild).mockResolvedValue(detail);
    const { result } = renderHook(() => useBuild("r1"), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.getBuild).toHaveBeenCalledWith("r1");
    expect(result.current.data?.state).toBe("awaiting_plan");
  });
});

describe("useStartBuild", () => {
  beforeEach(() => vi.clearAllMocks());

  it("passes params through and invalidates the builds list", async () => {
    vi.mocked(client.startBuild).mockResolvedValue(detail);
    const qc = createTestQueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useStartBuild(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate({ product_description: "yoga app" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.startBuild).toHaveBeenCalledWith({
      product_description: "yoga app",
    });
    expect(spy).toHaveBeenCalled();
  });

  it("surfaces SidecarDown when the orchestrator crashes", async () => {
    vi.mocked(client.startBuild).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "decomposer failed" },
    });
    const { result } = renderHook(() => useStartBuild(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    result.current.mutate({ product_description: "yoga" });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.kind).toBe("SidecarDown");
  });
});

describe("useApproveBuildStage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("invalidates both the specific run and the list on success", async () => {
    vi.mocked(client.approveBuildStage).mockResolvedValue({
      ...detail,
      state: "building",
    });
    const qc = createTestQueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useApproveBuildStage(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate({ run_id: "r1", approved: true });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.approveBuildStage).toHaveBeenCalledWith({
      run_id: "r1",
      approved: true,
    });
    // Two invalidations: list and specific run detail
    expect(spy).toHaveBeenCalledTimes(2);
  });

  it("surfaces InvalidParams when run is not awaiting approval", async () => {
    vi.mocked(client.approveBuildStage).mockRejectedValue({
      kind: "InvalidParams",
      detail: { message: "Run is not awaiting approval (state: building)" },
    });
    const { result } = renderHook(() => useApproveBuildStage(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    result.current.mutate({ run_id: "r1", approved: true });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.kind).toBe("InvalidParams");
  });
});
