import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { fetchCostSummary, fetchCostDaily, setCostBudget, fetchRoutingStats } from '../api/client'
import type { CostSummary, DailyCost, CostBySolution } from '../types/module'
import { DollarSign, TrendingUp, Phone, Calculator, Settings, Check } from 'lucide-react'

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

// ---------------------------------------------------------------------------
// Inline SVG bar chart (dark theme)
// ---------------------------------------------------------------------------
function DailyBarChart({ data }: { data: DailyCost[] }) {
  if (!data || data.length === 0) {
    return (
      <div style={{ height: 128, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, color: '#9ca3af' }}>
        No data for this period
      </div>
    )
  }

  const maxCost = Math.max(...data.map(d => d.cost_usd), 0.000001)
  const chartH = 80
  const barW = Math.max(4, Math.floor(420 / data.length) - 2)

  return (
    <div style={{ overflowX: 'auto' }}>
      <svg
        width={Math.max(420, data.length * (barW + 2))}
        height={chartH + 28}
        style={{ display: 'block' }}
      >
        {data.map((d, i) => {
          const h = Math.max(2, Math.round((d.cost_usd / maxCost) * chartH))
          const x = i * (barW + 2)
          const y = chartH - h
          return (
            <g key={d.date}>
              <rect x={x} y={y} width={barW} height={h} rx={2} fill="#3b82f6" opacity={0.8}>
                <title>{d.date}: {fmt(d.cost_usd)} ({d.calls} calls)</title>
              </rect>
              {data.length <= 14 && (
                <text x={x + barW / 2} y={chartH + 14} textAnchor="middle" fontSize="9" fill="#52525b">
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
  const [budgetAmount, setBudgetAmount] = useState('')
  const [budgetSolution, setBudgetSolution] = useState('')

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

  const budgetMutation = useMutation({
    mutationFn: () => setCostBudget({
      monthly_usd: parseFloat(budgetAmount),
      ...(budgetSolution ? { solution: budgetSolution } : {}),
    }),
  })

  const routingQuery = useQuery({
    queryKey: ['routing-stats'],
    queryFn: fetchRoutingStats,
    refetchInterval: 30_000,
    retry: false,
  })

  const summary: CostSummary | undefined = summaryQuery.data
  const dailyData: DailyCost[] = dailyQuery.data?.daily ?? []

  const projectedMonthly = summary
    ? (summary.total_cost_usd / period) * 30
    : 0

  if (summaryQuery.isError) {
    return (
      <div style={{ padding: 24, color: '#ef4444', fontSize: 13 }}>
        Could not reach costs API. Make sure the backend is running.
      </div>
    )
  }

  const STAT_ITEMS = [
    { label: `Total Spend (${period}d)`, value: fmt(summary?.total_cost_usd ?? 0), color: '#e4e4e7' },
    { label: 'Est. Monthly', value: fmt(projectedMonthly), color: '#60a5fa' },
    { label: 'Total Calls', value: fmtK(summary?.total_calls ?? 0), color: '#a78bfa' },
    { label: 'Avg Cost/Call', value: fmt(summary?.avg_cost_per_call ?? 0), color: '#4ade80' },
  ]

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-lg font-semibold" style={{ color: '#e4e4e7', display: 'flex', alignItems: 'center', gap: 8 }}>
            <DollarSign size={18} style={{ color: '#22c55e' }} />
            Cost Tracker
          </h1>
          <p className="text-xs mt-1" style={{ color: '#9ca3af' }}>
            LLM usage costs, budget controls, and token analytics
          </p>
        </div>
        <div className="flex gap-1 p-1" style={{ background: '#ffffff', borderRadius: 8 }}>
          {PERIODS.map(p => (
            <button
              key={p.value}
              onClick={() => setPeriod(p.value)}
              style={{
                padding: '4px 12px', fontSize: 12, fontWeight: 500, borderRadius: 6, cursor: 'pointer', border: 'none',
                background: period === p.value ? '#d1d5db' : 'transparent',
                color: period === p.value ? '#f4f4f5' : '#71717a',
              }}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
        {STAT_ITEMS.map(s => (
          <div key={s.label} className="sage-card" style={{ background: '#ffffff', borderColor: '#e5e7eb', textAlign: 'center', padding: '16px 8px' }}>
            <div style={{ fontSize: 22, fontWeight: 700, color: s.color }}>
              {summaryQuery.isLoading ? '—' : s.value}
            </div>
            <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 2 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Daily chart */}
      <div className="sage-card mb-4" style={{ background: '#ffffff', borderColor: '#e5e7eb' }}>
        <h3 className="text-sm font-semibold mb-3" style={{ color: '#e4e4e7' }}>
          <TrendingUp size={14} className="inline mr-1.5" style={{ color: '#3b82f6' }} />
          Daily Cost ({period}d)
        </h3>
        {dailyQuery.isLoading ? (
          <div style={{ height: 128, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, color: '#9ca3af' }}>Loading...</div>
        ) : (
          <DailyBarChart data={dailyData} />
        )}
        <p className="text-xs mt-2" style={{ color: '#d1d5db' }}>
          Hover a bar to see exact cost and call count. Costs are estimated — CLI providers do not expose exact token counts.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        {/* Budget Controls */}
        <div className="sage-card" style={{ background: '#ffffff', borderColor: '#e5e7eb' }}>
          <h3 className="text-sm font-semibold mb-3" style={{ color: '#e4e4e7' }}>
            <Settings size={14} className="inline mr-1.5" style={{ color: '#f59e0b' }} />
            Monthly Budget
          </h3>
          <div className="space-y-3">
            <div>
              <label className="block text-xs mb-1" style={{ color: '#9ca3af' }}>Budget Amount (USD)</label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={budgetAmount}
                onChange={e => setBudgetAmount(e.target.value)}
                placeholder="e.g. 50.00"
                className="w-full text-sm px-3 py-2"
                style={{ background: '#111113', color: '#e4e4e7', border: '1px solid #e5e7eb', borderRadius: 8, outline: 'none' }}
              />
            </div>
            <div>
              <label className="block text-xs mb-1" style={{ color: '#9ca3af' }}>Solution (optional)</label>
              <input
                value={budgetSolution}
                onChange={e => setBudgetSolution(e.target.value)}
                placeholder="Leave blank for global budget"
                className="w-full text-sm px-3 py-2"
                style={{ background: '#111113', color: '#e4e4e7', border: '1px solid #e5e7eb', borderRadius: 8, outline: 'none' }}
              />
            </div>
            <button
              onClick={() => budgetMutation.mutate()}
              disabled={!budgetAmount || budgetMutation.isPending}
              className="sage-btn sage-btn-primary"
            >
              <Calculator size={12} />
              {budgetMutation.isPending ? 'Saving...' : 'Set Budget'}
            </button>
            {budgetMutation.isSuccess && (
              <div className="flex items-center gap-1 text-xs" style={{ color: '#22c55e' }}>
                <Check size={12} /> Budget set: ${budgetMutation.data?.monthly_usd}/mo
              </div>
            )}
            {budgetMutation.isError && (
              <div className="text-xs" style={{ color: '#ef4444' }}>
                {(budgetMutation.error as Error).message}
              </div>
            )}
          </div>
        </div>

        {/* Token Totals */}
        {summary && summary.total_calls > 0 && (
          <div className="sage-card" style={{ background: '#ffffff', borderColor: '#e5e7eb' }}>
            <h3 className="text-sm font-semibold mb-3" style={{ color: '#e4e4e7' }}>
              <Phone size={14} className="inline mr-1.5" style={{ color: '#6366f1' }} />
              Token Usage ({period}d)
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <div style={{ background: '#111113', borderRadius: 8, padding: 12, textAlign: 'center' }}>
                <div style={{ fontSize: 20, fontWeight: 700, color: '#e4e4e7' }}>{fmtK(summary.total_input_tokens)}</div>
                <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 2 }}>Input Tokens</div>
              </div>
              <div style={{ background: '#111113', borderRadius: 8, padding: 12, textAlign: 'center' }}>
                <div style={{ fontSize: 20, fontWeight: 700, color: '#e4e4e7' }}>{fmtK(summary.total_output_tokens)}</div>
                <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 2 }}>Output Tokens</div>
              </div>
            </div>
            <p className="text-xs mt-2" style={{ color: '#d1d5db' }}>
              Token counts estimated at 1 token per 4 characters.
            </p>
          </div>
        )}
      </div>

      {/* Top solutions by cost */}
      {summary && summary.by_solution.length > 0 && (
        <div className="sage-card mb-4" style={{ background: '#ffffff', borderColor: '#e5e7eb' }}>
          <h3 className="text-sm font-semibold mb-3" style={{ color: '#e4e4e7' }}>Top Solutions by Cost</h3>
          <div className="space-y-3">
            {summary.by_solution.map((s: CostBySolution) => {
              const pct = summary.total_cost_usd > 0
                ? Math.min(100, Math.round((s.cost / summary.total_cost_usd) * 100))
                : 0
              return (
                <div key={s.solution}>
                  <div className="flex justify-between text-xs mb-1">
                    <span style={{ color: '#e4e4e7', fontWeight: 500 }}>{s.solution || 'default'}</span>
                    <span style={{ color: '#9ca3af' }}>{fmt(s.cost)} ({s.calls} calls)</span>
                  </div>
                  <div style={{ height: 6, background: '#e5e7eb', borderRadius: 999, overflow: 'hidden' }}>
                    <div style={{ height: '100%', background: '#3b82f6', borderRadius: 999, width: `${pct}%` }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Model breakdown */}
      {summary && summary.by_model.length > 0 && (
        <div className="sage-card mb-4" style={{ background: '#ffffff', borderColor: '#e5e7eb' }}>
          <h3 className="text-sm font-semibold mb-3" style={{ color: '#e4e4e7' }}>Cost by Model</h3>
          <table className="sage-table">
            <thead>
              <tr>
                <th>Model</th>
                <th style={{ textAlign: 'right' }}>Calls</th>
                <th style={{ textAlign: 'right' }}>Cost</th>
              </tr>
            </thead>
            <tbody>
              {summary.by_model.map(m => (
                <tr key={m.model}>
                  <td style={{ color: '#e4e4e7', fontFamily: 'monospace', fontSize: 11 }}>{m.model || 'unknown'}</td>
                  <td style={{ textAlign: 'right', color: '#9ca3af' }}>{fmtK(m.calls)}</td>
                  <td style={{ textAlign: 'right', color: '#e4e4e7', fontWeight: 500 }}>{fmt(m.cost)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Complexity Routing Stats */}
      {routingQuery.data && routingQuery.data.total_classified > 0 && (
        <div className="sage-card" style={{ background: '#ffffff', borderColor: '#e5e7eb' }}>
          <h2 className="text-sm font-semibold mb-3" style={{ color: '#e4e4e7' }}>
            <TrendingUp size={14} className="inline mr-2" style={{ color: '#a78bfa' }} />
            Complexity Routing
          </h2>
          <div className="grid grid-cols-3 gap-3">
            {(['low', 'medium', 'high'] as const).map(level => {
              const count = routingQuery.data!.routing_stats[level] ?? 0
              const pct = routingQuery.data!.distribution[level] ?? 0
              const colors = { low: '#22c55e', medium: '#f59e0b', high: '#ef4444' }
              return (
                <div key={level} style={{ padding: '12px 16px', background: '#111113', borderRadius: 8, textAlign: 'center' }}>
                  <div style={{ fontSize: 20, fontWeight: 700, color: colors[level] }}>{fmtK(count)}</div>
                  <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 2 }}>{level.toUpperCase()} ({pct}%)</div>
                </div>
              )
            })}
          </div>
          <p style={{ fontSize: 11, color: '#9ca3af', marginTop: 8 }}>
            {routingQuery.data.total_classified} prompts classified across {Object.keys(routingQuery.data.routing_stats).length} complexity tiers
          </p>
        </div>
      )}

      {/* Zero state */}
      {!summaryQuery.isLoading && summary?.total_calls === 0 && (
        <div className="sage-empty">
          <DollarSign size={32} />
          <p className="text-sm">No LLM calls recorded in the last {period} days.</p>
          <p style={{ fontSize: 12, color: '#9ca3af' }}>Cost tracking activates automatically on the next LLM call.</p>
        </div>
      )}
    </div>
  )
}
