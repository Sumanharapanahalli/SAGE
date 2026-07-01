# Task 15: Copy-to-clipboard for diff/code blocks

**Category:** ui  
**Score:** 9.0/10  
**Converged:** True  
**Iterations:** 2  
**Elapsed:** 189s  

---

## Task

Add a copy-to-clipboard button to the diff <pre> block in web/src/components/proposals/ProposalCard.tsx. The button appears in the top-right corner of the pre block on hover, shows a clipboard icon, and changes to a check mark for 2 seconds after copying. Use the browser Clipboard API (no external dep). Also apply to any <pre> blocks in the Audit log page.

## Criteria

Copy button appears on hover over <pre>; clipboard API is used; visual feedback (check icon) shows for 2s after copy; button is accessible (aria-label='Copy to clipboard'); TypeScript compiles.

## Proposal (submit to HITL approval gate)

// === FILE: web/src/components/ui/CopyButton.tsx (NEW) ===
import { useEffect, useRef, useState } from 'react'
import { Copy, Check } from 'lucide-react'

interface CopyButtonProps {
  /** Text to copy to the clipboard. */
  text: string
  /** Optional extra classes for positioning/styling within the parent. */
  className?: string
}

/**
 * Small clipboard button intended to overlay a <pre> block.
 *
 * Place inside a `relative group` container; the button stays hidden until the
 * container is hovered/focused, then copies `text` via the browser Clipboard
 * API and flips to a check mark for 2 seconds. No external dependencies.
 */
export default function CopyButton({ text, className = '' }: CopyButtonProps) {
  const [copied, setCopied] = useState(false)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Clean up the pending timer if the component unmounts mid-countdown.
  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
  }, [])

  const handleCopy = async () => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text)
      } else {
        // Fallback for non-secure contexts / older browsers.
        const textarea = document.createElement('textarea')
        textarea.value = text
        textarea.style.position = 'fixed'
        textarea.style.opacity = '0'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
      }
      setCopied(true)
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
      timeoutRef.current = setTimeout(() => setCopied(false), 2000)
    } catch {
      // Silently ignore copy failures (e.g. permission denied).
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label={copied ? 'Copied' : 'Copy to clipboard'}
      title={copied ? 'Copied' : 'Copy'}
      className={
        'absolute top-2 right-2 p-1.5 rounded bg-gray-800/80 text-gray-300 ' +
        'hover:bg-gray-700 hover:text-white focus:outline-none focus:ring-1 focus:ring-gray-400 ' +
        'opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity ' +
        className
      }
    >
      {copied ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
    </button>
  )
}
```

```tsx
// === FILE: web/src/components/ui/CodeBlock.tsx (NEW) ===
// Reusable <pre> wrapper for the Audit log page (and anywhere else that renders
// raw text/JSON). Drop-in: <CodeBlock>{logText}</CodeBlock>.
import CopyButton from './CopyButton'

interface CodeBlockProps {
  /** Raw text rendered inside the <pre>. Also used as the copy payload. */
  children: string
  className?: string
}

export default function CodeBlock({ children, className = '' }: CodeBlockProps) {
  return (
    <div className="relative group">
      <CopyButton text={children} />
      <pre
        className={
          'text-xs bg-gray-900 text-gray-100 rounded p-3 overflow-x-auto ' + className
        }
      >
        {children}
      </pre>
    </div>
  )
}
```

```tsx
// === FILE: web/src/components/proposals/ProposalCard.tsx ===
import { useState } from 'react'
import { CheckCircle, XCircle, AlertTriangle, Clock, ChevronDown, ChevronUp } from 'lucide-react'
import RiskBadge, { RISK_CONFIG } from '../ui/RiskBadge'
import CopyButton from '../ui/CopyButton'
import { formatRelativeTime } from '../../lib/date'

interface Proposal {
  trace_id: string
  action_type: string
  risk_class: 'INFORMATIONAL' | 'EPHEMERAL' | 'STATEFUL' | 'EXTERNAL' | 'DESTRUCTIVE'
  reversible: boolean
  proposed_by: string
  description: string
  payload: Record<string, unknown>
  status: string
  created_at: string
}

interface ProposalCardProps {
  proposal: Proposal
  onApprove: (traceId: string, approvedBy?: string, note?: string) => Promise<void>
  onReject: (traceId: string, feedback: string) => Promise<void>
}

export default function ProposalCard({ proposal, onApprove, onReject }: ProposalCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [rejecting, setRejecting] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [note, setNote] = useState('')
  const [loading, setLoading] = useState(false)

  const diff = (proposal.payload as any)?.diff as string | undefined
  const isDestructive = proposal.risk_class === 'DESTRUCTIVE'

  const handleApprove = async () => {
    setLoading(true)
    try {
      await onApprove(proposal.trace_id, 'human', note)
    } finally {
      setLoading(false)
    }
  }

  const handleReject = async () => {
    if (!feedback.trim()) return
    setLoading(true)
    try {
      await onReject(proposal.trace_id, feedback)
    } finally {
      setLoading(false)
      setRejecting(false)
    }
  }

  const relativeTime = formatRelativeTime(proposal.created_at)

  const riskConfig = RISK_CONFIG[proposal.risk_class] || RISK_CONFIG.STATEFUL

  return (
    <div
      className="rounded-lg border p-4"
      style={{
        backgroundColor: riskConfig.bgVar,
        color: riskConfig.colorVar,
        borderColor: riskConfig.borderVar,
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <RiskBadge risk={proposal.risk_class} />
            {!proposal.reversible && (
              <span className="text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded font-medium">
                Irreversible
              </span>
            )}
          </div>
          <div className="text-sm font-medium text-gray-800 leading-snug">
            {proposal.description}
          </div>
          <div className="text-xs text-gray-500 mt-1 flex items-center gap-2">
            <Clock size={11} />
            <span>Proposed by {proposal.proposed_by} · {relativeTime}</span>
          </div>
        </div>
        {diff && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1 shrink-0"
          >
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            diff
          </button>
        )}
      </div>

      {expanded && diff && (
        <div className="relative group mt-3">
          <CopyButton text={diff} />
          <pre className="text-xs bg-gray-900 text-gray-100 rounded p-3 overflow-x-auto max-h-64 overflow-y-auto">
            {diff}
          </pre>
        </div>
      )}

      {isDestructive && (
        <div className="mt-3 flex items-start gap-2 bg-red-100 rounded p-2">
          <AlertTriangle size={14} className="text-red-600 mt-0.5 shrink-0" />
          <p className="text-xs text-red-700">
            This action is <strong>irreversible</strong>. Provide a reason note before approving.
          </p>
        </div>
      )}

      {isDestructive && (
        <input
          type="text"
          placeholder="Reason for deletion (required)"
          value={note}
          onChange={e => setNote(e.target.value)}
          className="mt-2 w-full text-xs border border-red-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-red-400"
        />
      )}

      {rejecting && (
        <div className="mt-3 space-y-2">
          <textarea
            className="w-full text-xs border rounded px-2 py-1.5 resize-none focus:outline-none focus:ring-1 focus:ring-gray-400"
            placeholder="Reason for rejection..."
            rows={2}
            value={feedback}
            onChange={e => setFeedback(e.target.value)}
          />
          <div className="flex gap-2">
            <button
              onClick={handleReject}
              disabled={!feedback.trim() || loading}
              className="text-xs px-3 py-1.5 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
            >
              Confirm Reject
            </button>
            <button
              onClick={() => setRejecting(false)}
              className="text-xs px-3 py-1.5 text-gray-600 hover:text-gray-800"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {!rejecting && (
        <div className="mt-3 flex gap-2">
          <button
            onClick={handleApprove}
            disabled={loading || (isDestructive && !note.trim())}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-orange-600 text-white rounded hover:bg-orange-700 disabled:opacity-50"
          >
            <CheckCircle size={13} />
            Approve
          </button>
          <button
            onClick={() => setRejecting(true)}
            disabled={loading}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-white border border-gray-300 text-gray-700 rounded hover:bg-gray-50 disabled:opacity-50"
          >
            <XCircle size={13} />
            Reject
          </button>
        </div>
      )}
    </div>
  )
}
```

```tsx
// === FILE: web/src/pages/AuditLog.tsx ===
// Audit log page. Each entry exposes its raw diff/payload in a <pre> block,
// now wrapped with <CodeBlock> so reviewers can copy the contents with the
// hover clipboard button (icon flips to a check for 2s after copying).
import { useEffect, useState } from 'react'
import { Clock } from 'lucide-react'
import CodeBlock from '../components/ui/CodeBlock'
import RiskBadge from '../components/ui/RiskBadge'
import { formatRelativeTime } from '../lib/date'

interface AuditEntry {
  trace_id: string
  action_type: string
  risk_class: 'INFORMATIONAL' | 'EPHEMERAL' | 'STATEFUL' | 'EXTERNAL' | 'DESTRUCTIVE'
  decision: 'approved' | 'rejected'
  decided_by: string
  note?: string
  payload: Record<string, unknown>
  created_at: string
}

export default function AuditLog() {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetch('/api/audit')
      .then(res => {
        if (!res.ok) throw new Error(`Failed to load audit log (${res.status})`)
        return res.json()
      })
      .then((data: AuditEntry[]) => {
        if (!cancelled) setEntries(data)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load audit log')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (loading) {
    return <div className="p-6 text-sm text-gray-500">Loading audit log…</div>
  }

  if (error) {
    return <div className="p-6 text-sm text-red-600">{error}</div>
  }

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-lg font-semibold text-gray-800">Audit Log</h1>

      {entries.length === 0 && (
        <div className="text-sm text-gray-500">No audit entries yet.</div>
      )}

      {entries.map(entry => {
        const diff = (entry.payload as any)?.diff as string | undefined
        const payloadJson = JSON.stringify(entry.payload, null, 2)

        return (
          <div key={entry.trace_id} className="rounded-lg border border-gray-200 p-4">
            <div className="flex items-center gap-2 mb-1">
              <RiskBadge risk={entry.risk_class} />
              <span
                className={
                  'text-xs px-1.5 py-0.5 rounded font-medium ' +
                  (entry.decision === 'approved'
                    ? 'bg-green-100 text-green-700'
                    : 'bg-red-100 text-red-700')
                }
              >
                {entry.decision}
              </span>
              <span className="text-sm font-medium text-gray-800">{entry.action_type}</span>
            </div>

            <div className="text-xs text-gray-500 mb-3 flex items-center gap-2">
              <Clock size={11} />
              <span>
                {entry.decision === 'approved' ? 'Approved' : 'Rejected'} by {entry.decided_by} ·{' '}
                {formatRelativeTime(entry.created_at)}
              </span>
            </div>

            {entry.note && (
              <p className="text-xs text-gray-600 mb-3">
                <span className="font-medium">Note:</span> {entry.note}
              </p>
            )}

            {/* Copy-enabled diff block (when present). */}
            {diff && (
              <div className="mb-3">
                <div className="text-xs font-medium text-gray-500 mb-1">Diff</div>
                <CodeBlock className="max-h-96 overflow-y-auto">{diff}</CodeBlock>
              </div>
            )}

            {/* Copy-enabled raw payload block. */}
            <div>
              <div className="text-xs font-medium text-gray-500 mb-1">Payload</div>
              <CodeBlock className="max-h-96 overflow-y-auto">{payloadJson}</CodeBlock>
            </div>
          </div>
        )
      })}
    </div>
  )
}

---

## Iteration History

**Iter 1** — score 6.5 pass=False  
Feedback: Strong shared-component work (CopyButton + CodeBlock) satisfies rubric points 1-8 and 10-13: top-right absolute button, opacity-0/group-hover reveal, lucide Copy→Check icons, navigator.clipboard.write  

**Iter 2** — score 9.0 pass=True  
Feedback:   

