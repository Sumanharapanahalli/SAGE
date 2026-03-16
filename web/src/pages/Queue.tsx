import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchQueueTasks } from '../api/client'
import type { QueueTask } from '../types/module'
import ModuleWrapper from '../components/shared/ModuleWrapper'
import { Loader2, ChevronDown, ChevronUp, ListOrdered, Clock, CheckCircle, XCircle, Zap } from 'lucide-react'

// ---------------------------------------------------------------------------
// Task type badge styling
// ---------------------------------------------------------------------------

const TASK_TYPE_COLORS: Record<string, string> = {
  ANALYZE:     'bg-blue-100 text-blue-700',
  ANALYZE_LOG: 'bg-blue-100 text-blue-700',
  DEVELOP:     'bg-green-100 text-green-700',
  REVIEW:      'bg-yellow-100 text-yellow-700',
  REVIEW_MR:   'bg-yellow-100 text-yellow-700',
  TEST:        'bg-teal-100 text-teal-700',
  DOCUMENT:    'bg-gray-100 text-gray-600',
  PLAN:        'bg-purple-100 text-purple-700',
  PLAN_TASK:   'bg-purple-100 text-purple-700',
}

function taskTypeColor(taskType: string): string {
  return TASK_TYPE_COLORS[taskType.toUpperCase()] ?? 'bg-slate-100 text-slate-600'
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

const STATUS_STYLES: Record<string, string> = {
  pending:     'bg-gray-100 text-gray-600 border-gray-200',
  in_progress: 'bg-blue-100 text-blue-700 border-blue-200',
  completed:   'bg-green-100 text-green-700 border-green-200',
  failed:      'bg-red-100 text-red-600 border-red-200',
}

const STATUS_ICONS: Record<string, React.ReactNode> = {
  pending:     <Clock size={11} />,
  in_progress: <Zap size={11} className="animate-pulse" />,
  completed:   <CheckCircle size={11} />,
  failed:      <XCircle size={11} />,
}

// ---------------------------------------------------------------------------
// Filter pill component
// ---------------------------------------------------------------------------

function FilterPill({
  label, active, onClick,
}: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
        active
          ? 'bg-gray-800 text-white'
          : 'bg-white border border-gray-200 text-gray-600 hover:border-gray-400'
      }`}
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

  const isSage = (task.source === 'sage') || (task.feature_scope === 'sage')
  const borderColor = isSage ? 'border-l-4 border-purple-400' : 'border-l-4 border-orange-400'
  const status = task.status ?? 'pending'

  const hasPayload = task.payload && Object.keys(task.payload).length > 0

  return (
    <div className={`bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden ${borderColor}`}>
      <div className="flex items-start gap-3 px-4 py-3">
        {/* Source badge */}
        <div className="shrink-0 pt-0.5">
          {isSage ? (
            <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded-full bg-purple-100 text-purple-700">
              SAGE
            </span>
          ) : (
            <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded-full bg-orange-100 text-orange-700">
              {task.feature_scope ?? task.source ?? 'solution'}
            </span>
          )}
        </div>

        {/* Task type badge */}
        <span className={`shrink-0 text-[10px] font-bold uppercase px-1.5 py-0.5 rounded mt-0.5 ${taskTypeColor(task.task_type)}`}>
          {task.task_type.replace('_', ' ')}
        </span>

        {/* Main content */}
        <div className="flex-1 min-w-0">
          {task.feature_title ? (
            <div className="text-sm font-medium text-gray-800 truncate">{task.feature_title}</div>
          ) : (
            <div className="text-sm text-gray-600 font-mono truncate">{task.task_id.slice(0, 8)}…</div>
          )}
          <div className="flex items-center gap-2 mt-0.5 flex-wrap">
            <span className="text-xs text-gray-400 font-mono">{task.task_id.slice(0, 8)}…</span>
            <span className="text-xs text-gray-300">·</span>
            <span className="text-xs text-gray-400">
              {new Date(task.created_at).toLocaleString()}
            </span>
            {task.plan_trace_id && (
              <>
                <span className="text-xs text-gray-300">·</span>
                <span className="text-xs text-gray-400 font-mono" title={task.plan_trace_id}>
                  plan: {task.plan_trace_id.slice(0, 8)}…
                </span>
              </>
            )}
          </div>
          {task.error && (
            <div className="mt-1 text-xs text-red-600 bg-red-50 rounded px-2 py-1 truncate">
              {task.error}
            </div>
          )}
        </div>

        {/* Status badge + expand */}
        <div className="flex items-center gap-2 shrink-0">
          <span className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border font-medium capitalize ${STATUS_STYLES[status] ?? STATUS_STYLES.pending}`}>
            {STATUS_ICONS[status]}
            {status.replace('_', ' ')}
          </span>
          {hasPayload && (
            <button
              onClick={() => setOpen(v => !v)}
              className="text-gray-400 hover:text-gray-600 transition-colors"
              title="Toggle payload"
            >
              {open ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
            </button>
          )}
        </div>
      </div>

      {/* Collapsible payload */}
      {open && hasPayload && (
        <div className="border-t border-gray-100">
          <pre className="bg-gray-50 px-4 py-3 text-[11px] font-mono overflow-auto max-h-40 whitespace-pre-wrap text-gray-600">
            {JSON.stringify(task.payload, null, 2)}
          </pre>
        </div>
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

  // Stats always from full unfiltered count is not available without a second query,
  // so compute from current result set (which may be filtered)
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

  const STATUS_FILTERS: { label: string; value: StatusFilter }[] = [
    { label: 'All', value: 'all' },
    { label: 'Pending', value: 'pending' },
    { label: 'In Progress', value: 'in_progress' },
    { label: 'Completed', value: 'completed' },
    { label: 'Failed', value: 'failed' },
  ]

  const SOURCE_FILTERS: { label: string; value: SourceFilter }[] = [
    { label: 'All Sources', value: 'all' },
    { label: 'SAGE Framework', value: 'sage' },
    { label: 'Solution', value: 'solution' },
  ]

  return (
    <ModuleWrapper moduleId="queue">
      <div className="space-y-6">

        {/* Page header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
              <ListOrdered size={20} className="text-gray-500" />
              Task Queue
            </h2>
            <p className="text-xs text-gray-500 mt-0.5">
              All queued tasks from approved implementation plans. Auto-refreshes every 5 seconds.
            </p>
          </div>
        </div>

        {/* Stats bar */}
        <div className="grid grid-cols-5 gap-3">
          {[
            { label: 'Total',       value: stats.total,       color: 'text-gray-800' },
            { label: 'Pending',     value: stats.pending,     color: 'text-gray-500' },
            { label: 'In Progress', value: stats.in_progress, color: 'text-blue-600' },
            { label: 'Completed',   value: stats.completed,   color: 'text-green-600' },
            { label: 'Failed',      value: stats.failed,      color: 'text-red-600' },
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm text-center">
              <div className={`text-2xl font-bold ${color}`}>{value}</div>
              <div className="text-xs text-gray-500 mt-0.5">{label}</div>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="space-y-2">
          {/* Status filter pills */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-medium text-gray-500 uppercase tracking-wide mr-1">Status</span>
            {STATUS_FILTERS.map(f => (
              <FilterPill
                key={f.value}
                label={f.label}
                active={statusFilter === f.value}
                onClick={() => setStatusFilter(f.value)}
              />
            ))}
          </div>

          {/* Source filter pills */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-medium text-gray-500 uppercase tracking-wide mr-1">Source</span>
            {SOURCE_FILTERS.map(f => (
              <FilterPill
                key={f.value}
                label={f.label}
                active={sourceFilter === f.value}
                onClick={() => setSourceFilter(f.value)}
              />
            ))}
          </div>
        </div>

        {/* Task list */}
        {isLoading ? (
          <div className="flex items-center justify-center h-48 text-gray-400 gap-2">
            <Loader2 className="animate-spin" size={18} /> Loading…
          </div>
        ) : allTasks.length === 0 ? (
          <div className="bg-white rounded-xl border border-dashed border-gray-300 p-12 text-center">
            <div className="mx-auto mb-3 w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center">
              <ListOrdered size={20} className="text-gray-400" />
            </div>
            <div className="font-medium text-gray-700 mb-1">No tasks found</div>
            <p className="text-sm text-gray-400">
              Tasks appear here when approved implementation plans are executed.
              {(statusFilter !== 'all' || sourceFilter !== 'all') && ' Try removing your filters.'}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {allTasks.map(task => (
              <TaskRow key={task.task_id} task={task} />
            ))}
          </div>
        )}
      </div>
    </ModuleWrapper>
  )
}
