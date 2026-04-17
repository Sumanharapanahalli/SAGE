import { ErrorBanner } from "@/components/layout/ErrorBanner";
import { QueueTile } from "@/components/domain/QueueTile";
import { useStatus } from "@/hooks/useStatus";
import { useQueueStatus } from "@/hooks/useQueue";

function Tile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-sage-100 bg-white p-4">
      <div className="text-xs font-medium uppercase text-slate-400">{label}</div>
      <div className="mt-1 text-lg font-semibold text-sage-900">{value}</div>
    </div>
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
        <Tile label="Pending approvals" value={data.pending_approvals} />
      </div>
      {queue.isSuccess && <QueueTile status={queue.data} />}
    </div>
  );
}
