import { toDesktopError } from "@/api/client";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import { useEvalHistory, useEvalSuites, useRunEval } from "@/hooks/useEval";

/** Run Agent Gym eval suites for the active solution and review recent
 * history. Suites live under solutions/<name>/evals/*.yaml — an empty
 * list means the solution has none, not an error. */
export default function Eval() {
  const suites = useEvalSuites();
  const run = useRunEval();
  const history = useEvalHistory();

  const suitesError = suites.error ? toDesktopError(suites.error) : null;
  const runError = run.error ? toDesktopError(run.error) : null;
  const suiteList = suites.data?.suites ?? [];

  return (
    <div className="p-6 space-y-4">
      <h2 className="font-semibold text-lg">Eval</h2>
      <p className="text-sm text-slate-500">
        Score agent quality against the active solution's eval suites.
      </p>

      <ErrorBanner error={suitesError} />

      {suites.isLoading && (
        <div className="text-sm text-slate-500">Loading suites…</div>
      )}

      {!suites.isLoading && suiteList.length === 0 && !suitesError && (
        <div className="rounded border border-dashed border-sage-100 bg-white p-6 text-center text-sm text-slate-500">
          No eval suites available. Add YAML files under this solution's{" "}
          <code>evals/</code> directory to define one.
        </div>
      )}

      {suiteList.length > 0 && (
        <ul className="space-y-2">
          {suiteList.map((name) => (
            <li
              key={name}
              className="flex items-center justify-between rounded border border-sage-100 bg-white p-3"
            >
              <span className="font-mono text-sm">{name}</span>
              <button
                type="button"
                onClick={() => run.mutate(name)}
                disabled={run.isPending}
                className="rounded bg-sage-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
              >
                {run.isPending ? "Running…" : "Run"}
              </button>
            </li>
          ))}
        </ul>
      )}

      <ErrorBanner error={runError} />

      {run.data && (
        <div className="rounded border border-sage-100 bg-white p-4 text-sm">
          <div className="font-medium">
            {run.data.suite}: {run.data.passed_cases} / {run.data.total_cases} passed
          </div>
          <div className="text-slate-500">
            mean score {run.data.mean_score.toFixed(1)}
          </div>
        </div>
      )}

      <div className="rounded border border-sage-100 bg-white p-4">
        <div className="text-sm font-medium mb-2">History</div>
        {history.data && history.data.history.length === 0 && (
          <div className="text-sm text-slate-500">No runs yet.</div>
        )}
        {history.data && history.data.history.length > 0 && (
          <ul className="space-y-1 text-sm">
            {history.data.history.map((entry) => (
              <li key={entry.run_id} className="flex justify-between">
                <span className="font-mono text-xs">{entry.run_id}</span>
                <span>{entry.suite}</span>
                <span>
                  {entry.passed_cases}/{entry.total_cases}
                </span>
                <span>{entry.mean_score.toFixed(1)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
