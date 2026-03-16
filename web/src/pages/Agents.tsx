import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchAgentRoles, runAgent, hireAgent } from '../api/client'
import { useProjectConfig } from '../hooks/useProjectConfig'
import { Loader2, ChevronDown, ChevronUp, CheckCircle, Sparkles, UserPlus, X } from 'lucide-react'

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
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-start gap-3 px-5 py-4">
        <span className="text-2xl shrink-0">{result.icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-gray-800 text-sm">{result.role_name}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${sevStyle}`}>
              {result.severity}
            </span>
            <span className={`text-xs font-medium ${CONF_COLOR[result.confidence] ?? 'text-gray-500'}`}>
              {result.confidence} confidence
            </span>
          </div>
          <p className="text-sm text-gray-700 mt-1 font-medium">{result.summary}</p>
          <p className="text-xs text-gray-400 mt-0.5 font-mono truncate">
            trace: {result.trace_id.slice(0, 16)}…
          </p>
        </div>
        <button
          onClick={() => setExpanded(v => !v)}
          className="text-gray-400 hover:text-gray-600 shrink-0"
        >
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-gray-100 px-5 pb-5 pt-4 space-y-4">
          {/* Analysis */}
          <div>
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">Analysis</h4>
            <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{result.analysis}</p>
          </div>

          {/* Recommendations */}
          {result.recommendations.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Recommendations</h4>
              <ul className="space-y-1.5">
                {result.recommendations.map((r, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                    <CheckCircle size={14} className="text-green-500 mt-0.5 shrink-0" />
                    {r}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Next steps */}
          {result.next_steps.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Next Steps</h4>
              <ol className="space-y-1.5 list-none">
                {result.next_steps.map((s, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                    <span className="bg-gray-100 text-gray-600 text-xs font-bold rounded-full w-5 h-5
                                     flex items-center justify-center shrink-0 mt-0.5">
                      {i + 1}
                    </span>
                    {s}
                  </li>
                ))}
              </ol>
            </div>
          )}

          <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
            ⚠ Pending human review — approve or reject this recommendation before acting on it.
          </p>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Role selector card
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
      className={`text-left p-4 rounded-xl border transition-all ${
        selected
          ? 'border-indigo-400 bg-indigo-50 shadow-sm'
          : 'border-gray-200 bg-white hover:border-indigo-300 hover:bg-indigo-50/50'
      }`}
    >
      <div className="text-2xl mb-2">{role.icon}</div>
      <div className="text-sm font-semibold text-gray-800">{role.name}</div>
      <div className="text-xs text-gray-500 mt-0.5 leading-snug">{role.description}</div>
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
const EMOJI_SUGGESTIONS = ['🤖','🔍','🧭','⚙️','🛡️','📊','🧪','🎯','💡','🔧','🚀','🧠','📋','🔐','🌐']

function HireAgentModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const [roleId, setRoleId]           = useState('')
  const [name, setName]               = useState('')
  const [description, setDescription] = useState('')
  const [icon, setIcon]               = useState('🤖')
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

  if (submitted) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8 text-center space-y-4">
          <div className="text-4xl">{icon}</div>
          <h3 className="text-lg font-semibold text-gray-800">Proposal submitted</h3>
          <p className="text-sm text-gray-600">{submitted.description}</p>
          <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-xs text-amber-700 text-left">
            <p className="font-semibold mb-1">Waiting for human approval</p>
            <p>Go to <strong>Proposals &amp; Approvals</strong> in the sidebar to approve this role.
               Once approved, the role card will appear immediately in the Agents page.</p>
            <p className="mt-1 font-mono text-amber-500">trace: {submitted.trace_id.slice(0, 16)}…</p>
          </div>
          <button
            onClick={onClose}
            className="w-full bg-indigo-600 text-white rounded-lg py-2.5 text-sm font-medium hover:bg-indigo-700"
          >
            Done
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <UserPlus size={18} className="text-indigo-600" />
            <h2 className="text-base font-semibold text-gray-800">Hire a New Agent</h2>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={18} />
          </button>
        </div>

        <div className="px-6 py-5 space-y-4">
          {/* Icon picker */}
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1.5">Icon</label>
            <div className="flex flex-wrap gap-2 mb-2">
              {EMOJI_SUGGESTIONS.map(e => (
                <button
                  key={e}
                  onClick={() => setIcon(e)}
                  className={`text-xl w-9 h-9 rounded-lg border flex items-center justify-center transition-all ${
                    icon === e ? 'border-indigo-400 bg-indigo-50' : 'border-gray-200 hover:border-indigo-300'
                  }`}
                >{e}</button>
              ))}
            </div>
            <input
              value={icon}
              onChange={e => setIcon(e.target.value)}
              placeholder="Or type any emoji"
              className="w-24 border border-gray-200 rounded-lg px-3 py-1.5 text-sm text-center focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>

          {/* Name */}
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1.5">
              Display Name <span className="text-red-500">*</span>
            </label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. Security Reviewer"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
            {name && (
              <p className="text-xs text-gray-400 mt-1">
                Role ID: <code className="bg-gray-100 px-1 rounded">{autoRoleId || '…'}</code>
              </p>
            )}
          </div>

          {/* Description */}
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1.5">
              Description <span className="text-red-500">*</span>
            </label>
            <input
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="e.g. Reviews code and configs for security vulnerabilities"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>

          {/* System prompt */}
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1.5">
              System Prompt <span className="text-red-500">*</span>
            </label>
            <textarea
              value={systemPrompt}
              onChange={e => setSystemPrompt(e.target.value)}
              placeholder={`You are a [role] expert.\nWhen given a task:\n1. Analyze carefully\n2. Provide actionable recommendations\n\nReturn JSON with: summary, analysis, recommendations, next_steps, severity, confidence`}
              rows={7}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm font-mono
                         resize-none focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>

          {/* Task types */}
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1.5">
              Task Types <span className="text-gray-400 font-normal">(optional, comma-separated)</span>
            </label>
            <input
              value={taskTypesStr}
              onChange={e => setTaskTypesStr(e.target.value)}
              placeholder="e.g. SECURITY_REVIEW, VULN_SCAN"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
            <p className="text-xs text-gray-400 mt-1">Will be added to this solution's tasks.yaml</p>
          </div>

          {error && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {(error as Error).message}
            </p>
          )}
        </div>

        {/* Footer */}
        <div className="flex gap-3 px-6 pb-6">
          <button
            onClick={onClose}
            className="flex-1 border border-gray-200 text-gray-600 rounded-lg py-2.5 text-sm font-medium hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={() => mutate()}
            disabled={isPending || !name.trim() || !description.trim() || !systemPrompt.trim()}
            className="flex-1 flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700
                       disabled:opacity-40 text-white rounded-lg py-2.5 text-sm font-medium transition-colors"
          >
            {isPending
              ? <><Loader2 size={15} className="animate-spin" /> Proposing…</>
              : <><UserPlus size={15} /> Propose Role</>
            }
          </button>
        </div>
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
      <div className="flex items-center justify-center h-48 text-gray-400 gap-2">
        <Loader2 className="animate-spin" size={18} /> Loading agents…
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
            className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700
                       text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            <UserPlus size={15} /> Hire Agent
          </button>
        </div>
        <div className="bg-white rounded-xl border border-dashed border-gray-300 p-12 text-center max-w-xl mx-auto">
          <div className="text-4xl mb-3">🤖</div>
          <div className="font-semibold text-gray-700 mb-1">No agent roles defined</div>
          <p className="text-sm text-gray-400">
            Click <strong>Hire Agent</strong> above to define a new role on the fly — it writes
            directly to <code className="bg-gray-100 px-1 rounded">prompts.yaml</code> via HITL approval.
            <br /><br />
            Or switch to a solution that has agent roles defined in its{' '}
            <code className="bg-gray-100 px-1 rounded">prompts.yaml</code>.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {showHire && <HireAgentModal onClose={() => setShowHire(false)} />}

      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">AI Agents</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Select a role, describe your task, and get expert-level analysis with recommendations.
            Every result requires human approval before acting.
          </p>
        </div>
        <button
          onClick={() => setShowHire(true)}
          className="flex items-center gap-1.5 shrink-0 bg-indigo-600 hover:bg-indigo-700
                     text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          <UserPlus size={15} /> Hire Agent
        </button>
      </div>

      {/* Role grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
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
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 space-y-4">
          <div className="flex items-center gap-2">
            <span className="text-xl">{selectedRole.icon}</span>
            <h3 className="font-semibold text-gray-800">{selectedRole.name}</h3>
            <span className="text-xs text-gray-400">— {selectedRole.description}</span>
          </div>

          {/* Task templates — loaded from project.yaml ui_labels.agent_quick_templates */}
          {(() => {
            const templates: TaskTemplate[] = (projectData?.ui_labels as any)?.agent_quick_templates?.[selectedRole.id] ?? []
            if (templates.length === 0) return null
            return (
              <div>
                <div className="flex items-center gap-1.5 mb-2">
                  <Sparkles size={12} className="text-indigo-500" />
                  <span className="text-xs font-medium text-gray-500">Quick templates</span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {templates.map(tmpl => (
                    <button
                      key={tmpl.label}
                      onClick={() => { setTask(tmpl.task); if (tmpl.context) setContext(tmpl.context) }}
                      className="text-xs bg-indigo-50 text-indigo-700 hover:bg-indigo-100 px-2.5 py-1.5
                                 rounded-lg border border-indigo-200 transition-colors"
                    >
                      {tmpl.label}
                    </button>
                  ))}
                </div>
              </div>
            )
          })()}

          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1.5">
              Task / Question <span className="text-red-500">*</span>
            </label>
            <textarea
              value={task}
              onChange={e => setTask(e.target.value)}
              placeholder={`Describe what you need from the ${selectedRole.name}…`}
              rows={4}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm
                         resize-none focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>

          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1.5">
              Additional context <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <textarea
              value={context}
              onChange={e => setContext(e.target.value)}
              placeholder="Company stage, constraints, existing work, relevant numbers…"
              rows={2}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm
                         resize-none focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>

          <button
            onClick={() => mutate()}
            disabled={isPending || !task.trim()}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700
                       disabled:opacity-40 text-white text-sm font-medium
                       px-5 py-2.5 rounded-lg transition-colors"
          >
            {isPending
              ? <><Loader2 size={15} className="animate-spin" /> {selectedRole.name} is thinking…</>
              : <><span>{selectedRole.icon}</span> Ask {selectedRole.name}</>
            }
          </button>
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide">
              Results — {results.length}
            </h3>
            <button
              onClick={() => setResults([])}
              className="text-xs text-gray-400 hover:text-red-500 transition-colors"
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
