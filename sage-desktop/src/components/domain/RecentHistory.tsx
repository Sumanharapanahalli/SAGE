import type { HistorySession } from "@/api/types";

interface Props {
  sessions: HistorySession[];
}

function formatTimestamp(ts: string | undefined): string {
  if (!ts) return "—";
  const d = new Date(ts);
  if (Number.isNaN(d.valueOf())) return ts;
  return d.toLocaleString();
}

export function RecentHistory({ sessions }: Props) {
  if (sessions.length === 0) {
    return (
      <div className="rounded border border-sage-100 bg-white p-6 text-sm text-slate-500">
        No training history yet.
      </div>
    );
  }
  return (
    <ul className="divide-y divide-sage-100 rounded border border-sage-100 bg-white">
      {sessions.map((s) => (
        <li
          key={s.session_id}
          className="flex items-center justify-between px-3 py-2 text-sm"
        >
          <div>
            <div className="font-medium">{s.agent_role}</div>
            <div className="text-xs text-slate-500">
              {s.exercise_id ?? "—"} · {formatTimestamp(s.timestamp)}
            </div>
          </div>
          <div className="text-right">
            <div className="font-medium">
              {typeof s.score === "number" ? s.score.toFixed(1) : "—"}
            </div>
            <div
              className={
                s.passed
                  ? "text-xs text-emerald-600"
                  : "text-xs text-rose-600"
              }
            >
              {s.passed === undefined ? "—" : s.passed ? "passed" : "failed"}
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}
