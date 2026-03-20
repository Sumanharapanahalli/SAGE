import { useQuery } from '@tanstack/react-query'
import { fetchActiveAgents } from '../api/client'
import type { ActiveAgentEntry } from '../api/client'
import { Activity } from 'lucide-react'

export function ActiveAgentsPanel() {
  const { data } = useQuery({
    queryKey: ['activeAgents'],
    queryFn: fetchActiveAgents,
    refetchInterval: 3000,
  })

  const agents = data?.agents ?? []

  return (
    <div className="rounded-lg p-4" style={{ background: '#18181b', border: '1px solid #27272a' }}>
      <div className="flex items-center gap-2 mb-3">
        <Activity size={14} color="#71717a" />
        <span className="text-xs font-medium" style={{ color: '#71717a' }}>ACTIVE AGENTS</span>
        {agents.length > 0 && (
          <span className="ml-auto text-xs px-1.5 py-0.5 rounded" style={{ background: '#16a34a22', color: '#86efac' }}>
            {agents.length} running
          </span>
        )}
      </div>
      {agents.length === 0 ? (
        <p className="text-xs" style={{ color: '#52525b' }}>No active agents</p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {agents.map((a: ActiveAgentEntry) => (
            <li key={a.task_id} className="flex items-center gap-2 text-xs">
              <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: a.status === 'in_progress' ? '#22c55e' : '#eab308' }} />
              <span style={{ color: '#d4d4d8' }}>{a.task_type}</span>
              <span className="ml-auto" style={{ color: '#52525b' }}>{a.status}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
