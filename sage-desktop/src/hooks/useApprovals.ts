import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  approveProposal,
  batchApprove,
  getApproval,
  listPendingApprovals,
  rejectProposal,
} from "@/api/client";
import type {
  BatchApproveResult,
  DesktopError,
  Proposal,
} from "@/api/types";

export const approvalsKey = ["approvals"] as const;
export const approvalKey = (trace_id: string) =>
  ["approval", trace_id] as const;

export function useApprovals() {
  return useQuery<Proposal[], DesktopError>({
    queryKey: approvalsKey,
    queryFn: () => listPendingApprovals(),
  });
}

export function useApproval(trace_id: string) {
  return useQuery<Proposal, DesktopError>({
    queryKey: approvalKey(trace_id),
    queryFn: () => getApproval(trace_id),
    enabled: trace_id.length > 0,
  });
}

interface DecideVars {
  trace_id: string;
  decided_by?: string;
  feedback?: string;
}

export function useApproveProposal() {
  const qc = useQueryClient();
  return useMutation<Proposal, DesktopError, DecideVars>({
    mutationFn: (v) => approveProposal(v.trace_id, v.decided_by, v.feedback),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: approvalsKey });
    },
  });
}

export function useRejectProposal() {
  const qc = useQueryClient();
  return useMutation<Proposal, DesktopError, DecideVars>({
    mutationFn: (v) => rejectProposal(v.trace_id, v.decided_by, v.feedback),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: approvalsKey });
    },
  });
}

interface BatchVars {
  trace_ids: string[];
  decided_by?: string;
  feedback?: string;
}

export function useBatchApprove() {
  const qc = useQueryClient();
  return useMutation<BatchApproveResult, DesktopError, BatchVars>({
    mutationFn: (v) => batchApprove(v.trace_ids, v.decided_by, v.feedback),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: approvalsKey });
    },
  });
}
