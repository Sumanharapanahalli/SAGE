import { useState, useEffect, useRef, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  startBuild, fetchBuildStatus, approveBuild, fetchBuildRuns, fetchBuildRoles,
  type BuildStatus, type BuildRunSummary, type BuildCriticScore,
  type BuildAgentResult, type AgentRole,
} from '../api/client'
import {
  Hammer, Play, CheckCircle2, XCircle, Clock, AlertTriangle,
  ChevronRight, RefreshCw, ThumbsUp, ThumbsDown, ChevronDown,
  ChevronUp, Loader2, Terminal, Zap, FileCode, GitBranch,
  Activity, Target, Wrench, Sparkles, Copy, ExternalLink,
} from 'lucide-react'

// ---------------------------------------------------------------------------
// Types for local UI state
// ---------------------------------------------------------------------------
interface ActivityLogEntry {
  id: string
  timestamp: string
  type: 'thought' | 'action' | 'observation' | 'tool_call' | 'tool_response' | 'error' | 'info'
  agent?: string
  content: string
  detail?: string
  duration_ms?: number
}

interface CriticIssue {
  description: string
  severity: 'critical' | 'major' | 'minor' | 'info'
  category?: string
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function classNames(...classes: (string | false | undefined | null)[]): string {
  return classes.filter(Boolean).join(' ')
}

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return iso
  }
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60_000).toFixed(1)}m`
}

// ---------------------------------------------------------------------------
// Spinner component
// ---------------------------------------------------------------------------
function Spinner({ size = 14, className = '' }: { size?: number; className?: string }) {
  return <Loader2 size={size} className={classNames('animate-spin', className)} />
}

// ---------------------------------------------------------------------------
// Phase stepper
// ---------------------------------------------------------------------------
const PHASES = [
  { key: 'decomposing',         label: 'Decompose',          icon: Target },
  { key: 'critic_plan',        label: 'Critic Review',      icon: AlertTriangle },
  { key: 'awaiting_plan',      label: 'Plan Approval',      icon: ThumbsUp },
  { key: 'scaffolding',        label: 'Scaffold',           icon: GitBranch },
  { key: 'executing',          label: 'Execute',            icon: Zap },
  { key: 'critic_code',        label: 'Code Review',        icon: AlertTriangle },
  { key: 'integrating',        label: 'Integrate',          icon: Wrench },
  { key: 'critic_integration', label: 'Integration Review', icon: AlertTriangle },
  { key: 'awaiting_build',     label: 'Final Approval',     icon: ThumbsUp },
  { key: 'completed',          label: 'Done',               icon: CheckCircle2 },
]

function phaseIndex(state: string): number {
  const idx = PHASES.findIndex(p => p.key === state)
  return idx >= 0 ? idx : (state === 'failed' ? -1 : 0)
}

function PhaseStepper({ state }: { state: string }) {
  const current = phaseIndex(state)
  const isFailed = state === 'failed'
  return (
    <div className="flex items-center gap-1 overflow-x-auto py-3 px-1">
      {PHASES.map((phase, i) => {
        const done = i < current
        const active = i === current && !isFailed
        const Icon = phase.icon
        return (
          <div key={phase.key} className="flex items-center">
            <div
              className={classNames(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-all duration-200',
                done && 'bg-emerald-100 text-emerald-700',
                active && 'bg-emerald-50 text-emerald-700 ring-2 ring-emerald-300 shadow-sm',
                !done && !active && 'bg-zinc-100 text-zinc-400',
                isFailed && i === 0 && 'bg-red-100 text-red-700 ring-2 ring-red-300',
              )}
            >
              {done ? (
                <CheckCircle2 size={12} />
              ) : active ? (
                <Spinner size={12} />
              ) : (
                <Icon size={12} />
              )}
              {phase.label}
            </div>
            {i < PHASES.length - 1 && <ChevronRight size={14} className="text-zinc-300 mx-0.5 flex-shrink-0" />}
          </div>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Critic score badge
// ---------------------------------------------------------------------------
function CriticBadge({ score }: { score: number }) {
  const color = score >= 80 ? 'bg-emerald-100 text-emerald-700' :
                score >= 50 ? 'bg-amber-100 text-amber-700' :
                'bg-red-100 text-red-700'
  return (
    <span className={classNames('inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold', color)}>
      {score}/100
    </span>
  )
}

function SeverityDot({ severity }: { severity: string }) {
  const color =
    severity === 'critical' ? 'bg-red-500' :
    severity === 'major' ? 'bg-orange-500' :
    severity === 'minor' ? 'bg-amber-400' :
    'bg-emerald-400'
  return <span className={classNames('inline-block w-2 h-2 rounded-full flex-shrink-0', color)} />
}

// ---------------------------------------------------------------------------
// Critic card — enhanced with iteration history and issue list
// ---------------------------------------------------------------------------
function CriticCard({ scores, reports }: {
  scores: BuildCriticScore[]
  reports: Array<{ phase: string; result: Record<string, unknown> }>
}) {
  const [expandedPhase, setExpandedPhase] = useState<number | null>(null)

  if (!scores.length) return null
  return (
    <div className="bg-white rounded-lg border p-4 space-y-3">
      <h3 className="text-sm font-semibold text-zinc-700 flex items-center gap-2">
        <AlertTriangle size={16} className="text-amber-500" /> Critic Reports
      </h3>
      {scores.map((s, i) => {
        const report = reports[i]?.result as Record<string, unknown> | undefined
        const history = (report?.history ?? []) as Array<Record<string, unknown>>
        const issues = (report?.issues ?? report?.flaws ?? []) as CriticIssue[]
        const finalReview = report?.final_review as Record<string, unknown> | undefined
        const isExpanded = expandedPhase === i

        return (
          <div key={i} className="border rounded-md overflow-hidden">
            {/* Header — clickable */}
            <button
              onClick={() => setExpandedPhase(isExpanded ? null : i)}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-zinc-50 transition-colors"
            >
              <span className="font-medium capitalize">{s.phase}</span>
              <CriticBadge score={s.score} />
              {s.passed ? (
                <span className="flex items-center gap-1 text-emerald-600 text-xs">
                  <CheckCircle2 size={12} /> Passed
                </span>
              ) : (
                <span className="flex items-center gap-1 text-red-600 text-xs">
                  <XCircle size={12} /> Needs work
                </span>
              )}
              {s.iterations > 1 && (
                <span className="text-zinc-400 text-xs">
                  ({s.iterations} revision{s.iterations > 1 ? 's' : ''})
                </span>
              )}
              {/* Score progression inline */}
              {history.length > 1 && (
                <span className="ml-auto text-xs text-zinc-400 font-mono">
                  {history.map((h) => String(h.score ?? 0)).join(' -> ')}
                </span>
              )}
              <span className="ml-auto">
                {isExpanded ? <ChevronUp size={14} className="text-zinc-400" /> : <ChevronDown size={14} className="text-zinc-400" />}
              </span>
            </button>

            {/* Expanded detail */}
            {isExpanded && (
              <div className="border-t px-3 py-3 space-y-3 bg-zinc-50/50">
                {/* Iteration history timeline */}
                {history.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-2">
                      Score History
                    </h4>
                    <div className="flex items-center gap-2">
                      {history.map((h, j) => {
                        const sc = Number(h.score ?? 0)
                        const prev = j > 0 ? Number(history[j - 1].score ?? 0) : null
                        const improved = prev !== null && sc > prev
                        const declined = prev !== null && sc < prev
                        return (
                          <div key={j} className="flex items-center gap-1">
                            {j > 0 && (
                              <ChevronRight
                                size={12}
                                className={classNames(
                                  improved ? 'text-emerald-500' : declined ? 'text-red-500' : 'text-zinc-300',
                                )}
                              />
                            )}
                            <span
                              className={classNames(
                                'px-2 py-0.5 rounded text-xs font-mono font-medium',
                                sc >= 80 ? 'bg-emerald-100 text-emerald-700' :
                                sc >= 50 ? 'bg-amber-100 text-amber-700' :
                                'bg-red-100 text-red-700',
                              )}
                            >
                              {sc}
                            </span>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}

                {/* Issues found */}
                {issues.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-2">
                      Issues Found ({issues.length})
                    </h4>
                    <div className="space-y-1.5">
                      {issues.map((issue, j) => (
                        <div key={j} className="flex items-start gap-2 text-xs">
                          <SeverityDot severity={typeof issue === 'object' ? (issue.severity ?? 'info') : 'info'} />
                          <span className="text-zinc-600">
                            {typeof issue === 'string' ? issue : issue.description ?? JSON.stringify(issue)}
                          </span>
                          {typeof issue === 'object' && issue.category && (
                            <span className="ml-auto px-1.5 py-0.5 bg-zinc-100 text-zinc-500 rounded text-[10px] whitespace-nowrap">
                              {issue.category}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Final review summary */}
                {finalReview && typeof finalReview.summary === 'string' && (
                  <div className="text-xs text-zinc-600 bg-white rounded p-2 border">
                    <span className="font-medium text-zinc-700">Summary: </span>
                    {finalReview.summary}
                  </div>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Agent task card — expandable
// ---------------------------------------------------------------------------
function AgentTaskCard({ result, waveLabel }: {
  result: BuildAgentResult & { wave?: number; agent_role?: string; acceptance_criteria?: string[]; files_changed?: string[]; error_detail?: string }
  waveLabel?: string
}) {
  const [expanded, setExpanded] = useState(false)
  const isRunning = result.status === 'running' || result.status === 'pending'
  const isError = result.status === 'error' || result.status === 'failed'
  const isDone = result.status === 'completed'

  const statusIcon = isRunning ? <Spinner size={12} className="text-emerald-500" /> :
    isDone ? <CheckCircle2 size={12} className="text-emerald-500" /> :
    isError ? <XCircle size={12} className="text-red-500" /> :
    <Clock size={12} className="text-zinc-400" />

  const criteria = result.acceptance_criteria ?? []
  const files = result.files_changed ?? []

  return (
    <div className={classNames(
      'border rounded-md overflow-hidden transition-all',
      isError && 'border-red-200 bg-red-50/30',
      isRunning && 'border-emerald-200 bg-emerald-50/30',
    )}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-sm hover:bg-zinc-50/50 transition-colors"
      >
        {statusIcon}
        <span className="px-1.5 py-0.5 bg-violet-100 text-violet-700 rounded text-xs font-mono">
          {result.task_type}
        </span>
        {result.agent_role && (
          <span className="px-1.5 py-0.5 bg-emerald-50 text-emerald-600 rounded text-xs">
            @{result.agent_role}
          </span>
        )}
        {waveLabel && (
          <span className="px-1.5 py-0.5 bg-zinc-100 text-zinc-500 rounded text-[10px] font-semibold">
            {waveLabel}
          </span>
        )}
        <span className={classNames(
          'text-xs font-medium',
          isDone ? 'text-emerald-600' : isError ? 'text-red-600' : isRunning ? 'text-emerald-600' : 'text-zinc-400',
        )}>
          {result.status}
        </span>
        {result.tier && <span className="text-zinc-300 text-[10px]">via {result.tier}</span>}
        {/* Progress bar for running tasks */}
        {isRunning && (
          <div className="ml-auto w-16 h-1.5 bg-zinc-200 rounded-full overflow-hidden">
            <div className="h-full bg-emerald-500 rounded-full animate-pulse" style={{ width: '60%' }} />
          </div>
        )}
        <span className="ml-auto">
          {expanded ? <ChevronUp size={12} className="text-zinc-400" /> : <ChevronDown size={12} className="text-zinc-400" />}
        </span>
      </button>

      {expanded && (
        <div className="border-t px-3 py-2.5 space-y-2 bg-zinc-50/50 text-xs">
          {/* Description */}
          <p className="text-zinc-600">{result.description}</p>

          {/* Error detail */}
          {isError && result.error_detail && (
            <div className="bg-red-50 border border-red-200 rounded p-2 text-red-700 font-mono text-[11px] whitespace-pre-wrap">
              {result.error_detail}
            </div>
          )}

          {/* Acceptance criteria checklist */}
          {criteria.length > 0 && (
            <div>
              <h5 className="font-semibold text-zinc-500 mb-1">Acceptance Criteria</h5>
              <ul className="space-y-0.5">
                {criteria.map((c, j) => (
                  <li key={j} className="flex items-start gap-1.5">
                    {isDone ? (
                      <CheckCircle2 size={11} className="text-emerald-500 mt-0.5 flex-shrink-0" />
                    ) : (
                      <span className="w-[11px] h-[11px] border border-zinc-300 rounded-sm mt-0.5 flex-shrink-0" />
                    )}
                    <span className="text-zinc-600">{c}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Files changed */}
          {files.length > 0 && (
            <div>
              <h5 className="font-semibold text-zinc-500 mb-1 flex items-center gap-1">
                <FileCode size={11} /> Files Changed ({files.length})
              </h5>
              <ul className="space-y-0.5 font-mono text-[11px]">
                {files.map((f, j) => (
                  <li key={j} className="text-zinc-500 truncate">{f}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Agent Execution Grid — grouped by wave
// ---------------------------------------------------------------------------
function AgentExecutionGrid({ results }: {
  results: (BuildAgentResult & { wave?: number; agent_role?: string; acceptance_criteria?: string[]; files_changed?: string[]; error_detail?: string })[]
}) {
  if (results.length === 0) return null

  // Group by wave
  const waves = new Map<number, typeof results>()
  results.forEach(r => {
    const w = r.wave ?? 0
    if (!waves.has(w)) waves.set(w, [])
    waves.get(w)!.push(r)
  })
  const sortedWaves = [...waves.entries()].sort((a, b) => a[0] - b[0])
  const hasMultipleWaves = sortedWaves.length > 1

  return (
    <div className="bg-white rounded-lg border p-4 space-y-4">
      <h3 className="text-sm font-semibold text-zinc-700 flex items-center gap-2">
        <Zap size={16} className="text-violet-500" /> Agent Tasks
        <span className="text-zinc-400 font-normal text-xs">
          {results.length} task{results.length !== 1 ? 's' : ''}
          {hasMultipleWaves && ` in ${sortedWaves.length} waves`}
        </span>
      </h3>

      {sortedWaves.map(([wave, tasks]) => (
        <div key={wave}>
          {hasMultipleWaves && (
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-400">
                Wave {wave + 1}
              </span>
              <div className="flex-1 h-px bg-zinc-100" />
              <span className="text-[10px] text-zinc-400">
                {tasks.filter(t => t.status === 'completed').length}/{tasks.length} done
              </span>
            </div>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {tasks.map((r, i) => (
              <AgentTaskCard
                key={i}
                result={r}
                waveLabel={hasMultipleWaves ? `W${wave + 1}` : undefined}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Activity Log Panel (MCP / Integration / ReAct visibility)
// ---------------------------------------------------------------------------
function ActivityLogPanel({ entries, isLive }: { entries: ActivityLogEntry[]; isLive: boolean }) {
  const [collapsed, setCollapsed] = useState(false)
  const [filter, setFilter] = useState<string>('all')
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new entries arrive
  useEffect(() => {
    if (scrollRef.current && !collapsed) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [entries.length, collapsed])

  const filtered = filter === 'all' ? entries : entries.filter(e => e.type === filter)

  const typeColors: Record<string, string> = {
    thought:        'text-purple-600 bg-purple-50',
    action:         'text-emerald-600 bg-emerald-50',
    observation:    'text-emerald-600 bg-emerald-50',
    tool_call:      'text-cyan-600 bg-cyan-50',
    tool_response:  'text-teal-600 bg-teal-50',
    error:          'text-red-600 bg-red-50',
    info:           'text-zinc-500 bg-zinc-50',
  }

  return (
    <div className="bg-white rounded-lg border overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center gap-2 px-4 py-2.5 hover:bg-zinc-50 transition-colors"
      >
        <Terminal size={16} className="text-zinc-500" />
        <span className="text-sm font-semibold text-zinc-700">Agent Activity Log</span>
        {isLive && (
          <span className="flex items-center gap-1 text-[10px] text-emerald-600 font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            LIVE
          </span>
        )}
        <span className="text-xs text-zinc-400 ml-auto mr-2">{entries.length} entries</span>
        {collapsed ? <ChevronDown size={14} className="text-zinc-400" /> : <ChevronUp size={14} className="text-zinc-400" />}
      </button>

      {!collapsed && (
        <>
          {/* Filter bar */}
          <div className="flex items-center gap-1 px-4 py-1.5 border-t border-b bg-zinc-50/50 overflow-x-auto">
            {['all', 'thought', 'action', 'tool_call', 'tool_response', 'observation', 'error'].map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={classNames(
                  'px-2 py-0.5 rounded text-[10px] font-medium whitespace-nowrap transition-colors',
                  filter === f ? 'bg-emerald-600 text-white' : 'text-zinc-500 hover:bg-emerald-50',
                )}
              >
                {f === 'all' ? 'All' : f.replace('_', ' ')}
              </button>
            ))}
          </div>

          {/* Log entries */}
          <div ref={scrollRef} className="max-h-72 overflow-y-auto font-mono text-[11px] divide-y divide-zinc-100">
            {filtered.length === 0 && (
              <div className="px-4 py-6 text-center text-zinc-400 text-xs">
                {entries.length === 0 ? 'Activity will appear here when the build starts...' : 'No entries match the current filter.'}
              </div>
            )}
            {filtered.map(entry => (
              <div key={entry.id} className="px-4 py-1.5 hover:bg-zinc-50/50 flex items-start gap-2">
                <span className="text-zinc-300 whitespace-nowrap w-16 flex-shrink-0 pt-0.5 tabular-nums">
                  {formatTimestamp(entry.timestamp)}
                </span>
                <span className={classNames(
                  'px-1.5 py-0.5 rounded text-[10px] font-medium whitespace-nowrap flex-shrink-0',
                  typeColors[entry.type] ?? 'text-zinc-500 bg-zinc-50',
                )}>
                  {entry.type.replace('_', ' ')}
                </span>
                {entry.agent && (
                  <span className="text-violet-500 whitespace-nowrap flex-shrink-0">@{entry.agent}</span>
                )}
                <span className="text-zinc-700 break-words min-w-0">{entry.content}</span>
                {entry.duration_ms !== undefined && (
                  <span className="text-zinc-300 whitespace-nowrap flex-shrink-0 ml-auto">
                    {formatDuration(entry.duration_ms)}
                  </span>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Quick-start example buttons
// ---------------------------------------------------------------------------
const EXAMPLE_PRODUCTS = [
  {
    label: 'SaaS Dashboard',
    description: 'A multi-tenant SaaS analytics dashboard with user authentication, real-time charts, Stripe billing integration, and a REST API backend built with Python FastAPI and React frontend.',
  },
  {
    label: 'Mobile Fitness App',
    description: 'A cross-platform mobile fitness tracking app built with Flutter that includes workout logging, progress charts, social sharing, offline mode, and integration with Apple HealthKit and Google Fit.',
  },
  {
    label: 'CLI Dev Tool',
    description: 'A developer CLI tool in Rust that scans a codebase, generates documentation, detects code smells, and produces a dependency graph. Supports config via TOML and outputs Markdown reports.',
  },
  {
    label: 'IoT Monitor',
    description: 'An IoT device monitoring platform with a Node.js backend that ingests MQTT telemetry, stores time-series data in InfluxDB, triggers alerts via email/Slack, and shows live dashboards.',
  },
]

// ---------------------------------------------------------------------------
// Error display component
// ---------------------------------------------------------------------------
function ErrorBanner({ error, title, onRetry }: { error: string; title?: string; onRetry?: () => void }) {
  const [expanded, setExpanded] = useState(false)
  const isLong = error.length > 200

  return (
    <div className="bg-red-50 border border-red-200 rounded-lg overflow-hidden">
      <div className="flex items-start gap-2 p-3">
        <XCircle size={16} className="text-red-500 mt-0.5 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          {title && <p className="text-sm font-medium text-red-800 mb-0.5">{title}</p>}
          <p className={classNames(
            'text-sm text-red-700 font-mono',
            !expanded && isLong && 'line-clamp-3',
          )}>
            {error}
          </p>
          {isLong && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-xs text-red-500 hover:text-red-700 mt-1"
            >
              {expanded ? 'Show less' : 'Show full error'}
            </button>
          )}
        </div>
        {onRetry && (
          <button
            onClick={onRetry}
            className="flex items-center gap-1 px-2 py-1 text-xs text-red-600 hover:bg-red-100 rounded transition-colors"
          >
            <RefreshCw size={12} /> Retry
          </button>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Build activity log generator — derives log entries from BuildStatus
// ---------------------------------------------------------------------------
function deriveActivityLog(status: BuildStatus | undefined, prevEntries: ActivityLogEntry[]): ActivityLogEntry[] {
  if (!status) return prevEntries

  const entries: ActivityLogEntry[] = []
  let counter = 0
  const makeId = () => `${status.run_id}-${counter++}`

  // Phase transitions
  if (status.state) {
    entries.push({
      id: makeId(),
      timestamp: status.updated_at || status.created_at,
      type: 'info',
      content: `Build state: ${status.state_description || status.state}`,
    })
  }

  // Plan generation
  if (status.plan.length > 0) {
    entries.push({
      id: makeId(),
      timestamp: status.created_at,
      type: 'thought',
      agent: 'planner',
      content: `Decomposed into ${status.plan.length} tasks across the implementation plan`,
    })
  }

  // Critic reports
  status.critic_scores.forEach((cs, i) => {
    const report = status.critic_reports[i]?.result as Record<string, unknown> | undefined
    entries.push({
      id: makeId(),
      timestamp: status.updated_at,
      type: 'observation',
      agent: 'critic',
      content: `${cs.phase} review: score ${cs.score}/100 (${cs.passed ? 'PASSED' : 'FAILED'})`,
      detail: report?.summary as string | undefined,
    })
    // Issues from critic
    const issues = (report?.issues ?? report?.flaws ?? []) as CriticIssue[]
    issues.forEach(issue => {
      entries.push({
        id: makeId(),
        timestamp: status.updated_at,
        type: 'observation',
        agent: 'critic',
        content: typeof issue === 'string' ? issue : (issue.description ?? JSON.stringify(issue)),
      })
    })
  })

  // Agent results
  status.agent_results.forEach(r => {
    entries.push({
      id: makeId(),
      timestamp: status.updated_at,
      type: r.status === 'error' ? 'error' : 'action',
      agent: r.agent_role ?? r.task_type,
      content: `[${r.task_type}] ${r.description} -- ${r.status}`,
    })
  })

  // Integration
  if (status.integration_result) {
    const ir = status.integration_result as Record<string, unknown>
    entries.push({
      id: makeId(),
      timestamp: status.updated_at,
      type: 'tool_response',
      agent: 'integrator',
      content: `Integration: ${ir.completed_tasks ?? 0}/${ir.total_tasks ?? 0} tasks, ${((ir.files_changed as string[]) ?? []).length} files changed`,
    })
  }

  // MCP tool calls from agent results (if they contain tool_calls metadata)
  status.agent_results.forEach(r => {
    const result = r as unknown as Record<string, unknown>
    const toolCalls = result.tool_calls as Array<Record<string, unknown>> | undefined
    if (toolCalls && Array.isArray(toolCalls)) {
      toolCalls.forEach(tc => {
        entries.push({
          id: makeId(),
          timestamp: status.updated_at,
          type: 'tool_call',
          agent: r.agent_role ?? r.task_type,
          content: `Tool: ${tc.name ?? tc.tool ?? 'unknown'} -- ${tc.status ?? 'called'}`,
          duration_ms: tc.duration_ms as number | undefined,
        })
        if (tc.response || tc.result) {
          entries.push({
            id: makeId(),
            timestamp: status.updated_at,
            type: 'tool_response',
            content: String(tc.response ?? tc.result ?? '').slice(0, 200),
          })
        }
      })
    }
  })

  // Error
  if (status.error) {
    entries.push({
      id: makeId(),
      timestamp: status.updated_at,
      type: 'error',
      content: status.error,
    })
  }

  return entries
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function BuildConsole() {
  const queryClient = useQueryClient()
  const [description, setDescription] = useState('')
  const [solutionName, setSolutionName] = useState('')
  const [repoUrl, setRepoUrl] = useState('')
  const [workspaceDir, setWorkspaceDir] = useState('')
  const [criticThreshold, setCriticThreshold] = useState(70)
  const [hitlLevel, setHitlLevel] = useState<'minimal' | 'standard' | 'strict'>('standard')
  const [activeRunId, setActiveRunId] = useState<string | null>(null)
  const [feedback, setFeedback] = useState('')
  const [activityLog, setActivityLog] = useState<ActivityLogEntry[]>([])
  const [pollStartTime, setPollStartTime] = useState<number | null>(null)
  const [pollStuck, setPollStuck] = useState(false)
  const [consecutiveErrors, setConsecutiveErrors] = useState(0)
  const [pollStopped, setPollStopped] = useState(false)

  const MAX_POLL_MINUTES = 30
  const MAX_CONSECUTIVE_ERRORS = 3

  // Start build mutation
  const startMutation = useMutation({
    mutationFn: () => startBuild({
      product_description: description,
      solution_name: solutionName || undefined,
      repo_url: repoUrl || undefined,
      workspace_dir: workspaceDir || undefined,
      critic_threshold: criticThreshold !== 70 ? criticThreshold : undefined,
      hitl_level: hitlLevel,
    }),
    onSuccess: (data) => {
      setActiveRunId(data.run_id)
      setDescription('')
      setActivityLog([])
      setPollStartTime(Date.now())
      setPollStuck(false)
      setConsecutiveErrors(0)
      setPollStopped(false)
      queryClient.invalidateQueries({ queryKey: ['build-runs'] })
    },
  })

  // Approve mutation
  const approveMutation = useMutation({
    mutationFn: ({ runId, approved }: { runId: string; approved: boolean }) =>
      approveBuild(runId, approved, feedback),
    onSuccess: () => {
      setFeedback('')
      queryClient.invalidateQueries({ queryKey: ['build-status', activeRunId] })
    },
  })

  // Available agent roles
  const rolesQuery = useQuery({
    queryKey: ['build-roles'],
    queryFn: fetchBuildRoles,
    retry: false,
  })

  // List runs
  const runsQuery = useQuery({
    queryKey: ['build-runs'],
    queryFn: fetchBuildRuns,
    refetchInterval: 10_000,
  })

  // Active run status (poll every 3s, with timeout and error tracking)
  const statusQuery = useQuery({
    queryKey: ['build-status', activeRunId],
    queryFn: async () => {
      try {
        const data = await fetchBuildStatus(activeRunId!)
        setConsecutiveErrors(0)
        return data
      } catch (err) {
        setConsecutiveErrors(prev => {
          const next = prev + 1
          if (next >= MAX_CONSECUTIVE_ERRORS) {
            setPollStopped(true)
          }
          return next
        })
        throw err
      }
    },
    enabled: !!activeRunId && !pollStopped,
    refetchInterval: 3_000,
  })

  const status = statusQuery.data
  const isAwaiting = status?.state === 'awaiting_plan' || status?.state === 'awaiting_build'
  const isActive = !!status && status.state !== 'completed' && status.state !== 'failed'

  // Poll timeout detection — warn after 30 minutes
  useEffect(() => {
    if (!pollStartTime || !isActive) return
    const interval = setInterval(() => {
      const elapsed = Date.now() - pollStartTime
      if (elapsed > MAX_POLL_MINUTES * 60 * 1000) {
        setPollStuck(true)
      }
    }, 10_000)
    return () => clearInterval(interval)
  }, [pollStartTime, isActive])

  // Reset poll state when build completes
  useEffect(() => {
    if (status?.state === 'completed' || status?.state === 'failed') {
      setPollStartTime(null)
      setPollStuck(false)
    }
  }, [status?.state])

  // Derive activity log from status updates
  useEffect(() => {
    if (status) {
      setActivityLog(deriveActivityLog(status, activityLog))
    }
  // Only re-derive when status changes (updated_at or state)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status?.updated_at, status?.state, status?.agent_results.length])

  const handleQuickStart = useCallback((desc: string) => {
    setDescription(desc)
  }, [])

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-emerald-100 rounded-lg">
          <Hammer size={20} className="text-emerald-600" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-zinc-800">Build Console</h1>
          <span className="text-xs text-zinc-400">0 &rarr; 1 &rarr; N Pipeline &mdash; describe a product, get a working codebase</span>
        </div>
      </div>

      {/* Start Build form */}
      <div className="bg-white rounded-lg border p-5 space-y-4">
        <h2 className="text-sm font-semibold text-zinc-700 flex items-center gap-2">
          <Sparkles size={14} className="text-amber-500" />
          Start a New Build
        </h2>

        {/* Quick-start examples */}
        <div>
          <p className="text-xs text-zinc-400 mb-1.5">Quick start examples:</p>
          <div className="flex flex-wrap gap-1.5">
            {EXAMPLE_PRODUCTS.map(ex => (
              <button
                key={ex.label}
                onClick={() => handleQuickStart(ex.description)}
                className="px-2.5 py-1 rounded-full text-xs border border-zinc-200 text-zinc-600 hover:bg-emerald-50 hover:border-emerald-200 hover:text-emerald-700 transition-colors"
              >
                {ex.label}
              </button>
            ))}
          </div>
        </div>

        {/* Description textarea */}
        <textarea
          value={description}
          onChange={e => setDescription(e.target.value)}
          placeholder="Describe what you want to build in plain English. Be specific about tech stack, features, and integrations..."
          className="w-full h-32 border rounded-md p-3 text-sm resize-none focus:ring-2 focus:ring-emerald-300 focus:outline-none placeholder:text-zinc-300"
        />

        {/* Config fields row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div>
            <label className="block text-[11px] font-medium text-zinc-500 mb-1">Solution Name</label>
            <input
              value={solutionName}
              onChange={e => setSolutionName(e.target.value)}
              placeholder="my_app (optional)"
              className="w-full border rounded-md px-3 py-1.5 text-sm focus:ring-2 focus:ring-emerald-300 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-[11px] font-medium text-zinc-500 mb-1">Repo URL</label>
            <div className="relative">
              <input
                value={repoUrl}
                onChange={e => setRepoUrl(e.target.value)}
                placeholder="https://github.com/..."
                className="w-full border rounded-md px-3 py-1.5 text-sm pr-8 focus:ring-2 focus:ring-emerald-300 focus:outline-none"
              />
              <ExternalLink size={12} className="absolute right-2.5 top-2.5 text-zinc-300" />
            </div>
          </div>
          <div>
            <label className="block text-[11px] font-medium text-zinc-500 mb-1">Workspace Directory</label>
            <input
              value={workspaceDir}
              onChange={e => setWorkspaceDir(e.target.value)}
              placeholder="/path/to/workspace"
              className="w-full border rounded-md px-3 py-1.5 text-sm focus:ring-2 focus:ring-emerald-300 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-[11px] font-medium text-zinc-500 mb-1">HITL Level</label>
            <select
              value={hitlLevel}
              onChange={e => setHitlLevel(e.target.value as 'minimal' | 'standard' | 'strict')}
              className="w-full border rounded-md px-3 py-1.5 text-sm focus:ring-2 focus:ring-emerald-300 focus:outline-none"
              title="HITL approval granularity"
            >
              <option value="minimal">Minimal (2 gates)</option>
              <option value="standard">Standard (3 gates)</option>
              <option value="strict">Strict (every stage)</option>
            </select>
          </div>
        </div>

        {/* Critic threshold slider */}
        <div className="flex items-center gap-4">
          <div className="flex-1 max-w-xs">
            <label className="flex items-center justify-between text-[11px] font-medium text-zinc-500 mb-1">
              <span>Critic Threshold</span>
              <span className={classNames(
                'text-xs font-semibold tabular-nums',
                criticThreshold >= 80 ? 'text-emerald-600' :
                criticThreshold >= 50 ? 'text-amber-600' : 'text-red-600',
              )}>
                {criticThreshold}/100
              </span>
            </label>
            <input
              type="range"
              min={0}
              max={100}
              value={criticThreshold}
              onChange={e => setCriticThreshold(Number(e.target.value))}
              className="w-full h-1.5 bg-zinc-200 rounded-full appearance-none cursor-pointer accent-emerald-600"
            />
            <div className="flex justify-between text-[10px] text-zinc-300 mt-0.5">
              <span>Permissive</span>
              <span>Strict</span>
            </div>
          </div>

          <button
            onClick={() => startMutation.mutate()}
            disabled={!description.trim() || startMutation.isPending}
            className="flex items-center gap-2 bg-emerald-600 text-white px-5 py-2 rounded-md text-sm font-medium hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
          >
            {startMutation.isPending ? <Spinner size={14} /> : <Play size={14} />}
            {startMutation.isPending ? 'Starting...' : 'Start Build'}
          </button>
        </div>

        {/* Mutation errors */}
        {startMutation.isError && (
          <ErrorBanner
            error={(startMutation.error as Error).message}
            title="Build failed to start"
            onRetry={() => startMutation.mutate()}
          />
        )}

        {/* Available Agent Roles */}
        {rolesQuery.data?.roles && rolesQuery.data.roles.length > 0 && (
          <div className="mt-4 p-3 bg-gray-50 rounded-lg border border-gray-100">
            <h4 className="text-xs font-semibold text-gray-600 mb-2">Available Agent Roles ({rolesQuery.data.roles.length})</h4>
            <div className="flex flex-wrap gap-1.5">
              {rolesQuery.data.roles.map((r: AgentRole) => (
                <span key={r.role} className="inline-flex items-center gap-1 text-xs px-2 py-0.5 bg-white border border-gray-200 rounded-full text-gray-600" title={r.description}>
                  {r.title || r.role}
                  {r.team && <span className="text-gray-400">· {r.team}</span>}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Active run */}
      {status && (
        <div className="space-y-4">
          {/* Phase stepper */}
          <div className="bg-white rounded-lg border px-4 py-1">
            <PhaseStepper state={status.state} />
          </div>

          {/* Poll timeout warning */}
          {pollStuck && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-center gap-2 text-sm text-amber-800">
              <AlertTriangle size={16} className="text-amber-500 flex-shrink-0" />
              <span>Build may be stuck (polling for over 30 minutes) — consider restarting.</span>
            </div>
          )}

          {/* Consecutive fetch errors */}
          {pollStopped && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2 text-sm text-red-800">
              <XCircle size={16} className="text-red-500 flex-shrink-0" />
              <span>Status polling stopped after {MAX_CONSECUTIVE_ERRORS} consecutive fetch failures.</span>
              <button
                onClick={() => { setConsecutiveErrors(0); setPollStopped(false) }}
                className="ml-auto flex items-center gap-1 px-2 py-1 text-xs text-red-600 hover:bg-red-100 rounded transition-colors"
              >
                <RefreshCw size={12} /> Resume polling
              </button>
            </div>
          )}

          {/* Status bar */}
          <div className="flex items-center gap-3 text-sm bg-white rounded-lg border px-4 py-3">
            <span className="font-semibold text-zinc-700">{status.solution_name}</span>
            <span className={classNames(
              'px-2 py-0.5 rounded text-xs font-medium',
              status.state === 'completed' ? 'bg-emerald-100 text-emerald-700' :
              status.state === 'failed' ? 'bg-red-100 text-red-700' :
              'bg-emerald-100 text-emerald-700',
            )}>
              {isActive && <Spinner size={10} className="inline mr-1" />}
              {status.state_description || status.state}
            </span>
            <span className="text-zinc-400 text-xs">{status.task_count} task(s)</span>
            {status.hitl_level && (
              <span className="text-xs text-zinc-400 ml-auto">
                HITL: <span className="font-medium text-zinc-500">{status.hitl_level}</span>
              </span>
            )}
          </div>

          {/* Plan review */}
          {status.plan.length > 0 && (
            <PlanPanel plan={status.plan} />
          )}

          {/* Critic reports */}
          <CriticCard scores={status.critic_scores} reports={status.critic_reports} />

          {/* Agent execution grid */}
          <AgentExecutionGrid results={status.agent_results} />

          {/* Integration results */}
          {status.integration_result && (
            <IntegrationPanel result={status.integration_result} />
          )}

          {/* Activity log */}
          <ActivityLogPanel entries={activityLog} isLive={isActive} />

          {/* Approval buttons */}
          {isAwaiting && (
            <div className="bg-amber-50 rounded-lg border border-amber-200 p-4 space-y-3">
              <h3 className="text-sm font-semibold text-amber-800 flex items-center gap-2">
                <AlertTriangle size={14} />
                {status.state === 'awaiting_plan' ? 'Review Implementation Plan' : 'Review Final Build'}
              </h3>
              <p className="text-xs text-amber-700">
                {status.state === 'awaiting_plan'
                  ? 'Review the plan above. Approve to proceed with execution, or reject with feedback to regenerate.'
                  : 'The build is complete. Review the results and approve to finalize, or reject to iterate.'}
              </p>
              <textarea
                value={feedback}
                onChange={e => setFeedback(e.target.value)}
                placeholder="Optional feedback for the agent..."
                className="w-full h-16 border border-amber-200 rounded-md p-2 text-sm resize-none focus:ring-2 focus:ring-amber-300 focus:outline-none bg-white"
              />
              <div className="flex gap-2">
                <button
                  onClick={() => approveMutation.mutate({ runId: status.run_id, approved: true })}
                  disabled={approveMutation.isPending}
                  className="flex items-center gap-1.5 bg-emerald-600 text-white px-4 py-1.5 rounded-md text-sm font-medium hover:bg-emerald-700 disabled:opacity-50 transition-colors"
                >
                  {approveMutation.isPending ? <Spinner size={14} /> : <ThumbsUp size={14} />}
                  Approve
                </button>
                <button
                  onClick={() => approveMutation.mutate({ runId: status.run_id, approved: false })}
                  disabled={approveMutation.isPending}
                  className="flex items-center gap-1.5 bg-red-600 text-white px-4 py-1.5 rounded-md text-sm font-medium hover:bg-red-700 disabled:opacity-50 transition-colors"
                >
                  <ThumbsDown size={14} /> Reject
                </button>
              </div>
              {approveMutation.isError && (
                <ErrorBanner error={(approveMutation.error as Error).message} title="Approval action failed" />
              )}
            </div>
          )}

          {/* Error */}
          {status.error && (
            <ErrorBanner
              error={status.error}
              title={`Build failed at: ${status.state_description || status.state}`}
            />
          )}
        </div>
      )}

      {/* Loading state when waiting for first status */}
      {activeRunId && !status && statusQuery.isFetching && (
        <div className="flex items-center justify-center gap-3 py-12 text-zinc-400">
          <Spinner size={20} />
          <span className="text-sm">Loading build status...</span>
        </div>
      )}

      {/* Past runs */}
      {runsQuery.data && runsQuery.data.runs.length > 0 && (
        <div className="bg-white rounded-lg border p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-zinc-700 flex items-center gap-2">
              <Clock size={14} className="text-zinc-400" />
              Build History
              <span className="text-xs font-normal text-zinc-400">{runsQuery.data.runs.length} runs</span>
            </h3>
            <button
              onClick={() => queryClient.invalidateQueries({ queryKey: ['build-runs'] })}
              className="text-zinc-400 hover:text-zinc-600 transition-colors"
              title="Refresh"
            >
              <RefreshCw size={14} />
            </button>
          </div>
          <div className="space-y-1">
            {runsQuery.data.runs.map(run => (
              <button
                key={run.run_id}
                onClick={() => {
                  setActiveRunId(run.run_id)
                  setActivityLog([])
                }}
                className={classNames(
                  'w-full text-left flex items-center gap-3 px-3 py-2 rounded-md text-sm hover:bg-zinc-50 transition-colors',
                  activeRunId === run.run_id && 'bg-emerald-50 border border-emerald-200',
                )}
              >
                {run.state === 'completed' ? (
                  <CheckCircle2 size={14} className="text-emerald-500" />
                ) : run.state === 'failed' ? (
                  <XCircle size={14} className="text-red-500" />
                ) : (
                  <Spinner size={14} className="text-emerald-500" />
                )}
                <span className="font-medium text-zinc-700">{run.solution_name}</span>
                <span className={classNames(
                  'px-1.5 py-0.5 rounded text-xs',
                  run.state === 'completed' ? 'bg-emerald-100 text-emerald-700' :
                  run.state === 'failed' ? 'bg-red-100 text-red-700' :
                  'bg-emerald-100 text-emerald-600',
                )}>
                  {run.state}
                </span>
                <span className="text-zinc-400 text-xs ml-auto">{run.task_count} tasks</span>
                <span className="text-zinc-300 text-xs">
                  {formatTimestamp(run.created_at)}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Plan panel — extracted for clarity
// ---------------------------------------------------------------------------
function PlanPanel({ plan }: {
  plan: BuildStatus['plan']
}) {
  const [expandedTask, setExpandedTask] = useState<number | null>(null)

  return (
    <div className="bg-white rounded-lg border p-4">
      <h3 className="text-sm font-semibold text-zinc-700 mb-3 flex items-center gap-2">
        <Target size={14} className="text-emerald-500" />
        Implementation Plan
        <span className="text-xs font-normal text-zinc-400">{plan.length} steps</span>
      </h3>
      <div className="space-y-1.5">
        {plan.map((task, i) => {
          const isExpanded = expandedTask === i
          return (
            <div key={i} className="border rounded-md overflow-hidden">
              <button
                onClick={() => setExpandedTask(isExpanded ? null : i)}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-zinc-50 transition-colors"
              >
                <span className="text-zinc-400 w-5 text-right text-xs tabular-nums">{task.step}.</span>
                <span className="px-1.5 py-0.5 bg-zinc-100 rounded text-xs font-mono">
                  {task.task_type}
                </span>
                {task.agent_role && (
                  <span className="px-1.5 py-0.5 bg-violet-50 text-violet-600 rounded text-xs">
                    @{task.agent_role}
                  </span>
                )}
                <span className="text-zinc-600 text-left truncate">{task.description}</span>
                {task.depends_on && task.depends_on.length > 0 && (
                  <span className="text-zinc-300 text-[10px] whitespace-nowrap flex-shrink-0">
                    deps: [{task.depends_on.join(', ')}]
                  </span>
                )}
                <span className="ml-auto flex-shrink-0">
                  {isExpanded ? <ChevronUp size={12} className="text-zinc-400" /> : <ChevronDown size={12} className="text-zinc-400" />}
                </span>
              </button>

              {isExpanded && (
                <div className="border-t px-3 py-2.5 bg-zinc-50/50 space-y-2">
                  <p className="text-xs text-zinc-600">{task.description}</p>

                  {/* Acceptance criteria */}
                  {task.acceptance_criteria && task.acceptance_criteria.length > 0 && (
                    <div>
                      <h5 className="text-[11px] font-semibold text-zinc-500 mb-1">Acceptance Criteria</h5>
                      <ul className="space-y-0.5">
                        {task.acceptance_criteria.map((c, j) => (
                          <li key={j} className="flex items-start gap-1.5 text-xs text-zinc-600">
                            <span className="w-[11px] h-[11px] border border-zinc-300 rounded-sm mt-0.5 flex-shrink-0" />
                            {c}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Dependencies */}
                  {task.depends_on && task.depends_on.length > 0 && (
                    <p className="text-[11px] text-zinc-400">
                      Depends on steps: {task.depends_on.join(', ')}
                    </p>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Integration panel — enhanced
// ---------------------------------------------------------------------------
function IntegrationPanel({ result }: { result: Record<string, unknown> }) {
  const [expanded, setExpanded] = useState(false)
  const completedTasks = result.completed_tasks as number | undefined
  const totalTasks = result.total_tasks as number | undefined
  const filesChanged = (result.files_changed as string[]) ?? []
  const errors = (result.errors as string[]) ?? []

  return (
    <div className="bg-white rounded-lg border overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-4 py-3 hover:bg-zinc-50 transition-colors"
      >
        <Activity size={16} className="text-emerald-500" />
        <span className="text-sm font-semibold text-zinc-700">Integration Results</span>
        <span className="text-xs text-zinc-400">
          {completedTasks ?? 0}/{totalTasks ?? 0} tasks
        </span>
        <span className="text-xs text-zinc-400">
          {filesChanged.length} files
        </span>
        {errors.length > 0 && (
          <span className="text-xs text-red-500">{errors.length} errors</span>
        )}
        <span className="ml-auto">
          {expanded ? <ChevronUp size={14} className="text-zinc-400" /> : <ChevronDown size={14} className="text-zinc-400" />}
        </span>
      </button>

      {expanded && (
        <div className="border-t px-4 py-3 space-y-3 bg-zinc-50/50">
          {/* Progress bar */}
          {totalTasks != null && totalTasks > 0 && (
            <div>
              <div className="flex justify-between text-[11px] text-zinc-500 mb-1">
                <span>Progress</span>
                <span>{completedTasks ?? 0}/{totalTasks}</span>
              </div>
              <div className="w-full h-2 bg-zinc-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                  style={{ width: `${((completedTasks ?? 0) / totalTasks) * 100}%` }}
                />
              </div>
            </div>
          )}

          {/* Files changed */}
          {filesChanged.length > 0 && (
            <div>
              <h5 className="text-[11px] font-semibold text-zinc-500 mb-1 flex items-center gap-1">
                <FileCode size={11} /> Files Changed ({filesChanged.length})
              </h5>
              <ul className="space-y-0.5 font-mono text-[11px] max-h-32 overflow-y-auto">
                {filesChanged.map((f, i) => (
                  <li key={i} className="text-zinc-500 truncate">{f}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Errors */}
          {errors.length > 0 && (
            <div>
              <h5 className="text-[11px] font-semibold text-red-500 mb-1">Errors</h5>
              {errors.map((err, i) => (
                <p key={i} className="text-xs text-red-600 font-mono">{err}</p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
