import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchAgentRoles, runAgent, hireAgent, analyzeJd } from '../api/client'
import { useProjectConfig } from '../hooks/useProjectConfig'
import { Loader2, ChevronDown, ChevronUp, CheckCircle, Sparkles, UserPlus, X, Bot } from 'lucide-react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface AgentRole {
  id: string
  name: string
  description: string
  icon: string
}

interface AgentResult {
  trace_id: string
  role_id: string
  role_name: string
  icon: string
  task: string
  summary: string
  analysis: string
  recommendations: string[]
  next_steps: string[]
  severity: string
  confidence: string
  status: string
}

// ---------------------------------------------------------------------------
// Severity styling
// ---------------------------------------------------------------------------
const SEV_STYLES: Record<string, string> = {
  RED:   'bg-red-50 border-red-300 text-red-700',
  AMBER: 'bg-amber-50 border-amber-300 text-amber-700',
  GREEN: 'bg-green-50 border-green-300 text-green-700',
}

const CONF_COLOR: Record<string, string> = {
  HIGH:   'text-green-600',
  MEDIUM: 'text-amber-600',
  LOW:    'text-red-600',
}

// ---------------------------------------------------------------------------
// Result card
// ---------------------------------------------------------------------------
function ResultCard({ result }: { result: AgentResult }) {
  const [expanded, setExpanded] = useState(true)
  const sevStyle = SEV_STYLES[result.severity] ?? SEV_STYLES.GREEN

  return (
    <div
      className="overflow-hidden"
      style={{ border: '1px solid #3f3f46', backgroundColor: '#18181b' }}
    >
      {/* Header */}
      <div className="flex items-start gap-3 px-4 py-3">
        <span className="text-xl shrink-0">{result.icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-sm" style={{ color: '#f4f4f5' }}>{result.role_name}</span>
            <span
              className="text-xs px-1.5 py-0.5 font-medium"
              style={{ border: '1px solid #3f3f46', color: '#a1a1aa' }}
            >
              {result.severity}
            </span>
            <span className={`text-xs font-medium ${CONF_COLOR[result.confidence] ?? 'text-gray-500'}`}>
              {result.confidence} conf
            </span>
          </div>
          <p className="text-sm font-medium mt-1" style={{ color: '#d4d4d8' }}>{result.summary}</p>
          <p className="text-xs mt-0.5 font-mono truncate" style={{ color: '#52525b' }}>
            trace: {result.trace_id.slice(0, 16)}…
          </p>
        </div>
        <button
          onClick={() => setExpanded(v => !v)}
          className="shrink-0"
          style={{ color: '#52525b' }}
        >
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="px-4 pb-4 pt-3 space-y-3" style={{ borderTop: '1px solid #27272a' }}>
          {/* Analysis */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-widest mb-1.5" style={{ color: '#52525b' }}>Analysis</h4>
            <p className="text-xs whitespace-pre-wrap leading-relaxed" style={{ color: '#a1a1aa' }}>{result.analysis}</p>
          </div>

          {/* Recommendations */}
          {result.recommendations.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-widest mb-2" style={{ color: '#52525b' }}>Recommendations</h4>
              <ul className="space-y-1.5">
                {result.recommendations.map((r, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs" style={{ color: '#a1a1aa' }}>
                    <CheckCircle size={12} className="mt-0.5 shrink-0" style={{ color: '#22c55e' }} />
                    {r}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Next steps */}
          {result.next_steps.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-widest mb-2" style={{ color: '#52525b' }}>Next Steps</h4>
              <ol className="space-y-1.5 list-none">
                {result.next_steps.map((s, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs" style={{ color: '#a1a1aa' }}>
                    <span
                      className="text-xs font-bold w-4 h-4 flex items-center justify-center shrink-0 mt-0.5"
                      style={{ backgroundColor: '#27272a', color: '#71717a' }}
                    >
                      {i + 1}
                    </span>
                    {s}
                  </li>
                ))}
              </ol>
            </div>
          )}

          <p
            className="text-xs px-3 py-2"
            style={{ backgroundColor: '#1a1500', border: '1px solid #52400a', color: '#a16207' }}
          >
            Pending human review — approve or reject this recommendation before acting on it.
          </p>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Role selector card — Paperclip-style sharp card grid
// ---------------------------------------------------------------------------
function RoleCard({
  role,
  selected,
  onClick,
}: {
  role: AgentRole
  selected: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className="text-left p-4 transition-all w-full"
      style={{
        border: selected ? '1px solid #f4f4f5' : '1px solid #3f3f46',
        backgroundColor: selected ? '#27272a' : '#18181b',
        color: selected ? '#f4f4f5' : '#a1a1aa',
      }}
    >
      {/* Status indicator + icon row */}
      <div className="flex items-start justify-between mb-3">
        <span className="text-xl">{role.icon}</span>
        {/* Status dot: always "idle" in this view — active when selected */}
        <span
          className="w-1.5 h-1.5 mt-1"
          style={{
            display: 'inline-block',
            backgroundColor: selected ? '#22c55e' : '#52525b',
            flexShrink: 0,
          }}
          title={selected ? 'Active' : 'Idle'}
        />
      </div>
      <div className="text-xs font-semibold mb-0.5" style={{ color: selected ? '#f4f4f5' : '#a1a1aa' }}>
        {role.name}
      </div>
      <div className="text-xs leading-snug" style={{ color: '#52525b' }}>
        {role.description}
      </div>
      {/* Status label */}
      <div
        className="mt-2 text-xs font-medium"
        style={{ color: selected ? '#22c55e' : '#3f3f46' }}
      >
        {selected ? 'active' : 'idle'}
      </div>
    </button>
  )
}

// Task templates are loaded from project.yaml ui_labels.agent_quick_templates
// (solution-specific). This keeps solution content out of framework code.
// Format in project.yaml:
//   ui_labels:
//     agent_quick_templates:
//       role_id:
//         - { label: "...", task: "...", context: "..." }
type TaskTemplate = { label: string; task: string; context?: string }

// ---------------------------------------------------------------------------
// Hire Agent Modal
// ---------------------------------------------------------------------------
const EMOJI_SUGGESTIONS = ['A','D','M','P','S','U','E','F','R','Q','T','G','L','C','W']

function HireAgentModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const [tab, setTab] = useState<'ai' | 'manual'>('ai')
  const [jdText, setJdText] = useState('')
  const [isAnalysing, setIsAnalysing] = useState(false)
  const [analyseError, setAnalyseError] = useState('')
  const [roleId, setRoleId]           = useState('')
  const [name, setName]               = useState('')
  const [description, setDescription] = useState('')
  const [icon, setIcon]               = useState('A')
  const [systemPrompt, setSystemPrompt] = useState('')
  const [taskTypesStr, setTaskTypesStr] = useState('')
  const [submitted, setSubmitted]     = useState<{ trace_id: string; description: string } | null>(null)

  const { mutate, isPending, error } = useMutation({
    mutationFn: () => hireAgent({
      role_id:       roleId.trim().toLowerCase().replace(/\s+/g, '_'),
      name:          name.trim(),
      description:   description.trim(),
      icon,
      system_prompt: systemPrompt.trim(),
      task_types:    taskTypesStr.split(',').map(t => t.trim().toUpperCase()).filter(Boolean),
    }),
    onSuccess: (res) => {
      setSubmitted(res)
      qc.invalidateQueries({ queryKey: ['agent-roles'] })
    },
  })

  const autoRoleId = name.trim().toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '')

  const inputStyle = {
    backgroundColor: '#09090b',
    border: '1px solid #3f3f46',
    color: '#d4d4d8',
    width: '100%',
    padding: '0.5rem 0.75rem',
    fontSize: '0.875rem',
    outline: 'none',
  }

  const handleAnalyse = async () => {
    if (!jdText.trim()) return
    setIsAnalysing(true)
    setAnalyseError('')
    try {
      const config = await analyzeJd({ jd_text: jdText })
      setName(config.name || '')
      setDescription(config.description || '')
      setSystemPrompt(config.system_prompt || '')
      setTaskTypesStr(config.task_types.map(t => t.name).join(', '))
      if (config.role_key) {
        setRoleId(config.role_key)
      }
      setTab('manual')
    } catch (err: unknown) {
      setAnalyseError(err instanceof Error ? err.message : 'Analysis failed. Please try again.')
    } finally {
      setIsAnalysing(false)
    }
  }

  if (submitted) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
        <div
          className="w-full max-w-md p-8 text-center space-y-4"
          style={{ backgroundColor: '#18181b', border: '1px solid #3f3f46' }}
        >
          <div className="text-3xl">{icon}</div>
          <h3 className="text-sm font-semibold" style={{ color: '#f4f4f5' }}>Proposal submitted</h3>
          <p className="text-xs" style={{ color: '#a1a1aa' }}>{submitted.description}</p>
          <div className="px-4 py-3 text-xs text-left" style={{ backgroundColor: '#1a1500', border: '1px solid #52400a', color: '#a16207' }}>
            <p className="font-semibold mb-1">Waiting for human approval</p>
            <p>Go to <strong>Proposals &amp; Approvals</strong> in the sidebar to approve this role.
               Once approved, the role card will appear immediately in the Agents page.</p>
            <p className="mt-1 font-mono" style={{ color: '#71717a' }}>trace: {submitted.trace_id.slice(0, 16)}…</p>
          </div>
          <button
            onClick={onClose}
            className="w-full py-2.5 text-sm font-medium transition-colors"
            style={{ backgroundColor: '#f4f4f5', color: '#09090b' }}
          >
            Done
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div
        className="w-full max-w-lg max-h-[90vh] overflow-y-auto"
        style={{ backgroundColor: '#18181b', border: '1px solid #3f3f46' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4" style={{ borderBottom: '1px solid #27272a' }}>
          <div className="flex items-center gap-2">
            <UserPlus size={15} style={{ color: '#71717a' }} />
            <h2 className="text-sm font-semibold" style={{ color: '#f4f4f5' }}>Hire a New Agent</h2>
          </div>
          <button onClick={onClose} style={{ color: '#52525b' }}>
            <X size={16} />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex" style={{ borderBottom: '1px solid #27272a' }}>
          {(['ai', 'manual'] as const).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className="px-5 py-2.5 text-xs font-medium transition-colors"
              style={{
                color: tab === t ? '#f4f4f5' : '#52525b',
                borderBottom: tab === t ? '2px solid #f4f4f5' : '2px solid transparent',
                backgroundColor: 'transparent',
              }}
            >
              {t === 'ai' ? 'AI from JD' : 'Manual'}
            </button>
          ))}
        </div>

        {tab === 'ai' ? (
          <div className="px-5 py-4 space-y-4">
            <p className="text-xs" style={{ color: '#71717a' }}>
              Paste a job description — SAGE will extract the role config automatically.
            </p>
            <textarea
              value={jdText}
              onChange={e => setJdText(e.target.value)}
              placeholder={"Senior QA Engineer — MedTech Platform\n\nResponsibilities:\n- Own end-to-end testing strategy...\n\nRequired skills:\n- 5+ years in QA for regulated medical devices..."}
              rows={10}
              className="font-mono resize-none focus:outline-none"
              style={{
                backgroundColor: '#09090b', border: '1px solid #3f3f46',
                color: '#d4d4d8', width: '100%',
                padding: '0.5rem 0.75rem', fontSize: '0.75rem', outline: 'none',
              }}
            />
            {analyseError && (
              <p className="text-xs px-3 py-2" style={{ backgroundColor: '#1a0000', border: '1px solid #7f1d1d', color: '#fca5a5' }}>
                {analyseError}
              </p>
            )}
            <button
              onClick={handleAnalyse}
              disabled={isAnalysing || !jdText.trim()}
              className="w-full flex items-center justify-center gap-2 py-2.5 text-sm font-medium disabled:opacity-40"
              style={{ backgroundColor: '#18181b', border: '1px solid #3f3f46', color: '#f4f4f5' }}
            >
              {isAnalysing
                ? <><Loader2 size={14} className="animate-spin" /> Analysing…</>
                : <><Sparkles size={14} /> Analyse with AI</>
              }
            </button>
          </div>
        ) : (
          <div className="px-5 py-4 space-y-4">
            {/* Icon picker */}
            <div>
              <label className="text-xs font-medium block mb-1.5" style={{ color: '#71717a' }}>Icon</label>
              <div className="flex flex-wrap gap-1.5 mb-2">
                {EMOJI_SUGGESTIONS.map(e => (
                  <button
                    key={e}
                    onClick={() => setIcon(e)}
                    className="text-lg w-8 h-8 flex items-center justify-center transition-all"
                    style={{
                      border: icon === e ? '1px solid #f4f4f5' : '1px solid #3f3f46',
                      backgroundColor: icon === e ? '#27272a' : 'transparent',
                    }}
                  >{e}</button>
                ))}
              </div>
              <input
                value={icon}
                onChange={e => setIcon(e.target.value)}
                placeholder="Or type any emoji"
                style={{ ...inputStyle, width: '6rem', textAlign: 'center' }}
              />
            </div>

            {/* Name */}
            <div>
              <label className="text-xs font-medium block mb-1.5" style={{ color: '#71717a' }}>
                Display Name <span style={{ color: '#ef4444' }}>*</span>
              </label>
              <input
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="e.g. Security Reviewer"
                style={inputStyle}
              />
              {name && (
                <p className="text-xs mt-1" style={{ color: '#52525b' }}>
                  Role ID: <code style={{ backgroundColor: '#27272a', padding: '0 4px', color: '#a1a1aa' }}>{autoRoleId || '…'}</code>
                </p>
              )}
            </div>

            {/* Description */}
            <div>
              <label className="text-xs font-medium block mb-1.5" style={{ color: '#71717a' }}>
                Description <span style={{ color: '#ef4444' }}>*</span>
              </label>
              <input
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="e.g. Reviews code and configs for security vulnerabilities"
                style={inputStyle}
              />
            </div>

            {/* System prompt */}
            <div>
              <label className="text-xs font-medium block mb-1.5" style={{ color: '#71717a' }}>
                System Prompt <span style={{ color: '#ef4444' }}>*</span>
              </label>
              <textarea
                value={systemPrompt}
                onChange={e => setSystemPrompt(e.target.value)}
                placeholder={`You are a [role] expert.\nWhen given a task:\n1. Analyze carefully\n2. Provide actionable recommendations\n\nReturn JSON with: summary, analysis, recommendations, next_steps, severity, confidence`}
                rows={7}
                className="font-mono resize-none focus:outline-none"
                style={inputStyle}
              />
            </div>

            {/* Task types */}
            <div>
              <label className="text-xs font-medium block mb-1.5" style={{ color: '#71717a' }}>
                Task Types <span style={{ color: '#52525b' }}>(optional, comma-separated)</span>
              </label>
              <input
                value={taskTypesStr}
                onChange={e => setTaskTypesStr(e.target.value)}
                placeholder="e.g. SECURITY_REVIEW, VULN_SCAN"
                style={inputStyle}
              />
              <p className="text-xs mt-1" style={{ color: '#52525b' }}>Will be added to this solution's tasks.yaml</p>
            </div>

            {error && (
              <p className="text-xs px-3 py-2" style={{ backgroundColor: '#1a0000', border: '1px solid #7f1d1d', color: '#fca5a5' }}>
                {(error as Error).message}
              </p>
            )}
          </div>
        )}

        {/* Footer */}
        {tab === 'manual' && (
          <div className="flex gap-2 px-5 pb-5">
            <button
              onClick={onClose}
              className="flex-1 py-2.5 text-sm font-medium transition-colors"
              style={{ border: '1px solid #3f3f46', color: '#71717a', backgroundColor: 'transparent' }}
            >
              Cancel
            </button>
            <button
              onClick={() => mutate()}
              disabled={isPending || !name.trim() || !description.trim() || !systemPrompt.trim()}
              className="flex-1 flex items-center justify-center gap-2 text-sm font-medium py-2.5 transition-colors disabled:opacity-40"
              style={{ backgroundColor: '#f4f4f5', color: '#09090b' }}
            >
              {isPending
                ? <><Loader2 size={14} className="animate-spin" /> Proposing…</>
                : <><UserPlus size={14} /> Propose Role</>
              }
            </button>
          </div>
        )}
        {tab === 'ai' && (
          <div className="px-5 pb-5">
            <button
              onClick={onClose}
              className="w-full py-2.5 text-sm font-medium"
              style={{ border: '1px solid #3f3f46', color: '#71717a', backgroundColor: 'transparent' }}
            >
              Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  )
}


// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function Agents() {
  const [selectedRole, setSelectedRole] = useState<AgentRole | null>(null)
  const [task, setTask]     = useState('')
  const [context, setContext] = useState('')
  const [results, setResults] = useState<AgentResult[]>([])
  const [showHire, setShowHire] = useState(false)
  const { data: projectData } = useProjectConfig()

  const { data: rolesData, isLoading: rolesLoading } = useQuery({
    queryKey: ['agent-roles'],
    queryFn: fetchAgentRoles,
  })

  const { mutate, isPending } = useMutation({
    mutationFn: () => runAgent(selectedRole!.id, task, context),
    onSuccess: (result) => {
      setResults(prev => [result, ...prev])
      setTask('')
      setContext('')
    },
  })

  const roles = rolesData?.roles ?? []

  if (rolesLoading) {
    return (
      <div className="flex items-center justify-center h-48 gap-2" style={{ color: '#52525b' }}>
        <Loader2 className="animate-spin" size={16} /> Loading agents…
      </div>
    )
  }

  if (roles.length === 0) {
    return (
      <div className="space-y-4">
        {showHire && <HireAgentModal onClose={() => setShowHire(false)} />}
        <div className="flex justify-end">
          <button
            onClick={() => setShowHire(true)}
            className="flex items-center gap-1.5 text-xs font-medium px-3 py-2 transition-colors"
            style={{ backgroundColor: '#f4f4f5', color: '#09090b' }}
          >
            <UserPlus size={13} /> Hire Agent
          </button>
        </div>
        <div
          className="p-12 text-center max-w-xl mx-auto"
          style={{ border: '1px dashed #3f3f46', backgroundColor: '#18181b' }}
        >
          <div className="flex justify-center mb-3"><Bot size={32} style={{ color: '#52525b' }} /></div>
          <div className="font-semibold mb-1 text-sm" style={{ color: '#a1a1aa' }}>No agent roles defined</div>
          <p className="text-xs" style={{ color: '#52525b' }}>
            Click <strong style={{ color: '#71717a' }}>Hire Agent</strong> above to define a new role on the fly — it writes
            directly to <code style={{ backgroundColor: '#27272a', padding: '0 4px', color: '#a1a1aa' }}>prompts.yaml</code> via HITL approval.
            {' '}Or switch to a solution that has agent roles defined in its{' '}
            <code style={{ backgroundColor: '#27272a', padding: '0 4px', color: '#a1a1aa' }}>prompts.yaml</code>.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-5 max-w-4xl">
      {showHire && <HireAgentModal onClose={() => setShowHire(false)} />}

      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold" style={{ color: '#f4f4f5' }}>AI Agents</h2>
          <p className="text-xs mt-0.5" style={{ color: '#71717a' }}>
            Select a role, describe your task, and get expert-level analysis.
            Every result requires human approval before acting.
          </p>
        </div>
        <button
          onClick={() => setShowHire(true)}
          className="flex items-center gap-1.5 shrink-0 text-xs font-medium px-3 py-2 transition-colors"
          style={{ backgroundColor: '#f4f4f5', color: '#09090b' }}
        >
          <UserPlus size={13} /> Hire Agent
        </button>
      </div>

      {/* Role grid — Paperclip org-chart style */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
        {roles.map(role => (
          <RoleCard
            key={role.id}
            role={role}
            selected={selectedRole?.id === role.id}
            onClick={() => setSelectedRole(role)}
          />
        ))}
      </div>

      {/* Task form */}
      {selectedRole && (
        <div className="p-4 space-y-4" style={{ border: '1px solid #3f3f46', backgroundColor: '#18181b' }}>
          <div className="flex items-center gap-2">
            <span className="text-lg">{selectedRole.icon}</span>
            <h3 className="font-semibold text-sm" style={{ color: '#f4f4f5' }}>{selectedRole.name}</h3>
            <span className="text-xs" style={{ color: '#52525b' }}>— {selectedRole.description}</span>
          </div>

          {/* Task templates — loaded from project.yaml ui_labels.agent_quick_templates */}
          {(() => {
            const templates: TaskTemplate[] = (projectData?.ui_labels as any)?.agent_quick_templates?.[selectedRole.id] ?? []
            if (templates.length === 0) return null
            return (
              <div>
                <div className="flex items-center gap-1.5 mb-2">
                  <Sparkles size={11} style={{ color: '#71717a' }} />
                  <span className="text-xs font-medium" style={{ color: '#52525b' }}>Quick templates</span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {templates.map(tmpl => (
                    <button
                      key={tmpl.label}
                      onClick={() => { setTask(tmpl.task); if (tmpl.context) setContext(tmpl.context) }}
                      className="text-xs px-2 py-1 transition-colors"
                      style={{ backgroundColor: '#27272a', color: '#a1a1aa', border: '1px solid #3f3f46' }}
                    >
                      {tmpl.label}
                    </button>
                  ))}
                </div>
              </div>
            )
          })()}

          <div>
            <label className="text-xs font-medium block mb-1.5" style={{ color: '#71717a' }}>
              Task / Question <span style={{ color: '#ef4444' }}>*</span>
            </label>
            <textarea
              value={task}
              onChange={e => setTask(e.target.value)}
              placeholder={`Describe what you need from the ${selectedRole.name}…`}
              rows={4}
              className="w-full px-3 py-2.5 text-sm resize-none focus:outline-none"
              style={{
                backgroundColor: '#09090b',
                border: '1px solid #3f3f46',
                color: '#d4d4d8',
              }}
            />
          </div>

          <div>
            <label className="text-xs font-medium block mb-1.5" style={{ color: '#71717a' }}>
              Additional context <span style={{ color: '#52525b' }}>(optional)</span>
            </label>
            <textarea
              value={context}
              onChange={e => setContext(e.target.value)}
              placeholder="Company stage, constraints, existing work, relevant numbers…"
              rows={2}
              className="w-full px-3 py-2 text-sm resize-none focus:outline-none"
              style={{
                backgroundColor: '#09090b',
                border: '1px solid #3f3f46',
                color: '#d4d4d8',
              }}
            />
          </div>

          <button
            onClick={() => mutate()}
            disabled={isPending || !task.trim()}
            className="flex items-center gap-2 text-sm font-medium px-4 py-2 transition-colors disabled:opacity-40"
            style={{ backgroundColor: '#f4f4f5', color: '#09090b' }}
          >
            {isPending
              ? <><Loader2 size={14} className="animate-spin" /> {selectedRole.name} is thinking…</>
              : <><span>{selectedRole.icon}</span> Ask {selectedRole.name}</>
            }
          </button>
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase tracking-widest" style={{ color: '#52525b' }}>
              Results — {results.length}
            </h3>
            <button
              onClick={() => setResults([])}
              className="text-xs transition-colors"
              style={{ color: '#52525b' }}
            >
              Clear all
            </button>
          </div>
          {results.map(r => (
            <ResultCard key={r.trace_id} result={r} />
          ))}
        </div>
      )}
    </div>
  )
}
