import type { AuditEntry } from '../../api/client'

interface Props { entries: AuditEntry[] }

const SEVERITY_STYLES: Record<string, string> = {
  RED: 'bg-red-100 text-red-700 border-red-200',
  AMBER: 'bg-amber-100 text-amber-700 border-amber-200',
  GREEN: 'bg-green-100 text-green-700 border-green-200',
}

function getSeverity(entry: AuditEntry): string {
  try {
    const meta = JSON.parse(entry.metadata || '{}')
    return (meta.severity || 'GREEN').toUpperCase()
  } catch {
    return 'GREEN'
  }
}

export default function ActiveAlertsPanel({ entries }: Props) {
  const proposals = entries.filter((e) => e.action_type === 'ANALYSIS_PROPOSAL').slice(0, 5)

  if (!proposals.length) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Active Proposals</h2>
        <p className="text-sm text-gray-400">No pending proposals.</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Active Proposals</h2>
      <div className="space-y-2">
        {proposals.map((entry) => {
          const sev = getSeverity(entry)
          return (
            <div key={entry.id} className={`rounded-lg border px-3 py-2 text-sm ${SEVERITY_STYLES[sev] ?? SEVERITY_STYLES.GREEN}`}>
              <div className="font-medium">{sev}</div>
              <div className="text-xs opacity-80 truncate">{entry.input_context?.slice(0, 80)}</div>
              <div className="text-xs opacity-60">{new Date(entry.timestamp).toLocaleString()}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
