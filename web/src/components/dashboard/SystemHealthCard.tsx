import { CheckCircle, XCircle } from 'lucide-react'
import type { HealthResponse } from '../../api/client'

interface Props { data: HealthResponse }

export default function SystemHealthCard({ data }: Props) {
  const integrations = [
    { label: 'GitLab', ok: data.environment.gitlab_configured },
    { label: 'Teams', ok: data.environment.teams_configured },
    { label: 'Metabase', ok: data.environment.metabase_configured },
    { label: 'Spira', ok: data.environment.spira_configured },
  ]

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">System Health</h2>
      <div className="flex items-center gap-2 mb-4">
        <span className="w-3 h-3 rounded-full bg-green-500" />
        <span className="font-bold text-gray-800">{data.service}</span>
        <span className="text-gray-400 text-sm">v{data.version}</span>
      </div>
      <div className="text-sm text-gray-600 mb-1"><span className="font-medium">LLM:</span> {data.llm_provider}</div>
      <div className="text-sm text-gray-400 mb-4">Last check: {new Date(data.timestamp).toLocaleTimeString()}</div>
      <div className="grid grid-cols-2 gap-2">
        {integrations.map(({ label, ok }) => (
          <div key={label} className="flex items-center gap-1.5 text-sm">
            {ok ? <CheckCircle size={14} className="text-green-500" /> : <XCircle size={14} className="text-red-400" />}
            <span className={ok ? 'text-gray-700' : 'text-gray-400'}>{label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
