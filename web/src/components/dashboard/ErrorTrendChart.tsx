import { useMemo } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import type { AuditEntry } from '../../api/client'

interface Props { entries: AuditEntry[] }

export default function ErrorTrendChart({ entries }: Props) {
  const data = useMemo(() => {
    const counts: Record<string, number> = {}
    entries
      .filter((e) => e.action_type.includes('ANALYSIS') || e.action_type.includes('FAILED'))
      .forEach((e) => {
        const hour = new Date(e.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        counts[hour] = (counts[hour] ?? 0) + 1
      })
    return Object.entries(counts).map(([time, count]) => ({ time, count })).slice(-12)
  }, [entries])

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">Error Trend (last 24h)</h2>
      {data.length === 0 ? (
        <p className="text-sm text-gray-400">No error events in audit log.</p>
      ) : (
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="time" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
            <Tooltip />
            <Line type="monotone" dataKey="count" stroke="#16a34a" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
