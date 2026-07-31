import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  analyzeJobDescription,
  getProjectConfig,
  hireAgent,
  runAgent,
} from "@/api/client";
import type {
  AgentRoleDraft,
  AgentRunResponse,
  DesktopError,
  HireAgentParams,
  ProjectConfigResult,
  Proposal,
} from "@/api/types";
import { approvalsKey } from "@/hooks/useApprovals";

export const projectConfigKey = ["projectConfig"] as const;

/** The runnable roster (UniversalAgent roles from prompts.yaml) plus the
 * parsed project.yaml. Narrower than `agents.list` — see ProjectConfigResult. */
export function useProjectConfig() {
  return useQuery<ProjectConfigResult, DesktopError>({
    queryKey: projectConfigKey,
    queryFn: () => getProjectConfig(),
  });
}

interface RunAgentVars {
  role_id: string;
  task: string;
  context?: string;
}

/** Running an agent persists a real proposal, so refresh the inbox on success
 * — same reason useAnalyzeLog does. */
export function useRunAgent() {
  const qc = useQueryClient();
  return useMutation<AgentRunResponse, DesktopError, RunAgentVars>({
    mutationFn: (v) => runAgent(v.role_id, v.task, v.context),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: approvalsKey });
    },
  });
}

/**
 * Hiring only ever PROPOSES. No YAML is written here — `agent_hire` is one of
 * the HITL proposal kinds under Law 1, and the write happens on approval in
 * proposal_executor._execute_agent_hire. The new role therefore will not show
 * up in useProjectConfig() until the human approves, so this deliberately does
 * not invalidate projectConfigKey.
 */
export function useHireAgent() {
  const qc = useQueryClient();
  return useMutation<Proposal, DesktopError, HireAgentParams>({
    mutationFn: (params) => hireAgent(params),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: approvalsKey });
    },
  });
}

interface AnalyzeJdVars {
  jd_text: string;
  solution_context?: string;
}

/** Pure read — extracts a role draft from a job description. Creates nothing. */
export function useAnalyzeJobDescription() {
  return useMutation<AgentRoleDraft, DesktopError, AnalyzeJdVars>({
    mutationFn: (v) => analyzeJobDescription(v.jd_text, v.solution_context),
  });
}
