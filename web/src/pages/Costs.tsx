import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchCostSummary, fetchCostDaily } from '../api/client'
import type { CostSummary, DailyCost, CostBySolution } from '../types/module'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function fmt(usd: number): string {
  if (usd === 0) return '$0.00'
  if (usd < 0.001) return `$${usd.toFixed(6)}`
  if (usd < 1) return `$${usd.toFixed(4)}`
  return `$${usd.toFixed(2)}`
}

function fmtK(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

function budgetColor(pct: number): string {
  if (pct >= 100) return 'text-red-600'
  if (pct >= 80) return 'text-amber-600'
  return 'text-green-600'
}

function budgetBarColor(pct: number): string {
  if (pct >= 100) return 'bg-red-500'
  if (pct >= 80) return 'bg-amber-400'
  return 'bg-green-500'
}

// ---------------------------------------------------------------------------
// Inline SVG bar chart
// ---------------------------------------------------------------------------
function DailyBarChart({ data }: { data: DailyCost[] }) {
  if (!data || data.length === 0) {
    return (
      <div className="h-32 flex items-center justify-center text-sm text-gray-400">
        No data for this period
      </div>
    )
  }

  const maxCost = Math.max(...data.map(d => d.cost_usd), 0.000001)
  const chartH = 80
  const barW = Math.max(4, Math.floor(420 / data.length) - 2)

  return (
    <div className="overflow-x-auto">
      <svg
        width={Math.max(420, data.length * (barW + 2))}
        height={chartH + 28}
        className="block"
      >
        {data.map((d, i) => {
          const h = Math.max(2, Math.round((d.cost_usd / maxCost) * chartH))
          const x = i * (barW + 2)
          const y = chartH - h
          return (
            <g key={d.date}>
              <rect
                x={x}
                y={y}
                width={barW}
                height={h}
                rx={2}
                className="fill-blue-500 opacity-80 hover:opacity-100 transition-opacity"
              >
                <title>{d.date}: {fmt(d.cost_usd)} ({d.calls} calls)</title>
              </rect>
              {data.length <= 14 && (
                <text
                  x={x + barW / 2}
                  y={chartH + 14}
                  textAnchor="middle"
                  fontSize="9"
                  className="fill-gray-400"
                >
                  {d.date.slice(5)}
                </text>
              )}
            </g>
          )
        })}
      </svg>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
const PERIODS = [
  { label: '7d', value: 7 },
  { label: '30d', value: 30 },
  { label: '90d', value: 90 },
]

export default function Costs() {
  const [period, setPeriod] = useState(30)

  const summaryQuery = useQuery({
    queryKey: ['costs-summary', period],
    queryFn: () => fetchCostSummary({ period_days: period }),
    refetchInterval: 30_000,
  })

  const dailyQuery = useQuery({
    queryKey: ['costs-daily', period],
    queryFn: () => fetchCostDaily({ period_days: period }),
    refetchInterval: 30_000,
  })

  const summary: CostSummary | undefined = summaryQuery.data
  const dailyData: DailyCost[] = dailyQuery.data?.daily ?? []

  // Project monthly spend (annualise from period)
  const projectedMonthly = summary
    ? (summary.total_cost_usd / period) * 30
    : 0

  if (summaryQuery.isError) {
    return (
      <div className="p-6 text-red-500 text-sm">
        Could not reach costs API. Make sure the backend is running.
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header + period selector */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-800">Cost Tracker</h2>
        <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
          {PERIODS.map(p => (
            <button
              key={p.value}
              onClick={() => setPeriod(p.value)}
              className={`px-3 py-1 text-sm font-medium rounded-md transition-colors ${
                period === p.value
                  ? 'bg-white text-gray-800 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-xs text-gray-500 mb-1">Total Spend ({period}d)</div>
          <div className="text-2xl font-bold text-gray-800 tabular-nums">
            {summaryQuery.isLoading ? '—' : fmt(summary?.total_cost_usd ?? 0)}
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-xs text-gray-500 mb-1">Est. Monthly</div>
          <div className="text-2xl font-bold text-gray-800 tabular-nums">
            {summaryQuery.isLoading ? '—' : fmt(projectedMonthly)}
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-xs text-gray-500 mb-1">Total Calls</div>
          <div className="text-2xl font-bold text-gray-800 tabular-nums">
            {summaryQuery.isLoading ? '—' : fmtK(summary?.total_calls ?? 0)}
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-xs text-gray-500 mb-1">Avg Cost / Call</div>
          <div className="text-2xl font-bold text-gray-800 tabular-nums">
            {summaryQuery.isLoading ? '—' : fmt(summary?.avg_cost_per_call ?? 0)}
          </div>
        </div>
      </div>

      {/* Daily cost chart */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Daily Cost ({period}d)</h3>
        {dailyQuery.isLoading ? (
          <div className="h-32 flex items-center justify-center text-sm text-gray-400">Loading…</div>
        ) : (
          <DailyBarChart data={dailyData} />
        )}
        <p className="text-xs text-gray-400 mt-2">
          Hover a bar to see exact cost and call count for that day.
          Costs are estimated — CLI providers do not expose exact token counts.
        </p>
      </div>

      {/* Top solutions by cost */}
      {summary && summary.by_solution.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Top Solutions by Cost</h3>
          <div className="space-y-3">
            {summary.by_solution.map((s: CostBySolution) => {
              const pct = summary.total_cost_usd > 0
                ? Math.min(100, Math.round((s.cost / summary.total_cost_usd) * 100))
                : 0
              return (
                <div key={s.solution}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-700 font-medium truncate max-w-[200px]">
                      {s.solution || 'default'}
                    </span>
                    <span className="text-gray-500 tabular-nums ml-2">
                      {fmt(s.cost)} ({s.calls} calls)
                    </span>
                  </div>
                  <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-400 rounded-full"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Model breakdown */}
      {summary && summary.by_model.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Cost by Model</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-500 border-b border-gray-100">
                <th className="text-left pb-2 font-medium">Model</th>
                <th className="text-right pb-2 font-medium">Calls</th>
                <th className="text-right pb-2 font-medium">Cost</th>
              </tr>
            </thead>
            <tbody>
              {summary.by_model.map(m => (
                <tr key={m.model} className="border-b border-gray-50 last:border-0">
                  <td className="py-2 text-gray-700 font-mono text-xs">{m.model || 'unknown'}</td>
                  <td className="py-2 text-right text-gray-500 tabular-nums">{fmtK(m.calls)}</td>
                  <td className="py-2 text-right text-gray-700 tabular-nums font-medium">{fmt(m.cost)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Token totals */}
      {summary && summary.total_calls > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Token Usage ({period}d)</h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-gray-50 rounded-lg p-3 text-center">
              <div className="text-xl font-bold text-gray-800 tabular-nums">
                {fmtK(summary.total_input_tokens)}
              </div>
              <div className="text-xs text-gray-500 mt-0.5">Input Tokens</div>
            </div>
            <div className="bg-gray-50 rounded-lg p-3 text-center">
              <div className="text-xl font-bold text-gray-800 tabular-nums">
                {fmtK(summary.total_output_tokens)}
              </div>
              <div className="text-xs text-gray-500 mt-0.5">Output Tokens</div>
            </div>
          </div>
          <p className="text-xs text-gray-400 mt-3">
            Token counts are estimated at 1 token per 4 characters.
            API providers with native token reporting will produce exact figures.
          </p>
        </div>
      )}

      {/* Zero state */}
      {!summaryQuery.isLoading && summary?.total_calls === 0 && (
        <div className="bg-gray-50 rounded-xl border border-gray-200 p-8 text-center">
          <div className="text-gray-400 text-sm">
            No LLM calls recorded in the last {period} days.
          </div>
          <div className="text-gray-400 text-xs mt-1">
            Cost tracking activates automatically on the next LLM call.
          </div>
        </div>
      )}
    </div>
  )
}
