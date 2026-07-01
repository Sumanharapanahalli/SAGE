import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import * as client from "@/api/client";
import { useAnalyzeLog } from "@/hooks/useAnalyze";
import { approvalsKey } from "@/hooks/useApprovals";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

vi.mock("@/api/client");

const PROPOSAL = {
  trace_id: "t1",
  created_at: "",
  action_type: "analysis",
  risk_class: "INFORMATIONAL",
  reversible: true,
  proposed_by: "desktop-operator",
  description: "[AMBER] disk usage climbing",
  payload: {},
  status: "pending",
  decided_by: null,
  decided_at: null,
  feedback: null,
  expires_at: null,
  required_role: null,
  approved_by: null,
} as any;

describe("useAnalyzeLog", () => {
  beforeEach(() => vi.resetAllMocks());

  it("submits the log entry and returns the created proposal", async () => {
    vi.mocked(client.analyzeLog).mockResolvedValue(PROPOSAL);
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useAnalyzeLog(), {
      wrapper: wrapperWith(qc),
    });

    result.current.mutate({ log_entry: "disk at 95%" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.analyzeLog).toHaveBeenCalledWith("disk at 95%");
    expect(result.current.data).toEqual(PROPOSAL);
  });

  it("invalidates the approvals cache on success so the inbox refreshes", async () => {
    vi.mocked(client.analyzeLog).mockResolvedValue(PROPOSAL);
    const qc = createTestQueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useAnalyzeLog(), {
      wrapper: wrapperWith(qc),
    });

    result.current.mutate({ log_entry: "disk at 95%" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: approvalsKey });
  });

  it("surfaces the rejection as result.current.error", async () => {
    vi.mocked(client.analyzeLog).mockRejectedValue({
      kind: "Other",
      detail: { code: -32000, message: "analysis failed: llm down" },
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useAnalyzeLog(), {
      wrapper: wrapperWith(qc),
    });

    result.current.mutate({ log_entry: "x" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toEqual({
      kind: "Other",
      detail: { code: -32000, message: "analysis failed: llm down" },
    });
  });
});
