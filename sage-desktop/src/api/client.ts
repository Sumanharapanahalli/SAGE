/**
 * Typed wrapper around Tauri's `invoke`.
 *
 * Each function corresponds to a `#[tauri::command]` in src-tauri. This
 * module is the *only* place in the frontend that should import from
 * `@tauri-apps/api/core` — everything else uses the typed helpers here.
 */
import { invoke } from "@tauri-apps/api/core";

import type {
  Agent,
  ApproveBuildParams,
  AuditEvent,
  AuditListResponse,
  AuditStats,
  AuditTraceResponse,
  BatchApproveResult,
  BuildRunDetail,
  BuildRunSummary,
  CheckActionResult,
  CollectiveGetResult,
  CollectiveHelpCreateResult,
  CollectiveHelpListResult,
  CollectiveHelpMutationResult,
  CollectiveListResult,
  CollectivePublishResult,
  CollectiveSearchResult,
  CollectiveStats,
  CollectiveSyncResult,
  CollectiveValidateResult,
  ComplianceChecklist,
  ComplianceDomainsResult,
  ComplianceGapResult,
  ConstitutionData,
  ConstitutionState,
  ConstitutionUpdateResult,
  CostBudgetResult,
  CostDailyResult,
  CostSummary,
  DesktopError,
  FeatureRequest,
  FeatureRequestScope,
  FeatureRequestStatus,
  FeatureRequestSubmit,
  FeatureRequestUpdate,
  HandshakeResponse,
  KnowledgeAddResult,
  KnowledgeDeleteResult,
  KnowledgeListResult,
  KnowledgeSearchResult,
  KnowledgeStats,
  LlmInfo,
  LlmSwitchResult,
  McpToolsResult,
  OrgData,
  OrgReloadResult,
  OrgUpdateResult,
  PlanResult,
  Proposal,
  QueueStatus,
  QueueTask,
  SkillsListResult,
  SkillsReloadResult,
  SkillVisibilitySetResult,
  SolutionRef,
  StartBuildParams,
  CurrentSolution,
  SwitchSolutionResult,
  OnboardingParams,
  OnboardingResult,
  StatusResponse,
  WorkflowListResult,
  WorkflowRunResult,
  WorkflowStatusResult,
  YamlFileName,
  YamlReadResult,
  YamlWriteResult,
} from "./types";

/**
 * Normalize a caught error into our typed DesktopError shape.
 *
 * Tauri serializes Result<_, E> where E: Serialize onto the JS side as a
 * thrown value. Our `DesktopError` is tagged ({kind, detail}), so most
 * errors will already be shaped correctly. For non-structured errors
 * (e.g. a panic) we wrap into `SidecarDown`.
 */
export function toDesktopError(e: unknown): DesktopError {
  if (
    e !== null &&
    typeof e === "object" &&
    "kind" in e &&
    typeof (e as { kind: unknown }).kind === "string"
  ) {
    return e as DesktopError;
  }
  if (typeof e === "string") {
    return { kind: "SidecarDown", detail: { message: e } };
  }
  if (e instanceof Error) {
    return { kind: "SidecarDown", detail: { message: e.message } };
  }
  return {
    kind: "SidecarDown",
    detail: { message: "unknown error" },
  };
}

/** Call a Tauri command, normalizing any thrown error to DesktopError. */
export async function call<T>(command: string, args?: unknown): Promise<T> {
  try {
    return await invoke<T>(command, args as Record<string, unknown>);
  } catch (e) {
    throw toDesktopError(e);
  }
}

// ── Handshake / Status ────────────────────────────────────────────────────

export const handshake = () => call<HandshakeResponse>("handshake");
export const getStatus = () => call<StatusResponse>("get_status");

// ── Analyze ───────────────────────────────────────────────────────────────
// The desktop operator's SURFACE -> PROPOSE trigger: runs the AnalystAgent
// against a log/signal and creates a real proposal, visible immediately in
// Approvals (list_pending_approvals reads the same store).

export const analyzeLog = (log_entry: string) =>
  call<Proposal>("analyze_run", { log_entry });

// ── Compliance ────────────────────────────────────────────────────────────
// Assessment tooling on top of the audit RECORD already on desktop — lets a
// compliance operator check conformance (domain checklists, gap assessment)
// without leaving the app.

export const listComplianceDomains = () =>
  call<ComplianceDomainsResult>("compliance_domains");

export const getComplianceChecklist = (domain: string, risk_level?: string) =>
  call<ComplianceChecklist>("compliance_checklist", { domain, risk_level });

export const assessComplianceGap = (
  domain: string,
  risk_level: string,
  completed_tasks: string[],
) =>
  call<ComplianceGapResult>("compliance_gap_assessment", {
    domain,
    risk_level,
    completed_tasks,
  });

// ── Approvals ─────────────────────────────────────────────────────────────

export const listPendingApprovals = () =>
  call<Proposal[]>("list_pending_approvals");

export const getApproval = (trace_id: string) =>
  call<Proposal>("get_approval", { trace_id });

export const approveProposal = (
  trace_id: string,
  decided_by?: string,
  feedback?: string,
) =>
  call<Proposal>("approve_proposal", {
    trace_id,
    decided_by,
    feedback,
  });

export const rejectProposal = (
  trace_id: string,
  decided_by?: string,
  feedback?: string,
) =>
  call<Proposal>("reject_proposal", {
    trace_id,
    decided_by,
    feedback,
  });

export const batchApprove = (
  trace_ids: string[],
  decided_by?: string,
  feedback?: string,
) =>
  call<BatchApproveResult>("batch_approve", {
    trace_ids,
    decided_by,
    feedback,
  });

// ── Audit ─────────────────────────────────────────────────────────────────

export interface ListAuditParams {
  limit?: number;
  offset?: number;
  action_type?: string;
  trace_id?: string;
}

export const listAuditEvents = (params: ListAuditParams = {}) =>
  call<AuditListResponse>("list_audit_events", params);

export const getAuditByTrace = (trace_id: string) =>
  call<AuditTraceResponse>("get_audit_by_trace", { trace_id });

export const auditStats = () => call<AuditStats>("audit_stats");

// ── Agents ────────────────────────────────────────────────────────────────

export const listAgents = () => call<Agent[]>("list_agents");
export const getAgent = (name: string) => call<Agent>("get_agent", { name });

// ── LLM ───────────────────────────────────────────────────────────────────

export const getLlmInfo = () => call<LlmInfo>("get_llm_info");

export const switchLlm = (req: {
  provider: string;
  model?: string;
  save_as_default?: boolean;
}) => call<LlmSwitchResult>("switch_llm", req);

// ── Backlog ───────────────────────────────────────────────────────────────

export const listFeatureRequests = (
  params: { status?: FeatureRequestStatus; scope?: FeatureRequestScope } = {},
) => call<FeatureRequest[]>("list_feature_requests", params);

export const submitFeatureRequest = (req: FeatureRequestSubmit) =>
  call<FeatureRequest>("submit_feature_request", req);

export const updateFeatureRequest = (req: FeatureRequestUpdate) =>
  call<FeatureRequest>("update_feature_request", req);

// The desktop PROPOSE trigger for a backlog item: SAGE-scope requests open a
// GitHub issue (no LLM call), solution-scope requests run the PlannerAgent
// and create a real "implementation_plan" proposal — visible immediately in
// Approvals (list_pending_approvals reads the same store).
export const planFeatureRequest = (req_id: string) =>
  call<PlanResult>("plan_feature_request", { req_id });

// ── Solutions ─────────────────────────────────────────────────────────────

export const listSolutions = () => call<SolutionRef[]>("list_solutions");

export const getCurrentSolution = () =>
  call<CurrentSolution | null>("get_current_solution");

export const switchSolution = (name: string, path: string) =>
  call<SwitchSolutionResult>("switch_solution", { name, path });

// ── Onboarding ────────────────────────────────────────────────────────────

export const onboardingGenerate = (params: OnboardingParams) =>
  call<OnboardingResult>("onboarding_generate", params);

// ── Builds ────────────────────────────────────────────────────────────────

export const startBuild = (params: StartBuildParams) =>
  call<BuildRunDetail>("start_build", params);

export const listBuilds = () => call<BuildRunSummary[]>("list_builds");

export const getBuild = (run_id: string) =>
  call<BuildRunDetail>("get_build", { run_id });

export const approveBuildStage = (params: ApproveBuildParams) =>
  call<BuildRunDetail>("approve_build_stage", params);

// ── YAML authoring ────────────────────────────────────────────────────────

export const readYaml = (file: YamlFileName) =>
  call<YamlReadResult>("read_yaml", { file });

export const writeYaml = (file: YamlFileName, content: string) =>
  call<YamlWriteResult>("write_yaml", { file, content });

// ── Constitution ──────────────────────────────────────────────────────────

export const constitutionGet = () =>
  call<ConstitutionState>("constitution_get");

export const constitutionUpdate = (
  data: ConstitutionData,
  changed_by?: string,
) =>
  call<ConstitutionUpdateResult>("constitution_update", {
    data,
    changed_by,
  });

export const constitutionPreamble = () =>
  call<{ preamble: string }>("constitution_preamble");

export const constitutionCheckAction = (action_description: string) =>
  call<CheckActionResult>("constitution_check_action", {
    action_description,
  });

// ── Knowledge Browser ─────────────────────────────────────────────────────

export const knowledgeList = (params: { limit?: number; offset?: number } = {}) =>
  call<KnowledgeListResult>("knowledge_list", params);

export const knowledgeSearch = (query: string, top_k?: number) =>
  call<KnowledgeSearchResult>("knowledge_search", { query, top_k });

export const knowledgeAdd = (text: string, metadata?: Record<string, unknown>) =>
  call<KnowledgeAddResult>("knowledge_add", { text, metadata });

export const knowledgeDelete = (id: string) =>
  call<KnowledgeDeleteResult>("knowledge_delete", { id });

export const knowledgeStats = () => call<KnowledgeStats>("knowledge_stats");

// ── Queue ─────────────────────────────────────────────────────────────────

export const getQueueStatus = () => call<QueueStatus>("get_queue_status");

export const listQueueTasks = (
  params: { status?: string; limit?: number } = {},
) => call<QueueTask[]>("list_queue_tasks", params);

// ── Collective Intelligence ─────────────────────────────────────────────

export const collectiveListLearnings = (params: {
  solution?: string;
  topic?: string;
  limit?: number;
  offset?: number;
} = {}) => call<CollectiveListResult>("collective_list_learnings", params);

export const collectiveGetLearning = (id: string) =>
  call<CollectiveGetResult>("collective_get_learning", { id });

export const collectiveSearchLearnings = (params: {
  query: string;
  tags?: string[];
  solution?: string;
  limit?: number;
}) => call<CollectiveSearchResult>("collective_search_learnings", params);

export const collectivePublishLearning = (payload: {
  author_agent: string;
  author_solution: string;
  topic: string;
  title: string;
  content: string;
  tags?: string[];
  confidence?: number;
  source_task_id?: string;
  proposed_by?: string;
}) => call<CollectivePublishResult>("collective_publish_learning", payload);

export const collectiveValidateLearning = (id: string, validated_by: string) =>
  call<CollectiveValidateResult>("collective_validate_learning", {
    id,
    validated_by,
  });

export const collectiveListHelpRequests = (params: {
  status?: "open" | "closed";
  expertise?: string[];
} = {}) =>
  call<CollectiveHelpListResult>("collective_list_help_requests", params);

export const collectiveCreateHelpRequest = (payload: {
  title: string;
  requester_agent: string;
  requester_solution: string;
  urgency?: "low" | "medium" | "high" | "critical";
  required_expertise?: string[];
  context?: string;
}) =>
  call<CollectiveHelpCreateResult>("collective_create_help_request", payload);

export const collectiveClaimHelpRequest = (
  id: string,
  agent: string,
  solution: string,
) =>
  call<CollectiveHelpMutationResult>("collective_claim_help_request", {
    id,
    agent,
    solution,
  });

export const collectiveRespondToHelpRequest = (payload: {
  id: string;
  responder_agent: string;
  responder_solution: string;
  content: string;
}) =>
  call<CollectiveHelpMutationResult>(
    "collective_respond_to_help_request",
    payload,
  );

export const collectiveCloseHelpRequest = (id: string) =>
  call<CollectiveHelpMutationResult>("collective_close_help_request", { id });

export const collectiveSync = () =>
  call<CollectiveSyncResult>("collective_sync");

export const collectiveStats = () =>
  call<CollectiveStats>("collective_stats");

// ── Skills & Tools ─────────────────────────────────────────────────────────
// Read-and-toggle only: list skills, toggle visibility, hot-reload from
// disk, and browse MCP tools. Visibility/reload are framework control
// (no HITL approval) — mirrors the web API's `/skills/visibility` and
// `/skills/reload` docstrings.

export const listSkills = (include_disabled?: boolean) =>
  call<SkillsListResult>("list_skills", { include_disabled });

export const setSkillVisibility = (name: string, visibility: string) =>
  call<SkillVisibilitySetResult>("set_skill_visibility", { name, visibility });

export const reloadSkills = () => call<SkillsReloadResult>("reload_skills");

export const listMcpTools = () => call<McpToolsResult>("list_mcp_tools");

// ── Costs (T1-004) ───────────────────────────────────────────────────────
// LLM spend summary/daily breakdown and per-solution monthly budget
// controls. Budget writes go straight to config.yaml — the operator's own
// explicit action, not an agent proposal — mirroring api.py's
// /costs/budget endpoint.

export const getCostsSummary = (
  tenant?: string,
  solution?: string,
  period_days?: number,
) => call<CostSummary>("costs_summary", { tenant, solution, period_days });

export const getCostsDaily = (
  tenant?: string,
  solution?: string,
  period_days?: number,
) => call<CostDailyResult>("costs_daily", { tenant, solution, period_days });

export const setCostsBudget = (
  monthly_usd: number,
  tenant?: string,
  solution?: string,
) =>
  call<CostBudgetResult>("costs_set_budget", {
    monthly_usd,
    tenant,
    solution,
  });

// ── Workflows (LangGraph) ────────────────────────────────────────────────
// List registered workflows for the active solution, start/resume
// approval-gated runs, and poll status. Empty list / thrown "not found"
// errors are the graceful-degradation path when orchestration.engine !=
// "langgraph" or the langgraph package isn't installed.

export const listWorkflows = () => call<WorkflowListResult>("list_workflows");

export const runWorkflow = (
  workflow_name: string,
  state?: Record<string, unknown>,
) => call<WorkflowRunResult>("run_workflow", { workflow_name, state });

export const resumeWorkflow = (
  run_id: string,
  feedback?: Record<string, unknown>,
) => call<WorkflowRunResult>("resume_workflow", { run_id, feedback });

export const getWorkflowStatus = (run_id: string) =>
  call<WorkflowStatusResult>("get_workflow_status", { run_id });

// ── Organization ──────────────────────────────────────────────────────────
// org.yaml is a SAGE_ROOT-level file (not per-solution) — identity fields
// (name/mission/vision/core_values) shape every solution's onboarding and
// agent context. Channel/solution/route CRUD is out of scope for this pass
// (a follow-up, same shape as /org/channels, /org/solutions, /org/routes on
// the web API); this is read (incl. read-only routes) + edit + reload.

export const getOrg = () => call<OrgData>("org_get");

export const updateOrg = (fields: {
  name?: string;
  mission?: string;
  vision?: string;
  core_values?: string[];
}) => call<OrgUpdateResult>("org_update", fields);

export const reloadOrg = () => call<OrgReloadResult>("org_reload");

// Re-exports to reduce import boilerplate at call sites
export type {
  Agent,
  ApproveBuildParams,
  AuditEvent,
  AuditListResponse,
  AuditStats,
  AuditTraceResponse,
  BatchApproveResult,
  BuildRunDetail,
  BuildRunSummary,
  CheckActionResult,
  ConstitutionData,
  ConstitutionState,
  ConstitutionUpdateResult,
  DesktopError,
  FeatureRequest,
  FeatureRequestScope,
  FeatureRequestStatus,
  FeatureRequestSubmit,
  FeatureRequestUpdate,
  HandshakeResponse,
  LlmInfo,
  LlmSwitchResult,
  McpToolsResult,
  OrgData,
  OrgReloadResult,
  OrgUpdateResult,
  PlanResult,
  Proposal,
  QueueStatus,
  QueueTask,
  SkillsListResult,
  SkillsReloadResult,
  SkillVisibilitySetResult,
  SolutionRef,
  StartBuildParams,
  CurrentSolution,
  SwitchSolutionResult,
  OnboardingParams,
  OnboardingResult,
  StatusResponse,
  WorkflowListResult,
  WorkflowRunResult,
  WorkflowStatusResult,
  YamlFileName,
  YamlReadResult,
  YamlWriteResult,
};
