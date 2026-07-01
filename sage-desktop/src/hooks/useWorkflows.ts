import { useMutation, useQuery } from "@tanstack/react-query";

import {
  getWorkflowStatus,
  listWorkflows,
  resumeWorkflow,
  runWorkflow,
} from "@/api/client";
import type {
  DesktopError,
  WorkflowListResult,
  WorkflowRunResult,
  WorkflowStatusResult,
} from "@/api/types";

export function useWorkflowList() {
  return useQuery<WorkflowListResult, DesktopError>({
    queryKey: ["workflowList"],
    queryFn: () => listWorkflows(),
  });
}

interface RunWorkflowVars {
  workflow_name: string;
  state?: Record<string, unknown>;
}

export function useRunWorkflow() {
  return useMutation<WorkflowRunResult, DesktopError, RunWorkflowVars>({
    mutationFn: (v) => runWorkflow(v.workflow_name, v.state),
  });
}

interface ResumeWorkflowVars {
  run_id: string;
  feedback?: Record<string, unknown>;
}

export function useResumeWorkflow() {
  return useMutation<WorkflowRunResult, DesktopError, ResumeWorkflowVars>({
    mutationFn: (v) => resumeWorkflow(v.run_id, v.feedback),
  });
}

export function useWorkflowStatus(runId: string, enabled = true) {
  return useQuery<WorkflowStatusResult, DesktopError>({
    queryKey: ["workflowStatus", runId],
    queryFn: () => getWorkflowStatus(runId),
    enabled: enabled && runId.length > 0,
  });
}
