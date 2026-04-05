import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { analyzeLog, type AnalysisResponse } from '../../api/client'
import { Search } from 'lucide-react'

interface Props {
  onResult: (r: AnalysisResponse) => void
  placeholder?: string
}

export default function LogAnalysisForm({ onResult, placeholder }: Props) {
  const [logEntry, setLogEntry] = useState('')
  const { mutate, isPending, isError, error } = useMutation({
    mutationFn: () => analyzeLog(logEntry),
    onSuccess: (data) => { onResult(data); setLogEntry('') },
  })

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Analyze Log Entry</h2>
      <textarea
        className="w-full h-32 border border-gray-200 rounded-lg p-3 text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-orange-500"
        placeholder={placeholder ?? 'Paste error log here...'}
        value={logEntry}
        onChange={(e) => setLogEntry(e.target.value)}
      />
      {isError && <p className="text-sm text-red-500 mt-1">{String((error as Error)?.message)}</p>}
      <button
        disabled={isPending || !logEntry.trim()}
        onClick={() => mutate()}
        className="mt-3 flex items-center gap-2 bg-orange-600 hover:bg-orange-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
      >
        <Search size={15} />
        {isPending ? 'Analyzing...' : 'Analyze'}
      </button>
    </div>
  )
}
