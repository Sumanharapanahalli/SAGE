import { useState } from "react";

import type { DesktopError } from "@/api/types";
import { AddKnowledgeForm } from "@/components/domain/AddKnowledgeForm";
import { KnowledgeEntryRow } from "@/components/domain/KnowledgeEntryRow";
import { KnowledgeSearchResults } from "@/components/domain/KnowledgeSearchResults";
import {
  useAddKnowledge,
  useDeleteKnowledge,
  useKnowledgeList,
  useKnowledgeSearch,
  useKnowledgeStats,
} from "@/hooks/useKnowledge";

const PAGE_SIZE = 50;

function errorMessage(error: DesktopError): string {
  if (
    error.kind === "InvalidParams" ||
    error.kind === "SidecarDown" ||
    error.kind === "SolutionUnavailable"
  ) {
    return `${error.kind}: ${error.detail.message}`;
  }
  if (error.kind === "Other") {
    return error.detail.message;
  }
  return `Failed (${error.kind}).`;
}

type Tab = "browse" | "search";

export default function Knowledge() {
  const [tab, setTab] = useState<Tab>("browse");
  const [offset, setOffset] = useState(0);
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [topK, setTopK] = useState(10);

  const stats = useKnowledgeStats();
  const list = useKnowledgeList(PAGE_SIZE, offset);
  const search = useKnowledgeSearch(submittedQuery, topK);
  const add = useAddKnowledge();
  const del = useDeleteKnowledge();

  const total = list.data?.total ?? 0;
  const atStart = offset === 0;
  const atEnd = offset + PAGE_SIZE >= total;

  const backend = stats.data?.backend ?? "minimal";
  const unwired =
    stats.isError && (stats.error as DesktopError | undefined)?.kind !== undefined;

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-6">
      <header className="flex items-baseline justify-between">
        <div>
          <h2 className="text-lg font-semibold">Knowledge</h2>
          <p className="text-sm text-slate-600">
            Vector memory for the active solution. Operator edits bypass the
            proposal queue; agent changes still flow through STATEFUL /
            DESTRUCTIVE proposals.
          </p>
        </div>
        {stats.data && (
          <div className="text-right text-xs text-slate-500">
            <div className="font-semibold text-slate-700">
              {stats.data.solution}
            </div>
            <div className="font-mono">{stats.data.collection}</div>
            <div>
              backend: <span className="font-mono">{backend}</span> ·{" "}
              {stats.data.total} entries
            </div>
          </div>
        )}
      </header>

      {unwired && (
        <div
          role="alert"
          className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-900"
        >
          Knowledge base unavailable: {errorMessage(stats.error!)}
        </div>
      )}

      <nav className="flex gap-2" aria-label="Knowledge view">
        <button
          type="button"
          className={
            tab === "browse"
              ? "rounded bg-sage-700 px-3 py-1 text-sm text-white"
              : "rounded border border-slate-300 px-3 py-1 text-sm text-slate-700 hover:bg-slate-100"
          }
          onClick={() => setTab("browse")}
        >
          Browse
        </button>
        <button
          type="button"
          className={
            tab === "search"
              ? "rounded bg-sage-700 px-3 py-1 text-sm text-white"
              : "rounded border border-slate-300 px-3 py-1 text-sm text-slate-700 hover:bg-slate-100"
          }
          onClick={() => setTab("search")}
        >
          Search
        </button>
      </nav>

      {tab === "browse" && (
        <section className="space-y-3" data-testid="knowledge-browse">
          <div className="flex items-center justify-between text-xs text-slate-600">
            <span>
              {total === 0
                ? "No entries yet"
                : `Showing ${offset + 1}–${Math.min(offset + PAGE_SIZE, total)} of ${total}`}
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                disabled={atStart}
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              >
                ‹ Prev
              </button>
              <button
                type="button"
                className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                disabled={atEnd}
                onClick={() => setOffset(offset + PAGE_SIZE)}
              >
                Next ›
              </button>
            </div>
          </div>

          {list.isLoading && (
            <p className="text-sm text-slate-500">Loading entries…</p>
          )}
          {list.isError && (
            <div
              role="alert"
              className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-900"
            >
              Could not load entries: {errorMessage(list.error!)}
            </div>
          )}
          {list.data && list.data.entries.length === 0 && !list.isLoading && (
            <p className="text-sm text-slate-500">No entries on this page.</p>
          )}
          {list.data && list.data.entries.length > 0 && (
            <ul className="space-y-2">
              {list.data.entries.map((e) => (
                <KnowledgeEntryRow
                  key={e.id}
                  entry={e}
                  onDelete={(id) => del.mutate(id)}
                  isDeleting={del.isPending}
                />
              ))}
            </ul>
          )}
        </section>
      )}

      {tab === "search" && (
        <section className="space-y-3" data-testid="knowledge-search">
          {backend === "minimal" && (
            <div
              role="status"
              className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"
            >
              Semantic search is unavailable — ChromaDB is not installed. Only
              exact-match browse is available.
            </div>
          )}
          <form
            className="flex flex-wrap items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              setSubmittedQuery(query.trim());
            }}
          >
            <input
              aria-label="search query"
              className="min-w-[240px] flex-1 rounded border border-slate-300 p-2 text-sm"
              placeholder="Search query…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <label className="flex items-center gap-1 text-xs text-slate-600">
              top_k
              <input
                type="number"
                aria-label="top_k"
                min={1}
                max={50}
                className="w-16 rounded border border-slate-300 p-1 text-right font-mono text-xs"
                value={topK}
                onChange={(e) =>
                  setTopK(
                    Math.max(1, Math.min(50, Number(e.target.value) || 10)),
                  )
                }
              />
            </label>
            <button
              type="submit"
              disabled={!query.trim()}
              className="rounded bg-sage-700 px-3 py-1 text-sm text-white hover:bg-sage-800 disabled:bg-slate-300 disabled:text-slate-500"
            >
              Search
            </button>
          </form>

          {search.isFetching && submittedQuery && (
            <p className="text-sm text-slate-500">Searching…</p>
          )}
          {search.isError && (
            <div
              role="alert"
              className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-900"
            >
              Search failed: {errorMessage(search.error!)}
            </div>
          )}
          {search.data && (
            <KnowledgeSearchResults hits={search.data.results} />
          )}
        </section>
      )}

      <AddKnowledgeForm
        isSubmitting={add.isPending}
        error={add.error ? errorMessage(add.error) : null}
        onSubmit={(text, metadata) => add.mutate({ text, metadata })}
      />
    </div>
  );
}
