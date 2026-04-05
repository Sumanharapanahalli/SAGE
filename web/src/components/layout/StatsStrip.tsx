import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { fetchPendingProposals, fetchQueueTasks } from '../../api/client'
import Tooltip from './Tooltip'

export default function StatsStrip() {
  const navigate = useNavigate()

  const { data: approvalsData } = useQuery({
    queryKey: ['proposals-pending'],
    queryFn: fetchPendingProposals,
    refetchInterval: 10_000,
  })

  const { data: queueData } = useQuery({
    queryKey: ['queue-tasks-sidebar'],
    queryFn: () => fetchQueueTasks(),
    refetchInterval: 10_000,
  })

  const approvalsCount = approvalsData?.count ?? 0
  const queuedCount = (queueData ?? []).filter(
    t => t.status === 'pending' || t.status === 'in_progress'
  ).length
  const agentsCount = (queueData ?? []).filter(t => t.status === 'in_progress').length

  const tiles = [
    { label: 'APPROVALS', count: approvalsCount, color: '#ef4444', route: '/approvals', tooltip: 'Proposals waiting for your sign-off' },
    { label: 'QUEUED',    count: queuedCount,    color: '#f59e0b', route: '/queue',     tooltip: 'Tasks in queue or actively running' },
    { label: 'AGENTS',    count: agentsCount,    color: '#f97316', route: '/queue',     tooltip: 'Agent tasks currently in progress' },
  ]

  return (
    <div style={{ display: 'flex', borderBottom: '1px solid #1e293b' }}>
      {tiles.map(({ label, count, color, route, tooltip }) => (
        <Tooltip key={label} text={tooltip} side="bottom">
          <button
            onClick={() => navigate(route)}
            style={{
              flex: 1,
              padding: '8px 4px',
              textAlign: 'center',
              background: 'transparent',
              border: 'none',
              borderRight: label !== 'AGENTS' ? '1px solid #1e293b' : 'none',
              cursor: 'pointer',
            }}
          >
            <div style={{ fontSize: '16px', fontWeight: 700, color, lineHeight: 1 }}>
              {count}
            </div>
            <div style={{ fontSize: '9px', color: '#475569', marginTop: '2px', letterSpacing: '0.05em' }}>
              {label}
            </div>
          </button>
        </Tooltip>
      ))}
    </div>
  )
}
