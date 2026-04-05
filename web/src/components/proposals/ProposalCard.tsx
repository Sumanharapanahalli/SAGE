import { useState } from 'react'
import { CheckCircle, XCircle, AlertTriangle, Clock, ChevronDown, ChevronUp } from 'lucide-react'

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

const riskColors: Record<string, string> = {
  INFORMATIONAL: 'bg-gray-100 text-gray-600 border-gray-200',
  EPHEMERAL:     'bg-blue-50 text-blue-700 border-blue-200',
  STATEFUL:      'bg-amber-50 text-amber-700 border-amber-200',
  EXTERNAL:      'bg-orange-50 text-orange-700 border-orange-200',
  DESTRUCTIVE:   'bg-red-50 text-red-700 border-red-200',
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

  const relativeTime = (() => {
    const ms = Date.now() - new Date(proposal.created_at).getTime()
    if (ms < 60000) return 'just now'
    if (ms < 3600000) return `${Math.floor(ms / 60000)}m ago`
    return `${Math.floor(ms / 3600000)}h ago`
  })()

  return (
    <div className={`rounded-lg border p-4 ${riskColors[proposal.risk_class] || riskColors.STATEFUL}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-bold uppercase tracking-wide opacity-70">
              [{proposal.risk_class}]
            </span>
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
        <pre className="mt-3 text-xs bg-white text-gray-100 rounded p-3 overflow-x-auto max-h-64 overflow-y-auto">
          {diff}
        </pre>
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
