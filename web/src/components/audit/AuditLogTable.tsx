import type { AuditEntry } from '../../api/client'

interface Props {
  entries: AuditEntry[]
  total: number
  page: number
  onPage: (p: number) => void
  onSelect: (e: AuditEntry) => void
  limit: number
}

export default function AuditLogTable({ entries, total, page, onPage, onSelect, limit }: Props) {
  const totalPages = Math.ceil(total / limit)
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b border-gray-200">
          <tr>
            <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Timestamp</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Actor</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Action Type</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Trace ID</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {entries.map((entry) => (
            <tr key={entry.id} onClick={() => onSelect(entry)}
              className="hover:bg-gray-50 cursor-pointer transition-colors">
              <td className="px-4 py-3 text-gray-600 whitespace-nowrap">{new Date(entry.timestamp).toLocaleString()}</td>
              <td className="px-4 py-3 text-gray-800 font-medium">{entry.actor}</td>
              <td className="px-4 py-3"><span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">{entry.action_type}</span></td>
              <td className="px-4 py-3 font-mono text-xs text-gray-400">{entry.id?.slice(0, 12)}…</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100">
        <span className="text-xs text-gray-500">Showing {entries.length} of {total} entries</span>
        <div className="flex gap-2">
          <button disabled={page === 0} onClick={() => onPage(page - 1)}
            className="text-xs px-3 py-1.5 border rounded disabled:opacity-40">Previous</button>
          <span className="text-xs px-2 py-1.5 text-gray-500">{page + 1} / {totalPages || 1}</span>
          <button disabled={(page + 1) >= totalPages} onClick={() => onPage(page + 1)}
            className="text-xs px-3 py-1.5 border rounded disabled:opacity-40">Next</button>
        </div>
      </div>
    </div>
  )
}
