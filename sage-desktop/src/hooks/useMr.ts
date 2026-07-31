import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  commentOnMr,
  listOpenMrs,
  mrConfig,
  mrPipeline,
  proposeMr,
  reviewMr,
} from "@/api/client";
import type {
  DesktopError,
  MrCommentResult,
  MrConfig,
  MrListResult,
  MrPipelineResult,
  MrReviewStarted,
  Proposal,
} from "@/api/types";
import { approvalsKey } from "@/hooks/useApprovals";

export const mrConfigKey = ["mrConfig"] as const;
export const openMrsKey = (projectId: number) => ["openMrs", projectId] as const;

/** GitLab reachability — a state, never an error, so the page can render a
 *  setup prompt instead of a failure. */
export function useMrConfig() {
  return useQuery<MrConfig, DesktopError>({
    queryKey: mrConfigKey,
    queryFn: () => mrConfig(),
  });
}

export function useOpenMrs(projectId: number | null) {
  return useQuery<MrListResult, DesktopError>({
    queryKey: openMrsKey(projectId ?? 0),
    queryFn: () => listOpenMrs(projectId as number),
    enabled: projectId !== null && projectId > 0,
  });
}

interface MrRef {
  project_id: number;
  mr_iid: number;
}

export function useMrPipeline() {
  return useMutation<MrPipelineResult, DesktopError, MrRef>({
    mutationFn: (v) => mrPipeline(v.project_id, v.mr_iid),
  });
}

export function useReviewMr() {
  return useMutation<MrReviewStarted, DesktopError, MrRef>({
    mutationFn: (v) => reviewMr(v.project_id, v.mr_iid),
  });
}

interface ProposeVars {
  project_id: number;
  issue_iid: number;
  source_branch?: string;
}

/** Files a proposal rather than opening the MR, so the approvals inbox — not
 *  the MR list — is what changes. */
export function useProposeMr() {
  const qc = useQueryClient();
  return useMutation<Proposal, DesktopError, ProposeVars>({
    mutationFn: (v) => proposeMr(v.project_id, v.issue_iid, v.source_branch),
    onSuccess: () => qc.invalidateQueries({ queryKey: approvalsKey }),
  });
}

export function useCommentOnMr() {
  return useMutation<MrCommentResult, DesktopError, MrRef & { comment: string }>({
    mutationFn: (v) => commentOnMr(v.project_id, v.mr_iid, v.comment),
  });
}
