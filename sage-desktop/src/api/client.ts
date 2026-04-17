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
  AuditEvent,
  AuditListResponse,
  AuditStats,
  AuditTraceResponse,
  BatchApproveResult,
  DesktopError,
  HandshakeResponse,
  Proposal,
  StatusResponse,
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

// Re-exports to reduce import boilerplate at call sites
export type {
  Agent,
  AuditEvent,
  AuditListResponse,
  AuditStats,
  AuditTraceResponse,
  BatchApproveResult,
  DesktopError,
  HandshakeResponse,
  Proposal,
  StatusResponse,
};
