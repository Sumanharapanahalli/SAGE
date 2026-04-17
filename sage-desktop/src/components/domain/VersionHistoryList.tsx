import type { ConstitutionHistoryEntry } from "@/api/types";

interface Props {
  history: ConstitutionHistoryEntry[];
}

export function VersionHistoryList({ history }: Props) {
  const ordered = [...history].sort((a, b) => b.version - a.version);
  return (
    <section className="space-y-2" data-testid="version-history">
      <header>
        <h3 className="text-sm font-semibold">Version history</h3>
      </header>
      {ordered.length === 0 ? (
        <p className="text-xs text-slate-500">No revisions yet.</p>
      ) : (
        <ol className="space-y-1 text-xs">
          {ordered.map((h) => (
            <li
              key={`${h.version}-${h.timestamp}`}
              className="flex justify-between border-b border-slate-100 pb-1 last:border-b-0"
            >
              <span className="font-mono">v{h.version}</span>
              <span className="text-slate-600">{h.timestamp}</span>
              <span className="text-slate-700">{h.changed_by}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
