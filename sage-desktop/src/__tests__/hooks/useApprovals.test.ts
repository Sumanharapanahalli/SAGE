import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  listPendingApprovals: vi.fn(),
  getApproval: vi.fn(),
  approveProposal: vi.fn(),
  rejectProposal: vi.fn(),
  batchApprove: vi.fn(),
}));

import * as client from "@/api/client";
import {
  useApproval,
  useApprovals,
  useApproveProposal,
  useBatchApprove,
  useRejectProposal,
} from "@/hooks/useApprovals";
import {
  createTestQueryClient,
  wrapperWith,
} from "../helpers/queryWrapper";
import type { Proposal } from "@/api/types";

const sample: Proposal = {
  trace_id: "t-1",
  created_at: "2026-04-16T10:00:00Z",
  action_type: "yaml_edit",
  risk_class: "STATEFUL",
  reversible: true,
  proposed_by: "analyst",
  description: "edit prompts.yaml",
  payload: { path: "prompts.yaml" },
  status: "pending",
  decided_by: null,
  decided_at: null,
  feedback: null,
  expires_at: null,
  required_role: null,
  approved_by: null,
  approver_role: null,
  approver_email: null,
};

describe("useApprovals", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches pending proposals", async () => {
    vi.mocked(client.listPendingApprovals).mockResolvedValue([sample]);
    const { result } = renderHook(() => useApprovals(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([sample]);
    expect(client.listPendingApprovals).toHaveBeenCalledTimes(1);
  });

  it("surfaces typed errors", async () => {
    vi.mocked(client.listPendingApprovals).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "dead" },
    });
    const { result } = renderHook(() => useApprovals(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toEqual({
      kind: "SidecarDown",
      detail: { message: "dead" },
    });
  });
});

describe("useApproval", () => {
  beforeEach(() => vi.clearAllMocks());

  it("returns nothing when trace_id is empty", () => {
    const { result } = renderHook(() => useApproval(""), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    expect(result.current.fetchStatus).toBe("idle");
    expect(client.getApproval).not.toHaveBeenCalled();
  });

  it("fetches the proposal when trace_id is set", async () => {
    vi.mocked(client.getApproval).mockResolvedValue(sample);
    const { result } = renderHook(() => useApproval("t-1"), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.getApproval).toHaveBeenCalledWith("t-1");
    expect(result.current.data).toEqual(sample);
  });
});

describe("useApproveProposal / useRejectProposal / useBatchApprove", () => {
  beforeEach(() => vi.clearAllMocks());

  it("approve mutation invalidates approvals on success", async () => {
    vi.mocked(client.approveProposal).mockResolvedValue({
      ...sample,
      status: "approved",
    });
    const qc = createTestQueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useApproveProposal(), {
      wrapper: wrapperWith(qc),
    });
    await result.current.mutateAsync({ trace_id: "t-1", decided_by: "me" });
    expect(client.approveProposal).toHaveBeenCalledWith("t-1", "me", undefined);
    expect(spy).toHaveBeenCalledWith({ queryKey: ["approvals"] });
  });

  it("reject mutation calls rejectProposal with feedback", async () => {
    vi.mocked(client.rejectProposal).mockResolvedValue({
      ...sample,
      status: "rejected",
    });
    const { result } = renderHook(() => useRejectProposal(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await result.current.mutateAsync({
      trace_id: "t-1",
      decided_by: "me",
      feedback: "nope",
    });
    expect(client.rejectProposal).toHaveBeenCalledWith("t-1", "me", "nope");
  });

  it("batch mutation passes through the array", async () => {
    vi.mocked(client.batchApprove).mockResolvedValue({ results: [] });
    const { result } = renderHook(() => useBatchApprove(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await result.current.mutateAsync({
      trace_ids: ["a", "b"],
      decided_by: "me",
    });
    expect(client.batchApprove).toHaveBeenCalledWith(["a", "b"], "me", undefined);
  });
});
