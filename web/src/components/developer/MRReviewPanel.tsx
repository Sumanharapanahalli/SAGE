import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { reviewMR, type MRReviewResponse } from '../../api/client'
import { CheckCircle, XCircle } from 'lucide-react'

export default function MRReviewPanel() {
  const [projectId, setProjectId] = useState('')
  const [mrIid, setMrIid] = useState('')
  const [result, setResult] = useState<MRReviewResponse | null>(null)

  const { mutate, isPending, isError, error } = useMutation({
    mutationFn: () => reviewMR(Number(projectId), Number(mrIid)),
    onSuccess: setResult,
  })

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">Review Merge Request</h2>
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Project ID</label>
          <input type="number" value={projectId} onChange={(e) => setProjectId(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500" placeholder="7" />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">MR IID</label>
          <input type="number" value={mrIid} onChange={(e) => setMrIid(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500" placeholder="15" />
        </div>
      </div>
      {isError && <p className="text-sm text-red-500 mb-2">{String((error as Error)?.message)}</p>}
      <button disabled={isPending || !projectId || !mrIid} onClick={() => mutate()}
        className="flex items-center gap-2 bg-orange-600 hover:bg-orange-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg mb-4 transition-colors">
        {isPending ? 'Reviewing (ReAct loop running)...' : 'Review MR'}
      </button>
      {result && (
        <div className="border border-gray-200 rounded-lg p-4 space-y-3">
          <div className="flex items-center gap-2">
            {result.approved ? <CheckCircle className="text-orange-500" size={18} /> : <XCircle className="text-red-400" size={18} />}
            <span className="font-semibold text-sm">{result.approved ? 'Approved' : 'Changes Required'}</span>
            <span className="text-xs text-gray-400 ml-auto font-mono">{result.trace_id?.slice(0, 8)}</span>
          </div>
          <p className="text-sm text-gray-700">{result.summary}</p>
          {result.issues?.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase mb-1">Issues</div>
              <ul className="list-disc list-inside text-sm text-red-600 space-y-0.5">
                {result.issues.map((i, n) => <li key={n}>{i}</li>)}
              </ul>
            </div>
          )}
          {result.suggestions?.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase mb-1">Suggestions</div>
              <ul className="list-disc list-inside text-sm text-gray-700 space-y-0.5">
                {result.suggestions.map((s, n) => <li key={n}>{s}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
