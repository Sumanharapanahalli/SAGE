import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchAudit, type AuditEntry } from '../api/client'
import AuditLogTable from '../components/audit/AuditLogTable'
import TraceDetailModal from '../components/audit/TraceDetailModal'
import ModuleWrapper from '../components/shared/ModuleWrapper'
import { Download, Loader2 } from 'lucide-react'

const LIMIT = 50

function exportCsv(entries: AuditEntry[]) {
  const headers = ['id', 'timestamp', 'actor', 'action_type']
  const rows = entries.map((e) => headers.map((h) => JSON.stringify((e as unknown as Record<string, unknown>)[h] ?? '')).join(','))
  const csv = [headers.join(','), ...rows].join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = 'sage-audit.csv'; a.click()
  URL.revokeObjectURL(url)
}

export default function AuditLog() {
  const [page, setPage] = useState(0)
  const [filter, setFilter] = useState('')
  const [selected, setSelected] = useState<AuditEntry | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['audit', page],
    queryFn: () => fetchAudit(LIMIT, page * LIMIT),
    refetchInterval: 60_000,
  })

  const entries = (data?.entries ?? []).filter((e) =>
    !filter || e.actor.toLowerCase().includes(filter.toLowerCase()) || e.action_type.toLowerCase().includes(filter.toLowerCase())
  )

  return (
    <ModuleWrapper moduleId="audit">
      <div className="space-y-4">
        <div className="flex gap-3 items-center">
          <input
            type="text" value={filter} onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter by actor or action type..."
            className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500"
          />
          <button onClick={() => exportCsv(data?.entries ?? [])}
            className="flex items-center gap-2 border border-gray-200 text-gray-600 hover:bg-gray-50 text-sm px-3 py-2 rounded-lg transition-colors">
            <Download size={14} /> Export CSV
          </button>
        </div>
        {isLoading ? (
          <div style={{ padding: '1rem' }}>
            {[1,2,3,4,5].map(i => (
              <div key={i} style={{
                height: '2.5rem', borderRadius: '0.375rem', marginBottom: '0.5rem',
                background: 'linear-gradient(90deg, #f3f4f6 25%, #e5e7eb 50%, #f3f4f6 75%)',
                backgroundSize: '200% 100%', animation: 'skeleton-shimmer 1.5s ease-in-out infinite',
              }} />
            ))}
            <style>{`@keyframes skeleton-shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }`}</style>
          </div>
        ) : (
          <AuditLogTable
            entries={entries}
            total={data?.total ?? 0}
            page={page}
            onPage={setPage}
            onSelect={setSelected}
            limit={LIMIT}
          />
        )}
        {selected && <TraceDetailModal entry={selected} onClose={() => setSelected(null)} />}
      </div>
    </ModuleWrapper>
  )
}
