import { useState } from "react";
import type { FormEvent } from "react";

import { useCostsDaily, useCostsSummary, useSetCostsBudget } from "@/hooks/useCosts";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import { toDesktopError } from "@/api/client";

const PERIODS = [7, 30, 90];

function fmtUsd(n: number): string {
  return `$${n.toFixed(4)}`;
}

/** LLM spend summary/daily breakdown and per-solution monthly budget
 * controls. Budget writes bypass the proposal queue — the operator's own
 * explicit action, not an agent proposal — mirroring api.py's
 * /costs/budget endpoint. */
export default function Costs() {
  const [periodDays, setPeriodDays] = useState(30);
  const summary = useCostsSummary(undefined, undefined, periodDays);
  const daily = useCostsDaily(undefined, undefined, periodDays);
  const setBudget = useSetCostsBudget();

  const [budgetSolution, setBudgetSolution] = useState("");
  const [budgetAmount, setBudgetAmount] = useState("");

  const handleSetBudget = (e: FormEvent) => {
    e.preventDefault();
    const monthly_usd = parseFloat(budgetAmount);
    if (Number.isNaN(monthly_usd)) return;
    setBudget.mutate({
      monthly_usd,
      solution: budgetSolution || undefined,
    });
  };

  const error = setBudget.error ? toDesktopError(setBudget.error) : null;

  return (
    <div className="p-6 space-y-4">
      <h2 className="font-semibold text-lg">Costs</h2>

      <label className="block w-32">
        <span className="block text-sm font-medium">Period (days)</span>
        <select
          className="mt-1 rounded border border-gray-300 p-2"
          value={periodDays}
          onChange={(e) => setPeriodDays(Number(e.target.value))}
        >
          {PERIODS.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </label>

      {summary.data && (
        <div className="rounded border border-sage-100 bg-white p-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div>
              <div className="text-xs text-slate-500">Total spend</div>
              <div className="text-lg font-semibold">
                {fmtUsd(summary.data.total_cost_usd)}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500">Total calls</div>
              <div className="text-lg font-semibold">
                {summary.data.total_calls}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500">Avg cost/call</div>
              <div className="text-lg font-semibold">
                {fmtUsd(summary.data.avg_cost_per_call)}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500">Tokens (in/out)</div>
              <div className="text-lg font-semibold">
                {summary.data.total_input_tokens}/{summary.data.total_output_tokens}
              </div>
            </div>
          </div>

          {summary.data.by_model.length > 0 && (
            <div className="mt-4">
              <div className="text-sm font-medium mb-1">By model</div>
              <ul className="space-y-1 text-sm">
                {summary.data.by_model.map((m) => (
                  <li key={m.model} className="flex justify-between">
                    <span>{m.model}</span>
                    <span className="text-slate-500">
                      {m.calls} calls — {fmtUsd(m.cost)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {summary.data.by_solution.length > 0 && (
            <div className="mt-4">
              <div className="text-sm font-medium mb-1">By solution</div>
              <ul className="space-y-1 text-sm">
                {summary.data.by_solution.map((s) => (
                  <li key={s.solution} className="flex justify-between">
                    <span>{s.solution || "default"}</span>
                    <span className="text-slate-500">
                      {s.calls} calls — {fmtUsd(s.cost)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <div className="rounded border border-sage-100 bg-white p-4">
        <div className="text-sm font-medium mb-2">Daily cost</div>
        {daily.data && daily.data.daily.length === 0 && (
          <div className="text-sm text-slate-500">
            No cost data for this period.
          </div>
        )}
        {daily.data && daily.data.daily.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500">
                <th className="pr-4">Date</th>
                <th className="pr-4">Calls</th>
                <th>Cost</th>
              </tr>
            </thead>
            <tbody>
              {daily.data.daily.map((row) => (
                <tr key={row.date}>
                  <td className="pr-4">{row.date}</td>
                  <td className="pr-4">{row.calls}</td>
                  <td>{fmtUsd(row.cost_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <form
        onSubmit={handleSetBudget}
        className="rounded border border-sage-100 bg-white p-4 space-y-3"
      >
        <div className="text-sm font-medium">Set monthly budget</div>
        <div className="flex gap-3">
          <label className="block">
            <span className="block text-sm font-medium">Solution</span>
            <input
              className="mt-1 rounded border border-gray-300 p-2"
              value={budgetSolution}
              onChange={(e) => setBudgetSolution(e.target.value)}
              placeholder="optional — defaults to 'default'"
            />
          </label>

          <label className="block">
            <span className="block text-sm font-medium">
              Monthly budget (USD)
            </span>
            <input
              type="number"
              step="0.01"
              min="0"
              className="mt-1 rounded border border-gray-300 p-2"
              value={budgetAmount}
              onChange={(e) => setBudgetAmount(e.target.value)}
              required
            />
          </label>
        </div>

        <button
          type="submit"
          disabled={setBudget.isPending || !budgetAmount}
          className="rounded bg-sage-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {setBudget.isPending ? "Saving…" : "Set budget"}
        </button>
      </form>

      <ErrorBanner error={error} />

      {setBudget.data && (
        <div className="rounded border border-sage-100 bg-white p-4 text-sm">
          Budget set: {fmtUsd(setBudget.data.monthly_usd)}/mo for &quot;
          {setBudget.data.key}&quot;
        </div>
      )}
    </div>
  );
}
