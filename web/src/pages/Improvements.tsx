import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchFeatureRequests,
  generatePlanForRequest,
  updateFeatureRequest,
  submitFeatureRequest,
} from '../api/client'
import type { FeatureRequest, RequestStatus, Priority } from '../types/module'
import ModuleWrapper from '../components/shared/ModuleWrapper'
import { Loader2, Zap, CheckCircle, XCircle, Clock, GitBranch, ChevronDown, ChevronUp, Plus, X } from 'lucide-react'
import { getModuleAccess } from '../registry/modules'
import { useProjectConfig } from '../hooks/useProjectConfig'

// ---------------------------------------------------------------------------
// Status + Priority display helpers
// ---------------------------------------------------------------------------

const STATUS_STYLES: Record<RequestStatus, string> = {
  pending:     'bg-yellow-100 text-yellow-700 border-yellow-200',
  approved:    'bg-blue-100  text-blue-700   border-blue-200',
  in_planning: 'bg-purple-100 text-purple-700 border-purple-200',
  in_progress: 'bg-cyan-100  text-cyan-700   border-cyan-200',
  completed:   'bg-green-100 text-green-700  border-green-200',
  rejected:    'bg-red-100   text-red-600    border-red-200',
}

const STATUS_ICON: Record<RequestStatus, React.ReactNode> = {
  pending:     <Clock size={12} />,
  approved:    <CheckCircle size={12} />,
  in_planning: <GitBranch size={12} />,
  in_progress: <Zap size={12} />,
  completed:   <CheckCircle size={12} />,
  rejected:    <XCircle size={12} />,
}

const PRIORITY_DOT: Record<Priority, string> = {
  low:      'bg-gray-400',
  medium:   'bg-amber-400',
  high:     'bg-orange-500',
  critical: 'bg-red-600',
}

// ---------------------------------------------------------------------------
// Request card
// ---------------------------------------------------------------------------

function RequestCard({ req }: { req: FeatureRequest }) {
  const [expanded, setExpanded]   = useState(false)
  const [reviewNote, setNote]     = useState('')
  const [showNote, setShowNote]   = useState(false)
  const access = getModuleAccess()
  const qc = useQueryClient()

  const { mutate: plan, isPending: planning } = useMutation({
    mutationFn: () => generatePlanForRequest(req.id),
    onSuccess:  () => qc.invalidateQueries({ queryKey: ['feature-requests'] }),
  })

  const { mutate: update, isPending: updating } = useMutation({
    mutationFn: (action: string) =>
      updateFeatureRequest(req.id, { action, reviewer_note: reviewNote }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['feature-requests'] })
      setShowNote(false)
      setNote('')
    },
  })

  const sStatus = req.status as RequestStatus
  const sPriority = req.priority as Priority

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      {/* Card header */}
      <div className="flex items-start gap-3 px-4 py-3">
        <div className={`w-2.5 h-2.5 rounded-full mt-1.5 shrink-0 ${PRIORITY_DOT[sPriority]}`} />
        <div className="flex-1 min-w-0">
          <div className="font-medium text-gray-800 text-sm">{req.title}</div>
          <div className="flex items-center flex-wrap gap-2 mt-1">
            <span className="text-xs text-gray-400">{req.module_name}</span>
            <span className="text-xs text-gray-300">·</span>
            <span className="text-xs text-gray-400">{req.requested_by}</span>
            <span className="text-xs text-gray-300">·</span>
            <span className="text-xs text-gray-400">
              {new Date(req.created_at).toLocaleDateString()}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border font-medium capitalize ${STATUS_STYLES[sStatus]}`}>
            {STATUS_ICON[sStatus]}
            {req.status.replace('_', ' ')}
          </span>
          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-gray-400 hover:text-gray-600"
          >
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-gray-100">
          <p className="text-sm text-gray-700 pt-3 whitespace-pre-wrap">{req.description}</p>

          {req.reviewer_note && (
            <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-600">
              <span className="font-semibold">Reviewer note:</span> {req.reviewer_note}
            </div>
          )}

          {req.plan_trace_id && (
            <div className="text-xs text-purple-600 bg-purple-50 rounded-lg px-3 py-1.5">
              Plan trace: <span className="font-mono">{req.plan_trace_id.slice(0, 16)}…</span>
            </div>
          )}

          {/* Action buttons — only shown when status warrants + user has access */}
          {access.canApprove && ['pending', 'approved'].includes(req.status) && (
            <div className="flex flex-wrap gap-2 pt-1">
              {access.canGeneratePlan && req.status !== 'in_planning' && (
                <button
                  disabled={planning}
                  onClick={() => plan()}
                  className="flex items-center gap-1.5 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
                >
                  <Zap size={13} />
                  {planning ? 'Generating plan…' : 'Generate AI Plan'}
                </button>
              )}

              {req.status === 'pending' && (
                <button
                  disabled={updating}
                  onClick={() => update('approve')}
                  className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
                >
                  <CheckCircle size={13} />
                  Approve
                </button>
              )}

              {req.status !== 'completed' && (
                <button
                  disabled={updating}
                  onClick={() => update('complete')}
                  className="flex items-center gap-1.5 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
                >
                  <CheckCircle size={13} />
                  Mark Complete
                </button>
              )}

              <button
                onClick={() => setShowNote((v) => !v)}
                className="flex items-center gap-1.5 bg-red-50 hover:bg-red-100 text-red-600 border border-red-200 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
              >
                <XCircle size={13} />
                Reject
              </button>
            </div>
          )}

          {showNote && (
            <div className="space-y-2">
              <textarea
                value={reviewNote}
                onChange={(e) => setNote(e.target.value)}
                className="w-full h-16 border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-red-400"
                placeholder="Optional: explain why it's rejected..."
              />
              <button
                disabled={updating}
                onClick={() => update('reject')}
                className="bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white text-xs px-3 py-1.5 rounded-lg transition-colors"
              >
                {updating ? 'Rejecting…' : 'Confirm Reject'}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Submit form
// ---------------------------------------------------------------------------

function SubmitForm({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const { data: projectData } = useProjectConfig()

  const [title, setTitle]       = useState('')
  const [desc, setDesc]         = useState('')
  const [priority, setPriority] = useState<Priority>('medium')
  const [module, setModule]     = useState('general')
  const [by, setBy]             = useState('')
  const [done, setDone]         = useState(false)

  const { mutate, isPending, error } = useMutation({
    mutationFn: () => submitFeatureRequest({
      module_id:   module.toLowerCase().replace(/\s+/g, '-'),
      module_name: module,
      title:       title.trim(),
      description: desc.trim(),
      priority,
      requested_by: by.trim() || 'Web UI',
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['feature-requests'] })
      setDone(true)
      setTimeout(onClose, 1200)
    },
  })

  const projectName = projectData?.name ?? 'SAGE Framework'

  if (done) {
    return (
      <div className="flex items-center gap-2 py-4 px-5 text-green-700 bg-green-50 rounded-xl border border-green-200">
        <CheckCircle size={18} /> Request submitted — thank you!
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl border border-amber-200 shadow-sm overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 bg-amber-50 border-b border-amber-200">
        <h3 className="text-sm font-semibold text-amber-800">New Improvement Request — {projectName}</h3>
        <button onClick={onClose} className="text-amber-500 hover:text-amber-700">
          <X size={16} />
        </button>
      </div>

      <div className="p-5 space-y-4">
        {/* Title */}
        <div>
          <label className="text-xs font-medium text-gray-600 block mb-1">Title <span className="text-red-500">*</span></label>
          <input
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="e.g. Add BLE reconnect context to analyst prompt"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"
          />
        </div>

        {/* Description */}
        <div>
          <label className="text-xs font-medium text-gray-600 block mb-1">Description <span className="text-red-500">*</span></label>
          <textarea
            value={desc}
            onChange={e => setDesc(e.target.value)}
            placeholder="What should change and why? Include any relevant context."
            rows={3}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-amber-400"
          />
        </div>

        <div className="grid grid-cols-3 gap-3">
          {/* Module */}
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1">Module</label>
            <input
              value={module}
              onChange={e => setModule(e.target.value)}
              placeholder="e.g. Analyst"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"
            />
          </div>

          {/* Priority */}
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1">Priority</label>
            <select
              value={priority}
              onChange={e => setPriority(e.target.value as Priority)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-amber-400"
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </div>

          {/* Requested by */}
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1">Your name</label>
            <input
              value={by}
              onChange={e => setBy(e.target.value)}
              placeholder="Optional"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"
            />
          </div>
        </div>

        {error && (
          <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">
            {(error as Error).message}
          </p>
        )}

        <div className="flex gap-2 pt-1">
          <button
            onClick={() => mutate()}
            disabled={isPending || !title.trim() || !desc.trim()}
            className="bg-amber-500 hover:bg-amber-600 disabled:opacity-40 text-white text-sm font-medium
                       px-4 py-2 rounded-lg transition-colors flex items-center gap-1.5"
          >
            {isPending ? <><Loader2 size={14} className="animate-spin" /> Submitting…</> : 'Submit Request'}
          </button>
          <button
            onClick={onClose}
            className="text-sm text-gray-500 hover:text-gray-700 px-4 py-2 rounded-lg transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Improvements page
// ---------------------------------------------------------------------------

const ALL_STATUSES: RequestStatus[] = [
  'pending', 'approved', 'in_planning', 'in_progress', 'completed', 'rejected',
]

export default function Improvements() {
  const [filterModule, setFilterModule] = useState('')
  const [filterStatus, setFilterStatus] = useState<RequestStatus | ''>('')
  const [showForm, setShowForm] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['feature-requests', filterModule, filterStatus],
    queryFn: () =>
      fetchFeatureRequests(filterModule || undefined, filterStatus || undefined),
    refetchInterval: 30_000,
  })

  const requests: FeatureRequest[] = data?.requests ?? []

  // Group by module
  const grouped = requests.reduce<Record<string, FeatureRequest[]>>((acc, r) => {
    const key = r.module_name
    ;(acc[key] = acc[key] ?? []).push(r)
    return acc
  }, {})

  const counts = {
    total:     requests.length,
    pending:   requests.filter((r) => r.status === 'pending').length,
    planning:  requests.filter((r) => r.status === 'in_planning').length,
    completed: requests.filter((r) => r.status === 'completed').length,
  }

  return (
    <ModuleWrapper moduleId="improvements">
      <div className="space-y-6">
        {/* Header row with New Request button */}
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-800">Improvement Requests</h2>
          <button
            onClick={() => setShowForm(v => !v)}
            className="flex items-center gap-1.5 bg-amber-500 hover:bg-amber-600 text-white
                       text-sm font-medium px-3 py-2 rounded-lg transition-colors"
          >
            <Plus size={15} />
            New Request
          </button>
        </div>

        {/* Submit form (toggled) */}
        {showForm && <SubmitForm onClose={() => setShowForm(false)} />}

        {/* Stats bar */}
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: 'Total Requests', value: counts.total,     color: 'text-gray-800' },
            { label: 'Pending Review', value: counts.pending,   color: 'text-amber-600' },
            { label: 'In Planning',    value: counts.planning,  color: 'text-purple-600' },
            { label: 'Completed',      value: counts.completed, color: 'text-green-600' },
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm text-center">
              <div className={`text-2xl font-bold ${color}`}>{value}</div>
              <div className="text-xs text-gray-500 mt-0.5">{label}</div>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="flex gap-3 flex-wrap">
          <input
            type="text"
            value={filterModule}
            onChange={(e) => setFilterModule(e.target.value)}
            placeholder="Filter by module name…"
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400 w-52"
          />
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value as RequestStatus | '')}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400 bg-white"
          >
            <option value="">All statuses</option>
            {ALL_STATUSES.map((s) => (
              <option key={s} value={s}>{s.replace('_', ' ')}</option>
            ))}
          </select>
        </div>

        {/* List */}
        {isLoading ? (
          <div className="flex items-center justify-center h-48 text-gray-400 gap-2">
            <Loader2 className="animate-spin" size={18} /> Loading requests…
          </div>
        ) : requests.length === 0 ? (
          <div className="bg-white rounded-xl border border-dashed border-gray-300 p-12 text-center">
            <Lightbulb size={32} className="text-amber-400 mx-auto mb-3" />
            <div className="font-medium text-gray-700 mb-1">No improvement requests yet</div>
            <p className="text-sm text-gray-400">
              Use the <span className="font-semibold text-amber-600">💡 Request Improvement</span> button
              on any page to submit the first one.
            </p>
          </div>
        ) : (
          Object.entries(grouped).map(([moduleName, reqs]) => (
            <div key={moduleName}>
              <div className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-2">
                {moduleName} <span className="font-normal text-gray-400">({reqs.length})</span>
              </div>
              <div className="space-y-2">
                {reqs.map((req) => (
                  <RequestCard key={req.id} req={req} />
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </ModuleWrapper>
  )
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function Lightbulb({ size, className }: { size: number; className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <line x1="9" y1="18" x2="15" y2="18" />
      <line x1="10" y1="22" x2="14" y2="22" />
      <path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 0 1 8.91 14" />
    </svg>
  )
}
