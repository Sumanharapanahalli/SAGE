import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchQueueTasks, fetchTaskSubtasks } from '../api/client'
import type { QueueTask } from '../types/module'
import { Loader2, ChevronDown, ChevronUp, ListOrdered, Clock, CheckCircle, XCircle, Zap, GitBranch } from 'lucide-react'

// ---------------------------------------------------------------------------
// Task type badge colors (dark theme)
// ---------------------------------------------------------------------------
const TASK_TYPE_COLORS: Record<string, { bg: string; color: string }> = {
  ANALYZE:     { bg: 'rgba(59,130,246,0.1)', color: '#60a5fa' },
  ANALYZE_LOG: { bg: 'rgba(59,130,246,0.1)', color: '#60a5fa' },
  DEVELOP:     { bg: 'rgba(34,197,94,0.1)',  color: '#4ade80' },
  REVIEW:      { bg: 'rgba(234,179,8,0.1)',  color: '#facc15' },
  REVIEW_MR:   { bg: 'rgba(234,179,8,0.1)',  color: '#facc15' },
  TEST:        { bg: 'rgba(20,184,166,0.1)', color: '#2dd4bf' },
  DOCUMENT:    { bg: 'rgba(113,113,122,0.1)', color: '#6b7280' },
  PLAN:        { bg: 'rgba(139,92,246,0.1)', color: '#a78bfa' },
  PLAN_TASK:   { bg: 'rgba(139,92,246,0.1)', color: '#a78bfa' },
}

function taskTypeStyle(taskType: string) {
  return TASK_TYPE_COLORS[taskType.toUpperCase()] ?? { bg: 'rgba(113,113,122,0.1)', color: '#6b7280' }
}

// ---------------------------------------------------------------------------
// Status styling
// ---------------------------------------------------------------------------
const STATUS_STYLES: Record<string, { bg: string; color: string }> = {
  pending:     { bg: 'rgba(113,113,122,0.15)', color: '#6b7280' },
  in_progress: { bg: 'rgba(59,130,246,0.15)',  color: '#60a5fa' },
  completed:   { bg: 'rgba(34,197,94,0.15)',   color: '#4ade80' },
  failed:      { bg: 'rgba(239,68,68,0.15)',   color: '#f87171' },
}

const STATUS_ICONS: Record<string, React.ReactNode> = {
  pending:     <Clock size={11} />,
  in_progress: <Zap size={11} className="animate-pulse" />,
  completed:   <CheckCircle size={11} />,
  failed:      <XCircle size={11} />,
}

// ---------------------------------------------------------------------------
// Filter pill
// ---------------------------------------------------------------------------
function FilterPill({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '4px 12px', borderRadius: 999, fontSize: 11, fontWeight: 500, cursor: 'pointer',
        background: active ? '#d1d5db' : 'transparent',
        color: active ? '#f4f4f5' : '#71717a',
        border: active ? 'none' : '1px solid #e5e7eb',
      }}
    >
      {label}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Task row
// ---------------------------------------------------------------------------
function TaskRow({ task }: { task: QueueTask }) {
  const [open, setOpen] = useState(false)
  const [showSubtasks, setShowSubtasks] = useState(false)
  const isSage = (task.source === 'sage') || (task.feature_scope === 'sage')
  const status = task.status ?? 'pending'
  const hasPayload = task.payload && Object.keys(task.payload).length > 0
  const tstyle = taskTypeStyle(task.task_type)
  const sstyle = STATUS_STYLES[status] ?? STATUS_STYLES.pending

  const { data: subtaskData } = useQuery({
    queryKey: ['task-subtasks', task.task_id],
    queryFn: () => fetchTaskSubtasks(task.task_id),
    enabled: showSubtasks,
    retry: false,
  })

  const subtasks: any[] = subtaskData?.subtasks ?? []

  return (
    <div className="sage-card" style={{
      background: '#ffffff', borderColor: '#e5e7eb', padding: 0, overflow: 'hidden',
      borderLeft: `3px solid ${isSage ? '#a78bfa' : '#f97316'}`,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '12px 16px' }}>
        <span className="sage-tag" style={{ fontSize: 9, background: isSage ? 'rgba(139,92,246,0.1)' : 'rgba(249,115,22,0.1)', color: isSage ? '#a78bfa' : '#fb923c', flexShrink: 0 }}>
          {isSage ? 'SAGE' : task.feature_scope ?? task.source ?? 'solution'}
        </span>
        <span className="sage-tag" style={{ fontSize: 9, background: tstyle.bg, color: tstyle.color, flexShrink: 0 }}>
          {task.task_type.replace('_', ' ')}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 500, color: '#e4e4e7', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {task.feature_title || `${task.task_id.slice(0, 8)}…`}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 2 }}>
            <span style={{ fontSize: 11, color: '#9ca3af', fontFamily: 'monospace' }}>{task.task_id.slice(0, 8)}</span>
            <span style={{ fontSize: 11, color: '#d1d5db' }}>·</span>
            <span style={{ fontSize: 11, color: '#9ca3af' }}>{new Date(task.created_at).toLocaleString()}</span>
          </div>
          {task.error && (
            <div style={{ marginTop: 4, fontSize: 11, color: '#f87171', background: 'rgba(239,68,68,0.1)', padding: '4px 8px', borderRadius: 4 }}>
              {task.error}
            </div>
          )}
        </div>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, padding: '3px 10px', borderRadius: 999, background: sstyle.bg, color: sstyle.color, fontWeight: 500, flexShrink: 0 }}>
          {STATUS_ICONS[status]} {status.replace('_', ' ')}
        </span>
        <button onClick={() => setShowSubtasks(v => !v)} title="Subtasks" style={{ background: 'none', border: 'none', color: showSubtasks ? '#60a5fa' : '#52525b', cursor: 'pointer' }}>
          <GitBranch size={14} />
        </button>
        {hasPayload && (
          <button onClick={() => setOpen(v => !v)} style={{ background: 'none', border: 'none', color: '#9ca3af', cursor: 'pointer' }}>
            {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        )}
      </div>
      {showSubtasks && (
        <div style={{ borderTop: '1px solid #e5e7eb', padding: '8px 16px 8px 40px', background: '#151517' }}>
          {subtasks.length > 0 ? subtasks.map((st: any, i: number) => (
            <div key={i} className="flex items-center gap-2 py-1" style={{ fontSize: 11 }}>
              <span style={{ color: st.status === 'completed' ? '#4ade80' : st.status === 'failed' ? '#f87171' : '#a1a1aa' }}>
                {st.status === 'completed' ? <CheckCircle size={10} /> : st.status === 'failed' ? <XCircle size={10} /> : <Clock size={10} />}
              </span>
              <span style={{ color: '#6b7280' }}>{st.description ?? st.task_type ?? `Subtask ${i + 1}`}</span>
              <span className="sage-tag" style={{ fontSize: 9 }}>{st.status ?? 'pending'}</span>
            </div>
          )) : (
            <span className="text-xs" style={{ color: '#9ca3af' }}>No subtasks</span>
          )}
        </div>
      )}
      {open && hasPayload && (
        <pre style={{ borderTop: '1px solid #e5e7eb', padding: '12px 16px', fontSize: 11, fontFamily: 'monospace', color: '#6b7280', background: '#111113', margin: 0, maxHeight: 160, overflow: 'auto', whiteSpace: 'pre-wrap' }}>
          {JSON.stringify(task.payload, null, 2)}
        </pre>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Queue page
// ---------------------------------------------------------------------------
type StatusFilter = 'all' | 'pending' | 'in_progress' | 'completed' | 'failed'
type SourceFilter = 'all' | 'sage' | 'solution'

export default function Queue() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('all')

  const queryParams: { status?: string; source?: string } = {}
  if (statusFilter !== 'all') queryParams.status = statusFilter
  if (sourceFilter !== 'all') queryParams.source = sourceFilter

  const { data: tasks, isLoading } = useQuery({
    queryKey: ['queue-tasks', statusFilter, sourceFilter],
    queryFn: () => fetchQueueTasks(queryParams),
    refetchInterval: 5000,
  })

  const allTasks: QueueTask[] = tasks ?? []

  const { data: allTasksData } = useQuery({
    queryKey: ['queue-tasks-all'],
    queryFn: () => fetchQueueTasks(),
    refetchInterval: 5000,
  })
  const fullList: QueueTask[] = allTasksData ?? []
  const stats = {
    total:       fullList.length,
    pending:     fullList.filter(t => t.status === 'pending').length,
    in_progress: fullList.filter(t => t.status === 'in_progress').length,
    completed:   fullList.filter(t => t.status === 'completed').length,
    failed:      fullList.filter(t => t.status === 'failed').length,
  }

  const STAT_ITEMS = [
    { label: 'Total',       value: stats.total,       color: '#e4e4e7' },
    { label: 'Pending',     value: stats.pending,     color: '#6b7280' },
    { label: 'In Progress', value: stats.in_progress, color: '#60a5fa' },
    { label: 'Completed',   value: stats.completed,   color: '#4ade80' },
    { label: 'Failed',      value: stats.failed,      color: '#f87171' },
  ]

  return (
    <div className="max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-lg font-semibold" style={{ color: '#e4e4e7', display: 'flex', alignItems: 'center', gap: 8 }}>
          <ListOrdered size={18} style={{ color: '#3b82f6' }} />
          Task Queue
        </h1>
        <p className="text-xs mt-1" style={{ color: '#9ca3af' }}>
          Queued tasks from approved plans. Auto-refreshes every 5s.
        </p>
      </div>

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 20 }}>
        {STAT_ITEMS.map(s => (
          <div key={s.label} className="sage-card" style={{ background: '#ffffff', borderColor: '#e5e7eb', textAlign: 'center', padding: '16px 8px' }}>
            <div style={{ fontSize: 24, fontWeight: 700, color: s.color }}>{s.value}</div>
            <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 2 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 16, alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          <span style={{ fontSize: 10, color: '#9ca3af', fontWeight: 600, textTransform: 'uppercase', marginRight: 4 }}>Status</span>
          {(['all', 'pending', 'in_progress', 'completed', 'failed'] as StatusFilter[]).map(f => (
            <FilterPill key={f} label={f === 'all' ? 'All' : f.replace('_', ' ')} active={statusFilter === f} onClick={() => setStatusFilter(f)} />
          ))}
        </div>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          <span style={{ fontSize: 10, color: '#9ca3af', fontWeight: 600, textTransform: 'uppercase', marginRight: 4 }}>Source</span>
          {(['all', 'sage', 'solution'] as SourceFilter[]).map(f => (
            <FilterPill key={f} label={f === 'all' ? 'All' : f === 'sage' ? 'SAGE' : 'Solution'} active={sourceFilter === f} onClick={() => setSourceFilter(f)} />
          ))}
        </div>
      </div>

      {/* Task list */}
      {isLoading ? (
        <div style={{ padding: '1rem' }}>
          {[1,2,3,4].map(i => (
            <div key={i} style={{
              height: '3rem', borderRadius: '0.5rem', marginBottom: '0.5rem',
              background: 'linear-gradient(90deg, #f3f4f6 25%, #e5e7eb 50%, #f3f4f6 75%)',
              backgroundSize: '200% 100%', animation: 'skeleton-shimmer 1.5s ease-in-out infinite',
            }} />
          ))}
          <style>{`@keyframes skeleton-shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }`}</style>
        </div>
      ) : allTasks.length === 0 ? (
        <div className="sage-empty">
          <ListOrdered size={32} />
          <p className="text-sm">No tasks found</p>
          <p style={{ fontSize: 12, color: '#9ca3af' }}>
            Tasks appear here when approved plans are executed.
            {(statusFilter !== 'all' || sourceFilter !== 'all') && ' Try removing your filters.'}
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {allTasks.map(task => (
            <TaskRow key={task.task_id} task={task} />
          ))}
        </div>
      )}
    </div>
  )
}
