import type { MonitorStatus } from '../../api/client'
import { Activity } from 'lucide-react'

interface Props { data: MonitorStatus }

const INTEGRATIONS = [
  { key: 'teams_configured',    label: 'Teams',    source: 'teams' },
  { key: 'metabase_configured', label: 'Metabase', source: 'metabase' },
  { key: 'gitlab_configured',   label: 'GitLab',   source: 'gitlab' },
] as const

export default function MonitorStatusPanel({ data }: Props) {
  return (
    <div className="space-y-4">
      {/* Overall status */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm flex items-center gap-3">
        <span className={`w-3 h-3 rounded-full ${data.running ? 'bg-orange-500 animate-pulse' : 'bg-gray-300'}`} />
        <div>
          <div className="text-sm font-semibold text-gray-800">
            Monitor {data.running ? 'Running' : 'Idle'}
          </div>
          <div className="text-xs text-gray-400">
            {data.thread_count} active thread{data.thread_count !== 1 ? 's' : ''} · {data.seen_messages} messages · {data.seen_issues} issues seen
          </div>
        </div>
      </div>

      {/* Integration poller cards */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-1.5">
          <Activity size={13} /> Poller Threads
        </h2>
        <div className="space-y-2">
          {INTEGRATIONS.map(({ key, label, source }) => {
            const configured = data[key]
            const active = data.active_threads.includes(source)
            return (
              <div key={key} className="flex items-center gap-3 p-3 border border-gray-100 rounded-lg">
                <span className={`w-2.5 h-2.5 rounded-full ${active ? 'bg-orange-500 animate-pulse' : configured ? 'bg-yellow-400' : 'bg-gray-300'}`} />
                <div className="flex-1">
                  <div className="text-sm font-medium text-gray-800">{label}</div>
                  <div className="text-xs text-gray-400">
                    {!configured ? 'Not configured' : active ? 'Polling' : 'Configured — not polling'}
                  </div>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                  active ? 'bg-orange-100 text-orange-700' :
                  configured ? 'bg-yellow-50 text-yellow-700' :
                  'bg-gray-100 text-gray-500'
                }`}>
                  {active ? 'Running' : configured ? 'Ready' : 'Off'}
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
