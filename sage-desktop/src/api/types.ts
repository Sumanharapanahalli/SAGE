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

/** The desktop's audit signer. `provider` is always "desktop-operator" — never
 *  "oidc": physical access to the machine is the trust boundary, and the record
 *  must not overclaim (21 CFR Part 11 §11.50 yes, §11.100 no). */
export interface Operator {
  name: string;
  email: string;
  provider: string;
}

export type JobState = "queued" | "running" | "succeeded" | "failed";

/** Background execution of an approved implementation_plan / code_diff. */
export interface Job {
  job_id: string;
  kind: string;
  label: string;
  state: JobState;
  result: unknown | null;
  error: string | null;
}

/** The outcome of running an approved proposal's executor. Fast action types
 *  carry the result inline; the multi-minute ones return a job_id to poll. */
export interface ExecutionOutcome {
  state: JobState;
  job_id?: string;
  result?: unknown;
  error?: string;
}

/** An approve response: the proposal, plus what its execution actually did.
 *  Before this existed, approval flipped a status column and stopped. */
export interface ApprovedProposal extends Proposal {
  execution?: ExecutionOutcome;
}

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

export interface AgentPerformance {
  role_key: string;
  total_proposals: number;
  approved: number;
  rejected: number;
  approval_rate: number | null;
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
  | "in_progress"
  | "in_planning"
  | "github_pr";

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

/** Result of backlog.plan — a SAGE-scope request opens a GitHub issue (no
 * approval-queue proposal); a solution-scope request creates a real
 * ProposalStore proposal (action_type "implementation_plan"). */
export interface PlanResultGithub {
  request_id: string;
  status: "github_pr";
  github_issue_url: string;
  message: string;
}

export type PlanResult = PlanResultGithub | Proposal;

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

/** Payload of `unload_solution` — both fields are null (no solution active). */
export interface UnloadSolutionResult {
  name: null;
  path: null;
}

export type RemoveSolutionMode = "archive" | "delete";

export interface RemoveSolutionResult {
  name: string;
  mode: RemoveSolutionMode;
  path: string;
  /** Only present for mode "archive". */
  archived_to?: string;
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

// ── YAML authoring ────────────────────────────────────────────────────────

export type YamlFileName = "project" | "prompts" | "tasks";

export interface YamlReadResult {
  file: YamlFileName;
  solution: string;
  content: string;
  path: string;
}

export interface YamlWriteResult {
  file: YamlFileName;
  solution: string;
  path: string;
  bytes: number;
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

// ── Constitution ──────────────────────────────────────────────────────────

export interface ConstitutionPrinciple {
  id: string;
  text: string;
  weight: number;
}

export interface ConstitutionMeta {
  name: string;
  version: number;
  last_updated: string;
  updated_by: string;
}

export interface ConstitutionVoice {
  tone?: string;
  avoid?: string[];
}

export interface ConstitutionDecisions {
  auto_approve_categories?: string[];
  escalation_keywords?: string[];
}

export interface ConstitutionHistoryEntry {
  version: number;
  changed_by: string;
  timestamp: string;
}

export interface ConstitutionData {
  meta?: ConstitutionMeta;
  principles?: ConstitutionPrinciple[];
  constraints?: string[];
  voice?: ConstitutionVoice;
  decisions?: ConstitutionDecisions;
  knowledge?: Record<string, unknown>;
  _history?: ConstitutionHistoryEntry[];
}

export interface ConstitutionStats {
  is_empty: boolean;
  name: string;
  version: number;
  principle_count: number;
  constraint_count: number;
  non_negotiable_count: number;
  has_voice: boolean;
  has_decisions: boolean;
  has_knowledge: boolean;
  history_entries: number;
}

export interface ConstitutionState {
  data: ConstitutionData;
  stats: ConstitutionStats;
  preamble: string;
  history: ConstitutionHistoryEntry[];
  errors: string[];
}

export interface ConstitutionUpdateResult {
  stats: ConstitutionStats;
  preamble: string;
  version: number;
  path: string;
}

export interface CheckActionResult {
  allowed: boolean;
  violations: string[];
}

// ── Knowledge Browser ─────────────────────────────────────────────────────

export type KnowledgeBackend = "full" | "lite" | "minimal";

export interface KnowledgeEntry {
  id: string;
  text: string;
  metadata: Record<string, unknown>;
}

export interface KnowledgeListResult {
  entries: KnowledgeEntry[];
  total: number;
  limit: number;
  offset: number;
}

export interface KnowledgeSearchHit {
  text: string;
  id?: string;
  score?: number;
  metadata?: Record<string, unknown>;
}

export interface KnowledgeSearchResult {
  query: string;
  results: KnowledgeSearchHit[];
  count: number;
}

export interface KnowledgeStats {
  total: number;
  collection: string;
  backend: KnowledgeBackend | string;
  solution: string;
}

export interface KnowledgeAddResult {
  id: string;
  text: string;
  metadata: Record<string, unknown>;
}

export interface KnowledgeDeleteResult {
  id: string;
  deleted: boolean;
}

// ── Collective Intelligence (Phase 5a) ──────────────────────────────────

export interface CollectiveLearning {
  id: string;
  author_agent: string;
  author_solution: string;
  topic: string;
  title: string;
  content: string;
  tags: string[];
  confidence: number;
  validation_count: number;
  created_at: string;
  updated_at: string;
  source_task_id: string;
}

export interface HelpRequestResponse {
  responder_agent: string;
  responder_solution: string;
  content: string;
  created_at: string;
}

export interface HelpRequestClaim {
  agent: string;
  solution: string;
  claimed_at: string;
}

export type HelpRequestStatus = "open" | "claimed" | "closed";
export type HelpRequestUrgency = "low" | "medium" | "high" | "critical";

export interface HelpRequest {
  id: string;
  title: string;
  requester_agent: string;
  requester_solution: string;
  status: HelpRequestStatus;
  urgency: HelpRequestUrgency;
  required_expertise: string[];
  context: string;
  created_at: string;
  claimed_by: HelpRequestClaim | null;
  responses: HelpRequestResponse[];
  resolved_at: string | null;
}

export interface CollectiveListResult {
  entries: CollectiveLearning[];
  total: number;
  limit: number;
  offset: number;
}

export interface CollectiveGetResult {
  learning: CollectiveLearning | null;
}

export interface CollectiveSearchResult {
  query: string;
  results: CollectiveLearning[];
  count: number;
}

export interface CollectivePublishResult {
  id: string | null;
  gated: boolean;
  trace_id?: string;
}

export interface CollectiveValidateResult {
  learning: CollectiveLearning;
}

export interface CollectiveHelpListResult {
  entries: HelpRequest[];
  count: number;
}

export interface CollectiveHelpCreateResult {
  id: string;
}

export interface CollectiveHelpMutationResult {
  request: HelpRequest;
}

export interface CollectiveSyncResult {
  pulled: boolean;
  indexed: number;
}

export interface CollectiveStats {
  learning_count: number;
  help_request_count: number;
  help_requests_closed: number;
  topics: Record<string, number>;
  contributors: Record<string, number>;
  git_available: boolean;
  repo_path: string;
}

// ── Compliance ────────────────────────────────────────────────────────────

export interface ComplianceDomain {
  domain: string;
  standard: string;
  description: string;
  authority: string;
  risk_levels: string[];
  hil_required_for: string[];
}

export interface ComplianceDomainsResult {
  domains: ComplianceDomain[];
}

export interface ComplianceChecklistItem {
  id: string;
  type: "compliance_flag" | "required_task" | "evidence_artifact";
  level: string;
  description: string;
  clause: string;
  hil_required: boolean;
  status: string | null;
  evidence_ref: string | null;
  notes: string;
}

export interface ComplianceChecklist {
  domain: string;
  risk_level: string;
  standard: string;
  description: string;
  authority: string;
  hil_testing_required: boolean;
  total_items: number;
  flags: number;
  required_tasks: number;
  artifacts: number;
  items: ComplianceChecklistItem[];
}

export interface ComplianceGapResult {
  domain: string;
  risk_level: string;
  required_tasks: string[];
  completed_tasks: string[];
  missing_tasks: string[];
  hil_tasks_missing: string[];
  compliance_pct: number;
  compliant: boolean;
  blocking_gaps: string[];
}

// ── Costs (T1-004) ────────────────────────────────────────────────────────

export interface CostByModel {
  model: string;
  calls: number;
  cost: number;
}

export interface CostBySolution {
  solution: string;
  calls: number;
  cost: number;
}

export interface CostSummary {
  total_cost_usd: number;
  total_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  avg_cost_per_call: number;
  by_model: CostByModel[];
  by_solution: CostBySolution[];
  period_days: number;
  tenant: string | null;
  solution: string | null;
}

export interface CostDailyRow {
  date: string;
  calls: number;
  cost_usd: number;
}

export interface CostDailyResult {
  daily: CostDailyRow[];
  count: number;
  period_days: number;
}

export interface CostBudgetResult {
  saved: boolean;
  key: string;
  monthly_usd: number;
}

// ── Skills & Tools ───────────────────────────────────────────────────────

export type SkillVisibility = "public" | "private" | "disabled";

export interface Skill {
  name: string;
  version: string;
  visibility: SkillVisibility | string;
  roles: string[];
  runner: string;
  description: string;
  tools: string[];
  prompt: string;
  acceptance_criteria: string[];
  certifications: string[];
  engines: string[];
  tags: string[];
}

export interface SkillStats {
  total: number;
  active: number;
  public: number;
  private: number;
  disabled: number;
  roles_covered: number;
  runners_covered: number;
  loaded_dirs: string[];
}

export interface SkillsListResult {
  skills: Skill[];
  stats: SkillStats;
}

export interface SkillVisibilitySetResult {
  status: "updated";
  name: string;
  visibility: SkillVisibility | string;
}

export interface SkillsReloadResult {
  status: "reloaded";
  skills_loaded: number;
  stats: SkillStats;
}

export interface McpTool {
  name: string;
  description: string;
  server: string;
}

export interface McpToolsResult {
  tools: McpTool[];
  count: number;
}

// ── Workflows (LangGraph) ─────────────────────────────────────────────────
// Empty list / an "error"-shaped result are the graceful-degradation path
// when orchestration.engine != "langgraph" or the langgraph package isn't
// installed — see src/integrations/langgraph_runner.py.

export interface WorkflowSummary {
  name: string;
}

export interface WorkflowListResult {
  workflows: WorkflowSummary[];
  count: number;
}

export type WorkflowRunStatus = "completed" | "awaiting_approval" | "error";

export interface WorkflowRunResult {
  run_id: string;
  status: WorkflowRunStatus;
  workflow_name: string;
  result: Record<string, unknown>;
}

export interface WorkflowStatusResult {
  run_id: string;
  workflow_name: string;
  status: WorkflowRunStatus;
}

// ── Organization ──────────────────────────────────────────────────────────
// org.yaml is a SAGE_ROOT-level file (not per-solution) — identity fields
// shape every solution's onboarding and agent context. This pass covers
// viewing the enriched org state (incl. read-only cross-team routes) and
// editing identity fields; channel/solution/route CRUD is a follow-up.

export interface OrgKnowledgeChannel {
  producers?: string[];
  consumers?: string[];
}

export interface OrgRoute {
  source: string;
  target: string;
}

/** The `org:` section of org.yaml, as read back from disk. Only
 * name/mission/vision/core_values are editable from this pass — other
 * keys (root_solution, knowledge_channels) are read-only passthrough. */
export interface OrgIdentity {
  name?: string;
  mission?: string;
  vision?: string;
  core_values?: string[];
  root_solution?: string;
  knowledge_channels?: Record<string, OrgKnowledgeChannel>;
  [key: string]: unknown;
}

export interface OrgData {
  org: OrgIdentity;
  routes: OrgRoute[];
}

export interface OrgUpdateResult {
  status: "saved";
  org: OrgIdentity;
}

export interface OrgReloadResult {
  status: "reloaded";
}

// ── Monitor ───────────────────────────────────────────────────────────────
// Mirrors GET /monitor/status and GET /scheduler/status from
// src/interface/api.py. Both subsystems are legitimately-often-off in the
// desktop sidecar; the handler degrades gracefully instead of raising, so
// these shapes are always well-formed — never an error response.

/** Shape of MonitorAgent.get_status() (src/agents/monitor.py). On a
 * construction/call failure the sidecar handler degrades to just
 * {running: false, error}, so every field but `running` is optional. */
export interface MonitorStatus {
  running: boolean;
  active_threads?: string[];
  thread_count?: number;
  seen_messages?: number;
  seen_issues?: number;
  teams_configured?: boolean;
  metabase_configured?: boolean;
  gitlab_configured?: boolean;
  error?: string;
}

/** Shape of TaskScheduler.status() (src/core/task_scheduler.py). On a
 * construction/call failure the sidecar handler degrades to exactly
 * {running: false, error}, matching the web API's /scheduler/status. */
export interface SchedulerStatus {
  running: boolean;
  scheduled_count?: number;
  next_check_in_seconds?: number;
  error?: string;
}

// ── Goals (OKR tracking) ─────────────────────────────────────────────────
// Scope note: the web API's `_get_goals_store()` resolves `goals.db` next
// to the shared audit_logger db path (framework-shared, not per-solution).
// The desktop sidecar deliberately diverges — `goals.db` lives inside THIS
// solution's own `.sage/` directory, matching proposals.db/audit_log.db/
// queue.db for genuine per-solution isolation. See
// `sidecar/handlers/goals.py`'s module docstring. The desktop is a
// single-operator interface, so `user_id` defaults to "desktop-operator"
// sidecar-side when omitted (mirrors approvals.py defaulting `decided_by`
// to "human").

export type GoalStatus = "on_track" | "at_risk" | "off_track" | "done";

export interface GoalKeyResult {
  text: string;
  done?: boolean;
  [key: string]: unknown;
}

export interface Goal {
  id: string;
  user_id: string;
  solution: string;
  title: string;
  quarter: string;
  status: GoalStatus | string;
  owner: string;
  key_results: GoalKeyResult[];
  created_at: string;
  updated_at: string;
}

export interface GoalCreateParams {
  title: string;
  quarter: string;
  user_id?: string;
  solution?: string;
  status?: GoalStatus | string;
  owner?: string;
  key_results?: GoalKeyResult[];
}

export interface GoalUpdateParams {
  goal_id: string;
  title?: string;
  quarter?: string;
  status?: GoalStatus | string;
  owner?: string;
  key_results?: GoalKeyResult[];
}

export interface GoalListParams {
  user_id?: string;
  solution?: string;
  quarter?: string;
}

export interface GoalDeleteResult {
  deleted: boolean;
}

// ── Eval (Agent Gym) ─────────────────────────────────────────────────────
// Scope note: eval_runs.db lives inside this solution's own `.sage/`
// directory (per-solution isolation), not the framework-shared
// data/eval_results.db the web API's global eval_runner singleton uses —
// same pattern as queue.db (Phase 5l) / goals.db (Phase 5m). See
// `sidecar/handlers/eval.py`'s module docstring.

export interface EvalSuiteList {
  suites: string[];
  count: number;
}

export interface EvalCaseResult {
  case_id: string;
  role?: string;
  input?: string;
  response?: string;
  score: number;
  passed: boolean;
  details?: unknown;
  error?: string;
}

export interface EvalSuiteResult {
  suite: string;
  name?: string;
  total_cases: number;
  passed_cases: number;
  mean_score: number;
  cases?: EvalCaseResult[];
  error?: string;
}

export interface EvalRunResult {
  run_id: string;
  suite: string;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  mean_score: number;
  results: EvalSuiteResult[];
}

export interface EvalHistoryEntry {
  run_id: string;
  suite: string;
  solution?: string;
  started_at: string;
  total_cases: number;
  passed_cases: number;
  mean_score: number;
}

export interface EvalHistoryResult {
  history: EvalHistoryEntry[];
  count: number;
}

// ── HIL (Hardware-in-the-Loop) ──────────────────────────────────────────
// Scope note: HILRunner.flash_firmware() is not ported — it has no
// endpoint in the web API either. See sidecar/handlers/hil.py's module
// docstring. Connect is always an explicit operator action (never
// auto-connects on page load) since it can spawn subprocesses
// (JLinkExe/openocd) or open a real serial/CAN handle.

export type HILTransportName = "mock" | "serial" | "jlink" | "can" | "openocd";

export interface HILStatus {
  connected: boolean;
  transport: string;
  session_id: string | null;
  tests_run: number;
  passed?: number;
  failed?: number;
  blocked?: number;
  message?: string;
  error?: string;
}

export interface HILConnectResult {
  transport: string;
  connected: boolean;
  session_id: string;
  message: string;
}

export interface HILTestCaseInput {
  id: string;
  name: string;
  requirement_id: string;
  description?: string;
  procedure?: string[];
  expected_result?: string;
  transport?: string;
  timeout_seconds?: number;
}

export interface HILTestResultOut {
  test_id: string;
  test_name: string;
  requirement_id: string;
  verdict: "PASS" | "FAIL" | "ERROR" | "SKIP" | "BLOCKED";
  actual_result: string;
  duration_seconds: number;
  timestamp: string;
  evidence?: Record<string, unknown>;
  deviation_notes?: string;
}

export interface HILRunSuiteResult {
  session_id: string;
  transport: string;
  total: number;
  passed: number;
  failed: number;
  errors: number;
  skipped: number;
  blocked: number;
  pass_rate: number;
  results: HILTestResultOut[];
}

export interface HILReportResult {
  report_type: string;
  standard: string;
  standard_full_name: string;
  generated_at: string;
  session_id: string;
  transport: string;
  evidence_sections: string[];
  pass_criteria: string;
  summary: {
    total_tests: number;
    passed: number;
    failed: number;
    blocked: number;
    pass_rate: number;
    overall_status: "PASS" | "FAIL";
  };
  traceability: Array<{
    requirement_id: string;
    test_id: string;
    test_name: string;
    verdict: string;
    timestamp: string;
    duration_seconds: number;
    evidence_captured: boolean;
  }>;
  deviations: Array<{ test_id: string; notes: string }>;
  failed_tests: Array<{
    test_id: string;
    test_name: string;
    requirement_id: string;
    actual_result: string;
    verdict: string;
  }>;
}
