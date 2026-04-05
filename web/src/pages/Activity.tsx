import { useState, useEffect, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchAuditEvents, type AuditEvent } from '../api/client'
import ModuleWrapper from '../components/shared/ModuleWrapper'
import { Loader2, Radio } from 'lucide-react'

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

// ---------------------------------------------------------------------------
// Event type classification
// ---------------------------------------------------------------------------

type EventCategory = 'tasks' | 'proposals' | 'llm' | 'errors'

interface EventDisplay {
  dot: string        // CSS color
  label: string
  category: EventCategory
}

function classifyEvent(event: AuditEvent): EventDisplay {
  const t = event.event_type?.toLowerCase() ?? ''
  const d = event.description?.toLowerCase() ?? ''

  if (t.includes('error') || d.includes('error') || t.includes('failed')) {
    return { dot: '#ef4444', label: buildLabel(event), category: 'errors' }
  }
  if (t.includes('proposal_approved') || t.includes('approved')) {
    const approver = (event.metadata?.decided_by as string) ?? ''
    return {
      dot: '#4ade80',
      label: `Approved: ${event.metadata?.action_type ?? event.event_type}${approver ? ` by ${approver}` : ''}`,
      category: 'proposals',
    }
  }
  if (t.includes('proposal_rejected') || t.includes('rejected')) {
    const approver = (event.metadata?.decided_by as string) ?? ''
    return {
      dot: '#ef4444',
      label: `Rejected: ${event.metadata?.action_type ?? event.event_type}${approver ? ` by ${approver}` : ''}`,
      category: 'proposals',
    }
  }
  if (t.includes('proposal') || t.includes('pending')) {
    return {
      dot: '#eab308',
      label: `Proposal created: ${event.metadata?.action_type ?? event.event_type} (awaiting approval)`,
      category: 'proposals',
    }
  }
  if (t.includes('task_completed') || t.includes('completed')) {
    return {
      dot: '#4ade80',
      label: `Task completed: ${event.metadata?.task_type ?? event.event_type}`,
      category: 'tasks',
    }
  }
  if (t.includes('task') || t.includes('submit') || t.includes('queue')) {
    return {
      dot: '#60a5fa',
      label: `New task submitted: ${event.metadata?.task_type ?? event.event_type}`,
      category: 'tasks',
    }
  }
  if (t.includes('llm') || t.includes('generate') || t.includes('model')) {
    const model  = (event.metadata?.model as string) ?? ''
    const tokens = (event.metadata?.tokens as number) ?? 0
    return {
      dot: '#71717a',
      label: `LLM called${model ? `: ${model}` : ''}${tokens ? ` (${tokens} tokens)` : ''}`,
      category: 'llm',
    }
  }

  // fallback
  return { dot: '#52525b', label: buildLabel(event), category: 'tasks' }
}

function buildLabel(event: AuditEvent): string {
  if (event.description && event.description.length > 4) return event.description
  return event.event_type ?? 'Event'
}

// ---------------------------------------------------------------------------
// Filter pill types
// ---------------------------------------------------------------------------

type FeedFilter = 'all' | EventCategory

const FEED_FILTERS: { label: string; value: FeedFilter }[] = [
  { label: 'All',       value: 'all' },
  { label: 'Tasks',     value: 'tasks' },
  { label: 'Proposals', value: 'proposals' },
  { label: 'LLM',       value: 'llm' },
  { label: 'Errors',    value: 'errors' },
]

const PAGE_SIZE = 50

// ---------------------------------------------------------------------------
// Single activity row
// ---------------------------------------------------------------------------

function ActivityRow({ event }: { event: AuditEvent }) {
  const { dot, label } = classifyEvent(event)

  return (
    <div
      className="flex items-start gap-3 px-4 py-2.5 transition-colors"
      style={{ borderBottom: '1px solid #e5e7eb' }}
      onMouseEnter={e => { (e.currentTarget as HTMLElement).style.backgroundColor = '#e5e7eb' }}
      onMouseLeave={e => { (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent' }}
    >
      {/* Timeline dot + line */}
      <div className="flex flex-col items-center shrink-0 mt-1" style={{ width: '12px' }}>
        <span
          style={{
            display: 'inline-block',
            width: '8px',
            height: '8px',
            backgroundColor: dot,
            flexShrink: 0,
          }}
        />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="text-sm" style={{ color: '#e4e4e7' }}>{label}</div>
        <div className="flex items-center gap-2 mt-0.5">
          {event.agent && (
            <span className="text-xs" style={{ color: '#9ca3af' }}>
              {event.agent}
            </span>
          )}
          {event.agent && event.trace_id && (
            <span style={{ color: '#d1d5db' }}>·</span>
          )}
          {event.trace_id && event.trace_id !== event.id && (
            <span className="text-xs font-mono" style={{ color: '#d1d5db' }}>
              {event.trace_id.slice(0, 10)}
            </span>
          )}
        </div>
      </div>

      {/* Time */}
      <div className="text-xs shrink-0" style={{ color: '#9ca3af' }}>
        {timeAgo(event.created_at)}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Activity feed page
// ---------------------------------------------------------------------------

export default function Activity() {
  const [filter, setFilter]   = useState<FeedFilter>('all')
  const [search, setSearch]   = useState('')
  const [page, setPage]       = useState(0)
  const [allEvents, setAllEvents] = useState<AuditEvent[]>([])

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['activity', page],
    queryFn: () => fetchAuditEvents(PAGE_SIZE, page * PAGE_SIZE),
    refetchInterval: 5_000,
  })

  // Append new pages; reset when page resets to 0
  useEffect(() => {
    if (!data) return
    if (page === 0) {
      setAllEvents(data)
    } else {
      setAllEvents(prev => {
        const existingIds = new Set(prev.map(e => e.id))
        const fresh = data.filter(e => !existingIds.has(e.id))
        return [...prev, ...fresh]
      })
    }
  }, [data, page])

  // Auto-refresh: refetch page 0 every 5 s and merge new entries at top
  const refreshTop = useCallback(async () => {
    if (page !== 0) return
    await refetch()
  }, [page, refetch])

  useEffect(() => {
    const id = setInterval(refreshTop, 5_000)
    return () => clearInterval(id)
  }, [refreshTop])

  const visible = allEvents.filter(e => {
    if (filter !== 'all' && classifyEvent(e).category !== filter) return false
    if (search) {
      const q = search.toLowerCase()
      if (
        !e.agent?.toLowerCase().includes(q) &&
        !e.description?.toLowerCase().includes(q) &&
        !e.event_type?.toLowerCase().includes(q)
      ) return false
    }
    return true
  })

  const hasMore = (data?.length ?? 0) === PAGE_SIZE

  return (
    <ModuleWrapper moduleId="audit">
      <div className="space-y-4">

        {/* Toolbar */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Filter pills */}
          <div className="flex items-center gap-1">
            {FEED_FILTERS.map(f => (
              <button
                key={f.value}
                onClick={() => setFilter(f.value)}
                className="text-xs px-2.5 py-1 font-medium transition-colors"
                style={{
                  backgroundColor: filter === f.value ? '#d1d5db' : 'transparent',
                  color:           filter === f.value ? '#f4f4f5' : '#71717a',
                  border:          filter === f.value ? '1px solid #52525b' : '1px solid transparent',
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
            placeholder="Search by agent or description…"
            className="flex-1 min-w-[200px] text-xs px-2.5 py-1.5"
            style={{
              backgroundColor: '#e5e7eb',
              border: '1px solid #d1d5db',
              color: '#374151',
            }}
          />

          {/* Live indicator */}
          <div className="flex items-center gap-1.5 text-xs shrink-0" style={{ color: '#9ca3af' }}>
            <Radio size={12} style={{ color: '#4ade80' }} />
            <span>Live</span>
          </div>
        </div>

        {/* Feed */}
        {isLoading && page === 0 ? (
          <div className="flex items-center justify-center h-48 gap-2" style={{ color: '#9ca3af' }}>
            <Loader2 size={16} className="animate-spin" /> Loading activity…
          </div>
        ) : visible.length === 0 ? (
          <div
            className="flex flex-col items-center justify-center h-48 gap-2 text-sm"
            style={{ color: '#9ca3af', border: '1px dashed #e5e7eb' }}
          >
            <Radio size={20} />
            <span>No activity yet</span>
          </div>
        ) : (
          <div style={{ border: '1px solid #e5e7eb' }}>
            {visible.map(event => (
              <ActivityRow key={`${event.id}-${event.created_at}`} event={event} />
            ))}
          </div>
        )}

        {/* Load more */}
        {hasMore && visible.length > 0 && (
          <div className="flex justify-center">
            <button
              onClick={() => setPage(p => p + 1)}
              className="text-xs px-4 py-2 transition-colors"
              style={{
                backgroundColor: '#e5e7eb',
                color: '#6b7280',
                border: '1px solid #d1d5db',
              }}
            >
              Load more
            </button>
          </div>
        )}
      </div>
    </ModuleWrapper>
  )
}
