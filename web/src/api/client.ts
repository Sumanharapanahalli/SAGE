const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.statusText}`)
  return res.json()
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    const apiError = new Error(
      (data as Record<string, unknown>).detail as string
      || (data as Record<string, unknown>).message as string
      || `POST ${path} failed: ${res.statusText}`
    ) as Error & { body: unknown }
    apiError.body = data
    throw apiError
  }
  return res.json()
}

async function patch<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`PATCH ${path} failed: ${res.statusText}`)
  return res.json()
}

async function put<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`PUT ${path} failed: ${res.statusText}`)
  return res.json()
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`DELETE ${path} failed: ${res.statusText}`)
  if (res.status === 204) return undefined as unknown as T
  return res.json()
}

// Health
export const fetchHealth = () => get<HealthResponse>('/health')

// LLM heartbeat
export const fetchLLMHealth = () =>
  get<{ connected: boolean; provider: string; latency_ms: number; detail: string }>('/health/llm')

// Analyze
export const analyzeLog = (log_entry: string) =>
  post<AnalysisResponse>('/analyze', { log_entry })

// Approve / Reject
export const approveProposal = (trace_id: string) =>
  post<ActionResponse>(`/approve/${trace_id}`)

export const rejectProposal = (trace_id: string, feedback: string) =>
  post<ActionResponse>(`/reject/${trace_id}`, { feedback })

// Audit log
export const fetchAudit = (limit = 50, offset = 0) =>
  get<AuditResponse>(`/audit?limit=${limit}&offset=${offset}`)

// MR operations
export const createMR = (project_id: number, issue_iid: number, source_branch?: string) =>
  post<MRCreateResponse>('/mr/create', { project_id, issue_iid, source_branch })

export const reviewMR = (project_id: number, mr_iid: number) =>
  post<MRReviewResponse>('/mr/review', { project_id, mr_iid })

export const fetchOpenMRs = (project_id: number) =>
  get<OpenMRsResponse>(`/mr/open?project_id=${project_id}`)

export const fetchPipelineStatus = (project_id: number, mr_iid: number) =>
  get<PipelineResponse>(`/mr/pipeline?project_id=${project_id}&mr_iid=${mr_iid}`)

// Monitor
export const fetchMonitorStatus = () => get<MonitorStatus>('/monitor/status')

// Scheduler
export const fetchSchedulerStatus = () =>
  get<{ running: boolean; scheduled_count: number }>('/scheduler/status')

// Feature requests — module self-improvement loop
export const submitFeatureRequest = (body: import('../types/module').FeatureRequestPayload) =>
  post<{ id: string; status: string; message: string }>('/feedback/feature-request', body)

export const fetchFeatureRequests = (module_id?: string, status?: string, scope?: string) => {
  const params = new URLSearchParams()
  if (module_id) params.set('module_id', module_id)
  if (status)    params.set('status', status)
  if (scope)     params.set('scope', scope)
  const qs = params.toString()
  return get<{ requests: import('../types/module').FeatureRequest[]; count: number }>(
    `/feedback/feature-requests${qs ? `?${qs}` : ''}`
  )
}

export const generatePlanForRequest = (req_id: string) =>
  post<{ request_id: string; status: string; plan?: unknown; github_issue_url?: string; message?: string }>(
    `/feedback/feature-requests/${req_id}/plan`
  )

export const updateFeatureRequest = (
  req_id: string,
  body: { action: string; reviewer_note?: string }
) =>
  patch<{ id: string; status: string; reviewer_note: string }>(
    `/feedback/feature-requests/${req_id}`,
    body
  )

// YAML editor — read / write solution config files
export const fetchYamlFile = (file: 'project' | 'prompts' | 'tasks') =>
  get<{ file: string; solution: string; content: string }>(`/config/yaml/${file}`)

export const saveYamlFile = (file: 'project' | 'prompts' | 'tasks', content: string) =>
  fetch(`/api/config/yaml/${file}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  }).then(async res => {
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail ?? 'Save failed')
    }
    return res.json() as Promise<{ saved: boolean; file: string; solution: string }>
  })

// SKILL.md editor — read / write single-file solution config
export const fetchSkillMd = () =>
  get<{ solution: string; content: string }>('/config/skill')

export const saveSkillMd = (content: string) =>
  fetch('/api/config/skill', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  }).then(async res => {
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail ?? 'Save failed')
    }
    return res.json() as Promise<{ saved: boolean; solution: string; message: string }>
  })

// Universal Agent roles + run
export const fetchAgentRoles = () =>
  get<{ roles: { id: string; name: string; description: string; icon: string }[] }>('/agent/roles')

export const runAgent = (role_id: string, task: string, context?: string) =>
  post<{
    trace_id: string; role_id: string; role_name: string; icon: string
    task: string; summary: string; analysis: string
    recommendations: string[]; next_steps: string[]
    severity: string; confidence: string; status: string
  }>('/agent/run', { role_id, task, context: context ?? '' })

export const hireAgent = (params: {
  role_id: string; name: string; description: string
  icon: string; system_prompt: string; task_types: string[]
}) => post<ProposalResponse>('/agents/hire', params)

export interface AgentRoleConfig {
  role_key: string
  name: string
  description: string
  system_prompt: string
  task_types: Array<{ name: string; description: string }>
  output_schema?: Record<string, unknown>
  eval_case?: { input: string; expected_keywords: string[] }
}

export const analyzeJd = (params: { jd_text: string; solution_context?: string }) =>
  post<AgentRoleConfig>('/agents/analyze-jd', params)

// Org Structure Templates — onboarding chooser
export interface OrgTemplateRole {
  key: string
  name: string
  description: string
}

export interface OrgTemplate {
  id: string
  name: string
  description: string
  role_count: number
  compliance_standards: string[]
  icon: string
  roles: OrgTemplateRole[]
}

export async function fetchOrgTemplates(): Promise<OrgTemplate[]> {
  const data = await get<{ templates: OrgTemplate[] }>('/onboarding/org-templates')
  return data.templates ?? []
}

// Conversational Onboarding
export interface OnboardingMessage { role: 'assistant' | 'user'; content: string; ts: number }
export interface OnboardingInfo {
  description: string; solution_name: string
  compliance_standards: string[]; integrations: string[]; team_context: string
}
export interface OnboardingSession {
  session_id: string; state: string
  messages: OnboardingMessage[]; info: OnboardingInfo
  proposal_trace_id?: string; solution_name_final?: string
}
export const startOnboardingSession = () =>
  post<OnboardingSession>('/onboarding/session')
export const sendOnboardingMessage = (session_id: string, message: string) =>
  post<{ reply: string; state: string; info: OnboardingInfo; session_id: string }>(
    `/onboarding/session/${session_id}/message`, { message }
  )
export const generateOnboardingSolution = (session_id: string) =>
  post<{ trace_id: string; description: string; solution_name: string; state: string }>(
    `/onboarding/session/${session_id}/generate`
  )

// Set active modules for current solution (runtime override) — returns proposal
export const setActiveModules = (modules: string[]) =>
  post<ProposalResponse>('/config/modules', { modules })

// Switch active solution at runtime — returns proposal
export const switchProject = (project: string) =>
  post<ProposalResponse>('/config/switch', { project })

// Pending approvals — for the Dashboard panel
export const fetchPendingProposals = () =>
  get<{ proposals: Proposal[]; count: number }>('/proposals/pending')

// Single proposal by trace_id — for plan detail view in Improvements
export const fetchProposal = (trace_id: string) =>
  get<Proposal>(`/proposals/${trace_id}`)

export const approveBatchProposals = (trace_ids: string[], decided_by: string, feedback = '') =>
  post<{ results: Array<{ trace_id: string; status: string; reason?: string; result?: unknown }>; count: number }>(
    '/proposals/approve-batch', { trace_ids, decided_by, feedback }
  )

export const fetchApprovalRoles = () =>
  get<{ approval_roles: Record<string, string | null>; approvers: Record<string, string[]> }>(
    '/config/approval-roles'
  )

// ---------------------------------------------------------------------------
// CDS Compliance
// ---------------------------------------------------------------------------

export const classifyCDSFunction = (data: {
  function_description: string; input_types: string[]; output_type: string;
  intended_user: string; urgency: string; data_sources: { name: string; type: string }[];
}) => post<Record<string, unknown>>('/cds/classify', data)

export const classifyCDSInputs = (input_types: string[]) =>
  post<Array<{ input_type: string; data_category: string; criterion_1_impact: string }>>('/cds/classify-inputs', { input_types })

export const validateCDSSources = (sources: { name: string; type: string }[]) =>
  post<Record<string, unknown>>('/cds/validate-sources', { sources })

export const classifyCDSOutput = (output_type: string) =>
  post<Record<string, unknown>>('/cds/classify-output', { output_type })

export const generateCDSTransparencyReport = (data: {
  function_description: string; inputs_used: string[];
  data_sources: { name: string; type: string }[];
  algorithm_description: string; known_limitations: string[];
}) => post<Record<string, unknown>>('/cds/transparency-report', data)

export const generateCDSLabeling = (data: {
  product_name: string; intended_use: string; intended_users: string[];
  target_population: string; algorithm_summary: string;
  data_sources: { name: string; type: string }[];
  validation_summary: string; known_limitations: string[];
}) => post<Record<string, unknown>>('/cds/labeling', data)

export const generateCDSCompliancePackage = (data: {
  product_name: string; function_description: string; input_types: string[];
  output_type: string; intended_user: string; urgency: string;
  data_sources: { name: string; type: string }[];
  algorithm_description: string; known_limitations: string[];
  target_population: string; validation_summary: string;
}) => post<Record<string, unknown>>('/cds/compliance-package', data)

// ---------------------------------------------------------------------------
// Regulatory Compliance (Multi-Standard)
// ---------------------------------------------------------------------------

export const fetchRegulatoryStandards = () =>
  get<Array<Record<string, unknown>>>('/regulatory/standards')

export const assessRegulatoryCompliance = (data: {
  product: Record<string, unknown>; standard_ids?: string[];
}) => post<Record<string, unknown>>('/regulatory/assess', data)

export const generateRegulatoryRoadmap = (product: Record<string, unknown>) =>
  post<Record<string, unknown>>('/regulatory/roadmap', product)

export const generateFullRegulatoryReport = (product: Record<string, unknown>) =>
  post<Record<string, unknown>>('/regulatory/full-report', product)

export const fetchRegulatoryChecklist = (standardId: string) =>
  get<Record<string, unknown>>(`/regulatory/checklist/${standardId}`)

// Approve a proposal (analysis or action)
export const approveProposalFull = (trace_id: string, decided_by = 'human', feedback = '') =>
  post<{ status: string; trace_id: string; action_type?: string; result?: unknown }>(
    `/approve/${trace_id}`, { decided_by, feedback }
  )

// Reject a proposal (analysis or action) with full decided_by + feedback
export const rejectProposalFull = (trace_id: string, _decided_by = 'human', feedback = '') =>
  post<{ status: string; trace_id: string; feedback_recorded: boolean; message: string }>(
    `/reject/${trace_id}`, { feedback }
  )

export const undoProposal = (trace_id: string) =>
  post<ActionResponse>(`/proposals/${trace_id}/undo`)

// Live log stream — returns an EventSource URL (no fetch wrapper needed)
export const logsStreamUrl = () => '/api/logs/stream'

// Composio integrations
export interface ComposioConnectedApp {
  app: string
  status: string
  connected_account_id: string
}
export interface ComposioTool {
  name: string
  description: string
}
export const fetchComposioStatus = () =>
  get<{ available: boolean; api_key_set: boolean; connected_apps: ComposioConnectedApp[]; count: number }>(
    '/integrations/composio/status'
  )
export const fetchComposioTools = () =>
  get<{ available: boolean; apps: string[]; tools: ComposioTool[]; count: number; message?: string }>(
    '/integrations/composio/tools'
  )
export const connectComposioApp = (app: string, redirect_url = '') =>
  post<{ status: string; trace_id: string; app: string; connection_url: string; message: string }>(
    '/integrations/composio/connect', { app, redirect_url }
  )

// Cost Tracking (T1-004)
export const fetchCostSummary = (params?: { tenant?: string; solution?: string; period_days?: number }) => {
  const qs = new URLSearchParams()
  if (params?.tenant)      qs.set('tenant', params.tenant)
  if (params?.solution)    qs.set('solution', params.solution)
  if (params?.period_days) qs.set('period_days', String(params.period_days))
  const q = qs.toString()
  return get<import('../types/module').CostSummary>(`/costs/summary${q ? `?${q}` : ''}`)
}

export const fetchCostDaily = (params?: { tenant?: string; solution?: string; period_days?: number }) => {
  const qs = new URLSearchParams()
  if (params?.tenant)      qs.set('tenant', params.tenant)
  if (params?.solution)    qs.set('solution', params.solution)
  if (params?.period_days) qs.set('period_days', String(params.period_days))
  const q = qs.toString()
  return get<{ daily: import('../types/module').DailyCost[]; count: number; period_days: number }>(
    `/costs/daily${q ? `?${q}` : ''}`
  )
}

export const setCostBudget = (body: { tenant?: string; solution?: string; monthly_usd: number }) =>
  post<{ saved: boolean; key: string; monthly_usd: number; message: string }>('/costs/budget', body)

// Workflow Diagrams
export interface WorkflowDiagram {
  solution: string
  workflow_name: string
  mermaid_diagram: string
  node_count: number
  description: string
}

export const fetchWorkflowDiagrams = () =>
  get<{ workflows: WorkflowDiagram[]; count: number; error?: string }>('/workflows')

export const fetchWorkflowDiagram = (solution: string, workflowName: string) =>
  get<WorkflowDiagram>(`/workflows/${solution}/${workflowName}`)

// Active Agents — live panel on Dashboard
export interface ActiveAgentEntry {
  task_id: string
  task_type: string
  status: string
  started_at: string | null
  source: string
}

export const fetchActiveAgents = () =>
  get<{ agents: ActiveAgentEntry[]; count: number }>('/agents/active')

// Repo Map
export const fetchRepoMap = (max_files = 50) =>
  get<{ map: string }>(`/repo/map?max_files=${max_files}`)

// Knowledge Sync
export const triggerKnowledgeSync = (directory = '') =>
  post<{ status: string; chunks_imported: number }>('/knowledge/sync', { directory })

// OpenShell Sandbox
export const fetchSandboxStatus = () =>
  get<{ available: boolean; version?: string; install?: string }>('/sandbox/status')

// Task Queue
export const fetchTaskSubtasks = (task_id: string) =>
  get<{ task_id: string; subtasks: unknown[] }>(`/tasks/${task_id}/subtasks`)

export const fetchQueueTasks = (params?: { status?: string; source?: string }) =>
  get<import('../types/module').QueueTask[]>(
    `/queue/tasks${params && Object.keys(params).length > 0 ? '?' + new URLSearchParams(params as Record<string, string>) : ''}`
  )

// Solution theme (all fields optional — missing fields fall back to CSS :root defaults)
export interface SageTheme {
  sidebar_bg?: string;          sidebar_text?: string
  sidebar_active_bg?: string;   sidebar_active_text?: string
  sidebar_hover_bg?: string;    sidebar_accent?: string
  accent?: string;              accent_hover?: string
  accent_light?: string;        accent_text?: string
  badge_bg?: string;            badge_text?: string
}

// Project config
export const fetchProjectConfig = () =>
  get<{
    project: string
    name: string
    version: string
    domain: string
    description: string
    active_modules: string[]
    compliance_standards: string[]
    task_types: string[]
    task_descriptions: Record<string, string>
    ui_labels: Record<string, unknown>
    dashboard?: Record<string, unknown>
    theme?: SageTheme
  }>('/config/project')

export const fetchProjects = () =>
  get<{ projects: Array<{ id: string; name: string; domain: string; version: string; description: string; theme?: Record<string, string> }>; active: string }>(
    '/config/projects'
  )

// --- Types ---

export interface Proposal {
  trace_id:      string
  created_at:    string
  action_type:   string
  risk_class:    'INFORMATIONAL' | 'EPHEMERAL' | 'STATEFUL' | 'EXTERNAL' | 'DESTRUCTIVE'
  reversible:    boolean
  proposed_by:   string
  description:   string
  payload:       Record<string, unknown>
  status:        'pending' | 'approved' | 'rejected' | 'expired'
  decided_by:    string | null
  decided_at:    string | null
  feedback:      string | null
  expires_at:    string | null
  required_role: string | null
}

export interface ProposalResponse {
  status:      string   // "pending_approval"
  trace_id:    string
  description: string
  [key: string]: unknown
}

export interface HealthResponse {
  status: string
  service: string
  version: string
  timestamp: string
  llm_provider: string
  environment: {
    gitlab_configured: boolean
    teams_configured: boolean
    metabase_configured: boolean
    spira_configured: boolean
  }
}

export interface AnalysisResponse {
  trace_id: string
  severity: string
  root_cause_hypothesis: string
  recommended_action: string
  confidence?: string
  [key: string]: unknown
}

export interface ActionResponse {
  status: string
  trace_id: string
  message: string
}

export interface AuditEntry {
  id: string
  timestamp: string
  actor: string
  action_type: string
  input_context: string
  output_content: string
  metadata: string
  verification_signature: string | null
}

export interface AuditResponse {
  entries: AuditEntry[]
  count: number
  total: number
  limit: number
  offset: number
}

export interface MRCreateResponse {
  mr_iid: number
  mr_url: string
  mr_title: string
  source_branch: string
  target_branch: string
  issue_iid: number
  trace_id: string
  error?: string
}

export interface MRReviewResponse {
  summary: string
  issues: string[]
  suggestions: string[]
  approved: boolean
  trace_id: string
  mr_iid: number
  mr_title: string
  error?: string
}

export interface MRItem {
  iid: number
  title: string
  author: string
  source_branch: string
  target_branch: string
  created_at: string
  web_url: string
  labels: string[]
  pipeline_status: string
}

export interface OpenMRsResponse {
  merge_requests: MRItem[]
  count: number
  project_id: number
}

export interface PipelineResponse {
  mr_iid: number
  pipeline_id: number
  status: string
  created_at: string
  finished_at: string
  duration: number
  web_url: string
  stages: Record<string, { name: string; status: string; duration: number; web_url: string }[]>
}

export interface MonitorStatus {
  running: boolean
  active_threads: string[]
  thread_count: number
  seen_messages: number
  seen_issues: number
  teams_configured: boolean
  metabase_configured: boolean
  gitlab_configured: boolean
}

// Issues — mapped from feature requests
export interface Issue {
  id: string
  title: string
  description: string
  status: 'open' | 'in_progress' | 'done' | 'cancelled'
  priority: 'urgent' | 'high' | 'medium' | 'low'
  scope: 'solution' | 'sage'
  created_at: string
  solution_name?: string
  proposed_solution?: string
}

export async function fetchIssues(): Promise<Issue[]> {
  const data = await get<{ requests: import('../types/module').FeatureRequest[]; count: number }>(
    '/feedback/feature-requests'
  )
  return (data.requests ?? []).map(r => {
    const statusMap: Record<string, Issue['status']> = {
      pending:     'open',
      approved:    'open',
      in_planning: 'in_progress',
      in_progress: 'in_progress',
      completed:   'done',
      rejected:    'cancelled',
    }
    const priorityMap: Record<string, Issue['priority']> = {
      critical: 'urgent',
      high:     'high',
      medium:   'medium',
      low:      'low',
    }
    return {
      id:                r.id,
      title:             r.title,
      description:       r.description,
      status:            statusMap[r.status] ?? 'open',
      priority:          priorityMap[r.priority] ?? 'medium',
      scope:             r.scope,
      created_at:        r.created_at,
      solution_name:     r.module_name,
      proposed_solution: r.reviewer_note,
    }
  })
}

// Activity feed — maps audit log entries
export interface AuditEvent {
  id: string
  trace_id: string
  event_type: string
  agent: string
  description: string
  metadata: Record<string, unknown>
  created_at: string
}

export async function fetchAuditEvents(limit = 50, offset = 0): Promise<AuditEvent[]> {
  const data = await get<AuditResponse>(`/audit?limit=${limit}&offset=${offset}`)
  return (data.entries ?? []).map(e => ({
    id:          e.id,
    trace_id:    e.verification_signature ?? e.id,
    event_type:  e.action_type,
    agent:       e.actor,
    description: e.output_content ?? e.action_type,
    metadata:    (() => { try { return JSON.parse(e.metadata ?? '{}') } catch { return {} } })(),
    created_at:  e.timestamp,
  }))
}

// Agent status — for OrgChart page
export interface AgentStatus {
  role: string
  status: 'active' | 'idle' | 'error'
  last_task?: string
  task_count_today?: number
}

export async function fetchAgentStatuses(): Promise<AgentStatus[]> {
  try {
    return await get<AgentStatus[]>('/agents/status')
  } catch {
    // Fall back to static list of known SAGE roles
    return [
      { role: 'Analyst',   status: 'idle', last_task: undefined, task_count_today: 0 },
      { role: 'Developer', status: 'idle', last_task: undefined, task_count_today: 0 },
      { role: 'Monitor',   status: 'idle', last_task: undefined, task_count_today: 0 },
      { role: 'Planner',   status: 'idle', last_task: undefined, task_count_today: 0 },
      { role: 'Universal', status: 'idle', last_task: undefined, task_count_today: 0 },
    ]
  }
}

// OrgChart node — used by legacy OrgChart rendering (falls back gracefully)
export interface OrgChartNode {
  role_id: string
  name: string
  icon: string
  department: string
  domain_type?: string
  children: OrgChartNode[]
}

export async function getOrgChart(): Promise<{ root_roles: OrgChartNode[]; total: number }> {
  try {
    return await get<{ root_roles: OrgChartNode[]; total: number }>('/org-chart')
  } catch {
    return { root_roles: [], total: 0 }
  }
}

// Org Graph — solution hierarchy, knowledge channels, task routing
export interface OrgChannel {
  producers: string[];
  consumers: string[];
}

export interface OrgRoute {
  source: string;
  target: string;
}

export interface OrgData {
  org?: {
    name?: string;
    mission?: string;
    vision?: string;
    core_values?: string[];
    solutions?: string[];
    root_solution?: string;
    knowledge_channels?: Record<string, OrgChannel>;
  };
  routes?: OrgRoute[];
}

export async function fetchOrg(): Promise<OrgData> {
  const res = await fetch(`${BASE}/org`);
  if (!res.ok) throw new Error("Failed to fetch org");
  return res.json();
}

export async function reloadOrg(): Promise<{ status: string }> {
  const res = await fetch(`${BASE}/org/reload`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to reload org");
  return res.json();
}

export interface OrgUpdateRequest {
  name?: string
  mission?: string
  vision?: string
  core_values?: string[]
}

export interface OrgUpdateResponse {
  status: string
  org: {
    name?: string
    mission?: string
    vision?: string
    core_values?: string[]
  }
}

export const saveOrg = (req: OrgUpdateRequest) =>
  put<OrgUpdateResponse>('/org', req)

// Dev users
export const fetchDevUsers = () =>
  get<{ users: import('./auth').DevUser[] }>('/config/dev-users')

// Chat — contextual LLM conversation
export interface ChatRequest {
  message: string
  user_id: string
  session_id: string
  page_context?: string
  solution: string
}

export interface ChatResponse {
  response_type: 'answer' | 'action'
  reply?: string
  action?: string
  params?: Record<string, unknown>
  confirmation_prompt?: string
  session_id: string
  message_id: string
}

export const postChat = (req: {
  message: string; user_id: string; session_id: string
  page_context?: string; solution: string
}) => post<ChatResponse>('/chat', req)

export interface ChatExecuteRequest {
  action: string
  params: Record<string, unknown>
  user_id: string
  session_id: string
  solution: string
}

export interface ChatExecuteResponse {
  status: 'success' | 'error'
  message: string
  result: Record<string, unknown>
}

export const executeChat = (req: ChatExecuteRequest) =>
  post<ChatExecuteResponse>('/chat/execute', req)

export const clearChatHistory = (user_id: string, solution: string) => {
  const params = new URLSearchParams({ user_id, solution })
  return fetch(`${BASE}/chat/history?${params}`, { method: 'DELETE' }).then(r => r.json())
}

// Onboarding — scan folder, refine, save
export interface ScanFolderRequest {
  folder_path: string
  intent: string
  solution_name: string
}

export interface GeneratedFiles {
  'project.yaml': string
  'prompts.yaml': string
  'tasks.yaml': string
}

export interface ScanSummary {
  name: string
  description: string
  task_types: Array<{ name: string; description: string }>
  compliance_standards: string[]
  integrations: string[]
}

export interface ScanFolderResponse {
  solution_name: string
  files: GeneratedFiles
  summary: ScanSummary
}

export interface RefineRequest {
  solution_name: string
  current_files: GeneratedFiles
  feedback: string
}

export interface SaveSolutionRequest {
  solution_name: string
  files: GeneratedFiles
}

export const scanFolder = (req: ScanFolderRequest) =>
  post<ScanFolderResponse>('/onboarding/scan-folder', req)

export const refineGeneration = (req: RefineRequest) =>
  post<ScanFolderResponse>('/onboarding/refine', req)

export const saveSolution = (req: SaveSolutionRequest) =>
  post<{ status: string; solution_name: string }>('/onboarding/save-solution', req)

// Build Orchestrator — 0→1→N pipeline
export interface BuildCriticScore {
  phase: string
  score: number
  passed: boolean
  iterations: number
}

export interface BuildAgentResult {
  task_type: string
  description: string
  status: string
  tier: string
  step: number
}

export interface BuildStatus {
  run_id: string
  solution_name: string
  state: string
  state_description: string
  created_at: string
  updated_at: string
  product_description: string
  hitl_level: string
  hitl_gates: string[]
  plan: Array<{
    step: number; task_type: string; description: string
    payload: Record<string, unknown>
    acceptance_criteria?: string[]
    depends_on?: number[]
    agent_role?: string
  }>
  task_count: number
  critic_scores: BuildCriticScore[]
  critic_reports: Array<{ phase: string; result: Record<string, unknown> }>
  agent_results: (BuildAgentResult & {
    wave?: number; agent_role?: string; acceptance_criteria?: string[]
  })[]
  integration_result: Record<string, unknown> | null
  error: string | null
}

export interface BuildRunSummary {
  run_id: string
  solution_name: string
  state: string
  created_at: string
  task_count: number
}

export const startBuild = (params: {
  product_description: string
  solution_name?: string
  repo_url?: string
  workspace_dir?: string
  critic_threshold?: number
  hitl_level?: 'minimal' | 'standard' | 'strict'
}) => post<BuildStatus>('/build/start', params)

export const fetchBuildStatus = (runId: string) =>
  get<BuildStatus>(`/build/status/${runId}`)

export const approveBuild = (runId: string, approved = true, feedback = '') =>
  post<BuildStatus>(`/build/approve/${runId}`, { approved, feedback })

export const fetchBuildRuns = () =>
  get<{ runs: BuildRunSummary[]; count: number }>('/build/runs')

// Agent roles for "Hire an Agent"
export interface AgentRole {
  role: string
  title: string
  description: string
  team: string
  skills: string[]
  tools: string[]
  mcp_server: string | null
  mcp_capabilities: string[]
  hire_when: string
}

export const fetchBuildRoles = () =>
  get<{ roles: AgentRole[]; count: number }>('/build/roles')

// Solution branding
export interface BrandingPayload {
  display_name?: string
  icon_name?:    string
  accent?:       string
  sidebar_bg?:   string
  sidebar_text?: string
  badge_bg?:     string
  badge_text?:   string
}
export const patchProjectTheme = (payload: BrandingPayload) =>
  patch<{ status: string; solution: string }>('/config/project/theme', payload)

// Product Owner - Requirements Gathering
export interface ProductOwnerQuestion {
  question: string
  topic: string
  importance: 'high' | 'medium' | 'low'
  follow_up_needed?: boolean
}

export interface ProductOwnerPersona {
  name: string
  description: string
  goals: string[]
  pain_points: string[]
  technical_comfort: 'low' | 'medium' | 'high'
}

export interface ProductOwnerUserStory {
  id: string
  title: string
  description: string
  persona: string
  acceptance_criteria: string[]
  priority: 'Must Have' | 'Should Have' | 'Could Have' | 'Won\'t Have'
  story_points: number
  business_value: 'high' | 'medium' | 'low'
  dependencies: string[]
}

export interface ProductOwnerBacklog {
  product_name: string
  vision: string
  target_audience: string
  success_metrics: string[]
  personas: ProductOwnerPersona[]
  user_stories: ProductOwnerUserStory[]
  technical_constraints: string[]
  business_constraints: string[]
  created_at: string
  po_notes: string
}

export interface RequirementsGatheringRequest {
  customer_input: string
  follow_up_qa?: Array<{
    question: string
    answer: string
    topic: string
  }>
}

export interface RequirementsGatheringResponse {
  status: 'needs_clarification' | 'complete' | 'error'
  questions?: ProductOwnerQuestion[]
  analysis?: any
  backlog?: ProductOwnerBacklog
  error?: string
  customer_input?: string
  handoff_ready?: boolean
}

export const gatherRequirements = (req: RequirementsGatheringRequest) =>
  post<RequirementsGatheringResponse>('/product-owner/requirements', req)

