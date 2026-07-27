import { useState } from "react";

import { toDesktopError } from "@/api/client";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import {
  useReflectRecent,
  useReflectStats,
  useRunReflection,
} from "@/hooks/useReflect";

/** Run the reflection engine (bounded generate -> critique -> refine loop) over
 * a task and inspect recent reflections. Results live in the sidecar's
 * in-process engine, so stats/recent cover the current session. */
export default function Reflect() {
  const [task, setTask] = useState("");
  const [context, setContext] = useState("");
  const stats = useReflectStats();
  const recent = useReflectRecent();
  const run = useRunReflection();

  const runError = run.error ? toDesktopError(run.error) : null;

  const submit = () => {
    if (task.trim()) run.mutate({ task, context: context || undefined });
  };

  return (
    <div className="p-6 space-y-4">
      <h2 className="font-semibold text-lg">Reflect</h2>
      <p className="text-sm text-slate-500">
        Run a bounded self-correction loop: the model generates an answer, a
        critic scores it, and it refines until the acceptance threshold is met.
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
          disabled={run.isPending || !task.trim()}
          className="rounded bg-sage-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {run.isPending ? "Reflecting…" : "Run reflection"}
        </button>
      </div>

      <ErrorBanner error={runError} />

      {run.data && (
        <div className="rounded border border-sage-100 bg-white p-4 text-sm space-y-1">
          <div className="font-medium">
            {run.data.accepted ? "✓ Accepted" : "✗ Not accepted"} · score{" "}
            {run.data.final_score.toFixed(2)} · {run.data.iterations} iteration
            {run.data.iterations === 1 ? "" : "s"}
          </div>
          {run.data.final_output != null && (
            <pre className="whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs">
              {String(run.data.final_output)}
            </pre>
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
