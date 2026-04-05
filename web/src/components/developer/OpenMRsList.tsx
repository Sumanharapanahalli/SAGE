import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchOpenMRs, type MRItem } from '../../api/client'
import { ExternalLink } from 'lucide-react'

const PIPELINE_BADGE: Record<string, string> = {
  success: 'bg-orange-100 text-orange-700',
  failed: 'bg-red-100 text-red-700',
  running: 'bg-blue-100 text-blue-700',
  pending: 'bg-amber-100 text-amber-700',
  none: 'bg-gray-100 text-gray-500',
}

export default function OpenMRsList() {
  const [projectId, setProjectId] = useState('')
  const [search, setSearch] = useState('')

  const { data, isFetching, refetch } = useQuery({
    queryKey: ['open-mrs', projectId],
    queryFn: () => fetchOpenMRs(Number(projectId)),
    enabled: false,
  })

  const mrs: MRItem[] = (data?.merge_requests ?? []).filter((mr) =>
    mr.title.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">Open Merge Requests</h2>
      <div className="flex gap-2 mb-3">
        <input type="number" value={projectId} onChange={(e) => setProjectId(e.target.value)}
          className="w-28 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500" placeholder="Project ID" />
        <button onClick={() => refetch()} disabled={!projectId || isFetching}
          className="bg-orange-600 hover:bg-orange-700 disabled:opacity-50 text-white text-sm px-3 py-2 rounded-lg transition-colors">
          {isFetching ? 'Loading...' : 'Load'}
        </button>
        {data && (
          <input type="text" value={search} onChange={(e) => setSearch(e.target.value)}
            className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none" placeholder="Filter by title..." />
        )}
      </div>
      {mrs.length > 0 && (
        <div className="space-y-2">
          {mrs.map((mr) => (
            <div key={mr.iid} className="flex items-center gap-3 p-3 border border-gray-100 rounded-lg">
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-gray-800 truncate">!{mr.iid} {mr.title}</div>
                <div className="text-xs text-gray-400">{mr.author} · {mr.source_branch} → {mr.target_branch}</div>
              </div>
              <span className={`text-xs px-2 py-0.5 rounded font-medium ${PIPELINE_BADGE[mr.pipeline_status] ?? PIPELINE_BADGE.none}`}>
                {mr.pipeline_status}
              </span>
              <a href={mr.web_url} target="_blank" rel="noreferrer" className="text-gray-400 hover:text-gray-700">
                <ExternalLink size={14} />
              </a>
            </div>
          ))}
        </div>
      )}
      {data && mrs.length === 0 && <p className="text-sm text-gray-400">No open MRs found.</p>}
    </div>
  )
}
