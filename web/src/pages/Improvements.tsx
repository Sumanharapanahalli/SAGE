import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchFeatureRequests,
  fetchProposal,
  approveProposalFull,
  generatePlanForRequest,
  updateFeatureRequest,
  submitFeatureRequest,
} from '../api/client'
import type { FeatureRequest, RequestStatus, Priority, RequestScope } from '../types/module'
import ModuleWrapper from '../components/shared/ModuleWrapper'
import { Loader2, Zap, CheckCircle, XCircle, Clock, GitBranch, ChevronDown, ChevronUp, Plus, X, Layers, Wrench, ExternalLink } from 'lucide-react'
import { getModuleAccess } from '../registry/modules'
import { useProjectConfig } from '../hooks/useProjectConfig'
import { Tooltip } from '../components/shared/Tooltip'
import OtherSelect from '../components/ui/OtherSelect'

// ---------------------------------------------------------------------------
// Status + Priority display helpers
// ---------------------------------------------------------------------------

const STATUS_STYLES: Record<RequestStatus, string> = {
  pending:     'bg-yellow-100 text-yellow-700 border-yellow-200',
  approved:    'bg-blue-100  text-blue-700   border-blue-200',
  in_planning: 'bg-purple-100 text-purple-700 border-purple-200',
  in_progress: 'bg-cyan-100  text-cyan-700   border-cyan-200',
  completed:   'bg-orange-100 text-orange-700  border-orange-200',
  rejected:    'bg-red-100   text-red-600    border-red-200',
  github_pr:   'bg-gray-100  text-gray-700   border-gray-300',
}

const STATUS_ICON: Record<RequestStatus, React.ReactNode> = {
  pending:     <Clock size={12} />,
  approved:    <CheckCircle size={12} />,
  in_planning: <GitBranch size={12} />,
  in_progress: <Zap size={12} />,
  completed:   <CheckCircle size={12} />,
  rejected:    <XCircle size={12} />,
  github_pr:   <ExternalLink size={12} />,
}

const STATUS_TOOLTIP: Record<RequestStatus, string> = {
  pending:     'Not yet reviewed. Click to expand and Approve or Generate AI Plan.',
  approved:    'Endorsed for implementation. Click Generate AI Plan to create implementation steps.',
  in_planning: 'AI plan generated and waiting for your approval. Expand to review and approve the plan.',
  in_progress: 'Plan approved — implementation tasks are queued and running.',
  completed:   'All implementation tasks have been completed.',
  rejected:    'This request was rejected. See reviewer note for details.',
  github_pr:   'Routed to GitHub — open the link to create an issue or pull request on the SAGE repo.',
}

const PRIORITY_DOT: Record<Priority, string> = {
  low:      'bg-gray-400',
  medium:   'bg-amber-400',
  high:     'bg-orange-500',
  critical: 'bg-red-600',
}

// ---------------------------------------------------------------------------
// StepCard — renders a single plan step
// ---------------------------------------------------------------------------

function StepCard({ step, index }: { step: { step?: number; task_type?: string; description?: string; payload?: Record<string, unknown> }, index: number }) {
  const [open, setOpen] = useState(false)
  const taskType = step.task_type ?? 'TASK'
  const TASK_COLORS: Record<string, string> = {
    ANALYZE:   'bg-blue-100 text-blue-700',
    DEVELOP:   'bg-orange-100 text-orange-700',
    REVIEW:    'bg-amber-100 text-amber-700',
    PLAN:      'bg-purple-100 text-purple-700',
    MONITOR:   'bg-cyan-100 text-cyan-700',
  }
  const colorClass = TASK_COLORS[taskType.toUpperCase()] ?? 'bg-gray-100 text-gray-600'

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      <div className="flex items-start gap-2 px-3 py-2">
        <span className="w-5 h-5 rounded-full bg-gray-100 text-gray-500 text-[10px] font-bold flex items-center justify-center shrink-0 mt-0.5">
          {index + 1}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${colorClass}`}>{taskType}</span>
            <span className="text-xs text-gray-700">{step.description}</span>
          </div>
        </div>
        {step.payload && Object.keys(step.payload).length > 0 && (
          <button onClick={() => setOpen(v => !v)} className="text-gray-400 hover:text-gray-600 shrink-0">
            {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>
        )}
      </div>
      {open && step.payload && (
        <pre className="bg-gray-50 border-t border-gray-100 px-3 py-2 text-[10px] font-mono overflow-auto max-h-32 whitespace-pre-wrap text-gray-600">
          {JSON.stringify(step.payload, null, 2)}
        </pre>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Request card — adapts based on scope
// ---------------------------------------------------------------------------

function RequestCard({ req }: { req: FeatureRequest }) {
  const [expanded, setExpanded] = useState(false)
  const [showPlan, setShowPlan] = useState(false)
  const [reviewNote, setNote]   = useState('')
  const [showNote, setShowNote] = useState(false)
  const [successMsg, setSuccessMsg] = useState('')
  const [errorMsg, setErrorMsg]     = useState('')
  const [approverIdentity, setApproverIdentity] = useState(() => localStorage.getItem('sage_approver_identity') || '')
  const access = getModuleAccess()
  const qc = useQueryClient()

  const { data: planData, isFetching: planLoading } = useQuery({
    queryKey: ['proposal', req.plan_trace_id],
    queryFn: () => fetchProposal(req.plan_trace_id!),
    enabled: showPlan && !!req.plan_trace_id,
    staleTime: 60_000,
  })

  const { mutate: plan, isPending: planning } = useMutation({
    mutationFn: () => generatePlanForRequest(req.id),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['feature-requests'] })
      // Sage-scope requests return a GitHub URL instead of a plan
      if (data && (data as { github_issue_url?: string }).github_issue_url) {
        const url = (data as { github_issue_url: string }).github_issue_url
        window.open(url, '_blank', 'noopener,noreferrer')
        setSuccessMsg('✓ GitHub issue opened — contribute this idea to the SAGE repo')
      } else {
        setSuccessMsg('✓ Plan generated — expand "View plan details" to review')
      }
      setTimeout(() => setSuccessMsg(''), 5000)
    },
    onError: (err: Error) => {
      setErrorMsg(`Failed: ${err.message}`)
      setSuccessMsg('')
    },
  })

  const { mutate: update, isPending: updating } = useMutation({
    mutationFn: (action: string) =>
      updateFeatureRequest(req.id, { action, reviewer_note: reviewNote }),
    onSuccess: (_data, action) => {
      qc.invalidateQueries({ queryKey: ['feature-requests'] })
      setShowNote(false)
      setNote('')
      const msgs: Record<string, string> = {
        approve: '✓ Approved — added to implementation backlog',
        reject:  '✓ Rejected and noted',
      }
      setSuccessMsg(msgs[action] ?? '✓ Updated')
      setErrorMsg('')
      setTimeout(() => setSuccessMsg(''), 3000)
    },
    onError: (err: Error) => {
      setErrorMsg(err.message ?? 'Update failed')
      setSuccessMsg('')
    },
  })

  const { mutate: approvePlan, isPending: approvingPlan } = useMutation({
    mutationFn: () => approveProposalFull(req.plan_trace_id!, approverIdentity || 'human'),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['feature-requests'] })
      qc.invalidateQueries({ queryKey: ['proposal', req.plan_trace_id] })
      setSuccessMsg('✓ Plan approved — tasks queued for implementation')
      setErrorMsg('')
      setTimeout(() => setSuccessMsg(''), 4000)
    },
    onError: (err: Error) => {
      setErrorMsg(err.message ?? 'Approval failed')
      setSuccessMsg('')
    },
  })

  const isSage = (req.scope ?? 'solution') === 'sage'
  const sStatus   = req.status as RequestStatus
  const sPriority = req.priority as Priority

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      <div className="flex items-start gap-3 px-4 py-3">
        <div className={`w-2.5 h-2.5 rounded-full mt-1.5 shrink-0 ${PRIORITY_DOT[sPriority]}`} />
        <div className="flex-1 min-w-0">
          <div className="font-medium text-gray-800 text-sm">{req.title}</div>
          <div className="flex items-center flex-wrap gap-2 mt-1">
            <span className="text-xs text-gray-400">{req.module_name}</span>
            <span className="text-xs text-gray-300">·</span>
            <span className="text-xs text-gray-400">{req.requested_by}</span>
            <span className="text-xs text-gray-300">·</span>
            <span className="text-xs text-gray-400">{new Date(req.created_at).toLocaleDateString()}</span>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {isSage && (
            <span className="text-[10px] font-semibold bg-blue-100 text-blue-600 px-1.5 py-0.5 rounded-full uppercase tracking-wide">
              SAGE
            </span>
          )}
          <Tooltip
            content={STATUS_TOOLTIP[sStatus] ?? 'Unknown status'}
            position="left"
          >
            <span className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border font-medium capitalize ${STATUS_STYLES[sStatus]}`}>
              {STATUS_ICON[sStatus]}
              {req.status.replace('_', ' ')}
            </span>
          </Tooltip>
          <button onClick={() => setExpanded((v) => !v)} className="text-gray-400 hover:text-gray-600">
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-gray-100">
          <p className="text-sm text-gray-700 pt-3 whitespace-pre-wrap">{req.description}</p>

          {req.reviewer_note && (
            <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-600">
              <span className="font-semibold">Reviewer note:</span> {req.reviewer_note}
            </div>
          )}

          {req.plan_trace_id && (
            <div className="space-y-2">
              <button
                onClick={() => setShowPlan((v) => !v)}
                className="flex items-center gap-1.5 text-xs text-purple-700 bg-purple-50 hover:bg-purple-100 border border-purple-200 rounded-lg px-3 py-1.5 transition-colors w-full"
              >
                {showPlan ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                {showPlan ? 'Hide plan details' : 'View plan details'}
                <Tooltip content="This is the AI-generated implementation plan. Review the steps, then approve to queue them for execution." position="top" icon />
                <span className="ml-auto font-mono text-purple-400">{req.plan_trace_id.slice(0, 12)}…</span>
              </button>

              {showPlan && (
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 space-y-3">
                  {planLoading && (
                    <div className="flex items-center gap-2 text-xs text-gray-400">
                      <Loader2 size={12} className="animate-spin" /> Loading plan…
                    </div>
                  )}

                  {!planLoading && !planData && (
                    <p className="text-xs text-gray-400">Plan not available. It may have expired or not yet been generated.</p>
                  )}

                  {!planLoading && planData && (() => {
                    const steps: Array<{step?: number; task_type?: string; description?: string; payload?: Record<string, unknown>}> = Array.isArray(planData.payload?.steps) ? planData.payload.steps as Array<{step?: number; task_type?: string; description?: string; payload?: Record<string, unknown>}> : []
                    return (
                      <div className="space-y-3">
                        {/* Plan header */}
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-semibold text-xs text-gray-800">{planData.description}</span>
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${planData.status === 'pending' ? 'bg-yellow-100 text-yellow-700' : planData.status === 'approved' ? 'bg-orange-100 text-orange-700' : 'bg-gray-200 text-gray-600'}`}>
                            {planData.status}
                          </span>
                          <Tooltip content={planData.status === 'pending' ? 'Waiting for your approval. Review the steps below, then click Approve Plan.' : planData.status === 'approved' ? 'This plan has been approved. Tasks are queued for execution.' : 'Plan status'} icon />
                        </div>

                        {/* Steps */}
                        {steps.length > 0 ? (
                          <div className="space-y-2">
                            {steps.map((step, i) => (
                              <StepCard key={i} step={step} index={i} />
                            ))}
                          </div>
                        ) : (
                          <pre className="bg-white border border-gray-200 rounded p-2 text-[11px] font-mono overflow-auto max-h-48 whitespace-pre-wrap">
                            {JSON.stringify(planData.payload, null, 2)}
                          </pre>
                        )}

                        {/* Approve plan section — only if plan is pending */}
                        {planData.status === 'pending' && (
                          <div className="border-t border-gray-200 pt-3 space-y-2">
                            <div className="flex items-center gap-1.5 text-xs text-gray-600">
                              <span className="font-semibold">Ready to approve?</span>
                              <Tooltip content="Approving queues these tasks for execution. Only admin can approve SAGE framework plans." icon />
                            </div>
                            {isSage && (
                              <div className="space-y-1">
                                <label className="text-[11px] text-gray-500 font-medium flex items-center gap-1">
                                  Approving as (admin required for SAGE plans)
                                  <Tooltip content="SAGE framework plans require admin approval. Enter your admin identity (e.g. 'admin' or 'suman') to proceed." icon />
                                </label>
                                <input
                                  value={approverIdentity}
                                  onChange={e => {
                                    setApproverIdentity(e.target.value)
                                    localStorage.setItem('sage_approver_identity', e.target.value)
                                  }}
                                  placeholder="Your admin identity…"
                                  className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-purple-400"
                                />
                              </div>
                            )}
                            <button
                              disabled={approvingPlan || (isSage && !approverIdentity.trim())}
                              onClick={() => approvePlan()}
                              className="flex items-center gap-1.5 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white text-xs font-medium px-4 py-1.5 rounded-lg transition-colors"
                            >
                              {approvingPlan ? <><Loader2 size={12} className="animate-spin" /> Approving…</> : <><CheckCircle size={12} /> Approve Plan & Queue Tasks</>}
                            </button>
                          </div>
                        )}

                        {planData.status === 'approved' && (
                          <div className="text-xs text-orange-700 bg-orange-50 border border-orange-200 rounded-lg px-3 py-2 flex items-center gap-1.5">
                            <CheckCircle size={12} /> Plan approved — implementation tasks are queued. Track progress in the Live Console.
                          </div>
                        )}
                      </div>
                    )
                  })()}
                </div>
              )}
            </div>
          )}

          {/* Success / error banners */}
          {successMsg && (
            <div className="text-xs text-orange-700 bg-orange-50 border border-orange-200 rounded-lg px-3 py-1.5">
              {successMsg}
            </div>
          )}
          {errorMsg && (
            <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-1.5">
              {errorMsg}
            </div>
          )}

          {/* Action buttons */}
          {access.canApprove && ['pending', 'approved'].includes(req.status) && (
            <div className="flex flex-wrap gap-2 pt-1">
              {access.canGeneratePlan && !['in_planning', 'github_pr'].includes(req.status) && (
                isSage ? (
                  <Tooltip content="SAGE framework improvements go through GitHub. This will open a pre-filled GitHub issue for the SAGE repo." position="top">
                    <button
                      disabled={planning}
                      onClick={() => plan()}
                      className="flex items-center gap-1.5 bg-gray-50 hover:bg-white disabled:opacity-50 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
                    >
                      <ExternalLink size={13} />
                      {planning ? 'Opening GitHub…' : 'Open GitHub Issue'}
                    </button>
                  </Tooltip>
                ) : (
                  <Tooltip content="Ask the AI to decompose this feature into concrete implementation steps. You will review and approve the plan before anything is built." position="top">
                    <button
                      disabled={planning}
                      onClick={() => plan()}
                      className="flex items-center gap-1.5 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
                    >
                      <Zap size={13} />
                      {planning ? 'Generating plan…' : 'Generate AI Plan'}
                    </button>
                  </Tooltip>
                )
              )}

              {req.status === 'pending' && (
                <Tooltip content="Mark this feature request as approved for planning. The next step is to Generate an AI Plan." position="top">
                  <button
                    disabled={updating}
                    onClick={() => update('approve')}
                    className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
                  >
                    <CheckCircle size={13} />
                    Approve
                  </button>
                </Tooltip>
              )}

              <Tooltip content="Reject this request. You can add a note explaining why." position="top">
                <button
                  onClick={() => setShowNote((v) => !v)}
                  className="flex items-center gap-1.5 bg-red-50 hover:bg-red-100 text-red-600 border border-red-200 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
                >
                  <XCircle size={13} />
                  Reject
                </button>
              </Tooltip>
            </div>
          )}

          {showNote && (
            <div className="space-y-2">
              <textarea
                value={reviewNote}
                onChange={(e) => setNote(e.target.value)}
                className="w-full h-16 border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-red-400"
                placeholder="Optional: explain why it's rejected..."
              />
              <button
                disabled={updating}
                onClick={() => update('reject')}
                className="bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white text-xs px-3 py-1.5 rounded-lg transition-colors"
              >
                {updating ? 'Rejecting…' : 'Confirm Reject'}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Submit form — scope selector baked in
// ---------------------------------------------------------------------------

function SubmitForm({ onClose, defaultScope }: { onClose: () => void; defaultScope?: RequestScope }) {
  const qc = useQueryClient()
  const { data: projectData } = useProjectConfig()

  const [scope, setScope]       = useState<RequestScope>(defaultScope ?? 'solution')
  const [title, setTitle]       = useState('')
  const [desc, setDesc]         = useState('')
  const [priority, setPriority] = useState<Priority>('medium')
  const [module, setModule]     = useState('general')
  const [by, setBy]             = useState('')
  const [done, setDone]         = useState(false)

  const { mutate, isPending, error } = useMutation({
    mutationFn: () => submitFeatureRequest({
      module_id:    module.toLowerCase().replace(/\s+/g, '-'),
      module_name:  module,
      title:        title.trim(),
      description:  desc.trim(),
      priority,
      requested_by: by.trim() || 'Web UI',
      scope,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['feature-requests'] })
      setDone(true)
      setTimeout(onClose, 1400)
    },
  })

  const projectName = projectData?.name ?? 'your solution'
  const isSage = scope === 'sage'

  if (done) return (
    <div className="flex items-center gap-2 py-4 px-5 text-orange-700 bg-orange-50 rounded-xl border border-orange-200">
      <CheckCircle size={18} />
      {isSage ? 'SAGE idea logged — thank you!' : 'Added to solution backlog!'}
    </div>
  )

  return (
    <div className={`bg-white rounded-xl border shadow-sm overflow-hidden ${isSage ? 'border-blue-200' : 'border-amber-200'}`}>
      {/* Header */}
      <div className={`flex items-center justify-between px-5 py-3 border-b ${isSage ? 'bg-blue-50 border-blue-200' : 'bg-amber-50 border-amber-200'}`}>
        <h3 className={`text-sm font-semibold ${isSage ? 'text-blue-800' : 'text-amber-800'}`}>
          New Improvement Request
        </h3>
        <button onClick={onClose} className={isSage ? 'text-blue-500 hover:text-blue-700' : 'text-amber-500 hover:text-amber-700'}>
          <X size={16} />
        </button>
      </div>

      <div className="p-5 space-y-4">
        {/* Scope selector */}
        <div>
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            What are you improving?
          </div>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => setScope('solution')}
              className={`flex items-center gap-2 p-3 rounded-lg border-2 transition-all text-left ${
                scope === 'solution' ? 'border-amber-400 bg-amber-50' : 'border-gray-200 hover:border-amber-300'
              }`}
            >
              <Layers size={16} className={scope === 'solution' ? 'text-amber-500' : 'text-gray-400'} />
              <div>
                <div className="text-xs font-bold text-gray-800">My Solution</div>
                <div className="text-[11px] text-gray-500">{projectName}</div>
              </div>
            </button>
            <button
              onClick={() => setScope('sage')}
              className={`flex items-center gap-2 p-3 rounded-lg border-2 transition-all text-left ${
                scope === 'sage' ? 'border-blue-400 bg-blue-50' : 'border-gray-200 hover:border-blue-300'
              }`}
            >
              <Wrench size={16} className={scope === 'sage' ? 'text-blue-500' : 'text-gray-400'} />
              <div>
                <div className="text-xs font-bold text-gray-800">SAGE Framework</div>
                <div className="text-[11px] text-gray-500">Platform improvement</div>
              </div>
            </button>
          </div>
          {isSage && (
            <p className="text-[11px] text-blue-600 mt-1.5">
              SAGE ideas are logged here. Also open a GitHub Issue on the SAGE repo so the community can track it.
            </p>
          )}
        </div>

        {/* Title */}
        <div>
          <label className="text-xs font-medium text-gray-600 block mb-1">Title <span className="text-red-500">*</span></label>
          <input
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder={isSage ? 'e.g. Add dark mode to SAGE UI' : 'e.g. Add voice feedback to coaching screen'}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"
          />
        </div>

        {/* Description */}
        <div>
          <label className="text-xs font-medium text-gray-600 block mb-1">Description <span className="text-red-500">*</span></label>
          <textarea
            value={desc}
            onChange={e => setDesc(e.target.value)}
            placeholder={isSage
              ? 'What should SAGE do differently? Which workflow does this improve?'
              : 'What should be built? Why does it matter to your users?'}
            rows={3}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-amber-400"
          />
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1">Module / Area</label>
            <input
              value={module}
              onChange={e => setModule(e.target.value)}
              placeholder="e.g. Analyst"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1">Priority</label>
            <OtherSelect
              value={priority}
              onChange={v => setPriority(v as Priority)}
              options={[
                { value: 'low',      label: 'Low' },
                { value: 'medium',   label: 'Medium' },
                { value: 'high',     label: 'High' },
                { value: 'critical', label: 'Critical' },
              ]}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-amber-400"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1">Your name</label>
            <input
              value={by}
              onChange={e => setBy(e.target.value)}
              placeholder="Optional"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"
            />
          </div>
        </div>

        {error && (
          <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{(error as Error).message}</p>
        )}

        <div className="flex gap-2 pt-1">
          <button
            onClick={() => mutate()}
            disabled={isPending || !title.trim() || !desc.trim()}
            className={`text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-40 ${
              isSage ? 'bg-blue-600 hover:bg-blue-700' : 'bg-amber-500 hover:bg-amber-600'
            }`}
          >
            {isPending ? <><Loader2 size={14} className="animate-spin" /> Submitting…</> : isSage ? 'Log SAGE Idea' : 'Add to Backlog'}
          </button>
          <button onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700 px-4 py-2 rounded-lg transition-colors">
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Improvements page — two clearly separated sections
// ---------------------------------------------------------------------------

const ALL_STATUSES: RequestStatus[] = [
  'pending', 'approved', 'in_planning', 'in_progress', 'completed', 'rejected', 'github_pr',
]

type TabId = 'solution' | 'sage'

export default function Improvements() {
  const [activeTab, setActiveTab]     = useState<TabId>('solution')
  const [filterStatus, setFilterStatus] = useState<RequestStatus | ''>('')
  const [showForm, setShowForm]       = useState(false)

  const { data: projectData } = useProjectConfig()
  const projectName = projectData?.name ?? 'your solution'

  const { data, isLoading } = useQuery({
    queryKey: ['feature-requests', activeTab, filterStatus],
    queryFn: () =>
      fetchFeatureRequests(undefined, filterStatus || undefined, activeTab),
    refetchInterval: 30_000,
  })

  const requests: FeatureRequest[] = data?.requests ?? []

  // Group by module for display
  const grouped = requests.reduce<Record<string, FeatureRequest[]>>((acc, r) => {
    const key = r.module_name
    ;(acc[key] = acc[key] ?? []).push(r)
    return acc
  }, {})

  const counts = {
    total:     requests.length,
    pending:   requests.filter((r) => r.status === 'pending').length,
    planning:  requests.filter((r) => r.status === 'in_planning').length,
    completed: requests.filter((r) => r.status === 'completed').length,
  }

  const isSageTab = activeTab === 'sage'

  return (
    <ModuleWrapper moduleId="improvements">
      <div className="space-y-6">

        {/* ── Page header ── */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-800">Improvements</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Solution backlog and SAGE framework ideas — kept separate so the right team owns each.
            </p>
          </div>
          <button
            onClick={() => setShowForm(v => !v)}
            className="flex items-center gap-1.5 bg-amber-500 hover:bg-amber-600 text-white text-sm font-medium px-3 py-2 rounded-lg transition-colors"
          >
            <Plus size={15} />
            New Request
          </button>
        </div>

        {/* Workflow guide */}
        <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 text-xs text-blue-700">
          <div className="font-semibold text-blue-800 mb-1 flex items-center gap-1.5">
            <Zap size={13} /> How it works
          </div>
          <div className="flex items-center gap-1.5 flex-wrap">
            {['1. Submit idea', '→', '2. Approve it', '→', '3. Generate AI Plan', '→', '4. Review & approve plan', '→', '5. Tasks execute automatically'].map((s, i) => (
              <span key={i} className={s === '→' ? 'text-blue-400' : 'bg-white border border-blue-200 rounded px-1.5 py-0.5 font-medium'}>
                {s}
              </span>
            ))}
          </div>
          <p className="mt-1.5 text-blue-600">SAGE framework items (blue SAGE badge) require admin approval for plan generation and approval.</p>
        </div>

        {/* Submit form */}
        {showForm && <SubmitForm onClose={() => setShowForm(false)} defaultScope={activeTab} />}

        {/* ── Tab switcher — the core distinction ── */}
        <div className="flex border border-gray-200 rounded-xl overflow-hidden bg-gray-50 p-1 gap-1">
          <button
            onClick={() => { setActiveTab('solution'); setShowForm(false) }}
            className={`flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'solution'
                ? 'bg-white text-amber-700 shadow-sm border border-amber-200'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <Layers size={15} />
            <span>Solution Backlog</span>
            <span className="text-xs text-gray-400">— features for {projectName}</span>
          </button>
          <button
            onClick={() => { setActiveTab('sage'); setShowForm(false) }}
            className={`flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'sage'
                ? 'bg-white text-blue-700 shadow-sm border border-blue-200'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <Wrench size={15} />
            <span>SAGE Framework Ideas</span>
            <span className="text-xs text-gray-400">— improve the platform</span>
          </button>
        </div>

        {/* SAGE-tab explainer banner */}
        {isSageTab && (
          <div className="flex items-start gap-3 bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm">
            <Wrench size={18} className="text-blue-500 shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="font-semibold text-blue-800 mb-1">SAGE Framework Ideas</div>
              <p className="text-blue-700 text-xs leading-relaxed">
                These are improvement ideas for the SAGE platform itself — new agent capabilities,
                UI improvements, integration ideas. They are logged here for visibility, but the
                canonical home for community tracking is <strong>GitHub Issues</strong> on the SAGE repo.
              </p>
            </div>
            <a
              href="https://github.com/Sumanharapanahalli/SAGE/issues"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 font-medium border border-blue-300 rounded-lg px-2.5 py-1.5 shrink-0 hover:bg-blue-100 transition-colors"
            >
              <ExternalLink size={12} />
              GitHub Issues
            </a>
          </div>
        )}

        {/* Stats bar */}
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: 'Total',        value: counts.total,     color: 'text-gray-800' },
            { label: 'Pending',      value: counts.pending,   color: 'text-amber-600' },
            { label: 'In Planning',  value: counts.planning,  color: 'text-purple-600' },
            { label: 'Completed',    value: counts.completed, color: 'text-orange-600' },
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm text-center">
              <div className={`text-2xl font-bold ${color}`}>{value}</div>
              <div className="text-xs text-gray-500 mt-0.5">{label}</div>
            </div>
          ))}
        </div>

        {/* Status filter */}
        <div>
          <OtherSelect
            value={filterStatus}
            onChange={v => setFilterStatus(v as RequestStatus | '')}
            options={ALL_STATUSES.map(s => ({ value: s, label: s.replace('_', ' ') }))}
            placeholder="All statuses"
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400 bg-white"
          />
        </div>

        {/* Request list */}
        {isLoading ? (
          <div className="flex items-center justify-center h-48 text-gray-400 gap-2">
            <Loader2 className="animate-spin" size={18} /> Loading…
          </div>
        ) : requests.length === 0 ? (
          <div className="bg-white rounded-xl border border-dashed border-gray-300 p-12 text-center">
            <div className={`mx-auto mb-3 w-10 h-10 rounded-full flex items-center justify-center ${isSageTab ? 'bg-blue-100' : 'bg-amber-100'}`}>
              {isSageTab ? <Wrench size={20} className="text-blue-500" /> : <Layers size={20} className="text-amber-500" />}
            </div>
            <div className="font-medium text-gray-700 mb-1">
              {isSageTab ? 'No SAGE framework ideas yet' : 'Solution backlog is empty'}
            </div>
            <p className="text-sm text-gray-400">
              {isSageTab
                ? 'Have an idea to improve SAGE itself? Click New Request and choose "SAGE Framework".'
                : `Use the 💡 button on any page, or click New Request to add the first item to ${projectName}'s backlog.`}
            </p>
          </div>
        ) : (
          Object.entries(grouped).map(([moduleName, reqs]) => (
            <div key={moduleName}>
              <div className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-2">
                {moduleName} <span className="font-normal text-gray-400">({reqs.length})</span>
              </div>
              <div className="space-y-2">
                {reqs.map((req) => (
                  <RequestCard key={req.id} req={req} />
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </ModuleWrapper>
  )
}
