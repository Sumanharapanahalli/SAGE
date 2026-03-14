import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchHealth, fetchAudit, fetchPendingProposals, approveProposal, rejectProposal, type Proposal } from '../api/client'
import { useProjectConfig } from '../hooks/useProjectConfig'
import SystemHealthCard from '../components/dashboard/SystemHealthCard'
import ActiveAlertsPanel from '../components/dashboard/ActiveAlertsPanel'
import ErrorTrendChart from '../components/dashboard/ErrorTrendChart'
import ModuleWrapper from '../components/shared/ModuleWrapper'
import { Loader2, CheckCircle2, XCircle, Clock, AlertTriangle, Trash2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useState } from 'react'

// Dashboard content is fully driven by the solution's project.yaml `dashboard:` section.
// No solution-specific logic lives in this file — add dashboard config to your project.yaml.

const RISK_COLOURS: Record<string, string> = {
  INFORMATIONAL: 'bg-gray-700 text-gray-300',
  EPHEMERAL:     'bg-blue-900/60 text-blue-300',
  STATEFUL:      'bg-yellow-900/60 text-yellow-300',
  EXTERNAL:      'bg-orange-900/60 text-orange-300',
  DESTRUCTIVE:   'bg-red-900/70 text-red-300',
}

function PendingApprovalsPanel() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['proposals-pending'],
    queryFn: fetchPendingProposals,
    refetchInterval: 10_000,
  })
  const [rejectNote, setRejectNote] = useState<Record<string, string>>({})
  const [rejectingId, setRejectingId] = useState<string | null>(null)

  const approveMut = useMutation({
    mutationFn: (trace_id: string) => approveProposal(trace_id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['proposals-pending'] }),
  })
  const rejectMut = useMutation({
    mutationFn: ({ trace_id, feedback }: { trace_id: string; feedback: string }) =>
      rejectProposal(trace_id, feedback),
    onSuccess: () => {
      setRejectingId(null)
      qc.invalidateQueries({ queryKey: ['proposals-pending'] })
    },
  })

  const proposals: Proposal[] = data?.proposals ?? []

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-xl p-4 lg:col-span-3">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-200 flex items-center gap-2">
          <Clock size={14} className="text-yellow-400" />
          Pending Approvals
          {proposals.length > 0 && (
            <span className="ml-1 bg-yellow-500 text-black text-xs font-bold px-1.5 py-0.5 rounded-full">
              {proposals.length}
            </span>
          )}
        </h3>
        <a href="/live-console" className="text-xs text-blue-400 hover:underline">
          Live Console
        </a>
      </div>

      {isLoading && (
        <div className="text-xs text-gray-500 flex items-center gap-1">
          <Loader2 size={12} className="animate-spin" /> Loading…
        </div>
      )}

      {!isLoading && proposals.length === 0 && (
        <div className="text-xs text-gray-500 py-2">No pending approvals.</div>
      )}

      <div className="space-y-2">
        {proposals.map(p => (
          <div key={p.trace_id} className="bg-gray-900 border border-gray-700 rounded-lg p-3">
            <div className="flex items-start gap-2 flex-wrap">
              <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${RISK_COLOURS[p.risk_class] ?? 'bg-gray-700 text-gray-300'}`}>
                {p.risk_class}
              </span>
              {!p.reversible && (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-red-900/60 text-red-300 flex items-center gap-1">
                  <Trash2 size={10} /> IRREVERSIBLE
                </span>
              )}
              <span className="text-xs text-gray-300 flex-1">{p.description}</span>
              <span className="text-[10px] text-gray-500 ml-auto">
                by {p.proposed_by} · {new Date(p.created_at).toLocaleTimeString()}
              </span>
            </div>

            {p.expires_at && (
              <div className="text-[10px] text-gray-500 mt-1 flex items-center gap-1">
                <AlertTriangle size={10} />
                Expires {new Date(p.expires_at).toLocaleString()}
              </div>
            )}

            {rejectingId === p.trace_id ? (
              <div className="mt-2 flex gap-2">
                <input
                  className="flex-1 bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 placeholder-gray-500"
                  placeholder="Reason for rejection…"
                  value={rejectNote[p.trace_id] ?? ''}
                  onChange={e => setRejectNote(n => ({ ...n, [p.trace_id]: e.target.value }))}
                />
                <button
                  onClick={() => rejectMut.mutate({ trace_id: p.trace_id, feedback: rejectNote[p.trace_id] ?? '' })}
                  disabled={rejectMut.isPending}
                  className="text-xs px-3 py-1 rounded bg-red-700 hover:bg-red-600 text-white"
                >
                  Confirm Reject
                </button>
                <button onClick={() => setRejectingId(null)} className="text-xs text-gray-400 hover:text-gray-200">
                  Cancel
                </button>
              </div>
            ) : (
              <div className="mt-2 flex gap-2">
                <button
                  onClick={() => approveMut.mutate(p.trace_id)}
                  disabled={approveMut.isPending}
                  className="text-xs px-3 py-1 rounded bg-green-700 hover:bg-green-600 text-white flex items-center gap-1"
                >
                  <CheckCircle2 size={12} /> Approve
                </button>
                <button
                  onClick={() => setRejectingId(p.trace_id)}
                  className="text-xs px-3 py-1 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 flex items-center gap-1"
                >
                  <XCircle size={12} /> Reject
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  })
  const { data: audit } = useQuery({
    queryKey: ['audit', 0],
    queryFn: () => fetchAudit(100, 0),
    refetchInterval: 30_000,
  })
  const { data: projectData } = useProjectConfig()
  const navigate = useNavigate()

  if (healthLoading) return (
    <div className="flex items-center justify-center h-64 text-gray-400 gap-2">
      <Loader2 className="animate-spin" size={20} /> Loading…
    </div>
  )

  // All dashboard content comes from project.yaml's `dashboard:` section
  const dashboardConfig = (projectData as any)?.dashboard ?? {}
  const contextItems: { label: string; description: string }[] = dashboardConfig.context_items ?? []
  const quickActions: { label: string; route: string; description: string }[] = dashboardConfig.quick_actions ?? []
  const contextColor: string = dashboardConfig.context_color ?? 'border-gray-200 bg-gray-50'

  return (
    <ModuleWrapper moduleId="dashboard">
      <div className="space-y-6">
        {/* Domain context card — content from project.yaml dashboard.context_items */}
        {(projectData?.name || contextItems.length > 0) && (
          <div className={`rounded-xl border p-5 ${contextColor}`}>
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-base font-semibold text-gray-800">
                  {projectData?.name ?? 'SAGE Framework'}
                </h3>
                <span className="text-xs text-gray-500">
                  {projectData?.description
                    ? String(projectData.description).slice(0, 80)
                    : projectData?.domain ?? 'General purpose AI agent framework'}
                </span>
              </div>
              {projectData?.version && (
                <span className="text-xs font-medium bg-white/70 px-2.5 py-1 rounded-full text-gray-600">
                  v{projectData.version}
                </span>
              )}
            </div>
            {contextItems.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {contextItems.map((item) => (
                  <div key={item.label} className="bg-white/60 rounded-lg px-3 py-2">
                    <div className="text-xs font-semibold text-gray-600 mb-0.5">{item.label}</div>
                    <div className="text-xs text-gray-500">{item.description}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Quick actions — content from project.yaml dashboard.quick_actions */}
        {quickActions.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-gray-600 mb-2">Quick Actions</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {quickActions.map((action) => (
                <button
                  key={action.label}
                  onClick={() => navigate(action.route)}
                  className="bg-white rounded-lg border border-gray-200 px-4 py-3 hover:bg-gray-50
                             hover:border-gray-300 transition-colors group text-left"
                >
                  <div className="text-sm font-medium text-gray-800 group-hover:text-blue-600">
                    {action.label}
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5">{action.description}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Pending Approvals — always visible, auto-refreshes */}
        <div className="grid grid-cols-1 gap-6">
          <PendingApprovalsPanel />
        </div>

        {/* Standard dashboard cards — always rendered, solution-agnostic */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {health && <SystemHealthCard data={health} />}
          <ActiveAlertsPanel entries={audit?.entries ?? []} />
          <ErrorTrendChart entries={audit?.entries ?? []} />
        </div>
      </div>
    </ModuleWrapper>
  )
}
