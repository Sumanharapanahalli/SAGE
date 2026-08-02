import { useMutation, useQuery } from "@tanstack/react-query";

import {
  codeApprove,
  codeExecute,
  codePlan,
  codeSandboxStatus,
} from "@/api/client";
import type {
  CodeApproveResult,
  CodeExecuteResult,
  CodePlanResult,
  CodeSandboxStatus,
  DesktopError,
} from "@/api/types";

export const sandboxStatusKey = ["codeSandboxStatus"] as const;

/**
 * Whether execution would be isolated.
 *
 * Fetched on mount, not on demand: the operator needs it while deciding
 * whether to approve, and the answer (is Docker running?) can change between
 * visits, so it is not cached indefinitely.
 */
export function useSandboxStatus() {
  return useQuery<CodeSandboxStatus, DesktopError>({
    queryKey: sandboxStatusKey,
    queryFn: () => codeSandboxStatus(),
  });
}

export function useCodePlan() {
  return useMutation<CodePlanResult, DesktopError, string>({
    mutationFn: (task) => codePlan(task),
  });
}

interface ApproveVars {
  run_id: string;
  comment?: string;
}

export function useCodeApprove() {
  return useMutation<CodeApproveResult, DesktopError, ApproveVars>({
    mutationFn: (v) => codeApprove(v.run_id, v.comment),
  });
}

export function useCodeExecute() {
  return useMutation<CodeExecuteResult, DesktopError, string>({
    mutationFn: (run_id) => codeExecute(run_id),
  });
}
