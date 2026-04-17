import type { AuditEvent } from "@/api/types";

interface Props {
  events: AuditEvent[];
}

export function AuditTable({ events }: Props) {
  if (events.length === 0) {
    return (
      <div className="rounded border border-sage-100 bg-white p-6 text-center text-sm text-slate-500">
        No audit events for the current filter.
      </div>
    );
  }
  return (
    <table className="min-w-full divide-y divide-sage-100 rounded-lg border border-sage-100 bg-white text-sm">
      <thead className="bg-sage-50 text-xs uppercase text-slate-500">
        <tr>
          <th className="px-3 py-2 text-left">Timestamp</th>
          <th className="px-3 py-2 text-left">Actor</th>
          <th className="px-3 py-2 text-left">Action</th>
          <th className="px-3 py-2 text-left">Trace</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-sage-50">
        {events.map((e) => (
          <tr key={e.id}>
            <td className="px-3 py-2 font-mono text-xs text-slate-600">
              {new Date(e.timestamp).toLocaleString()}
            </td>
            <td className="px-3 py-2">{e.actor}</td>
            <td className="px-3 py-2">{e.action_type}</td>
            <td className="px-3 py-2 font-mono text-xs text-slate-500">
              {e.trace_id ?? "—"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
