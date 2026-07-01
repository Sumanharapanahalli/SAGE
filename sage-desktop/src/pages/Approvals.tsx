import { ApprovalCard } from "@/components/domain/ApprovalCard";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import {
  useApprovals,
  useApproveProposal,
  useRejectProposal,
} from "@/hooks/useApprovals";
import { toDesktopError } from "@/api/client";

export function Approvals() {
  const { data, isLoading, error } = useApprovals();
  const approve = useApproveProposal();
  const reject = useRejectProposal();

  if (isLoading) {
    return <p className="text-sm text-slate-500">Loading approvals…</p>;
  }
  if (error) {
    return <ErrorBanner error={error} />;
  }

  const busy = approve.isPending || reject.isPending;
  const mutationError =
    (approve.error && toDesktopError(approve.error)) ||
    (reject.error && toDesktopError(reject.error)) ||
    null;

  // Transient confirmation so a decision does not just silently vanish.
  const decided =
    (approve.isSuccess && approve.data) ||
    (reject.isSuccess && reject.data) ||
    null;
  const decidedVerb = approve.isSuccess ? "Approved" : "Rejected";

  const isEmpty = !data || data.length === 0;

  return (
    <div className="flex flex-col gap-4">
      <ErrorBanner error={mutationError} />
      {decided && (
        <div
          role="status"
          className="rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800"
        >
          {decidedVerb} <span className="font-mono">{decided.trace_id}</span>.
          The decision is recorded in the Audit log.
        </div>
      )}

      {isEmpty ? (
        <div className="rounded border border-sage-100 bg-white p-6 text-center text-sm text-slate-500">
          Nothing pending. Approved and rejected decisions go to the Audit log.
        </div>
      ) : (
        data.map((p) => (
          <ApprovalCard
            key={p.trace_id}
            proposal={p}
            isPending={busy}
            onApprove={(id) => approve.mutate({ trace_id: id })}
            onReject={(id, feedback) =>
              reject.mutate({ trace_id: id, feedback })
            }
          />
        ))
      )}
    </div>
  );
}
