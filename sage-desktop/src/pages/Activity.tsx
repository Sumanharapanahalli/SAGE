import { useState } from "react";

import { ErrorBanner } from "@/components/layout/ErrorBanner";
import { useActivity } from "@/hooks/useActivity";
import type { ActivityCategory } from "@/api/types";

const PAGE_SIZE = 50;

const CATEGORIES: Array<{ value: ActivityCategory | "all"; label: string }> = [
  { value: "all", label: "All" },
  { value: "errors", label: "Errors" },
  { value: "proposals", label: "Proposals" },
  { value: "tasks", label: "Tasks" },
  { value: "llm", label: "LLM" },
];

const CATEGORY_STYLE: Record<ActivityCategory, string> = {
  errors: "bg-red-100 text-red-800",
  proposals: "bg-amber-100 text-amber-800",
  tasks: "bg-sage-100 text-sage-800",
  llm: "bg-blue-100 text-blue-800",
};

/** The triage feed over the audit log. Unlike Audit (an exact action_type
 * match), "show me everything that FAILED" is a real question here: the
 * sidecar classifies across event_type, action_type, the status column AND
 * the free text of output_content, in SQL — so totals and paging are honest. */
export default function Activity() {
  const [category, setCategory] = useState<ActivityCategory | "all">("all");
  const [queryInput, setQueryInput] = useState("");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);

  const { data, isLoading, error } = useActivity({
    category,
    ...(query ? { query } : {}),
    limit: PAGE_SIZE,
    offset,
  });

  const total = data?.total ?? 0;
  const events = data?.events ?? [];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        {CATEGORIES.map((c) => (
          <button
            key={c.value}
            type="button"
            onClick={() => {
              setCategory(c.value);
              setOffset(0);
            }}
            className={
              category === c.value
                ? "rounded-full bg-sage-500 px-3 py-1 text-sm text-white"
                : "rounded-full border border-sage-100 bg-white px-3 py-1 text-sm text-sage-900 hover:bg-sage-100"
            }
          >
            {c.label}
          </button>
        ))}

        <form
          className="flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setQuery(queryInput.trim());
            setOffset(0);
          }}
        >
          <input
            type="search"
            aria-label="Search activity"
            placeholder="Search actor, type, output…"
            value={queryInput}
            onChange={(e) => setQueryInput(e.target.value)}
            className="w-64 rounded border border-sage-100 bg-white px-2 py-1 text-sm"
          />
          <button
            type="submit"
            className="rounded bg-sage-600 px-3 py-1 text-sm text-white"
          >
            Search
          </button>
        </form>

        <div className="ml-auto flex items-center gap-2 text-xs text-slate-500">
          <span>
            {total === 0
              ? "0"
              : `${offset + 1}–${Math.min(offset + PAGE_SIZE, total)} of ${total}`}
          </span>
          <button
            type="button"
            onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
            disabled={offset === 0}
            className="rounded border border-sage-100 px-2 py-1 disabled:opacity-40"
          >
            Prev
          </button>
          <button
            type="button"
            onClick={() => setOffset((o) => o + PAGE_SIZE)}
            disabled={offset + PAGE_SIZE >= total}
            className="rounded border border-sage-100 px-2 py-1 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </div>

      <ErrorBanner error={error ?? null} />

      {isLoading ? (
        <p className="text-sm text-slate-500">Loading activity…</p>
      ) : events.length === 0 ? (
        <p className="text-sm text-slate-500">No activity events.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {events.map((e) => (
            <li
              key={e.id}
              className="rounded border border-sage-100 bg-white p-3 text-sm"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`rounded px-2 py-0.5 text-xs font-medium ${CATEGORY_STYLE[e.category]}`}
                >
                  {e.category}
                </span>
                <span className="font-medium text-sage-900">
                  {e.event_type ?? e.action_type}
                </span>
                <span className="text-slate-500">{e.actor}</span>
                <span className="ml-auto text-xs text-slate-500">
                  {e.timestamp}
                </span>
              </div>
              {e.output_content && (
                <p className="mt-1 line-clamp-3 whitespace-pre-wrap text-slate-700">
                  {e.output_content}
                </p>
              )}
              {e.trace_id && (
                <p className="mt-1 font-mono text-xs text-slate-400">
                  {e.trace_id}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
