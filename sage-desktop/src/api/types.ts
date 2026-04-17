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
