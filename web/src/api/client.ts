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
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.statusText}`)
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

// Health
export const fetchHealth = () => get<HealthResponse>('/health')

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
  post<{ request_id: string; status: string; plan: unknown }>(
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

// Set active modules for current solution (runtime override)
export const setActiveModules = (modules: string[]) =>
  post<{ active_modules: string[] }>('/config/modules', { modules })

// Switch active solution at runtime
export const switchProject = (project: string) =>
  post<{ switched: boolean; project: string; name: string; domain: string; active_modules: string[] }>(
    '/config/switch', { project }
  )

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
    ui_labels: Record<string, string>
  }>('/config/project')

export const fetchProjects = () =>
  get<{ projects: Array<{ id: string; name: string; domain: string; version: string; description: string }>; active: string }>(
    '/config/projects'
  )

// --- Types ---
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
  threads?: Record<string, { running: boolean; last_poll?: string; event_count: number }>
  [key: string]: unknown
}
