import { useQuery } from '@tanstack/react-query'
import { Users } from 'lucide-react'
import { fetchAgentStatuses, type AgentStatus } from '../api/client'

// ---------------------------------------------------------------------------
// Founder node (always at top)
// ---------------------------------------------------------------------------
function FounderNode() {
  return (
    <div
      className="flex flex-col items-center gap-1.5 px-4 py-3 w-36"
      style={{ border: '1px solid #f4f4f5', backgroundColor: '#ffffff' }}
    >
      <div
        className="flex items-center justify-center text-sm font-bold w-10 h-10"
        style={{ backgroundColor: '#f4f4f5', color: '#fafafa' }}
      >
        F
      </div>
      <div className="text-xs font-semibold text-center" style={{ color: '#374151' }}>Founder</div>
      <div className="text-xs" style={{ color: '#9ca3af' }}>Human</div>
      <span
        className="text-xs px-1.5 py-0.5 font-medium"
        style={{ backgroundColor: '#14532d22', color: '#22c55e' }}
      >
        In Control
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Agent node
// ---------------------------------------------------------------------------
const ROLE_INITIALS: Record<string, string> = {
  Analyst:      'An',
  Developer:    'Dv',
  Monitor:      'Mo',
  Planner:      'Pl',
  Universal:    'Uv',
  'SWE Engineer': 'SW',
}

const STATUS_DOT: Record<AgentStatus['status'], string> = {
  active: '#22c55e',
  idle:   '#52525b',
  error:  '#ef4444',
}

const STATUS_LABEL: Record<AgentStatus['status'], string> = {
  active: 'Active',
  idle:   'Idle',
  error:  'Error',
}

function AgentNode({ agent }: { agent: AgentStatus }) {
  const initial = ROLE_INITIALS[agent.role] ?? agent.role.slice(0, 2)
  const dotColor = STATUS_DOT[agent.status]

  return (
    <div
      className="flex flex-col items-center gap-1.5 px-4 py-3 w-36"
      style={{ border: '1px solid #d1d5db', backgroundColor: '#ffffff' }}
    >
      {/* Avatar */}
      <div className="relative">
        <div
          className="flex items-center justify-center text-sm font-bold w-10 h-10"
          style={{ backgroundColor: '#e5e7eb', color: '#6b7280' }}
        >
          {initial}
        </div>
        {/* Status dot */}
        <span
          className="absolute bottom-0 right-0 w-2.5 h-2.5"
          style={{ backgroundColor: dotColor, border: '2px solid #ffffff' }}
        />
      </div>

      {/* Role name */}
      <div className="text-xs font-semibold text-center" style={{ color: '#374151' }}>
        {agent.role}
      </div>

      {/* Status badge */}
      <div className="flex items-center gap-1">
        <span
          className="w-1.5 h-1.5"
          style={{ backgroundColor: dotColor, display: 'inline-block' }}
        />
        <span className="text-xs" style={{ color: '#9ca3af' }}>{STATUS_LABEL[agent.status]}</span>
      </div>

      {/* Last task / task count */}
      {agent.last_task ? (
        <div
          className="text-xs text-center line-clamp-2 mt-0.5"
          style={{ color: '#9ca3af' }}
          title={agent.last_task}
        >
          {agent.last_task}
        </div>
      ) : (
        <div className="text-xs" style={{ color: '#d1d5db' }}>No tasks yet</div>
      )}

      {typeof agent.task_count_today === 'number' && agent.task_count_today > 0 && (
        <span
          className="text-xs px-1.5 py-0.5 font-mono"
          style={{ backgroundColor: '#e5e7eb', color: '#9ca3af' }}
        >
          {agent.task_count_today} today
        </span>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Connector line between rows
// ---------------------------------------------------------------------------
function ConnectorTree({ count }: { count: number }) {
  if (count === 0) return null
  return (
    <div className="flex items-start justify-center">
      {/* Vertical stem from founder */}
      <div
        className="w-px"
        style={{ height: '24px', backgroundColor: '#d1d5db' }}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Static fallback for known SAGE roles (in case API is down)
// ---------------------------------------------------------------------------
const DEFAULT_ROLES: AgentStatus[] = [
  { role: 'Analyst',      status: 'idle', task_count_today: 0 },
  { role: 'Developer',    status: 'idle', task_count_today: 0 },
  { role: 'Monitor',      status: 'idle', task_count_today: 0 },
  { role: 'Planner',      status: 'idle', task_count_today: 0 },
  { role: 'SWE Engineer', status: 'idle', task_count_today: 0 },
  { role: 'Universal',    status: 'idle', task_count_today: 0 },
]

// ---------------------------------------------------------------------------
// OrgChart page
// ---------------------------------------------------------------------------
export default function OrgChart() {
  const { data: agents, isLoading } = useQuery({
    queryKey: ['agent-statuses'],
    queryFn: fetchAgentStatuses,
    refetchInterval: 15_000,
    staleTime: 10_000,
  })

  const roleList = (agents && agents.length > 0) ? agents : DEFAULT_ROLES

  // Split into two rows for the visual tree
  const row1 = roleList.slice(0, 3)
  const row2 = roleList.slice(3)

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Page header */}
      <div className="flex items-center gap-2">
        <Users size={18} style={{ color: '#9ca3af' }} />
        <h1 className="text-base font-semibold" style={{ color: '#374151' }}>Org Chart</h1>
        <span className="text-xs ml-auto" style={{ color: '#9ca3af' }}>
          {isLoading ? 'Loading…' : `${roleList.length} agents`}
        </span>
      </div>

      {/* Legend */}
      <div
        className="flex items-center gap-4 px-4 py-2 text-xs"
        style={{ backgroundColor: '#ffffff', border: '1px solid #e5e7eb' }}
      >
        {(['active', 'idle', 'error'] as const).map(s => (
          <div key={s} className="flex items-center gap-1.5">
            <span
              className="w-1.5 h-1.5"
              style={{ backgroundColor: STATUS_DOT[s], display: 'inline-block' }}
            />
            <span style={{ color: '#9ca3af' }}>{STATUS_LABEL[s]}</span>
          </div>
        ))}
      </div>

      {/* Tree */}
      <div className="flex flex-col items-center gap-0">
        {/* Founder */}
        <FounderNode />

        {/* Vertical connector */}
        <ConnectorTree count={roleList.length} />

        {/* Horizontal bar connecting to agents */}
        {roleList.length > 0 && (
          <div className="relative flex items-start justify-center w-full">
            {/* Horizontal line across all agent columns */}
            <div
              className="absolute top-0"
              style={{
                left: '50%',
                transform: 'translateX(-50%)',
                width: `${Math.min(roleList.length, 3) * 160}px`,
                height: '1px',
                backgroundColor: '#d1d5db',
              }}
            />

            {/* Row 1 agents */}
            <div className="flex flex-col items-center w-full gap-0">
              <div className="flex items-start justify-center gap-4 pt-6">
                {row1.map(agent => (
                  <div key={agent.role} className="flex flex-col items-center gap-0">
                    {/* Drop connector */}
                    <div
                      className="w-px"
                      style={{ height: '0px', backgroundColor: '#d1d5db' }}
                    />
                    <AgentNode agent={agent} />
                  </div>
                ))}
              </div>

              {row2.length > 0 && (
                <>
                  {/* Spacing between rows */}
                  <div style={{ height: '16px' }} />
                  {/* Second row */}
                  <div className="flex items-start justify-center gap-4">
                    {row2.map(agent => (
                      <AgentNode key={agent.role} agent={agent} />
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Stats row */}
      <div
        className="grid text-xs"
        style={{
          gridTemplateColumns: `repeat(${Math.min(roleList.length, 6)}, 1fr)`,
          border: '1px solid #e5e7eb',
          backgroundColor: '#fafafa',
        }}
      >
        {roleList.map((agent, i) => (
          <div
            key={agent.role}
            className="px-3 py-2.5 text-center"
            style={{
              borderRight: i < roleList.length - 1 ? '1px solid #e5e7eb' : 'none',
            }}
          >
            <div className="font-semibold" style={{ color: '#374151' }}>{agent.task_count_today ?? 0}</div>
            <div style={{ color: '#9ca3af' }}>{agent.role}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
