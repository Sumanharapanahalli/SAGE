import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { createMR, type MRCreateResponse } from '../../api/client'
import { GitMerge } from 'lucide-react'

export default function MRCreateForm() {
  const [projectId, setProjectId] = useState('')
  const [issueIid, setIssueIid] = useState('')
  const [branch, setBranch] = useState('')
  const [result, setResult] = useState<MRCreateResponse | null>(null)

  const { mutate, isPending, isError, error } = useMutation({
    mutationFn: () => createMR(Number(projectId), Number(issueIid), branch || undefined),
    onSuccess: setResult,
  })

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">Create Merge Request</h2>
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Project ID</label>
          <input type="number" value={projectId} onChange={(e) => setProjectId(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500" placeholder="7" />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Issue IID</label>
          <input type="number" value={issueIid} onChange={(e) => setIssueIid(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500" placeholder="42" />
        </div>
      </div>
      <div className="mb-3">
        <label className="text-xs text-gray-500 mb-1 block">Branch (optional)</label>
        <input type="text" value={branch} onChange={(e) => setBranch(e.target.value)}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500" placeholder="sage-ai/42-fix-sensor" />
      </div>
      {isError && <p className="text-sm text-red-500 mb-2">{String((error as Error)?.message)}</p>}
      {result && !result.error && (
        <div className="mb-3 p-3 bg-orange-50 border border-orange-200 rounded-lg text-sm">
          MR created: <a href={result.mr_url} target="_blank" rel="noreferrer" className="text-orange-700 underline">{result.mr_title}</a>
        </div>
      )}
      <button disabled={isPending || !projectId || !issueIid} onClick={() => mutate()}
        className="flex items-center gap-2 bg-orange-600 hover:bg-orange-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
        <GitMerge size={15} /> {isPending ? 'Creating...' : 'Create MR'}
      </button>
    </div>
  )
}
