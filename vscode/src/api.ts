/**
 * SAGE Framework — VS Code Extension API Client
 * Thin wrapper around the SAGE FastAPI backend.
 */

export interface HealthResponse {
  status: string
  service: string
  version: string
  llm_provider: string
  project: { project: string; name: string; domain: string; active_modules: string[] }
}

export interface LLMStatus {
  provider: string
  model_info: {
    model: string
    daily_request_limit: number
    context_tokens: number
    unlimited: boolean
  }
  session: {
    started_at: string
    current_time: string
    calls_made: number
    calls_today: number
    estimated_tokens: number
    errors: number
  }
  config: { minimal_mode: boolean; project: string }
}

export interface Proposal {
  trace_id: string
  severity: string
  root_cause_hypothesis: string
  recommended_action: string
  confidence?: string
}

export interface AuditEntry {
  id: string
  timestamp: string
  actor: string
  action_type: string
  input_context: string
  output_content: string
}

export interface FeatureRequest {
  id: string
  module_id: string
  module_name: string
  title: string
  description: string
  priority: string
  status: string
  created_at: string
}

export interface Solution {
  id: string
  name: string
  domain: string
  version: string
  description: string
}

export class SageApiClient {
  private baseUrl: string

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '')
  }

  private async get<T>(path: string): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      signal: AbortSignal.timeout(8000),
    })
    if (!res.ok) {
      throw new Error(`GET ${path} → ${res.status} ${res.statusText}`)
    }
    return res.json() as Promise<T>
  }

  private async post<T>(path: string, body?: unknown): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(120_000), // LLM calls can be slow
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText })) as { detail?: string }
      throw new Error(err.detail ?? `POST ${path} → ${res.status}`)
    }
    return res.json() as Promise<T>
  }

  async health(): Promise<HealthResponse> {
    return this.get<HealthResponse>('/health')
  }

  async llmStatus(): Promise<LLMStatus> {
    return this.get<LLMStatus>('/llm/status')
  }

  async analyze(logEntry: string): Promise<Proposal> {
    return this.post<Proposal>('/analyze', { log_entry: logEntry })
  }

  async approve(traceId: string): Promise<void> {
    await this.post(`/approve/${traceId}`)
  }

  async reject(traceId: string, feedback: string): Promise<void> {
    await this.post(`/reject/${traceId}`, { feedback })
  }

  async auditLog(limit = 20): Promise<{ entries: AuditEntry[]; total: number }> {
    return this.get(`/audit?limit=${limit}`)
  }

  async pendingImprovements(): Promise<{ requests: FeatureRequest[]; count: number }> {
    return this.get('/feedback/feature-requests?status=pending')
  }

  async submitImprovement(payload: {
    module_id: string
    module_name: string
    title: string
    description: string
    priority: string
  }): Promise<{ id: string }> {
    return this.post('/feedback/feature-request', {
      ...payload,
      requested_by: 'vscode-extension',
    })
  }

  async listSolutions(): Promise<{ projects: Solution[]; active: string }> {
    return this.get('/config/projects')
  }

  async switchSolution(project: string): Promise<void> {
    await this.post('/config/switch', { project })
  }
}
