import type { BuildRunSummary } from "@/api/types";

interface Props {
  runs: BuildRunSummary[];
  selectedId: string | null;
  onSelect: (runId: string) => void;
}

const STATE_COLOR: Record<string, string> = {
  decomposing: "bg-blue-100 text-blue-900",
  awaiting_plan: "bg-yellow-100 text-yellow-900",
  building: "bg-blue-100 text-blue-900",
  awaiting_build: "bg-yellow-100 text-yellow-900",
  integrating: "bg-blue-100 text-blue-900",
  completed: "bg-green-100 text-green-900",
  failed: "bg-red-100 text-red-900",
  rejected: "bg-red-100 text-red-900",
};

function stateBadge(state: string) {
  const cls = STATE_COLOR[state] ?? "bg-gray-100 text-gray-800";
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs ${cls}`}>
      {state}
    </span>
  );
}

export function BuildRunsTable({ runs, selectedId, onSelect }: Props) {
  if (runs.length === 0) {
    return (
      <div className="rounded border border-sage-100 bg-white p-6 text-center text-sm text-slate-500">
        No build runs yet.
      </div>
    );
  }
  return (
    <table className="min-w-full divide-y divide-sage-100 rounded-lg border border-sage-100 bg-white text-sm">
      <thead className="bg-sage-50 text-xs uppercase text-slate-500">
        <tr>
          <th className="px-3 py-2 text-left">Run ID</th>
          <th className="px-3 py-2 text-left">Solution</th>
          <th className="px-3 py-2 text-left">State</th>
          <th className="px-3 py-2 text-left">Tasks</th>
          <th className="px-3 py-2 text-left">Created</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-sage-50">
        {runs.map((r) => {
          const isSelected = r.run_id === selectedId;
          return (
            <tr
              key={r.run_id}
              className={`cursor-pointer hover:bg-sage-50 ${
                isSelected ? "bg-sage-100" : ""
              }`}
              onClick={() => onSelect(r.run_id)}
            >
              <td className="px-3 py-2 font-mono text-xs">{r.run_id}</td>
              <td className="px-3 py-2">{r.solution_name || "—"}</td>
              <td className="px-3 py-2">{stateBadge(r.state)}</td>
              <td className="px-3 py-2">{r.task_count}</td>
              <td className="px-3 py-2 font-mono text-xs text-slate-500">
                {new Date(r.created_at).toLocaleString()}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
