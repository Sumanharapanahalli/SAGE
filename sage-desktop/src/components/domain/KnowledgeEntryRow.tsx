import { useState } from "react";

import type { KnowledgeEntry } from "@/api/types";

interface Props {
  entry: KnowledgeEntry;
  onDelete: (id: string) => void;
  isDeleting?: boolean;
}

const PREVIEW_CHARS = 200;

export function KnowledgeEntryRow({ entry, onDelete, isDeleting }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const metadataEntries = Object.entries(entry.metadata ?? {});
  const needsTruncate = entry.text.length > PREVIEW_CHARS;
  const shown =
    expanded || !needsTruncate
      ? entry.text
      : `${entry.text.slice(0, PREVIEW_CHARS)}…`;

  return (
    <li
      data-testid="knowledge-entry-row"
      className="space-y-2 rounded border border-slate-200 bg-white p-3"
    >
      <div className="flex items-center justify-between gap-2">
        <code
          className="truncate font-mono text-xs text-slate-500"
          title={entry.id}
        >
          {entry.id}
        </code>
        {confirming ? (
          <div className="flex items-center gap-2">
            <span className="text-xs text-rose-700">Delete this entry?</span>
            <button
              type="button"
              className="rounded border border-rose-300 px-2 py-1 text-xs text-rose-700 hover:bg-rose-50"
              onClick={() => {
                onDelete(entry.id);
                setConfirming(false);
              }}
              disabled={isDeleting}
            >
              Confirm
            </button>
            <button
              type="button"
              className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-100"
              onClick={() => setConfirming(false)}
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            type="button"
            aria-label={`delete entry ${entry.id}`}
            className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-rose-50 hover:text-rose-700"
            onClick={() => setConfirming(true)}
          >
            Delete
          </button>
        )}
      </div>

      {metadataEntries.length > 0 && (
        <ul className="flex flex-wrap gap-1">
          {metadataEntries.map(([k, v]) => (
            <li
              key={k}
              className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-700"
            >
              {k}={String(v)}
            </li>
          ))}
        </ul>
      )}

      <p className="whitespace-pre-wrap text-sm text-slate-800">{shown}</p>
      {needsTruncate && (
        <button
          type="button"
          className="text-xs text-sage-700 hover:underline"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? "Collapse" : "Expand"}
        </button>
      )}
    </li>
  );
}
