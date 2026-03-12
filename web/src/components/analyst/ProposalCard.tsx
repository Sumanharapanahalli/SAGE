import type { AnalysisResponse } from '../../api/client'

interface Props { proposal: AnalysisResponse }

const SEVERITY_BADGE: Record<string, string> = {
  RED: 'bg-red-100 text-red-700',
  AMBER: 'bg-amber-100 text-amber-700',
  GREEN: 'bg-green-100 text-green-700',
}

export default function ProposalCard({ proposal }: Props) {
  const sev = (proposal.severity ?? 'GREEN').toUpperCase()
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
      <div className="flex items-center gap-3 mb-4">
        <span className={`text-xs font-bold px-2 py-1 rounded ${SEVERITY_BADGE[sev] ?? SEVERITY_BADGE.GREEN}`}>
          {sev}
        </span>
        <span className="text-xs text-gray-400 font-mono">Trace: {proposal.trace_id}</span>
      </div>
      <div className="mb-3">
        <div className="text-xs font-semibold text-gray-500 uppercase mb-1">Root Cause Hypothesis</div>
        <p className="text-sm text-gray-800">{proposal.root_cause_hypothesis}</p>
      </div>
      <div>
        <div className="text-xs font-semibold text-gray-500 uppercase mb-1">Recommended Action</div>
        <p className="text-sm text-gray-800">{proposal.recommended_action}</p>
      </div>
      {proposal.confidence && (
        <div className="mt-3 text-xs text-gray-400">Confidence: {proposal.confidence}</div>
      )}
    </div>
  )
}
