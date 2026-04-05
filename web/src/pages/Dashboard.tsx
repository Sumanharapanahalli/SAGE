import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchHealth, fetchAudit, fetchPendingProposals, approveProposalFull, rejectProposal, approveBatchProposals, fetchProjects, type Proposal } from '../api/client'
import { ActiveAgentsPanel } from '../components/ActiveAgentsPanel'
import { useProjectConfig } from '../hooks/useProjectConfig'
import SystemHealthCard from '../components/dashboard/SystemHealthCard'
import ActiveAlertsPanel from '../components/dashboard/ActiveAlertsPanel'
import ErrorTrendChart from '../components/dashboard/ErrorTrendChart'
import EmptyState from '../components/dashboard/EmptyState'
import ModuleWrapper from '../components/shared/ModuleWrapper'
import { Loader2, CheckCircle2, XCircle, Clock, AlertTriangle, Trash2, ChevronDown, ChevronUp } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'

// Dashboard content is fully driven by the solution's project.yaml `dashboard:` section.
// No solution-specific logic lives in this file — add dashboard config to your project.yaml.

const RISK_COLOURS: Record<string, string> = {
  INFORMATIONAL: 'bg-gray-700 text-gray-300',
  EPHEMERAL:     'bg-blue-900/60 text-blue-300',
  STATEFUL:      'bg-yellow-900/60 text-yellow-300',
  EXTERNAL:      'bg-orange-900/60 text-orange-300',
  DESTRUCTIVE:   'bg-red-900/70 text-red-300',
}

const ACTION_TYPE_LABELS: Record<string, string> = {
  yaml_edit:           'YAML Edit',
  llm_switch:          'LLM Switch',
  agent_hire:          'Hire Agent',
  onboarding_generate: 'New Solution',
  composio_connect:    'Composio Connect',
  knowledge_add:       'Knowledge Add',
  knowledge_delete:    'Knowledge Delete',
  knowledge_import:    'Knowledge Import',
  config_modules:      'Module Config',
  config_switch:       'Solution Switch',
  analysis:            'Analysis',
  code_diff:           'Code Review',
}

const BATCH_ELIGIBLE_RISK = new Set<string>(['INFORMATIONAL', 'EPHEMERAL'])

function ProposalCard({ p, approverIdentity }: { p: Proposal; approverIdentity: string }) {
  const qc = useQueryClient()
  const [rejectNote, setRejectNote] = useState('')
  const [rejecting, setRejecting] = useState(false)
  const [expanded, setExpanded] = useState(false)

  const approveMut = useMutation({
    mutationFn: () => approveProposalFull(p.trace_id, approverIdentity || 'human'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['proposals-pending'] }),
  })
  const rejectMut = useMutation({
    mutationFn: () => rejectProposal(p.trace_id, rejectNote),
    onSuccess: () => {
      setRejecting(false)
      qc.invalidateQueries({ queryKey: ['proposals-pending'] })
    },
  })

  const ageSeconds = Math.floor((Date.now() - new Date(p.created_at).getTime()) / 1000)
  const ageLabel = ageSeconds < 60 ? `${ageSeconds}s ago`
    : ageSeconds < 3600 ? `${Math.floor(ageSeconds / 60)}m ago`
    : `${Math.floor(ageSeconds / 3600)}h ago`

  const actionLabel = ACTION_TYPE_LABELS[p.action_type] ?? p.action_type
  const hasPayload = p.payload && Object.keys(p.payload).length > 0

  return (
    <div className="bg-white border border-gray-700 rounded-lg overflow-hidden">
      {/* Main row */}
      <div className="p-3">
        <div className="flex items-start gap-2 flex-wrap">
          <span className={`text-[10px] font-mono px-2 py-0.5 rounded shrink-0 ${RISK_COLOURS[p.risk_class] ?? 'bg-gray-700 text-gray-300'}`}>
            {p.risk_class}
          </span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-gray-700 text-gray-400 shrink-0">
            {actionLabel}
          </span>
          {!p.reversible && (
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-red-900/60 text-red-300 flex items-center gap-1 shrink-0">
              <Trash2 size={10} /> IRREVERSIBLE
            </span>
          )}
          {p.required_role && (
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-gray-700 text-gray-400 shrink-0">
              requires: {p.required_role}
            </span>
          )}
        </div>

        <p className="text-xs text-gray-200 mt-2 leading-relaxed">{p.description}</p>

        <div className="flex items-center gap-3 mt-1.5">
          <span className="text-[10px] text-gray-500">by {p.proposed_by} · {ageLabel}</span>
          {p.expires_at && (
            <span className="text-[10px] text-amber-500 flex items-center gap-0.5">
              <AlertTriangle size={9} /> expires {new Date(p.expires_at).toLocaleTimeString()}
            </span>
          )}
          {hasPayload && (
            <button
              onClick={() => setExpanded(v => !v)}
              className="text-[10px] text-blue-400 hover:text-blue-300 flex items-center gap-0.5 ml-auto"
            >
              Details {expanded ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
            </button>
          )}
        </div>

        {/* Expandable payload */}
        {expanded && hasPayload && (
          p.action_type === 'code_diff' ? (() => {
            const cd = p.payload as { summary?: string; tests_passed?: boolean; written_files?: string[]; diff?: string }
            return (
            <div className="mt-2 space-y-2">
              {cd.summary && (
                <p className="text-xs text-gray-300 leading-relaxed">{cd.summary}</p>
              )}
              <div className="flex items-center gap-2">
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${cd.tests_passed ? 'bg-orange-900/60 text-green-300' : 'bg-red-900/60 text-red-300'}`}>
                  Tests: {cd.tests_passed ? 'PASS' : 'FAIL'}
                </span>
                {cd.written_files && cd.written_files.length > 0 && (
                  <span className="text-[10px] text-gray-500">
                    {cd.written_files.length} file{cd.written_files.length !== 1 ? 's' : ''} changed
                  </span>
                )}
              </div>
              {cd.written_files && cd.written_files.length > 0 && (
                <ul className="text-[10px] text-gray-400 font-mono space-y-0.5">
                  {cd.written_files.map((f) => (
                    <li key={f} className="truncate">+ {f}</li>
                  ))}
                </ul>
              )}
              {cd.diff && (
                <pre className="bg-gray-950 rounded p-2 text-[10px] font-mono text-gray-300 overflow-x-auto max-h-64 whitespace-pre">
                  {cd.diff}
                </pre>
              )}
            </div>
            )
          })() : (
            <pre className="mt-2 bg-gray-50 rounded p-2 text-[10px] text-gray-400 overflow-x-auto max-h-40">
              {JSON.stringify(p.payload, null, 2)}
            </pre>
          )
        )}

        {/* Error feedback */}
        {(approveMut.isError || rejectMut.isError) && (
          <p className="text-[10px] text-red-400 mt-1.5">
            {((approveMut.error || rejectMut.error) as Error)?.message ?? 'Action failed'}
          </p>
        )}

        {/* Actions */}
        {rejecting ? (
          <div className="mt-2 flex gap-2">
            <input
              className="flex-1 bg-gray-50 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 placeholder-gray-500"
              placeholder="Reason for rejection (optional)…"
              value={rejectNote}
              onChange={e => setRejectNote(e.target.value)}
              autoFocus
            />
            <button
              onClick={() => rejectMut.mutate()}
              disabled={rejectMut.isPending}
              className="text-xs px-3 py-1 rounded bg-red-700 hover:bg-red-600 text-white shrink-0"
            >
              {rejectMut.isPending ? 'Rejecting…' : 'Confirm'}
            </button>
            <button onClick={() => setRejecting(false)} className="text-xs text-gray-400 hover:text-gray-200 shrink-0">
              Cancel
            </button>
          </div>
        ) : (
          <div className="mt-2 flex gap-2">
            <button
              onClick={() => approveMut.mutate()}
              disabled={approveMut.isPending}
              className="text-xs px-3 py-1.5 rounded bg-orange-700 hover:bg-orange-600 disabled:opacity-50 text-white flex items-center gap-1"
            >
              {approveMut.isPending
                ? <><Loader2 size={11} className="animate-spin" /> Approving…</>
                : <><CheckCircle2 size={12} /> Approve</>
              }
            </button>
            <button
              onClick={() => setRejecting(true)}
              className="text-xs px-3 py-1.5 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 flex items-center gap-1"
            >
              <XCircle size={12} /> Reject
            </button>
            <span className="text-[10px] text-gray-600 self-center ml-1 font-mono">
              {p.trace_id.slice(0, 8)}…
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

const IDENTITY_KEY = 'sage_approver_identity'

function PendingApprovalsPanel() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['proposals-pending'],
    queryFn: fetchPendingProposals,
    refetchInterval: 10_000,
  })

  const [approverIdentity, setApproverIdentity] = useState<string>(() =>
    localStorage.getItem(IDENTITY_KEY) ?? ''
  )

  useEffect(() => {
    localStorage.setItem(IDENTITY_KEY, approverIdentity)
  }, [approverIdentity])

  const proposals: Proposal[] = data?.proposals ?? []

  // Group by action_type
  const grouped = proposals.reduce<Record<string, Proposal[]>>((acc, p) => {
    const key = p.action_type
    ;(acc[key] = acc[key] ?? []).push(p)
    return acc
  }, {})

  const batchMut = useMutation({
    mutationFn: (ids: string[]) =>
      approveBatchProposals(ids, approverIdentity || 'human'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['proposals-pending'] }),
  })

  return (
    <div className="bg-gray-50 border border-gray-700 rounded-xl p-4 lg:col-span-3">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-200 flex items-center gap-2">
          <Clock size={14} className="text-yellow-400" />
          Pending Approvals
          {proposals.length > 0 && (
            <span className="ml-1 bg-yellow-500 text-zinc-900 text-xs font-bold px-1.5 py-0.5 rounded-full">
              {proposals.length}
            </span>
          )}
        </h3>
        <Link to="/live-console" className="text-xs text-blue-400 hover:underline">
          Live Console →
        </Link>
      </div>

      {/* Approving-as identity input */}
      <div className="mb-3">
        <input
          className="w-full bg-white border border-gray-600 rounded px-2 py-1.5 text-xs text-gray-200 placeholder-gray-500"
          placeholder="Approving as… (e.g. suman, admin)"
          value={approverIdentity}
          onChange={e => setApproverIdentity(e.target.value)}
        />
      </div>

      {isLoading && (
        <div className="text-xs text-gray-500 flex items-center gap-1.5">
          <Loader2 size={12} className="animate-spin" /> Loading…
        </div>
      )}

      {!isLoading && proposals.length === 0 && (
        <div className="text-xs text-gray-500 py-3 flex items-center gap-2">
          <CheckCircle2 size={14} className="text-orange-500" />
          All clear — no proposals awaiting review.
        </div>
      )}

      <div className="space-y-4">
        {Object.entries(grouped).map(([actionType, groupProposals]) => {
          const label = ACTION_TYPE_LABELS[actionType] ?? actionType
          const allBatchEligible = groupProposals.every(p => BATCH_ELIGIBLE_RISK.has(p.risk_class))
          const groupIds = groupProposals.map(p => p.trace_id)
          return (
            <div key={actionType}>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide">
                  {label}
                  <span className="ml-1.5 text-gray-600 font-normal normal-case tracking-normal">
                    ({groupProposals.length})
                  </span>
                </span>
                {allBatchEligible && groupProposals.length > 1 && (
                  <button
                    onClick={() => batchMut.mutate(groupIds)}
                    disabled={batchMut.isPending}
                    className="text-[10px] px-2 py-1 rounded bg-orange-800 hover:bg-orange-700 disabled:opacity-50 text-orange-200 flex items-center gap-1"
                  >
                    {batchMut.isPending
                      ? <><Loader2 size={9} className="animate-spin" /> Approving…</>
                      : <><CheckCircle2 size={10} /> Approve all in group</>
                    }
                  </button>
                )}
              </div>
              <div className="space-y-2">
                {groupProposals.map(p => (
                  <ProposalCard key={p.trace_id} p={p} approverIdentity={approverIdentity} />
                ))}
              </div>
            </div>
          )
        })}
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
  const { data: projectsData } = useQuery({
    queryKey: ['projects'],
    queryFn: fetchProjects,
  })
  const navigate = useNavigate()

  const hasProjects = (projectsData?.projects?.length ?? 0) > 0

  useEffect(() => {
    if (hasProjects) {
      localStorage.removeItem('sage_skip_empty_state')
    }
  }, [hasProjects])

  if (healthLoading) return (
    <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {[1,2,3].map(i => (
        <div key={i} style={{
          height: '5rem', borderRadius: '0.75rem', border: '1px solid #e5e7eb',
          background: 'linear-gradient(90deg, #f3f4f6 25%, #e5e7eb 50%, #f3f4f6 75%)',
          backgroundSize: '200% 100%', animation: 'skeleton-shimmer 1.5s ease-in-out infinite',
        }} />
      ))}
      <style>{`@keyframes skeleton-shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }`}</style>
    </div>
  )

  const skipped = localStorage.getItem('sage_skip_empty_state') === '1'
  if (!hasProjects && !skipped) return <EmptyState />

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
                  {(projectData as any)?.ui_labels?.dashboard_subtitle
                    ?? (projectData?.description
                        ? String(projectData.description).slice(0, 80)
                        : projectData?.domain ?? 'General purpose AI agent framework')}
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

        {/* Live active agents panel — polls GET /agents/active every 3s */}
        <ActiveAgentsPanel />
      </div>
    </ModuleWrapper>
  )
}
