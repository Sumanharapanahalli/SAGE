import { Link } from "react-router-dom";

import { ErrorBanner } from "@/components/layout/ErrorBanner";
import { QueueTile } from "@/components/domain/QueueTile";
import { useStatus } from "@/hooks/useStatus";
import { useQueueStatus } from "@/hooks/useQueue";

function Tile({
  label,
  value,
  to,
}: {
  label: string;
  value: string | number;
  to?: string;
}) {
  const body = (
    <>
      <div className="text-xs font-medium uppercase text-slate-400">{label}</div>
      <div className="mt-1 text-lg font-semibold text-sage-900">{value}</div>
    </>
  );
  if (to) {
    return (
      <Link
        to={to}
        className="block rounded-lg border border-sage-100 bg-white p-4 transition-colors hover:border-sage-300 hover:bg-sage-50"
      >
        {body}
      </Link>
    );
  }
  return (
    <div className="rounded-lg border border-sage-100 bg-white p-4">{body}</div>
  );
}

export function Status() {
  const { data, error } = useStatus();
  const queue = useQueueStatus();
  if (error) return <ErrorBanner error={error} />;
  if (!data) return <p className="text-sm text-slate-500">Loading status…</p>;

  const llmLabel = data.llm
    ? data.llm.provider
      ? `${data.llm.provider}${data.llm.model ? ` / ${data.llm.model}` : ""}`
      : (data.llm.error ?? "unknown")
    : "not configured";

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Tile label="Health" value={data.health} />
        <Tile label="Sidecar" value={data.sidecar_version} />
        <Tile
          label="Project"
          value={data.project?.name ?? "—"}
        />
        <Tile label="LLM" value={llmLabel} />
        <Tile
          label="Pending approvals"
          value={data.pending_approvals}
          to={data.pending_approvals > 0 ? "/approvals" : undefined}
        />
      </div>
      {queue.isSuccess && <QueueTile status={queue.data} />}
    </div>
  );
}
