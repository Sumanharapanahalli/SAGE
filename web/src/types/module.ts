// ---------------------------------------------------------------------------
// Module Registry Types
// ---------------------------------------------------------------------------
// Every UI module (page) registers itself here so the self-improvement system
// knows what it does, what it already supports, and what ideas exist for it.

export interface ModuleMetadata {
  /** Unique snake_case identifier matching the route */
  id: string
  /** Human-readable name */
  name: string
  /** One-sentence description */
  description: string
  /** SemVer string */
  version: string
  /** React Router path */
  route: string
  /** Current feature list (shown in module info panel) */
  features: string[]
  /** Seed ideas for improvement requests (shown as clickable hints) */
  improvementHints: string[]
}

// ---------------------------------------------------------------------------
// Feature Request Types
// ---------------------------------------------------------------------------

export type Priority = 'low' | 'medium' | 'high' | 'critical'

export type RequestStatus =
  | 'pending'
  | 'approved'
  | 'in_planning'
  | 'in_progress'
  | 'completed'
  | 'rejected'
  | 'github_pr'

/**
 * scope distinguishes WHO owns the backlog item:
 *   "solution" — a feature or task to build in your application (solution backlog)
 *   "sage"     — an improvement idea for the SAGE platform itself (community / framework)
 *
 * Solution requests go through the full SAGE workflow: plan → approve → implement.
 * SAGE requests are logged here AND should be raised as GitHub Issues on the framework repo
 * so the community can pick them up.
 */
export type RequestScope = 'solution' | 'sage'

export interface FeatureRequest {
  id: string
  module_id: string
  module_name: string
  title: string
  description: string
  priority: Priority
  status: RequestStatus
  requested_by: string
  scope: RequestScope
  created_at: string
  updated_at: string
  reviewer_note?: string
  plan_trace_id?: string
}

export interface FeatureRequestPayload {
  module_id: string
  module_name: string
  title: string
  description: string
  priority: Priority
  requested_by: string
  scope: RequestScope
}

// ---------------------------------------------------------------------------
// Access Control
// ---------------------------------------------------------------------------
// During development: IMPROVEMENT_MODE = 'open' → everyone can request
// After release:      IMPROVEMENT_MODE = 'role_based' → check user role
// Production freeze:  IMPROVEMENT_MODE = 'disabled'

export type ImprovementMode = 'open' | 'role_based' | 'disabled'

export interface ImprovementAccess {
  canRequest: boolean
  canApprove: boolean
  canGeneratePlan: boolean
  mode: ImprovementMode
}

// ---------------------------------------------------------------------------
// Task Queue Types
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Cost Tracking Types (T1-004)
// ---------------------------------------------------------------------------

export interface DailyCost {
  date: string
  calls: number
  cost_usd: number
}

export interface CostByModel {
  model: string
  calls: number
  cost: number
}

export interface CostBySolution {
  solution: string
  calls: number
  cost: number
}

export interface CostSummary {
  total_cost_usd: number
  total_calls: number
  total_input_tokens: number
  total_output_tokens: number
  avg_cost_per_call: number
  by_model: CostByModel[]
  by_solution: CostBySolution[]
  period_days: number
  tenant: string | null
  solution: string | null
}

export interface QueueTask {
  task_id: string
  task_type: string
  payload: Record<string, unknown>
  priority: number
  status: 'pending' | 'in_progress' | 'completed' | 'failed'
  created_at: string
  started_at?: string
  completed_at?: string
  result?: string
  error?: string
  plan_trace_id?: string
  source?: string
  // joined from feature_requests:
  feature_title?: string
  feature_scope?: string
}
