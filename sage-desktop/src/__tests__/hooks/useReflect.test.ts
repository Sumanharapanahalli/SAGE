import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import * as client from "@/api/client";
import {
  useReflectRecent,
  useReflectStats,
  useRunReflection,
} from "@/hooks/useReflect";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

vi.mock("@/api/client");

const RESULT = {
  reflection_id: "abc12345",
  iterations: 2,
  final_score: 0.9,
  accepted: true,
  history: [],
  started_at: "2026-07-27T00:00:00Z",
  completed_at: "2026-07-27T00:00:01Z",
  final_output: "a refined answer",
};

describe("useReflectStats", () => {
  beforeEach(() => vi.resetAllMocks());

  it("fetches session stats", async () => {
    vi.mocked(client.reflectStats).mockResolvedValue({
      total_reflections: 3,
      accepted_count: 2,
      rejected_count: 1,
      avg_iterations: 1.7,
      avg_final_score: 0.8,
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useReflectStats(), {
      wrapper: wrapperWith(qc),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.total_reflections).toBe(3);
  });
});

describe("useReflectRecent", () => {
  beforeEach(() => vi.resetAllMocks());

  it("fetches recent reflections", async () => {
    vi.mocked(client.reflectRecent).mockResolvedValue({
      reflections: [RESULT],
      count: 1,
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useReflectRecent(5), {
      wrapper: wrapperWith(qc),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.count).toBe(1);
    expect(client.reflectRecent).toHaveBeenCalledWith(5);
  });
});

describe("useRunReflection", () => {
  beforeEach(() => vi.resetAllMocks());

  it("runs a reflection with the given task", async () => {
    vi.mocked(client.reflectRun).mockResolvedValue(RESULT);
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useRunReflection(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate({ task: "improve the plan" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.accepted).toBe(true);
    expect(client.reflectRun).toHaveBeenCalledWith(
      "improve the plan",
      undefined,
      undefined,
      undefined,
    );
  });
});
