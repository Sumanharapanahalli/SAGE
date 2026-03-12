import type { MonitorStatus } from '../../api/client'
import { Activity } from 'lucide-react'

interface Props { data: MonitorStatus }

export default function MonitorStatusPanel({ data }: Props) {
  const threads = data.threads as Record<string, { running: boolean; last_poll?: string; event_count?: number }> | undefined

  if (!threads) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
        <div className="flex items-center gap-2 text-gray-500">
          <Activity size={16} />
          <span className="text-sm">Monitor status unavailable</span>
        </div>
        <pre className="text-xs mt-3 bg-gray-50 p-3 rounded overflow-auto">{JSON.stringify(data, null, 2)}</pre>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">Poller Threads</h2>
      <div className="space-y-3">
        {Object.entries(threads).map(([name, info]) => (
          <div key={name} className="flex items-center gap-3 p-3 border border-gray-100 rounded-lg">
            <span className={`w-2.5 h-2.5 rounded-full ${info.running ? 'bg-green-500' : 'bg-red-400'}`} />
            <div className="flex-1">
              <div className="text-sm font-medium text-gray-800 capitalize">{name}</div>
              {info.last_poll && (
                <div className="text-xs text-gray-400">Last poll: {new Date(info.last_poll).toLocaleTimeString()}</div>
              )}
            </div>
            <span className="text-xs text-gray-500">{info.event_count ?? 0} events</span>
            <span className={`text-xs px-2 py-0.5 rounded font-medium ${info.running ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-600'}`}>
              {info.running ? 'Running' : 'Stopped'}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
