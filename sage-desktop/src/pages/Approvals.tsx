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
  if (!data || data.length === 0) {
    return (
      <div className="rounded border border-sage-100 bg-white p-6 text-center text-sm text-slate-500">
        Nothing pending. Approved and rejected decisions go to the Audit log.
      </div>
    );
  }

  const busy = approve.isPending || reject.isPending;
  const mutationError =
    (approve.error && toDesktopError(approve.error)) ||
    (reject.error && toDesktopError(reject.error)) ||
    null;

  return (
    <div className="flex flex-col gap-4">
      <ErrorBanner error={mutationError} />
      {data.map((p) => (
        <ApprovalCard
          key={p.trace_id}
          proposal={p}
          isPending={busy}
          onApprove={(id) => approve.mutate({ trace_id: id })}
          onReject={(id) => reject.mutate({ trace_id: id })}
        />
      ))}
    </div>
  );
}
