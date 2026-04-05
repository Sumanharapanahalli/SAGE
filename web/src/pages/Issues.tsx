import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchIssues, updateFeatureRequest, submitFeatureRequest, type Issue } from '../api/client'
import ModuleWrapper from '../components/shared/ModuleWrapper'
import { Loader2, Plus, X, AlertCircle } from 'lucide-react'
import type { Priority, RequestScope } from '../types/module'
import OtherSelect from '../components/ui/OtherSelect'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function timeAgo(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime()
  const mins  = Math.floor(diff / 60_000)
  const hours = Math.floor(diff / 3_600_000)
  const days  = Math.floor(diff / 86_400_000)
  if (mins < 2)   return 'just now'
  if (hours < 1)  return `${mins}m ago`
  if (days < 1)   return `${hours}h ago`
  if (days < 30)  return `${days}d ago`
  return new Date(isoString).toLocaleDateString()
}

function truncate(s: string, n = 60): string {
  return s.length > n ? s.slice(0, n) + '…' : s
}

// ---------------------------------------------------------------------------
// Priority icon — small colored square
// ---------------------------------------------------------------------------
const PRIORITY_COLOR: Record<Issue['priority'], string> = {
  urgent: '#ef4444',
  high:   '#f97316',
  medium: '#eab308',
  low:    '#71717a',
}

function PriorityIcon({ priority }: { priority: Issue['priority'] }) {
  return (
    <span
      title={priority}
      style={{
        display: 'inline-block',
        width: '8px',
        height: '8px',
        backgroundColor: PRIORITY_COLOR[priority],
        flexShrink: 0,
      }}
    />
  )
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------
const STATUS_COLOR: Record<Issue['status'], { bg: string; text: string }> = {
  open:        { bg: '#e5e7eb', text: '#a1a1aa' },
  in_progress: { bg: '#1e3a5f', text: '#60a5fa' },
  done:        { bg: '#14532d', text: '#4ade80' },
  cancelled:   { bg: '#e5e7eb', text: '#52525b' },
}

function StatusBadge({ status }: { status: Issue['status'] }) {
  const c = STATUS_COLOR[status]
  const label = status === 'in_progress' ? 'In Progress' : status.charAt(0).toUpperCase() + status.slice(1)
  return (
    <span
      className="text-xs font-medium px-1.5 py-0.5"
      style={{ backgroundColor: c.bg, color: c.text }}
    >
      {label}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Scope badge
// ---------------------------------------------------------------------------
function ScopeBadge({ scope }: { scope: Issue['scope'] }) {
  const isSage = scope === 'sage'
  return (
    <span
      className="text-xs font-medium px-1.5 py-0.5"
      style={{
        backgroundColor: isSage ? '#134e4a' : '#3b0764',
        color:           isSage ? '#2dd4bf' : '#c084fc',
      }}
    >
      {isSage ? 'sage' : 'solution'}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Slide-over detail panel
// ---------------------------------------------------------------------------
interface SlideOverProps {
  issue: Issue
  onClose: () => void
  onUpdated: () => void
}

function SlideOver({ issue, onClose, onUpdated }: SlideOverProps) {
  const qc = useQueryClient()
  const [status, setStatus] = useState<Issue['status']>(issue.status)
  const [priority, setPriority] = useState<Issue['priority']>(issue.priority)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  // Map Issue status back to FeatureRequest action
  const statusToAction: Record<Issue['status'], string> = {
    open:        'approve',
    in_progress: 'approve',
    done:        'approve',
    cancelled:   'reject',
  }

  async function handleSave() {
    setSaving(true)
    try {
      await updateFeatureRequest(issue.id, { action: statusToAction[status] })
      qc.invalidateQueries({ queryKey: ['issues'] })
      setMsg('Saved')
      onUpdated()
      setTimeout(() => setMsg(''), 2000)
    } catch (e) {
      setMsg((e as Error).message ?? 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-20"
        style={{ backgroundColor: 'rgba(0,0,0,0.4)' }}
        onClick={onClose}
      />

      {/* Panel */}
      <div
        className="fixed top-0 right-0 h-full z-30 flex flex-col overflow-hidden"
        style={{
          width: '384px',
          backgroundColor: '#ffffff',
          borderLeft: '1px solid #e5e7eb',
          boxShadow: '-8px 0 32px rgba(0,0,0,0.5)',
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 py-3 shrink-0"
          style={{ borderBottom: '1px solid #e5e7eb' }}
        >
          <span className="text-xs font-semibold uppercase tracking-widest" style={{ color: '#9ca3af' }}>Issue Detail</span>
          <button onClick={onClose} style={{ color: '#9ca3af' }}>
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Title */}
          <div>
            <div className="text-xs font-medium mb-1" style={{ color: '#9ca3af' }}>Title</div>
            <div className="text-sm font-medium" style={{ color: '#374151' }}>{issue.title}</div>
          </div>

          {/* Status */}
          <div>
            <div className="text-xs font-medium mb-1" style={{ color: '#9ca3af' }}>Status</div>
            <OtherSelect
              value={status}
              onChange={v => setStatus(v as Issue['status'])}
              options={[
                { value: 'open',        label: 'Open' },
                { value: 'in_progress', label: 'In Progress' },
                { value: 'done',        label: 'Done' },
                { value: 'cancelled',   label: 'Cancelled' },
              ]}
              className="w-full text-sm px-2 py-1.5"
              style={{ backgroundColor: '#e5e7eb', border: '1px solid #d1d5db', color: '#374151' }}
              inputStyle={{ backgroundColor: '#e5e7eb', border: '1px solid #d1d5db', color: '#374151' }}
            />
          </div>

          {/* Priority */}
          <div>
            <div className="text-xs font-medium mb-1" style={{ color: '#9ca3af' }}>Priority</div>
            <OtherSelect
              value={priority}
              onChange={v => setPriority(v as Issue['priority'])}
              options={[
                { value: 'urgent', label: 'Urgent' },
                { value: 'high',   label: 'High' },
                { value: 'medium', label: 'Medium' },
                { value: 'low',    label: 'Low' },
              ]}
              className="w-full text-sm px-2 py-1.5"
              style={{ backgroundColor: '#e5e7eb', border: '1px solid #d1d5db', color: '#374151' }}
              inputStyle={{ backgroundColor: '#e5e7eb', border: '1px solid #d1d5db', color: '#374151' }}
            />
          </div>

          {/* Scope */}
          <div>
            <div className="text-xs font-medium mb-1" style={{ color: '#9ca3af' }}>Scope</div>
            <ScopeBadge scope={issue.scope} />
          </div>

          {/* Description */}
          <div>
            <div className="text-xs font-medium mb-1" style={{ color: '#9ca3af' }}>Description</div>
            <p className="text-sm whitespace-pre-wrap" style={{ color: '#6b7280' }}>{issue.description}</p>
          </div>

          {/* Proposed solution / AI analysis */}
          {issue.proposed_solution && (
            <div>
              <div className="text-xs font-medium mb-1" style={{ color: '#9ca3af' }}>Reviewer note / AI analysis</div>
              <p className="text-sm whitespace-pre-wrap" style={{ color: '#6b7280' }}>{issue.proposed_solution}</p>
            </div>
          )}

          {/* Created */}
          <div>
            <div className="text-xs font-medium mb-1" style={{ color: '#9ca3af' }}>Created</div>
            <div className="text-xs" style={{ color: '#9ca3af' }}>{timeAgo(issue.created_at)}</div>
          </div>
        </div>

        {/* Footer */}
        <div
          className="px-4 py-3 flex items-center gap-2 shrink-0"
          style={{ borderTop: '1px solid #e5e7eb' }}
        >
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5"
            style={{
              backgroundColor: '#d1d5db',
              color: '#374151',
              opacity: saving ? 0.6 : 1,
            }}
          >
            {saving ? <><Loader2 size={12} className="animate-spin" /> Saving…</> : 'Save changes'}
          </button>
          {msg && (
            <span className="text-xs" style={{ color: msg === 'Saved' ? '#4ade80' : '#ef4444' }}>
              {msg}
            </span>
          )}
        </div>
      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// New Issue form
// ---------------------------------------------------------------------------
function NewIssueForm({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const [title, setTitle] = useState('')
  const [desc, setDesc]   = useState('')
  const [priority, setPriority] = useState<Priority>('medium')
  const [scope, setScope] = useState<RequestScope>('solution')
  const [done, setDone]   = useState(false)

  const { mutate, isPending, error } = useMutation({
    mutationFn: () => submitFeatureRequest({
      module_id:    'issues',
      module_name:  'Issues',
      title:        title.trim(),
      description:  desc.trim(),
      priority,
      requested_by: 'Web UI',
      scope,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['issues'] })
      setDone(true)
      setTimeout(onClose, 1200)
    },
  })

  if (done) return (
    <div
      className="flex items-center gap-2 px-4 py-3 text-xs"
      style={{ backgroundColor: '#14532d', color: '#4ade80', border: '1px solid #166534' }}
    >
      Issue logged.
    </div>
  )

  return (
    <div
      className="p-4 space-y-3"
      style={{ backgroundColor: '#ffffff', border: '1px solid #e5e7eb' }}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold" style={{ color: '#374151' }}>New Issue</span>
        <button onClick={onClose} style={{ color: '#9ca3af' }}><X size={14} /></button>
      </div>

      <input
        value={title}
        onChange={e => setTitle(e.target.value)}
        placeholder="Issue title…"
        className="w-full text-sm px-2 py-1.5"
        style={{ backgroundColor: '#e5e7eb', border: '1px solid #d1d5db', color: '#374151' }}
      />
      <textarea
        value={desc}
        onChange={e => setDesc(e.target.value)}
        placeholder="Description…"
        rows={3}
        className="w-full text-sm px-2 py-1.5 resize-none"
        style={{ backgroundColor: '#e5e7eb', border: '1px solid #d1d5db', color: '#374151' }}
      />

      <div className="flex gap-2">
        <OtherSelect
          value={priority}
          onChange={v => setPriority(v as Priority)}
          options={[
            { value: 'low',      label: 'Low' },
            { value: 'medium',   label: 'Medium' },
            { value: 'high',     label: 'High' },
            { value: 'critical', label: 'Urgent' },
          ]}
          className="flex-1 text-xs px-2 py-1.5"
          style={{ backgroundColor: '#e5e7eb', border: '1px solid #d1d5db', color: '#6b7280' }}
          inputStyle={{ backgroundColor: '#e5e7eb', border: '1px solid #d1d5db', color: '#6b7280' }}
        />
        <OtherSelect
          value={scope}
          onChange={v => setScope(v as RequestScope)}
          options={[
            { value: 'solution', label: 'Solution' },
            { value: 'sage',     label: 'SAGE' },
          ]}
          className="flex-1 text-xs px-2 py-1.5"
          style={{ backgroundColor: '#e5e7eb', border: '1px solid #d1d5db', color: '#6b7280' }}
          inputStyle={{ backgroundColor: '#e5e7eb', border: '1px solid #d1d5db', color: '#6b7280' }}
        />
      </div>

      {error && (
        <p className="text-xs" style={{ color: '#ef4444' }}>{(error as Error).message}</p>
      )}

      <div className="flex gap-2">
        <button
          onClick={() => mutate()}
          disabled={isPending || !title.trim() || !desc.trim()}
          className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5"
          style={{ backgroundColor: '#d1d5db', color: '#374151', opacity: isPending || !title.trim() || !desc.trim() ? 0.5 : 1 }}
        >
          {isPending ? <><Loader2 size={11} className="animate-spin" /> Submitting…</> : 'Submit'}
        </button>
        <button onClick={onClose} className="text-xs px-3 py-1.5" style={{ color: '#9ca3af' }}>Cancel</button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Issues page
// ---------------------------------------------------------------------------

type StatusFilter = 'all' | Issue['status']

const STATUS_FILTERS: { label: string; value: StatusFilter }[] = [
  { label: 'All',         value: 'all' },
  { label: 'Open',        value: 'open' },
  { label: 'In Progress', value: 'in_progress' },
  { label: 'Done',        value: 'done' },
  { label: 'Cancelled',   value: 'cancelled' },
]

export default function Issues() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [search, setSearch]             = useState('')
  const [selected, setSelected]         = useState<Issue | null>(null)
  const [showForm, setShowForm]         = useState(false)
  const qc = useQueryClient()

  const { data: issues = [], isLoading } = useQuery({
    queryKey: ['issues'],
    queryFn: fetchIssues,
    refetchInterval: 30_000,
  })

  const filtered = issues.filter(i => {
    if (statusFilter !== 'all' && i.status !== statusFilter) return false
    if (search) {
      const q = search.toLowerCase()
      if (!i.title.toLowerCase().includes(q) && !i.description.toLowerCase().includes(q)) return false
    }
    return true
  })

  return (
    <ModuleWrapper moduleId="improvements">
      <div className="space-y-4">

        {/* Toolbar */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Filter pills */}
          <div className="flex items-center gap-1">
            {STATUS_FILTERS.map(f => (
              <button
                key={f.value}
                onClick={() => setStatusFilter(f.value)}
                className="text-xs px-2.5 py-1 font-medium transition-colors"
                style={{
                  backgroundColor: statusFilter === f.value ? '#d1d5db' : 'transparent',
                  color:           statusFilter === f.value ? '#f4f4f5' : '#71717a',
                  border:          statusFilter === f.value ? '1px solid #52525b' : '1px solid transparent',
                }}
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Search */}
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search issues…"
            className="flex-1 min-w-[160px] text-xs px-2.5 py-1.5"
            style={{
              backgroundColor: '#e5e7eb',
              border: '1px solid #d1d5db',
              color: '#374151',
            }}
          />

          {/* New Issue */}
          <button
            onClick={() => setShowForm(v => !v)}
            className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5"
            style={{ backgroundColor: '#d1d5db', color: '#374151', border: '1px solid #52525b' }}
          >
            <Plus size={12} />
            New Issue
          </button>
        </div>

        {/* New issue form */}
        {showForm && <NewIssueForm onClose={() => setShowForm(false)} />}

        {/* Issue list */}
        {isLoading ? (
          <div className="flex items-center justify-center h-48 gap-2" style={{ color: '#9ca3af' }}>
            <Loader2 size={16} className="animate-spin" /> Loading…
          </div>
        ) : filtered.length === 0 ? (
          <div
            className="flex flex-col items-center justify-center h-48 gap-2"
            style={{ color: '#9ca3af', border: '1px dashed #e5e7eb' }}
          >
            <AlertCircle size={20} />
            <span className="text-sm">No issues found</span>
          </div>
        ) : (
          <div style={{ border: '1px solid #e5e7eb' }}>
            {/* Table header */}
            <div
              className="grid text-xs font-semibold uppercase tracking-wider px-3 py-2"
              style={{
                gridTemplateColumns: '16px 1fr 100px 80px 72px 64px',
                gap: '12px',
                backgroundColor: '#fafafa',
                borderBottom: '1px solid #e5e7eb',
                color: '#9ca3af',
              }}
            >
              <span />
              <span>Title</span>
              <span>Status</span>
              <span>Scope</span>
              <span>Priority</span>
              <span className="text-right">Created</span>
            </div>

            {filtered.map((issue, idx) => (
              <button
                key={issue.id}
                onClick={() => setSelected(issue)}
                className="w-full text-left grid px-3 py-2.5 transition-colors"
                style={{
                  gridTemplateColumns: '16px 1fr 100px 80px 72px 64px',
                  gap: '12px',
                  alignItems: 'center',
                  borderBottom: idx < filtered.length - 1 ? '1px solid #e5e7eb' : 'none',
                  backgroundColor: 'transparent',
                }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.backgroundColor = '#e5e7eb' }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent' }}
              >
                <PriorityIcon priority={issue.priority} />
                <span className="text-sm truncate" style={{ color: '#e4e4e7' }}>
                  {truncate(issue.title, 60)}
                </span>
                <span><StatusBadge status={issue.status} /></span>
                <span><ScopeBadge scope={issue.scope} /></span>
                <span className="text-xs capitalize" style={{ color: PRIORITY_COLOR[issue.priority] }}>
                  {issue.priority}
                </span>
                <span className="text-xs text-right" style={{ color: '#9ca3af' }}>
                  {timeAgo(issue.created_at)}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Slide-over */}
      {selected && (
        <SlideOver
          issue={selected}
          onClose={() => setSelected(null)}
          onUpdated={() => qc.invalidateQueries({ queryKey: ['issues'] })}
        />
      )}
    </ModuleWrapper>
  )
}
