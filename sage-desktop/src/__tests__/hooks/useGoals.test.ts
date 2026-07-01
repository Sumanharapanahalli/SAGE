import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import * as client from "@/api/client";
import {
  useGoals,
  useCreateGoal,
  useUpdateGoal,
  useDeleteGoal,
} from "@/hooks/useGoals";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

vi.mock("@/api/client");

describe("useGoals", () => {
  beforeEach(() => vi.resetAllMocks());

  it("lists goals with filters", async () => {
    vi.mocked(client.listGoals).mockResolvedValue([]);
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useGoals({ quarter: "2026-Q3" }), {
      wrapper: wrapperWith(qc),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.listGoals).toHaveBeenCalledWith({ quarter: "2026-Q3" });
  });
});

describe("useCreateGoal", () => {
  beforeEach(() => vi.resetAllMocks());

  it("creates and invalidates the goals cache", async () => {
    vi.mocked(client.createGoal).mockResolvedValue({
      id: "abc", user_id: "desktop-operator", solution: "", title: "t",
      quarter: "2026-Q3", status: "on_track", owner: "", key_results: [],
      created_at: "", updated_at: "",
    } as any);
    const qc = createTestQueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useCreateGoal(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate({ title: "t", quarter: "2026-Q3" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["goals"] });
  });
});

describe("useUpdateGoal", () => {
  beforeEach(() => vi.resetAllMocks());

  it("updates and invalidates the goals cache", async () => {
    vi.mocked(client.updateGoal).mockResolvedValue({
      id: "abc", status: "at_risk",
    } as any);
    const qc = createTestQueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useUpdateGoal(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate({ goal_id: "abc", status: "at_risk" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["goals"] });
  });
});

describe("useDeleteGoal", () => {
  beforeEach(() => vi.resetAllMocks());

  it("deletes and invalidates the goals cache", async () => {
    vi.mocked(client.deleteGoal).mockResolvedValue({ deleted: true });
    const qc = createTestQueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useDeleteGoal(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate("abc");
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.deleteGoal).toHaveBeenCalledWith("abc");
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["goals"] });
  });
});
