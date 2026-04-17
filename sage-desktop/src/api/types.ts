/**
 * Shared response types between the React frontend and the Python sidecar.
 *
 * These mirror the handler return shapes defined in `sidecar/handlers/*.py`
 * — keep them in sync when changing the wire contract.
 */

// ── Errors ────────────────────────────────────────────────────────────────

/**
 * The serde-tagged enum DesktopError serializes as {kind, detail}.
 * kind names match the Rust DesktopError variants.
 */
export type DesktopError =
  | { kind: "ProposalNotFound"; detail: { trace_id: string } }
  | { kind: "ProposalExpired"; detail: { trace_id: string } }
  | {
      kind: "AlreadyDecided";
      detail: { trace_id: string; status: string };
    }
  | { kind: "RbacDenied"; detail: { required_role: string } }
  | { kind: "SolutionUnavailable"; detail: { message: string } }
  | {
      kind: "SageImportError";
      detail: { module: string; detail: string };
    }
  | { kind: "InvalidRequest"; detail: { message: string } }
  | { kind: "InvalidParams"; detail: { message: string } }
  | { kind: "MethodNotFound"; detail: { method: string } }
  | { kind: "SidecarDown"; detail: { message: string } }
  | { kind: "FeatureRequestNotFound"; detail: { feature_id: string } }
  | { kind: "SolutionNotFound"; detail: { name: string } }
  | { kind: "Other"; detail: { code: number; message: string } };

// ── Proposals ─────────────────────────────────────────────────────────────

export type RiskClass =
  | "INFORMATIONAL"
  | "EPHEMERAL"
  | "STATEFUL"
  | "EXTERNAL"
  | "DESTRUCTIVE";

export type ProposalStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "expired";

export interface Proposal {
  trace_id: string;
  created_at: string;
  action_type: string;
  risk_class: RiskClass;
  reversible: boolean;
  proposed_by: string;
  description: string;
  payload: Record<string, unknown>;
  status: ProposalStatus;
  decided_by: string | null;
  decided_at: string | null;
  feedback: string | null;
  expires_at: string | null;
  required_role: string | null;
  approved_by: string | null;
  approver_role: string | null;
  approver_email: string | null;
}

export interface BatchApproveResult {
  results: {
    trace_id: string;
    ok: boolean;
    proposal?: Proposal;
    error?: { code: number; message: string; data?: unknown };
  }[];
}

// ── Audit ─────────────────────────────────────────────────────────────────

export interface AuditEvent {
  id: string;
  timestamp: string;
  trace_id: string | null;
  event_type: string | null;
  status: string | null;
  actor: string;
  action_type: string;
  input_context: string | null;
  output_content: string | null;
  metadata: Record<string, unknown>;
  approved_by: string | null;
  approver_role: string | null;
  approver_email: string | null;
  approver_provider: string | null;
}

export interface AuditListResponse {
  total: number;
  limit: number;
  offset: number;
  events: AuditEvent[];
}

export interface AuditTraceResponse {
  trace_id: string;
  events: AuditEvent[];
}

export interface AuditStats {
  total: number;
  by_action_type: Record<string, number>;
}

// ── Agents ────────────────────────────────────────────────────────────────

export interface Agent {
  name: string;
  kind: "core" | "custom";
  description: string;
  system_prompt: string;
  event_count: number;
  last_active: string | null;
}

// ── Status ────────────────────────────────────────────────────────────────

export interface StatusResponse {
  health: "ok" | string;
  sidecar_version: string;
  project: { name: string | null; path: string | null } | null;
  llm: { provider?: string; model?: string; error?: string } | null;
  pending_approvals: number;
}

// ── Handshake ─────────────────────────────────────────────────────────────

export interface HandshakeResponse {
  sidecar_version: string;
  sage_version: string;
  solution_name: string;
  solution_path: string;
  warnings: string[];
}

// ── LLM ───────────────────────────────────────────────────────────────────

export interface LlmInfo {
  provider_name: string;
  model: string;
  available_providers: string[];
}

export interface LlmSwitchResult {
  provider: string;
  provider_name: string;
  saved_as_default: boolean;
}

// ── Feature requests (backlog) ────────────────────────────────────────────

export type FeatureRequestScope = "solution" | "sage";
export type FeatureRequestPriority = "low" | "medium" | "high" | "critical";
export type FeatureRequestStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "completed"
  | "in_progress";

export interface FeatureRequest {
  id: string;
  module_id: string;
  module_name: string;
  title: string;
  description: string;
  priority: FeatureRequestPriority;
  status: FeatureRequestStatus;
  requested_by: string;
  scope: FeatureRequestScope;
  created_at: string;
  updated_at: string;
  reviewer_note: string;
  plan_trace_id: string;
}

export interface FeatureRequestSubmit {
  title: string;
  description: string;
  priority?: FeatureRequestPriority;
  scope?: FeatureRequestScope;
  module_id?: string;
  module_name?: string;
  requested_by?: string;
}

export type FeatureRequestAction = "approve" | "reject" | "complete";

export interface FeatureRequestUpdate {
  id: string;
  action: FeatureRequestAction;
  reviewer_note?: string;
}

// ── Solutions ─────────────────────────────────────────────────────────────

export interface SolutionRef {
  name: string;
  path: string;
  has_sage_dir: boolean;
}

export interface CurrentSolution {
  name: string;
  path: string;
}

export interface SwitchSolutionResult {
  name: string;
  path: string;
}

// ── Queue ─────────────────────────────────────────────────────────────────

export interface QueueStatus {
  pending: number;
  in_progress: number;
  done: number;
  failed: number;
  blocked: number;
  parallel_enabled: boolean;
  max_workers: number;
}

export interface QueueTask {
  id: string;
  task_type: string;
  status: string;
  priority?: number;
  created_at?: string;
  started_at?: string;
  completed_at?: string;
  error?: string;
}

// ── Build pipeline ────────────────────────────────────────────────────────

export type BuildState =
  | "decomposing"
  | "awaiting_plan"
  | "building"
  | "awaiting_build"
  | "integrating"
  | "completed"
  | "failed"
  | "rejected";

export type HitlLevel = "permissive" | "standard" | "strict";

export interface StartBuildParams {
  product_description: string;
  solution_name?: string;
  repo_url?: string;
  workspace_dir?: string;
  critic_threshold?: number;
  hitl_level?: HitlLevel;
}

/** Summary shape returned by builds.list — one row per run. */
export interface BuildRunSummary {
  run_id: string;
  solution_name: string;
  state: BuildState | string;
  created_at: string;
  task_count: number;
}

export interface BuildCriticScore {
  phase: string;
  score: number;
  passed: boolean;
  iterations: number;
}

export interface BuildAgentResult {
  task_type: string;
  description: string;
  status: string;
  tier: string;
  step: number;
  wave: number;
  agent_role: string;
  acceptance_criteria: string[];
  error: string;
  files_changed: string[];
}

/** Full detail returned by builds.get / builds.start / builds.approve. */
export interface BuildRunDetail {
  run_id: string;
  solution_name: string;
  state: BuildState | string;
  state_description: string;
  created_at: string;
  updated_at: string;
  product_description: string;
  hitl_level: HitlLevel | string;
  hitl_gates: string[];
  detected_domains: string[];
  plan: Array<Record<string, unknown>>;
  task_count: number;
  critic_scores: BuildCriticScore[];
  critic_reports: Array<Record<string, unknown>>;
  agent_results: BuildAgentResult[];
  integration_result: Record<string, unknown> | null;
  phase_durations: Record<string, number>;
  error?: string;
}

export interface ApproveBuildParams {
  run_id: string;
  approved: boolean;
  feedback?: string;
}

// ── Onboarding wizard ─────────────────────────────────────────────────────

export interface OnboardingParams {
  description: string;
  solution_name: string;
  compliance_standards?: string[];
  integrations?: string[];
  parent_solution?: string;
}

export interface OnboardingResult {
  solution_name: string;
  path: string;
  status: "created" | "exists";
  files: Record<string, string>;
  suggested_routes: string[];
  message: string;
}
