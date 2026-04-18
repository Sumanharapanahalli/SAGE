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
  KnowledgeAddResult,
  KnowledgeDeleteResult,
  KnowledgeListResult,
  KnowledgeSearchResult,
  KnowledgeStats,
  LlmInfo,
  LlmSwitchResult,
  Proposal,
  QueueStatus,
  QueueTask,
  SolutionRef,
  StartBuildParams,
  CurrentSolution,
  SwitchSolutionResult,
  OnboardingParams,
  OnboardingResult,
  StatusResponse,
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
  Proposal,
  QueueStatus,
  QueueTask,
  SolutionRef,
  StartBuildParams,
  CurrentSolution,
  SwitchSolutionResult,
  OnboardingParams,
  OnboardingResult,
  StatusResponse,
  YamlFileName,
  YamlReadResult,
  YamlWriteResult,
};
