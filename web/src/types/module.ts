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
