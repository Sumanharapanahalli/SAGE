import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import * as client from "@/api/client";
import {
  useCostsDaily,
  useCostsSummary,
  useSetCostsBudget,
} from "@/hooks/useCosts";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

vi.mock("@/api/client");

const SUMMARY = {
  total_cost_usd: 1.5,
  total_calls: 10,
  total_input_tokens: 1000,
  total_output_tokens: 500,
  avg_cost_per_call: 0.15,
  by_model: [{ model: "claude-sonnet-4-6", calls: 10, cost: 1.5 }],
  by_solution: [{ solution: "demo", calls: 10, cost: 1.5 }],
  period_days: 30,
  tenant: null,
  solution: null,
};

describe("useCostsSummary", () => {
  beforeEach(() => vi.resetAllMocks());

  it("fetches the cost summary", async () => {
    vi.mocked(client.getCostsSummary).mockResolvedValue(SUMMARY);
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useCostsSummary(undefined, undefined, 30), {
      wrapper: wrapperWith(qc),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.total_cost_usd).toBe(1.5);
    expect(client.getCostsSummary).toHaveBeenCalledWith(undefined, undefined, 30);
  });
});

describe("useCostsDaily", () => {
  beforeEach(() => vi.resetAllMocks());

  it("fetches the daily cost breakdown", async () => {
    vi.mocked(client.getCostsDaily).mockResolvedValue({
      daily: [{ date: "2026-06-30", calls: 3, cost_usd: 0.5 }],
      count: 1,
      period_days: 30,
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useCostsDaily(undefined, undefined, 30), {
      wrapper: wrapperWith(qc),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.count).toBe(1);
    expect(client.getCostsDaily).toHaveBeenCalledWith(undefined, undefined, 30);
  });
});

describe("useSetCostsBudget", () => {
  beforeEach(() => vi.resetAllMocks());

  it("sets a monthly budget", async () => {
    vi.mocked(client.setCostsBudget).mockResolvedValue({
      saved: true,
      key: "demo",
      monthly_usd: 50,
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useSetCostsBudget(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate({ monthly_usd: 50, solution: "demo" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.key).toBe("demo");
    expect(client.setCostsBudget).toHaveBeenCalledWith(50, undefined, "demo");
  });
});
