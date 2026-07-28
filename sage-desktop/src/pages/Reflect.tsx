import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { toDesktopError } from "@/api/client";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import {
  reflectRecentKey,
  reflectStatsKey,
  useReflectProgress,
  useReflectRecent,
  useReflectStats,
  useStartReflection,
} from "@/hooks/useReflect";

/** Run the reflection engine (bounded generate -> critique -> refine loop) and
 * watch each iteration stream in live, then inspect session stats/recent runs.
 * The run executes as a background job; iterations are polled from the sidecar's
 * progress buffer, so the UI stays responsive during a multi-iteration run. */
export default function Reflect() {
  const qc = useQueryClient();
  const [task, setTask] = useState("");
  const [context, setContext] = useState("");
  const [runId, setRunId] = useState<string | null>(null);

  const stats = useReflectStats();
  const recent = useReflectRecent();
  const start = useStartReflection();
  const progress = useReflectProgress(runId);

  const startError = start.error ? toDesktopError(start.error) : null;
  const prog = progress.data;
  const running = prog?.state === "running";

  // When a run finishes, refresh the session stats + recent panels once.
  useEffect(() => {
    if (prog && prog.state !== "running") {
      qc.invalidateQueries({ queryKey: reflectStatsKey });
      qc.invalidateQueries({ queryKey: reflectRecentKey });
    }
  }, [prog?.state, qc]);

  const submit = () => {
    if (!task.trim()) return;
    start.mutate(
      { task, context: context || undefined },
      { onSuccess: (r) => setRunId(r.run_id) },
    );
  };

  return (
    <div className="p-6 space-y-4">
      <h2 className="font-semibold text-lg">Reflect</h2>
      <p className="text-sm text-slate-500">
        Run a bounded self-correction loop: the model generates an answer, a
        critic scores it, and it refines until the acceptance threshold is met.
        Iterations appear live as they complete.
      </p>

      <div className="rounded border border-sage-100 bg-white p-4 space-y-3">
        <label className="block text-sm font-medium" htmlFor="reflect-task">
          Task
        </label>
        <textarea
          id="reflect-task"
          value={task}
          onChange={(e) => setTask(e.target.value)}
          rows={3}
          placeholder="Describe what the model should produce or improve…"
          className="w-full rounded border border-sage-100 p-2 text-sm"
        />
        <label className="block text-sm font-medium" htmlFor="reflect-context">
          Context (optional)
        </label>
        <textarea
          id="reflect-context"
          value={context}
          onChange={(e) => setContext(e.target.value)}
          rows={2}
          placeholder="Any starting context or constraints…"
          className="w-full rounded border border-sage-100 p-2 text-sm"
        />
        <button
          type="button"
          onClick={submit}
          disabled={start.isPending || running || !task.trim()}
          className="rounded bg-sage-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {running ? "Reflecting…" : "Run reflection"}
        </button>
      </div>

      <ErrorBanner error={startError} />

      {prog && (
        <div className="rounded border border-sage-100 bg-white p-4 text-sm space-y-3">
          <div className="flex items-center gap-2 font-medium">
            <span>
              {prog.state === "running"
                ? "Reflecting…"
                : prog.state === "succeeded"
                  ? "Done"
                  : "Failed"}
            </span>
            {running && (
              <span className="h-2 w-2 animate-pulse rounded-full bg-sage-600" />
            )}
            <span className="text-slate-500">
              {prog.iterations.length} iteration
              {prog.iterations.length === 1 ? "" : "s"}
            </span>
          </div>

          {prog.error && (
            <div className="rounded border border-red-200 bg-red-50 p-2 text-xs text-red-700">
              {prog.error}
            </div>
          )}

          <ol className="space-y-2">
            {prog.iterations.map((it) => (
              <li
                key={it.iteration}
                className="rounded border border-sage-100 bg-slate-50 p-2"
              >
                <div className="flex justify-between font-mono text-xs">
                  <span>iteration {it.iteration}</span>
                  <span>score {it.score.toFixed(2)}</span>
                </div>
                {it.feedback && (
                  <div className="mt-1 text-xs text-slate-600">{it.feedback}</div>
                )}
                {it.output_preview && (
                  <pre className="mt-1 whitespace-pre-wrap text-xs text-slate-500">
                    {it.output_preview}
                  </pre>
                )}
              </li>
            ))}
          </ol>

          {prog.result && (
            <div className="rounded border border-sage-200 bg-white p-2">
              <div className="font-medium">
                {prog.result.accepted ? "✓ Accepted" : "✗ Not accepted"} · final
                score {prog.result.final_score.toFixed(2)}
              </div>
              {prog.result.final_output != null && (
                <pre className="mt-1 whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs">
                  {String(prog.result.final_output)}
                </pre>
              )}
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div className="rounded border border-sage-100 bg-white p-4">
          <div className="text-sm font-medium mb-2">Session stats</div>
          <ErrorBanner error={stats.error ? toDesktopError(stats.error) : null} />
          {stats.data && (
            <ul className="text-sm text-slate-600 space-y-1">
              <li>Total: {stats.data.total_reflections}</li>
              <li>Accepted: {stats.data.accepted_count}</li>
              <li>Avg iterations: {stats.data.avg_iterations}</li>
              <li>Avg score: {stats.data.avg_final_score}</li>
            </ul>
          )}
        </div>

        <div className="rounded border border-sage-100 bg-white p-4">
          <div className="text-sm font-medium mb-2">Recent</div>
          <ErrorBanner error={recent.error ? toDesktopError(recent.error) : null} />
          {recent.data && recent.data.reflections.length === 0 && (
            <div className="text-sm text-slate-500">No reflections yet.</div>
          )}
          {recent.data && recent.data.reflections.length > 0 && (
            <ul className="space-y-1 text-sm">
              {recent.data.reflections.map((r) => (
                <li key={r.reflection_id} className="flex justify-between gap-2">
                  <span className="font-mono text-xs truncate">
                    {r.reflection_id.slice(0, 8)}
                  </span>
                  <span>{r.accepted ? "✓" : "✗"}</span>
                  <span>{r.final_score.toFixed(2)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
