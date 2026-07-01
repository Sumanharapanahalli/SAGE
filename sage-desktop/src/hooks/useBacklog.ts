import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as client from "@/api/client";
import type {
  DesktopError,
  FeatureRequest,
  FeatureRequestScope,
  FeatureRequestStatus,
  FeatureRequestSubmit,
  FeatureRequestUpdate,
  PlanResult,
} from "@/api/types";
import { approvalsKey } from "@/hooks/useApprovals";

export const useFeatureRequests = (
  params: { status?: FeatureRequestStatus; scope?: FeatureRequestScope } = {},
) =>
  useQuery<FeatureRequest[], DesktopError>({
    queryKey: ["backlog", params.status ?? "all", params.scope ?? "all"],
    queryFn: () => client.listFeatureRequests(params),
  });

export const useSubmitFeatureRequest = () => {
  const qc = useQueryClient();
  return useMutation<FeatureRequest, DesktopError, FeatureRequestSubmit>({
    mutationFn: (req) => client.submitFeatureRequest(req),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["backlog"] }),
  });
};

export const useUpdateFeatureRequest = () => {
  const qc = useQueryClient();
  return useMutation<FeatureRequest, DesktopError, FeatureRequestUpdate>({
    mutationFn: (req) => client.updateFeatureRequest(req),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["backlog"] }),
  });
};

/** The backlog's PROPOSE trigger: generates an implementation plan for a
 * feature request. Solution-scope requests create a real proposal, so on
 * success we invalidate both the backlog list AND the approvals cache — a
 * new implementation_plan proposal should make the Approvals inbox refresh
 * too (mirrors useAnalyzeLog). */
export const usePlanFeatureRequest = () => {
  const qc = useQueryClient();
  return useMutation<PlanResult, DesktopError, string>({
    mutationFn: (req_id) => client.planFeatureRequest(req_id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["backlog"] });
      qc.invalidateQueries({ queryKey: approvalsKey });
    },
  });
};
