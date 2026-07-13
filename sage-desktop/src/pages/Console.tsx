import { useEffect, useMemo, useRef, useState } from "react";

import { ErrorBanner } from "@/components/layout/ErrorBanner";
import { MAX_LINES, useLogTail } from "@/hooks/useLogs";

const LEVEL_CLASS: Record<string, string> = {
  DEBUG: "text-slate-400",
  INFO: "text-sky-400",
  WARNING: "text-amber-400",
  ERROR: "text-red-400",
  CRITICAL: "text-red-500 font-bold",
};

/** Ordered by severity — selecting a level shows it and everything above it. */
const LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] as const;
const RANK: Record<string, number> = {
  DEBUG: 0,
  INFO: 1,
  WARNING: 2,
  ERROR: 3,
  CRITICAL: 4,
};

/**
 * Live Console — the operator's only window into the framework's own logging.
 * Without it, every agent/build/eval traceback is written to the sidecar's
 * stderr (a terminal the desktop operator does not have) and the UI shows just
 * a bare RPC error.
 */
export default function Console() {
  const [paused, setPaused] = useState(false);
  const [filter, setFilter] = useState("");
  const [minLevel, setMinLevel] = useState<string>("DEBUG");
  const { entries, connected, error, clear } = useLogTail(paused);
  const bottomRef = useRef<HTMLDivElement>(null);

  const visible = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    const floor = RANK[minLevel] ?? 0;
    return entries.filter((e) => {
      if ((RANK[e.level] ?? 1) < floor) return false;
      if (!needle) return true;
      return (
        e.message.toLowerCase().includes(needle) ||
        e.name.toLowerCase().includes(needle)
      );
    });
  }, [entries, filter, minLevel]);

  // Autoscroll unless the operator paused to read something.
  useEffect(() => {
    if (!paused) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [visible, paused]);

  return (
    <div className="flex h-full flex-col gap-3 p-6">
      <div className="flex flex-wrap items-center gap-3">
        <span
          data-testid="console-connection"
          className={`inline-flex items-center gap-1.5 rounded px-2 py-1 font-mono text-xs ${
            connected
              ? "bg-emerald-100 text-emerald-800"
              : "bg-red-100 text-red-800"
          }`}
        >
          <span
            className={`h-2 w-2 rounded-full ${
              connected ? "animate-pulse bg-emerald-500" : "bg-red-500"
            }`}
          />
          {connected ? "Connected" : "Not connected"}
        </span>

        <input
          type="text"
          placeholder="Filter logs…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="min-w-[180px] flex-1 rounded border border-gray-300 px-3 py-1 text-sm"
        />

        <select
          aria-label="Minimum level"
          value={minLevel}
          onChange={(e) => setMinLevel(e.target.value)}
          className="rounded border border-gray-300 px-2 py-1 text-sm"
        >
          {LEVELS.map((l) => (
            <option key={l} value={l}>
              {l}+
            </option>
          ))}
        </select>

        <button
          type="button"
          onClick={() => setPaused((p) => !p)}
          className="rounded border border-gray-300 px-3 py-1 text-xs hover:bg-sage-50"
        >
          {paused ? "Resume" : "Pause"}
        </button>

        <button
          type="button"
          onClick={clear}
          className="rounded border border-gray-300 px-3 py-1 text-xs hover:bg-sage-50"
        >
          Clear
        </button>

        <span className="ml-auto text-xs text-slate-500">
          {visible.length} / {MAX_LINES} lines
        </span>
      </div>

      <ErrorBanner error={error} />

      <div className="min-h-[320px] flex-1 overflow-y-auto rounded-lg border border-slate-700 bg-slate-950 p-3 font-mono text-xs leading-5">
        {visible.length === 0 && (
          <div className="mt-8 text-center text-slate-500">
            {connected
              ? "Waiting for log output…"
              : "Sidecar not reachable — retrying every 2s."}
          </div>
        )}
        {visible.map((e) => (
          <div key={e.seq} className="flex gap-2 rounded px-1 hover:bg-white/5">
            <span className="w-[86px] shrink-0 overflow-hidden text-slate-500">
              {e.ts.slice(11, 23)}
            </span>
            <span
              className={`w-[64px] shrink-0 ${LEVEL_CLASS[e.level] ?? "text-slate-400"}`}
            >
              {e.level}
            </span>
            <span className="max-w-[160px] shrink-0 truncate text-slate-500">
              {e.name}
            </span>
            {/* whitespace-pre-wrap: multi-line tracebacks arrive as one record
                and are the single most valuable thing on this page. */}
            <span className="whitespace-pre-wrap break-all text-slate-200">
              {e.message}
            </span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
