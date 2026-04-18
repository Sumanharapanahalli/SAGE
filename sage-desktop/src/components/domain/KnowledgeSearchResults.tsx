import type { KnowledgeSearchHit } from "@/api/types";

interface Props {
  hits: KnowledgeSearchHit[];
}

export function KnowledgeSearchResults({ hits }: Props) {
  if (hits.length === 0) {
    return (
      <p className="text-sm text-slate-500" data-testid="knowledge-search-empty">
        No matches.
      </p>
    );
  }
  return (
    <ol
      className="space-y-2"
      data-testid="knowledge-search-results"
    >
      {hits.map((hit, i) => (
        <li
          key={hit.id ?? `${i}-${hit.text.slice(0, 16)}`}
          className="rounded border border-slate-200 bg-white p-3"
        >
          <div className="mb-1 flex items-center justify-between text-xs text-slate-500">
            <span>#{i + 1}</span>
            {typeof hit.score === "number" && (
              <span className="font-mono">score {hit.score.toFixed(3)}</span>
            )}
          </div>
          <p className="whitespace-pre-wrap text-sm text-slate-800">
            {hit.text}
          </p>
        </li>
      ))}
    </ol>
  );
}
