import { useState } from "react";

import type { DesktopError } from "@/api/types";
import { useKnowledgeSync } from "@/hooks/useKnowledgeSync";

function errorMessage(error: DesktopError): string {
  if (
    error.kind === "InvalidParams" ||
    error.kind === "SidecarDown" ||
    error.kind === "SolutionUnavailable" ||
    error.kind === "Other"
  ) {
    return error.detail.message;
  }
  return `Sync failed (${error.kind}).`;
}

export function KnowledgeSync() {
  const [directory, setDirectory] = useState("");
  const sync = useKnowledgeSync();
  const result = sync.data;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = directory.trim();
    sync.mutate({ directory: trimmed || undefined });
  };

  return (
    <form
      data-testid="knowledge-sync"
      className="space-y-3 rounded border border-slate-200 bg-white p-4"
      onSubmit={handleSubmit}
    >
      <header className="flex items-baseline justify-between">
        <h3 className="text-sm font-semibold">Sync from directory</h3>
        <span className="text-xs text-slate-500">
          Operator action — bypasses proposal queue
        </span>
      </header>
      <p className="text-xs text-slate-600">
        Walks a directory, chunks its text files, and imports them into this
        solution's vector memory. Leave the path empty to sync the active
        solution's own directory. Re-running adds fresh chunks rather than
        replacing existing ones.
      </p>
      <div className="flex items-center gap-2">
        <input
          aria-label="directory"
          className="flex-1 rounded border border-slate-300 p-2 font-mono text-xs"
          placeholder="Active solution directory"
          value={directory}
          onChange={(e) => setDirectory(e.target.value)}
        />
        <button
          type="submit"
          disabled={sync.isPending}
          className="rounded bg-sage-700 px-3 py-2 text-sm text-white hover:bg-sage-800 disabled:bg-slate-300 disabled:text-slate-500"
        >
          {sync.isPending ? "Syncing…" : "Sync"}
        </button>
      </div>

      {sync.isError && (
        <p className="text-xs text-rose-700" role="alert">
          {errorMessage(sync.error as DesktopError)}
        </p>
      )}

      {result && (
        <div data-testid="knowledge-sync-result" className="space-y-2">
          <dl className="grid grid-cols-4 gap-2 text-center">
            {[
              { label: "Files scanned", value: result.files_scanned },
              { label: "Files indexed", value: result.files_indexed },
              { label: "Chunks added", value: result.chunks_added },
              { label: "Skipped", value: result.skipped },
            ].map((tile) => (
              <div key={tile.label} className="rounded bg-slate-50 p-2">
                <dt className="text-xs text-slate-500">{tile.label}</dt>
                <dd className="text-lg font-semibold text-slate-800">
                  {tile.value}
                </dd>
              </div>
            ))}
          </dl>
          <p className="font-mono text-xs text-slate-500">{result.directory}</p>
          {result.errors.length > 0 && (
            <ul className="space-y-1 rounded border border-amber-200 bg-amber-50 p-2">
              {result.errors.map((err) => (
                <li key={err.file} className="text-xs text-amber-800">
                  <span className="font-mono">{err.file}</span>: {err.error}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </form>
  );
}
