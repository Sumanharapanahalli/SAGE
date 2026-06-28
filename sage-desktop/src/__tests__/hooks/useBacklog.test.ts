import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import * as client from "@/api/client";
import {
  useFeatureRequests,
  useSubmitFeatureRequest,
  useUpdateFeatureRequest,
} from "@/hooks/useBacklog";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

vi.mock("@/api/client");

describe("useFeatureRequests", () => {
  beforeEach(() => vi.resetAllMocks());

  it("lists feature requests with filters", async () => {
    vi.mocked(client.listFeatureRequests).mockResolvedValue([]);
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useFeatureRequests({ scope: "solution" }), {
      wrapper: wrapperWith(qc),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.listFeatureRequests).toHaveBeenCalledWith({ scope: "solution" });
  });
});

describe("useSubmitFeatureRequest", () => {
  beforeEach(() => vi.resetAllMocks());

  it("submits and invalidates backlog cache", async () => {
    vi.mocked(client.submitFeatureRequest).mockResolvedValue({
      id: "abc", title: "t", description: "d", status: "pending",
      priority: "medium", scope: "solution", module_id: "general",
      module_name: "General", requested_by: "anon", created_at: "",
      updated_at: "", reviewer_note: "", plan_trace_id: "",
    } as any);
    const qc = createTestQueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useSubmitFeatureRequest(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate({ title: "t", description: "d" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["backlog"] });
  });
});

describe("useUpdateFeatureRequest", () => {
  beforeEach(() => vi.resetAllMocks());

  it("updates and invalidates backlog cache", async () => {
    vi.mocked(client.updateFeatureRequest).mockResolvedValue({
      id: "abc", status: "approved",
    } as any);
    const qc = createTestQueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useUpdateFeatureRequest(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate({ id: "abc", action: "approve" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["backlog"] });
  });
});
