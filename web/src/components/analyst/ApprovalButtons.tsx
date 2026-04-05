import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { approveProposal, rejectProposal } from '../../api/client'
import { CheckCircle, XCircle } from 'lucide-react'

interface Props { traceId: string; onDone: () => void }

export default function ApprovalButtons({ traceId, onDone }: Props) {
  const [feedback, setFeedback] = useState('')
  const [showReject, setShowReject] = useState(false)
  const qc = useQueryClient()

  const { mutate: approve, isPending: approving } = useMutation({
    mutationFn: () => approveProposal(traceId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['audit'] }); onDone() },
  })

  const { mutate: reject, isPending: rejecting } = useMutation({
    mutationFn: () => rejectProposal(traceId, feedback),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['audit'] }); onDone() },
  })

  return (
    <div className="space-y-3">
      <div className="flex gap-3">
        <button
          disabled={approving}
          onClick={() => approve()}
          className="flex items-center gap-2 bg-orange-600 hover:bg-orange-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          <CheckCircle size={15} /> {approving ? 'Approving...' : 'Approve'}
        </button>
        <button
          onClick={() => setShowReject(!showReject)}
          className="flex items-center gap-2 bg-red-50 hover:bg-red-100 text-red-600 border border-red-200 text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          <XCircle size={15} /> Reject & Teach
        </button>
      </div>
      {showReject && (
        <div className="space-y-2">
          <textarea
            className="w-full h-20 border border-gray-200 rounded-lg p-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-red-400"
            placeholder="Explain the correct root cause..."
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
          />
          <button
            disabled={rejecting || !feedback.trim()}
            onClick={() => reject()}
            className="bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white text-sm px-3 py-1.5 rounded-lg transition-colors"
          >
            {rejecting ? 'Submitting...' : 'Submit Feedback'}
          </button>
        </div>
      )}
    </div>
  )
}
