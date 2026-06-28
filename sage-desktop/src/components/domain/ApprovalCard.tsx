import clsx from "clsx";

import type { Proposal, RiskClass } from "@/api/types";

interface Props {
  proposal: Proposal;
  onApprove: (trace_id: string) => void;
  onReject: (trace_id: string) => void;
  isPending?: boolean;
}

const RISK_STYLES: Record<RiskClass, string> = {
  INFORMATIONAL: "bg-slate-100 text-slate-700",
  EPHEMERAL: "bg-sky-100 text-sky-700",
  STATEFUL: "bg-amber-100 text-amber-700",
  EXTERNAL: "bg-violet-100 text-violet-700",
  DESTRUCTIVE: "bg-red-100 text-red-700",
};

export function ApprovalCard({
  proposal,
  onApprove,
  onReject,
  isPending = false,
}: Props) {
  return (
    <article className="rounded-lg border border-sage-100 bg-white p-4 shadow-sm">
      <div className="mb-2 flex items-center gap-2 text-xs">
        <span className="rounded bg-sage-100 px-2 py-0.5 font-mono text-sage-900">
          {proposal.action_type}
        </span>
        <span
          className={clsx(
            "rounded px-2 py-0.5 font-semibold uppercase",
            RISK_STYLES[proposal.risk_class],
          )}
        >
          {proposal.risk_class}
        </span>
        <span className="ml-auto font-mono text-slate-400">
          {proposal.trace_id}
        </span>
      </div>
      <p className="mb-3 text-sm text-sage-900">{proposal.description}</p>
      <div className="mb-3 text-xs text-slate-500">
        Proposed by <span className="font-medium">{proposal.proposed_by}</span>
        {" · "}
        {new Date(proposal.created_at).toLocaleString()}
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => onApprove(proposal.trace_id)}
          disabled={isPending}
          className="rounded bg-sage-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-sage-600 disabled:opacity-50"
        >
          Approve
        </button>
        <button
          type="button"
          onClick={() => onReject(proposal.trace_id)}
          disabled={isPending}
          className="rounded border border-red-200 bg-white px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
        >
          Reject
        </button>
      </div>
    </article>
  );
}
