import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  fetchOrchestratorStats,
  fetchEventHistory,
  fetchBudgetOverview,
  fetchReflectionRecent,
  fetchSpawns,
  fetchToolHistory,
  fetchBacktrackRecords,
  fetchConsensusResults,
} from '../api/client'
import {
  Activity, DollarSign, RefreshCw, Brain, Wrench, GitBranch,
  Target, Users, Zap, ChevronDown, ChevronUp, Radio,
  TrendingUp, Shield, Clock, CheckCircle, XCircle, AlertTriangle,
} from 'lucide-react'

// ---------------------------------------------------------------------------
// Tab config
// ---------------------------------------------------------------------------
const TABS = [
  { id: 'overview', label: 'Overview', icon: Activity },
  { id: 'events', label: 'Live Events', icon: Radio },
  { id: 'budget', label: 'Budget', icon: DollarSign },
  { id: 'reflection', label: 'Reflection', icon: RefreshCw },
  { id: 'tools', label: 'Tools', icon: Wrench },
  { id: 'spawns', label: 'Agents', icon: GitBranch },
  { id: 'consensus', label: 'Consensus', icon: Users },
  { id: 'backtrack', label: 'Backtrack', icon: Target },
] as const

type TabId = typeof TABS[number]['id']

// ---------------------------------------------------------------------------
// Stat Card
// ---------------------------------------------------------------------------
function StatCard({ label, value, color, icon }: { label: string; value: string | number; color: string; icon: React.ReactNode }) {
  return (
    <div className="sage-card" style={{ background: '#ffffff', borderColor: '#e5e7eb', padding: '16px', textAlign: 'center' }}>
      <div style={{ color, marginBottom: 4 }}>{icon}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 2 }}>{label}</div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Overview Tab
// ---------------------------------------------------------------------------
function OverviewTab() {
  const { data: stats } = useQuery({
    queryKey: ['orchestrator-stats'],
    queryFn: fetchOrchestratorStats,
    refetchInterval: 5000,
  })

  if (!stats) return <LoadingSkeleton />

  const modules = [
    { name: 'Event Bus', data: stats.event_bus as Record<string, unknown> || {}, icon: <Radio size={14} />, color: '#60a5fa' },
    { name: 'Budget', data: stats.budget as Record<string, unknown> || {}, icon: <DollarSign size={14} />, color: '#4ade80' },
    { name: 'Reflection', data: stats.reflection as Record<string, unknown> || {}, icon: <RefreshCw size={14} />, color: '#a78bfa' },
    { name: 'Plan Selector', data: stats.plan_selector as Record<string, unknown> || {}, icon: <Brain size={14} />, color: '#facc15' },
    { name: 'Agent Spawner', data: stats.spawner as Record<string, unknown> || {}, icon: <GitBranch size={14} />, color: '#f97316' },
    { name: 'Tools', data: stats.tools as Record<string, unknown> || {}, icon: <Wrench size={14} />, color: '#2dd4bf' },
    { name: 'Backtrack', data: stats.backtrack as Record<string, unknown> || {}, icon: <Target size={14} />, color: '#f87171' },
    { name: 'Consensus', data: stats.consensus as Record<string, unknown> || {}, icon: <Users size={14} />, color: '#818cf8' },
    { name: 'Memory Planner', data: stats.memory_planner as Record<string, unknown> || {}, icon: <Brain size={14} />, color: '#fb923c' },
  ]

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
      {modules.map(m => (
        <div key={m.name} className="sage-card" style={{ background: '#ffffff', borderColor: '#e5e7eb', padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span style={{ color: m.color }}>{m.icon}</span>
            <span style={{ fontSize: 13, fontWeight: 600, color: '#e4e4e7' }}>{m.name}</span>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {Object.entries(m.data).slice(0, 4).map(([k, v]) => (
              <div key={k} style={{ fontSize: 11 }}>
                <span style={{ color: '#9ca3af' }}>{k.replace(/_/g, ' ')}: </span>
                <span style={{ color: '#e4e4e7', fontWeight: 500 }}>
                  {typeof v === 'number' ? (v % 1 === 0 ? v : (v as number).toFixed(3)) : String(v)}
                </span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Events Tab (Live SSE)
// ---------------------------------------------------------------------------
function EventsTab() {
  const [events, setEvents] = useState<unknown[]>([])
  const [connected, setConnected] = useState(false)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    const es = new EventSource('/api/orchestrator/events/stream')
    esRef.current = es
    es.onopen = () => setConnected(true)
    es.onerror = () => setConnected(false)
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        setEvents(prev => [data, ...prev].slice(0, 100))
      } catch {}
    }
    // Listen to all event types
    const types = ['task.started', 'task.completed', 'task.failed', 'budget.usage',
      'budget.warning', 'reflection.iteration', 'consensus.vote', 'agent.spawned']
    types.forEach(t => {
      es.addEventListener(t, (evt) => {
        try {
          const data = JSON.parse((evt as MessageEvent).data)
          setEvents(prev => [data, ...prev].slice(0, 100))
        } catch {}
      })
    })
    return () => es.close()
  }, [])

  // Also load history on mount
  const { data: historyData } = useQuery({
    queryKey: ['event-history'],
    queryFn: () => fetchEventHistory('', 50),
  })

  const allEvents = events.length > 0 ? events : (historyData?.events || [])

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <span style={{
          width: 8, height: 8, borderRadius: '50%',
          background: connected ? '#4ade80' : '#f87171',
          display: 'inline-block',
        }} />
        <span style={{ fontSize: 12, color: connected ? '#4ade80' : '#f87171' }}>
          {connected ? 'Connected' : 'Connecting...'}
        </span>
        <span style={{ fontSize: 11, color: '#9ca3af', marginLeft: 'auto' }}>
          {allEvents.length} events
        </span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 500, overflow: 'auto' }}>
        {(allEvents as Record<string, unknown>[]).map((evt, i) => (
          <div key={i} className="sage-card" style={{ background: '#ffffff', borderColor: '#e5e7eb', padding: '8px 12px', fontSize: 11 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="sage-tag" style={{ fontSize: 9 }}>{String(evt.type || evt.event_type || 'event')}</span>
              <span style={{ color: '#9ca3af', fontFamily: 'monospace' }}>{String(evt.timestamp || '').slice(11, 19)}</span>
              <span style={{ color: '#6b7280', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {JSON.stringify(evt.data || {}).slice(0, 120)}
              </span>
            </div>
          </div>
        ))}
        {allEvents.length === 0 && (
          <div className="sage-empty" style={{ padding: 32 }}>
            <Radio size={24} />
            <p style={{ fontSize: 12, color: '#9ca3af' }}>No events yet. Activity will appear here in real-time.</p>
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Budget Tab
// ---------------------------------------------------------------------------
function BudgetTab() {
  const { data } = useQuery({
    queryKey: ['budget-overview'],
    queryFn: fetchBudgetOverview,
    refetchInterval: 5000,
  })

  if (!data) return <LoadingSkeleton />

  const stats = data.stats as Record<string, unknown>
  const consumers = (data.top_consumers || []) as Record<string, unknown>[]

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 16 }}>
        <StatCard label="Tracked Scopes" value={stats.tracked_scopes as number || 0} color="#60a5fa" icon={<Shield size={16} />} />
        <StatCard label="Total Tokens" value={(stats.total_tokens as number || 0).toLocaleString()} color="#4ade80" icon={<Zap size={16} />} />
        <StatCard label="Total Cost" value={`$${((stats.total_cost_usd as number) || 0).toFixed(4)}`} color="#facc15" icon={<DollarSign size={16} />} />
        <StatCard label="Total Calls" value={stats.total_calls as number || 0} color="#a78bfa" icon={<Activity size={16} />} />
      </div>
      <h3 style={{ fontSize: 13, fontWeight: 600, color: '#e4e4e7', marginBottom: 8 }}>Top Consumers</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {consumers.map((c, i) => (
          <div key={i} className="sage-card" style={{ background: '#ffffff', borderColor: '#e5e7eb', padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#e4e4e7', minWidth: 120 }}>{String(c.scope)}</span>
            <span style={{ fontSize: 11, color: '#9ca3af' }}>{(c.total_tokens as number || 0).toLocaleString()} tokens</span>
            <span style={{ fontSize: 11, color: '#facc15' }}>${((c.estimated_cost_usd as number) || 0).toFixed(4)}</span>
            <span style={{ fontSize: 11, color: '#6b7280', marginLeft: 'auto' }}>{c.call_count as number || 0} calls</span>
          </div>
        ))}
        {consumers.length === 0 && <EmptyState text="No usage recorded yet." />}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Reflection Tab
// ---------------------------------------------------------------------------
function ReflectionTab() {
  const { data } = useQuery({
    queryKey: ['reflection-recent'],
    queryFn: () => fetchReflectionRecent(20),
    refetchInterval: 5000,
  })

  const results = (data?.results || []) as Record<string, unknown>[]

  return (
    <div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {results.map((r, i) => (
          <div key={i} className="sage-card" style={{ background: '#ffffff', borderColor: '#e5e7eb', padding: '12px 16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {r.accepted ? <CheckCircle size={14} style={{ color: '#4ade80' }} /> : <XCircle size={14} style={{ color: '#f87171' }} />}
              <span style={{ fontSize: 12, fontWeight: 500, color: '#e4e4e7' }}>
                {r.accepted ? 'Accepted' : 'Rejected'} after {r.iterations as number} iterations
              </span>
              <span className="sage-tag" style={{ fontSize: 9, background: 'rgba(139,92,246,0.1)', color: '#a78bfa' }}>
                Score: {((r.final_score as number) || 0).toFixed(2)}
              </span>
              <span style={{ fontSize: 10, color: '#9ca3af', marginLeft: 'auto' }}>{String(r.started_at || '').slice(0, 19)}</span>
            </div>
          </div>
        ))}
        {results.length === 0 && <EmptyState text="No reflections yet. The reflection engine activates when critic scores are below threshold." />}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tools Tab
// ---------------------------------------------------------------------------
function ToolsTab() {
  const { data: historyData } = useQuery({
    queryKey: ['tool-history'],
    queryFn: () => fetchToolHistory(50),
    refetchInterval: 5000,
  })

  const history = (historyData?.history || []) as Record<string, unknown>[]

  return (
    <div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {history.map((h, i) => (
          <div key={i} className="sage-card" style={{ background: '#ffffff', borderColor: '#e5e7eb', padding: '8px 16px', fontSize: 11 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="sage-tag" style={{ fontSize: 9 }}>{String(h.tool_name)}</span>
              {h.error ? (
                <XCircle size={10} style={{ color: '#f87171' }} />
              ) : (
                <CheckCircle size={10} style={{ color: '#4ade80' }} />
              )}
              <span style={{ color: '#9ca3af' }}>{h.duration_ms as number}ms</span>
              <span style={{ color: '#6b7280', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {h.error ? String(h.error) : String(h.result).slice(0, 80)}
              </span>
            </div>
          </div>
        ))}
        {history.length === 0 && <EmptyState text="No tool calls yet. Agents will use tools during task execution." />}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Spawns Tab
// ---------------------------------------------------------------------------
function SpawnsTab() {
  const { data } = useQuery({
    queryKey: ['agent-spawns'],
    queryFn: () => fetchSpawns(50),
    refetchInterval: 5000,
  })

  const spawns = (data?.spawns || []) as Record<string, unknown>[]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {spawns.map((s, i) => (
        <div key={i} className="sage-card" style={{ background: '#ffffff', borderColor: '#e5e7eb', padding: '12px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <GitBranch size={14} style={{ color: '#f97316' }} />
            <span style={{ fontSize: 12, fontWeight: 500, color: '#e4e4e7' }}>{String(s.role)}</span>
            <span className="sage-tag" style={{
              fontSize: 9,
              background: s.status === 'completed' ? 'rgba(34,197,94,0.1)' : s.status === 'failed' ? 'rgba(239,68,68,0.1)' : 'rgba(59,130,246,0.1)',
              color: s.status === 'completed' ? '#4ade80' : s.status === 'failed' ? '#f87171' : '#60a5fa',
            }}>{String(s.status)}</span>
            <span style={{ fontSize: 11, color: '#6b7280' }}>depth: {s.depth as number}</span>
            <span style={{ fontSize: 10, color: '#9ca3af', marginLeft: 'auto' }}>{String(s.spawned_at || '').slice(11, 19)}</span>
          </div>
          <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {String(s.task)}
          </div>
        </div>
      ))}
      {spawns.length === 0 && <EmptyState text="No agents spawned yet. Agents spawn sub-agents for recursive task decomposition." />}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Consensus Tab
// ---------------------------------------------------------------------------
function ConsensusTab() {
  const { data } = useQuery({
    queryKey: ['consensus-results'],
    queryFn: () => fetchConsensusResults(20),
    refetchInterval: 5000,
  })

  const results = (data?.results || []) as Record<string, unknown>[]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {results.map((r, i) => (
        <div key={i} className="sage-card" style={{ background: '#ffffff', borderColor: '#e5e7eb', padding: '12px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Users size={14} style={{ color: '#818cf8' }} />
            <span style={{ fontSize: 12, fontWeight: 500, color: '#e4e4e7' }}>{String(r.question).slice(0, 60)}</span>
            <span className="sage-tag" style={{ fontSize: 9 }}>{String(r.decision)}</span>
            <span style={{ fontSize: 11, color: '#9ca3af' }}>
              {((r.agreement_ratio as number) * 100).toFixed(0)}% agreement
            </span>
            {Boolean(r.needs_human) && (
              <span style={{ display: 'flex', alignItems: 'center', gap: 2, fontSize: 10, color: '#f97316' }}>
                <AlertTriangle size={10} /> Needs human
              </span>
            )}
          </div>
          <div style={{ display: 'flex', gap: 4, marginTop: 6 }}>
            {((r.votes || []) as Record<string, unknown>[]).map((v, j) => (
              <span key={j} className="sage-tag" style={{
                fontSize: 9,
                background: v.decision === 'approve' ? 'rgba(34,197,94,0.1)' : v.decision === 'reject' ? 'rgba(239,68,68,0.1)' : 'rgba(113,113,122,0.1)',
                color: v.decision === 'approve' ? '#4ade80' : v.decision === 'reject' ? '#f87171' : '#6b7280',
              }}>
                {String(v.voter)}: {String(v.decision)}
              </span>
            ))}
          </div>
        </div>
      ))}
      {results.length === 0 && <EmptyState text="No consensus rounds yet. Multi-agent voting activates for critical decisions." />}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Backtrack Tab
// ---------------------------------------------------------------------------
function BacktrackTab() {
  const { data } = useQuery({
    queryKey: ['backtrack-records'],
    queryFn: () => fetchBacktrackRecords(20),
    refetchInterval: 5000,
  })

  const records = (data?.records || []) as Record<string, unknown>[]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {records.map((r, i) => (
        <div key={i} className="sage-card" style={{ background: '#ffffff', borderColor: '#e5e7eb', padding: '12px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Target size={14} style={{ color: '#f87171' }} />
            <span style={{ fontSize: 12, fontWeight: 500, color: '#e4e4e7' }}>
              Task {String(r.failed_task_id).slice(0, 8)} ({String(r.failed_task_type)})
            </span>
            <span className="sage-tag" style={{
              fontSize: 9,
              background: r.status === 'replanned' ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
              color: r.status === 'replanned' ? '#4ade80' : '#f87171',
            }}>{String(r.status)}</span>
            <span style={{ fontSize: 11, color: '#9ca3af' }}>
              {r.original_plan_size as number} tasks replaced with {r.new_plan_size as number}
            </span>
          </div>
        </div>
      ))}
      {records.length === 0 && <EmptyState text="No backtracks yet. Backtracking activates when tasks fail repeatedly." />}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function LoadingSkeleton() {
  return (
    <div style={{ padding: '1rem' }}>
      {[1,2,3].map(i => (
        <div key={i} style={{
          height: '4rem', borderRadius: '0.5rem', marginBottom: '0.5rem',
          background: 'linear-gradient(90deg, #f3f4f6 25%, #e5e7eb 50%, #f3f4f6 75%)',
          backgroundSize: '200% 100%', animation: 'skeleton-shimmer 1.5s ease-in-out infinite',
        }} />
      ))}
      <style>{`@keyframes skeleton-shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }`}</style>
    </div>
  )
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="sage-empty" style={{ padding: 32 }}>
      <Activity size={24} />
      <p style={{ fontSize: 12, color: '#9ca3af' }}>{text}</p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------
export default function Orchestrator() {
  const [tab, setTab] = useState<TabId>('overview')

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-lg font-semibold" style={{ color: '#e4e4e7', display: 'flex', alignItems: 'center', gap: 8 }}>
          <Brain size={18} style={{ color: '#a78bfa' }} />
          Orchestrator Intelligence
        </h1>
        <p className="text-xs mt-1" style={{ color: '#9ca3af' }}>
          SOTA orchestration: reflection, consensus, beam search, budget controls, live events.
        </p>
      </div>

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16, overflowX: 'auto', paddingBottom: 4 }}>
        {TABS.map(t => {
          const Icon = t.icon
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                padding: '6px 14px', borderRadius: 999, fontSize: 11, fontWeight: 500, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 4,
                background: tab === t.id ? '#d1d5db' : 'transparent',
                color: tab === t.id ? '#f4f4f5' : '#71717a',
                border: tab === t.id ? 'none' : '1px solid #e5e7eb',
                whiteSpace: 'nowrap',
              }}
            >
              <Icon size={12} /> {t.label}
            </button>
          )
        })}
      </div>

      {/* Tab content */}
      {tab === 'overview' && <OverviewTab />}
      {tab === 'events' && <EventsTab />}
      {tab === 'budget' && <BudgetTab />}
      {tab === 'reflection' && <ReflectionTab />}
      {tab === 'tools' && <ToolsTab />}
      {tab === 'spawns' && <SpawnsTab />}
      {tab === 'consensus' && <ConsensusTab />}
      {tab === 'backtrack' && <BacktrackTab />}
    </div>
  )
}
