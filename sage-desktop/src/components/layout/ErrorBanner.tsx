import type { DesktopError } from "@/api/types";

interface Props {
  error: DesktopError | null;
}

function describe(err: DesktopError): { title: string; detail: string } {
  switch (err.kind) {
    case "SidecarDown":
      return {
        title: "Sidecar disconnected — attempting to reconnect…",
        detail: err.detail.message,
      };
    case "ProposalNotFound":
      return {
        title: "Proposal not found",
        detail: `trace_id: ${err.detail.trace_id}`,
      };
    case "ProposalExpired":
      return {
        title: "Proposal expired",
        detail: `trace_id: ${err.detail.trace_id}`,
      };
    case "AlreadyDecided":
      return {
        title: "Proposal already decided",
        detail: `${err.detail.trace_id} — ${err.detail.status}`,
      };
    case "RbacDenied":
      return {
        title: "Permission denied",
        detail: `required role: ${err.detail.required_role}`,
      };
    case "SolutionUnavailable":
      return { title: "No solution loaded", detail: err.detail.message };
    case "SageImportError":
      return {
        title: "SAGE module import error",
        detail: `${err.detail.module}: ${err.detail.detail}`,
      };
    case "InvalidRequest":
    case "InvalidParams":
      return { title: err.kind, detail: err.detail.message };
    case "MethodNotFound":
      return {
        title: "Method not found",
        detail: err.detail.method,
      };
    case "Other":
      return {
        title: `Error (${err.detail.code})`,
        detail: err.detail.message,
      };
  }
}

export function ErrorBanner({ error }: Props) {
  if (!error) return null;
  const { title, detail } = describe(error);
  return (
    <div
      role="alert"
      className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900"
    >
      <div className="font-semibold">{title}</div>
      <div className="mt-0.5 text-red-800/80">{detail}</div>
    </div>
  );
}
