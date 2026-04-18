import type { CollectiveStats as StatsT } from "@/api/types";

interface Props {
  stats: StatsT;
}

function sortedEntries(m: Record<string, number>): [string, number][] {
  return Object.entries(m).sort((a, b) => b[1] - a[1]);
}

function Histogram({
  title,
  data,
}: {
  title: string;
  data: Record<string, number>;
}) {
  const entries = sortedEntries(data);
  const max = entries.length > 0 ? entries[0][1] : 1;
  return (
    <section>
      <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
      {entries.length === 0 ? (
        <div className="text-xs text-slate-500">(empty)</div>
      ) : (
        <ul className="space-y-0.5">
          {entries.map(([k, v]) => (
            <li key={k} className="flex items-center gap-2 text-xs">
              <span className="w-32 truncate font-mono">{k}</span>
              <div
                className="h-2 rounded bg-sky-500"
                style={{ width: `${(v / max) * 100}%` }}
              />
              <span className="ml-1 text-slate-600">{v}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function CollectiveStats({ stats }: Props) {
  const totalLearnings = stats.learning_count;
  return (
    <div className="space-y-4">
      <section className="grid grid-cols-3 gap-2 rounded border border-slate-200 bg-white p-3 text-sm">
        <div className="text-xs text-slate-500">
          learnings{" "}
          <span className="block text-lg font-semibold text-slate-900">
            {stats.learning_count}
          </span>
        </div>
        <div className="text-xs text-slate-500">
          open help{" "}
          <span className="block text-lg font-semibold text-slate-900">
            {stats.help_request_count}
          </span>
        </div>
        <div className="text-xs text-slate-500">
          closed help{" "}
          <span className="block text-lg font-semibold text-slate-900">
            {stats.help_requests_closed}
          </span>
        </div>
      </section>
      {totalLearnings === 0 &&
      stats.help_request_count === 0 &&
      stats.help_requests_closed === 0 ? (
        <p className="text-sm text-slate-600">
          No contributions yet. Publish the first learning to get started.
        </p>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          <Histogram title="Topics" data={stats.topics} />
          <Histogram title="Contributors" data={stats.contributors} />
        </div>
      )}
    </div>
  );
}
