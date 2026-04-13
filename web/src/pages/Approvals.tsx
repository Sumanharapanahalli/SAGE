import { useState, useEffect, useCallback, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchPendingProposals,
  approveProposalFull,
  rejectProposalFull,
  approveBatchProposals,
  undoProposal,
} from '../api/client'
import type { Proposal } from '../api/client'
import { Inbox, CheckSquare, X, AlertTriangle, Clock, Check, RefreshCw } from 'lucide-react'
import EvolutionProposalCard from '../components/evolution/EvolutionProposalCard'

// ---------------------------------------------------------------------------
// Risk class config
// ---------------------------------------------------------------------------

const RISK_ORDER: Proposal['risk_class'][] = [
  'DESTRUCTIVE', 'EXTERNAL', 'STATEFUL', 'EPHEMERAL', 'INFORMATIONAL',
]

const RISK_STYLES: Record<Proposal['risk_class'], { dot: string; badge: string; border: string }> = {
  DESTRUCTIVE:   { dot: '#ef4444', badge: 'bg-red-900 text-red-300',    border: '#ef4444' },
  EXTERNAL:      { dot: '#f97316', badge: 'bg-orange-900 text-orange-300', border: '#f97316' },
  STATEFUL:      { dot: '#eab308', badge: 'bg-yellow-900 text-yellow-300', border: '#eab308' },
  EPHEMERAL:     { dot: '#3b82f6', badge: 'bg-blue-900 text-blue-300',   border: '#3b82f6' },
  INFORMATIONAL: { dot: '#71717a', badge: 'bg-zinc-800 text-zinc-400',   border: '#71717a' },
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function relativeTime(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime()
  if (ms < 60_000) return 'just now'
  if (ms < 3_600_000) return `${Math.floor(ms / 60_000)}m ago`
  if (ms < 86_400_000) return `${Math.floor(ms / 3_600_000)}h ago`
  return `${Math.floor(ms / 86_400_000)}d ago`
}

function formatCountdown(iso: string): string {
  const ms = new Date(iso).getTime() - Date.now()
  if (ms <= 0) return 'Expired'
  if (ms < 60_000) return `${Math.floor(ms / 1000)}s`
  if (ms < 3_600_000) return `${Math.floor(ms / 60_000)}m`
  return `${Math.floor(ms / 3_600_000)}h`
}

function formatActionType(actionType: string): string {
  return actionType
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
}

function isEvolutionProposal(proposal: Proposal): boolean {
  return proposal.action_type === 'evolution_candidate'
}

function sortProposals(proposals: Proposal[]): Proposal[] {
  return [...proposals].sort((a, b) => {
    const ai = RISK_ORDER.indexOf(a.risk_class)
    const bi = RISK_ORDER.indexOf(b.risk_class)
    if (ai !== bi) return ai - bi
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  })
}

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------

interface Toast {
  id: string
  message: string
  type: 'success' | 'error'
}

function ToastContainer({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: string) => void }) {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2" style={{ pointerEvents: 'none' }}>
      {toasts.map(t => (
        <div
          key={t.id}
          className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium"
          style={{
            backgroundColor: t.type === 'success' ? '#16a34a' : '#dc2626',
            color: '#fff',
            pointerEvents: 'all',
            minWidth: '220px',
          }}
        >
          {t.type === 'success' ? <Check size={14} /> : <X size={14} />}
          <span className="flex-1">{t.message}</span>
          <button onClick={() => onDismiss(t.id)} style={{ color: 'rgba(255,255,255,0.7)' }}>
            <X size={12} />
          </button>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Proposal list row (left panel)
// ---------------------------------------------------------------------------

function ProposalRow({
  proposal,
  selected,
  isNew,
  onClick,
  checked,
  onCheck,
  showCheckbox,
}: {
  proposal: Proposal
  selected: boolean
  isNew: boolean
  onClick: () => void
  checked: boolean
  onCheck: (v: boolean) => void
  showCheckbox: boolean
}) {
  const style = RISK_STYLES[proposal.risk_class]

  return (
    <button
      onClick={onClick}
      className="w-full text-left px-3 py-3 flex items-start gap-2.5 relative transition-colors"
      style={{
        backgroundColor: selected ? '#3f3f46' : 'transparent',
        borderLeft: selected ? `3px solid ${style.border}` : '3px solid transparent',
        borderBottom: '1px solid #27272a',
      }}
      onMouseEnter={e => { if (!selected) (e.currentTarget as HTMLElement).style.backgroundColor = '#27272a' }}
      onMouseLeave={e => { if (!selected) (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent' }}
    >
      {/* Unread dot */}
      <span
        className="mt-1.5 shrink-0"
        style={{
          width: '6px',
          height: '6px',
          backgroundColor: isNew ? style.dot : 'transparent',
          display: 'inline-block',
          flexShrink: 0,
        }}
      />

      {/* Checkbox (batch mode) */}
      {showCheckbox && (
        <input
          type="checkbox"
          checked={checked}
          onClick={e => e.stopPropagation()}
          onChange={e => onCheck(e.target.checked)}
          className="mt-0.5 shrink-0"
          style={{ accentColor: '#f4f4f5' }}
        />
      )}

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span
            className={`text-[10px] font-bold uppercase px-1.5 py-0.5 shrink-0 ${style.badge}`}
          >
            {proposal.risk_class}
          </span>
          <span
            className="text-xs font-medium truncate"
            style={{ color: '#f4f4f5' }}
          >
            {formatActionType(proposal.action_type)}
          </span>
        </div>
        <p className="text-xs truncate" style={{ color: '#a1a1aa' }}>
          {proposal.description}
        </p>
        <div className="flex items-center gap-1 mt-1" style={{ color: '#52525b' }}>
          <Clock size={10} />
          <span className="text-[10px]">{relativeTime(proposal.created_at)}</span>
        </div>
      </div>
    </button>
  )
}

// ---------------------------------------------------------------------------
// Detail panel (right)
// ---------------------------------------------------------------------------

function DetailPanel({
  proposal,
  onApprove,
  onReject,
  onUndo,
  loading,
}: {
  proposal: Proposal | null
  onApprove: (traceId: string, approver: string, feedback: string) => Promise<void>
  onReject: (traceId: string, approver: string, feedback: string) => Promise<void>
  onUndo: (traceId: string) => void
  loading: boolean
}) {
  const [approver, setApprover] = useState<string>(
    () => localStorage.getItem('sage_approver_name') ?? ''
  )
  const [feedback, setFeedback] = useState('')
  const [acting, setActing] = useState(false)

  // Persist approver name
  useEffect(() => {
    if (approver) localStorage.setItem('sage_approver_name', approver)
  }, [approver])

  // Reset feedback when proposal changes
  useEffect(() => { setFeedback('') }, [proposal?.trace_id])

  if (!proposal) {
    return (
      <div
        className="flex-1 flex flex-col items-center justify-center"
        style={{ backgroundColor: '#18181b' }}
      >
        <Inbox size={40} style={{ color: '#3f3f46' }} />
        <p className="mt-3 text-sm font-medium" style={{ color: '#52525b' }}>
          Select a proposal to review
        </p>
      </div>
    )
  }

  const style = RISK_STYLES[proposal.risk_class]
  const isDestructive = proposal.risk_class === 'DESTRUCTIVE'

  const handleApprove = async () => {
    setActing(true)
    try {
      await onApprove(proposal.trace_id, approver || 'human', feedback)
      setFeedback('')
    } finally {
      setActing(false)
    }
  }

  const handleReject = async () => {
    setActing(true)
    try {
      await onReject(proposal.trace_id, approver || 'human', feedback)
      setFeedback('')
    } finally {
      setActing(false)
    }
  }

  const disabled = acting || loading

  // Handle evolution proposals with specialized UI
  if (isEvolutionProposal(proposal)) {
    return (
      <div
        className="flex-1 flex flex-col overflow-hidden"
        style={{ backgroundColor: '#18181b' }}
      >
        <EvolutionProposalCard proposal={proposal} />
        <div
          className="px-6 py-4 shrink-0 space-y-3"
          style={{ borderTop: '1px solid #27272a', backgroundColor: '#09090b' }}
        >
          {/* Approving as */}
          <div className="flex items-center gap-2">
            <span className="text-xs shrink-0" style={{ color: '#52525b' }}>Approving as</span>
            <input
              type="text"
              value={approver}
              onChange={e => setApprover(e.target.value)}
              placeholder="your name"
              className="flex-1 text-xs px-2 py-1 bg-transparent border-b outline-none"
              style={{ borderColor: '#3f3f46', color: '#f4f4f5' }}
            />
          </div>

          {/* Evolution-specific feedback */}
          <select
            value={feedback}
            onChange={e => setFeedback(e.target.value)}
            className="w-full text-xs px-3 py-2 outline-none"
            style={{
              backgroundColor: '#18181b',
              border: '1px solid #3f3f46',
              color: '#f4f4f5',
            }}
          >
            <option value="">Select rejection reason...</option>
            <option value="poor_fitness">Poor Fitness Score</option>
            <option value="risky_mutation">Risky Mutation</option>
            <option value="premature_convergence">Premature Convergence</option>
            <option value="regulatory_concern">Regulatory Concern</option>
          </select>

          {/* Buttons */}
          <div className="flex gap-2">
            <button
              onClick={handleApprove}
              disabled={disabled}
              className="flex-1 flex items-center justify-center gap-1.5 text-xs font-semibold py-2 transition-colors"
              style={{
                backgroundColor: disabled ? '#166534' : '#16a34a',
                color: '#fff',
                opacity: disabled ? 0.6 : 1,
                cursor: disabled ? 'not-allowed' : 'pointer',
              }}
              onMouseEnter={e => { if (!disabled) (e.currentTarget as HTMLElement).style.backgroundColor = '#15803d' }}
              onMouseLeave={e => { if (!disabled) (e.currentTarget as HTMLElement).style.backgroundColor = '#16a34a' }}
            >
              <Check size={13} />
              Approve
            </button>
            <button
              onClick={handleReject}
              disabled={disabled || !feedback}
              className="flex-1 flex items-center justify-center gap-1.5 text-xs font-semibold py-2 transition-colors"
              style={{
                backgroundColor: disabled || !feedback ? '#7f1d1d' : '#dc2626',
                color: '#fff',
                opacity: disabled || !feedback ? 0.6 : 1,
                cursor: disabled || !feedback ? 'not-allowed' : 'pointer',
              }}
              onMouseEnter={e => { if (!disabled && feedback) (e.currentTarget as HTMLElement).style.backgroundColor = '#b91c1c' }}
              onMouseLeave={e => { if (!disabled && feedback) (e.currentTarget as HTMLElement).style.backgroundColor = '#dc2626' }}
            >
              <X size={13} />
              Reject
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div
      className="flex-1 flex flex-col overflow-hidden"
      style={{ backgroundColor: '#18181b' }}
    >
      {/* Detail header */}
      <div
        className="px-6 py-4 shrink-0"
        style={{ borderBottom: '1px solid #27272a' }}
      >
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-xs font-bold uppercase px-2 py-0.5 ${style.badge}`}>
                {proposal.risk_class}
              </span>
              {!proposal.reversible && (
                <span className="text-xs font-bold px-2 py-0.5 bg-red-950 text-red-400">
                  IRREVERSIBLE
                </span>
              )}
              {proposal.expires_at && (
                <span className="text-xs font-mono" style={{ color: '#71717a' }}>
                  expires in {formatCountdown(proposal.expires_at)}
                </span>
              )}
            </div>
            <h2 className="text-base font-semibold" style={{ color: '#f4f4f5' }}>
              {formatActionType(proposal.action_type)}
            </h2>
            <p className="text-sm mt-0.5" style={{ color: '#a1a1aa' }}>
              {proposal.description}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3 mt-2 text-xs" style={{ color: '#52525b' }}>
          <span>Proposed by <span style={{ color: '#71717a' }}>{proposal.proposed_by}</span></span>
          <span>·</span>
          <span>{relativeTime(proposal.created_at)}</span>
          <span>·</span>
          <span className="font-mono">{proposal.trace_id.slice(0, 8)}…</span>
        </div>
      </div>

      {/* Payload */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {isDestructive && (
          <div
            className="flex items-start gap-2 px-3 py-2 mb-4"
            style={{ backgroundColor: '#450a0a', border: '1px solid #ef4444' }}
          >
            <AlertTriangle size={14} className="shrink-0 mt-0.5" style={{ color: '#ef4444' }} />
            <p className="text-xs" style={{ color: '#fca5a5' }}>
              This action is <strong>destructive</strong> and may be irreversible.
              Review carefully before approving.
            </p>
          </div>
        )}

        {/* Payload block */}
        <div className="mb-4">
          <p className="text-xs font-semibold uppercase tracking-widest mb-2" style={{ color: '#52525b' }}>
            Payload
          </p>
          {proposal.action_type === 'code_diff' && proposal.payload?.diff ? (
            <div
              className="text-xs overflow-auto p-4 font-mono leading-relaxed"
              style={{
                backgroundColor: '#09090b',
                border: '1px solid #27272a',
                maxHeight: '320px',
              }}
            >
              {String(proposal.payload.diff).split('\n').map((line, i) => {
                let color = '#a1a1aa'
                let bg = 'transparent'
                if (line.startsWith('+') && !line.startsWith('+++')) {
                  color = '#86efac'
                  bg = 'rgba(22,101,52,0.3)'
                } else if (line.startsWith('-') && !line.startsWith('---')) {
                  color = '#fca5a5'
                  bg = 'rgba(127,29,29,0.3)'
                } else if (line.startsWith('@@')) {
                  color = '#93c5fd'
                  bg = 'rgba(30,58,138,0.2)'
                }
                return (
                  <span
                    key={i}
                    style={{ display: 'block', color, backgroundColor: bg, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}
                  >
                    {line || '\u00a0'}
                  </span>
                )
              })}
            </div>
          ) : (
            <pre
              className="text-xs overflow-auto p-4 font-mono leading-relaxed"
              style={{
                backgroundColor: '#09090b',
                color: '#a1a1aa',
                border: '1px solid #27272a',
                maxHeight: '320px',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
              }}
            >
              {JSON.stringify(proposal.payload, null, 2)}
            </pre>
          )}
        </div>
      </div>

      {/* Action area */}
      <div
        className="px-6 py-4 shrink-0 space-y-3"
        style={{ borderTop: '1px solid #27272a', backgroundColor: '#09090b' }}
      >
        {/* Approving as */}
        <div className="flex items-center gap-2">
          <span className="text-xs shrink-0" style={{ color: '#52525b' }}>Approving as</span>
          <input
            type="text"
            value={approver}
            onChange={e => setApprover(e.target.value)}
            placeholder="your name"
            className="flex-1 text-xs px-2 py-1 bg-transparent border-b outline-none"
            style={{ borderColor: '#3f3f46', color: '#f4f4f5' }}
          />
        </div>

        {/* Feedback */}
        <textarea
          rows={2}
          value={feedback}
          onChange={e => setFeedback(e.target.value)}
          placeholder="Optional context or feedback…"
          className="w-full text-xs px-3 py-2 resize-none outline-none"
          style={{
            backgroundColor: '#18181b',
            border: '1px solid #3f3f46',
            color: '#f4f4f5',
          }}
        />

        {/* Buttons */}
        <div className="flex gap-2">
          <button
            onClick={handleApprove}
            disabled={disabled}
            className="flex-1 flex items-center justify-center gap-1.5 text-xs font-semibold py-2 transition-colors"
            style={{
              backgroundColor: disabled ? '#166534' : '#16a34a',
              color: '#fff',
              opacity: disabled ? 0.6 : 1,
              cursor: disabled ? 'not-allowed' : 'pointer',
            }}
            onMouseEnter={e => { if (!disabled) (e.currentTarget as HTMLElement).style.backgroundColor = '#15803d' }}
            onMouseLeave={e => { if (!disabled) (e.currentTarget as HTMLElement).style.backgroundColor = '#16a34a' }}
          >
            <Check size={13} />
            Approve
          </button>
          <button
            onClick={handleReject}
            disabled={disabled}
            className="flex-1 flex items-center justify-center gap-1.5 text-xs font-semibold py-2 transition-colors"
            style={{
              backgroundColor: disabled ? '#7f1d1d' : '#dc2626',
              color: '#fff',
              opacity: disabled ? 0.6 : 1,
              cursor: disabled ? 'not-allowed' : 'pointer',
            }}
            onMouseEnter={e => { if (!disabled) (e.currentTarget as HTMLElement).style.backgroundColor = '#b91c1c' }}
            onMouseLeave={e => { if (!disabled) (e.currentTarget as HTMLElement).style.backgroundColor = '#dc2626' }}
          >
            <X size={13} />
            Reject
          </button>
        </div>
        {proposal.action_type === 'code_diff' && proposal.status === 'approved' && (
          <button
            onClick={() => onUndo(proposal.trace_id)}
            className="px-3 py-1.5 text-xs font-medium rounded"
            style={{ background: '#78350f', color: '#fde68a' }}
            title="Revert the applied code changes"
          >
            Undo
          </button>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Approvals page
// ---------------------------------------------------------------------------

export default function Approvals() {
  const queryClient = useQueryClient()

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [seenIds, setSeenIds] = useState<Set<string>>(new Set())
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set())
  const [toasts, setToasts] = useState<Toast[]>([])
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date())

  // Ref to track which IDs existed on first load — everything new after that is "unread"
  const initialIdsRef = useRef<Set<string> | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['proposals-pending'],
    queryFn: fetchPendingProposals,
    refetchInterval: 10_000,
  })

  // Handle post-fetch side effects (replaces deprecated onSuccess)
  useEffect(() => {
    if (!data) return
    setLastUpdated(new Date())
    const ids = new Set<string>(data.proposals.map((p: Proposal) => p.trace_id))
    if (initialIdsRef.current === null) {
      // First load: mark all as "seen" (not unread)
      initialIdsRef.current = ids
      setSeenIds(ids)
    }
  }, [data])

  const proposals = data?.proposals ?? []
  const sorted = sortProposals(proposals.filter((p: Proposal) => p.status === 'pending'))
  const pendingCount = sorted.length

  // Update browser tab title
  useEffect(() => {
    document.title = pendingCount > 0
      ? `Approvals (${pendingCount}) — SAGE`
      : 'Approvals — SAGE'
    return () => { document.title = 'SAGE[ai]' }
  }, [pendingCount])

  // Auto-select first proposal if none selected
  useEffect(() => {
    if (!selectedId && sorted.length > 0) {
      setSelectedId(sorted[0].trace_id)
    }
    // Clear selection if it's no longer in the list
    if (selectedId && !sorted.find(p => p.trace_id === selectedId)) {
      setSelectedId(sorted.length > 0 ? sorted[0].trace_id : null)
    }
  }, [sorted, selectedId])

  // Mark as seen when selected
  useEffect(() => {
    if (selectedId) setSeenIds(prev => new Set([...prev, selectedId]))
  }, [selectedId])

  const addToast = useCallback((message: string, type: 'success' | 'error') => {
    const id = Math.random().toString(36).slice(2)
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000)
  }, [])

  const removeProposal = useCallback((traceId: string) => {
    setCheckedIds(prev => { const s = new Set(prev); s.delete(traceId); return s })
    // After invalidation, auto-advance to next
    const idx = sorted.findIndex(p => p.trace_id === traceId)
    const next = sorted[idx + 1] ?? sorted[idx - 1]
    setSelectedId(next?.trace_id ?? null)
  }, [sorted])

  // Approve single
  const handleApprove = useCallback(async (traceId: string, approver: string, feedback: string) => {
    try {
      await approveProposalFull(traceId, approver || 'human', feedback)
      addToast('Proposal approved', 'success')
      removeProposal(traceId)
      queryClient.invalidateQueries({ queryKey: ['proposals-pending'] })
    } catch {
      addToast('Approval failed — check API', 'error')
    }
  }, [addToast, removeProposal, queryClient])

  // Reject single
  const handleReject = useCallback(async (traceId: string, approver: string, feedback: string) => {
    try {
      await rejectProposalFull(traceId, approver || 'human', feedback)
      addToast('Proposal rejected', 'success')
      removeProposal(traceId)
      queryClient.invalidateQueries({ queryKey: ['proposals-pending'] })
    } catch {
      addToast('Rejection failed — check API', 'error')
    }
  }, [addToast, removeProposal, queryClient])

  // Undo approved code_diff proposal
  const undoMutation = useMutation({
    mutationFn: (trace_id: string) => undoProposal(trace_id),
    onSuccess: () => addToast('Undo triggered — changes will be reverted', 'success'),
    onError: (err: Error) => addToast(err.message, 'error'),
  })

  // Batch approve
  const batchMutation = useMutation({
    mutationFn: (traceIds: string[]) =>
      approveBatchProposals(traceIds, localStorage.getItem('sage_approver_name') || 'human'),
    onSuccess: (data) => {
      const count = data.results.filter((r: { status: string }) => r.status === 'approved').length
      addToast(`Approved ${count} proposal${count !== 1 ? 's' : ''}`, 'success')
      setCheckedIds(new Set())
      queryClient.invalidateQueries({ queryKey: ['proposals-pending'] })
    },
    onError: () => addToast('Batch approval failed', 'error'),
  })

  const checkedList = sorted.filter(p => checkedIds.has(p.trace_id))
  const allLowRisk = checkedList.every(
    p => p.risk_class === 'INFORMATIONAL' || p.risk_class === 'EPHEMERAL'
  )
  const showCheckboxes = sorted.length > 1

  const secondsAgo = Math.floor((Date.now() - lastUpdated.getTime()) / 1000)

  const selected = sorted.find(p => p.trace_id === selectedId) ?? null

  return (
    <div
      className="flex h-full overflow-hidden"
      style={{ backgroundColor: '#09090b', margin: '-24px' }}
    >
      {/* Left panel — inbox list */}
      <div
        className="flex flex-col shrink-0 overflow-hidden"
        style={{ width: '320px', backgroundColor: '#18181b', borderRight: '1px solid #27272a' }}
      >
        {/* Panel header */}
        <div
          className="px-4 py-3 shrink-0 flex items-center gap-2"
          style={{ borderBottom: '1px solid #27272a' }}
        >
          <Inbox size={15} style={{ color: '#71717a' }} />
          <span className="text-sm font-semibold flex-1" style={{ color: '#f4f4f5' }}>
            Pending Approvals
          </span>
          {pendingCount > 0 && (
            <span
              className="text-xs font-bold px-2 py-0.5"
              style={{ backgroundColor: '#ef4444', color: '#fff' }}
            >
              {pendingCount}
            </span>
          )}
        </div>

        {/* Batch toolbar */}
        {showCheckboxes && (
          <div
            className="px-3 py-2 flex items-center gap-2 shrink-0"
            style={{ borderBottom: '1px solid #27272a', backgroundColor: '#09090b' }}
          >
            <input
              type="checkbox"
              checked={checkedIds.size === sorted.length && sorted.length > 0}
              onChange={e => {
                if (e.target.checked) setCheckedIds(new Set(sorted.map(p => p.trace_id)))
                else setCheckedIds(new Set())
              }}
              style={{ accentColor: '#f4f4f5' }}
            />
            <span className="text-xs flex-1" style={{ color: '#71717a' }}>
              {checkedIds.size > 0 ? `${checkedIds.size} selected` : 'Select all'}
            </span>
            {checkedIds.size > 0 && allLowRisk && (
              <button
                onClick={() => batchMutation.mutate([...checkedIds])}
                disabled={batchMutation.isPending}
                className="flex items-center gap-1 text-xs px-2 py-1 font-medium"
                style={{ backgroundColor: '#16a34a', color: '#fff' }}
              >
                <CheckSquare size={11} />
                Approve {checkedIds.size}
              </button>
            )}
            {checkedIds.size > 0 && !allLowRisk && (
              <span className="text-[10px]" style={{ color: '#52525b' }}>
                High-risk selected
              </span>
            )}
          </div>
        )}

        {/* List */}
        <div className="flex-1 overflow-y-auto">
          {isLoading && (
            <div className="flex items-center justify-center h-32 gap-2" style={{ color: '#52525b' }}>
              <RefreshCw size={14} className="animate-spin" />
              <span className="text-xs">Loading…</span>
            </div>
          )}
          {!isLoading && sorted.length === 0 && (
            <div className="flex flex-col items-center justify-center h-48 px-6 text-center">
              <CheckSquare size={32} style={{ color: '#3f3f46' }} />
              <p className="mt-3 text-sm font-medium" style={{ color: '#52525b' }}>
                No pending approvals
              </p>
              <p className="mt-1 text-xs" style={{ color: '#3f3f46' }}>
                Your agents are waiting for new tasks
              </p>
            </div>
          )}
          {sorted.map(p => (
            <ProposalRow
              key={p.trace_id}
              proposal={p}
              selected={selectedId === p.trace_id}
              isNew={!seenIds.has(p.trace_id)}
              onClick={() => setSelectedId(p.trace_id)}
              checked={checkedIds.has(p.trace_id)}
              onCheck={v => setCheckedIds(prev => {
                const s = new Set(prev)
                if (v) s.add(p.trace_id); else s.delete(p.trace_id)
                return s
              })}
              showCheckbox={showCheckboxes}
            />
          ))}
        </div>

        {/* Last updated */}
        <div
          className="px-3 py-2 flex items-center gap-1.5 shrink-0"
          style={{ borderTop: '1px solid #27272a' }}
        >
          <RefreshCw size={10} style={{ color: '#3f3f46' }} />
          <span className="text-[10px]" style={{ color: '#3f3f46' }}>
            Updated {secondsAgo}s ago
          </span>
        </div>
      </div>

      {/* Right panel — detail */}
      <DetailPanel
        proposal={selected}
        onApprove={handleApprove}
        onReject={handleReject}
        onUndo={(traceId) => undoMutation.mutate(traceId)}
        loading={batchMutation.isPending}
      />

      {/* Toasts */}
      <ToastContainer toasts={toasts} onDismiss={id => setToasts(prev => prev.filter(t => t.id !== id))} />
    </div>
  )
}
