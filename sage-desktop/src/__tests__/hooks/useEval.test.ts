import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import * as client from "@/api/client";
import { useEvalSuites, useRunEval, useEvalHistory } from "@/hooks/useEval";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

vi.mock("@/api/client");

describe("useEvalSuites", () => {
  beforeEach(() => vi.resetAllMocks());

  it("lists eval suites", async () => {
    vi.mocked(client.listEvalSuites).mockResolvedValue({
      suites: ["smoke"],
      count: 1,
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useEvalSuites(), {
      wrapper: wrapperWith(qc),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({ suites: ["smoke"], count: 1 });
  });
});

describe("useRunEval", () => {
  beforeEach(() => vi.resetAllMocks());

  it("runs a suite and invalidates the eval history cache", async () => {
    vi.mocked(client.runEval).mockResolvedValue({
      run_id: "r1",
      suite: "smoke",
      total_cases: 1,
      passed_cases: 1,
      failed_cases: 0,
      mean_score: 9.0,
      results: [],
    });
    const qc = createTestQueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useRunEval(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate("smoke");
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.runEval).toHaveBeenCalledWith("smoke");
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["evalHistory"] });
  });
});

describe("useEvalHistory", () => {
  beforeEach(() => vi.resetAllMocks());

  it("fetches history filtered by suite", async () => {
    vi.mocked(client.getEvalHistory).mockResolvedValue({
      history: [],
      count: 0,
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useEvalHistory("smoke"), {
      wrapper: wrapperWith(qc),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.getEvalHistory).toHaveBeenCalledWith("smoke", 20);
  });
});
