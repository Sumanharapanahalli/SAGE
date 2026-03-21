import type { ModuleMetadata, ImprovementAccess, ImprovementMode } from '../types/module'

// ---------------------------------------------------------------------------
// Access control switch
// ---------------------------------------------------------------------------
// DEV PHASE  → 'open'       : every user can submit + approve + plan
// POST RELEASE → 'role_based': check userRole from your auth system
// LOCKED     → 'disabled'   : no requests accepted
// ---------------------------------------------------------------------------
export const IMPROVEMENT_MODE: ImprovementMode = 'open'

// ---------------------------------------------------------------------------
// Module Registry
// Each module/page self-describes its current features and improvement ideas.
// This drives the ModuleWrapper info panel and FeatureRequestPanel hints.
// ---------------------------------------------------------------------------
export const MODULE_REGISTRY: Record<string, ModuleMetadata> = {
  dashboard: {
    id: 'dashboard',
    name: 'Dashboard',
    description: 'System overview: health, active proposals, error trends, integration status.',
    version: '2.0.0',
    route: '/',
    features: [
      'System health card with LLM provider and version info',
      'Active proposals panel with severity colour-coding (RED/AMBER/GREEN)',
      'Error trend chart — last 24 h Recharts line chart',
      'Integration status grid (GitLab / Teams / Metabase / Spira)',
      '30-second auto-refresh via TanStack Query',
    ],
    improvementHints: [
      'Add KPI counters: analyses today, MRs created, approvals',
      'Add a dark / light mode toggle',
      'Add configurable refresh interval selector',
      'Add a notification bell that pulses on new RED proposals',
      'Add a recent-activity feed showing the last 5 audit events',
      'Add quick-action buttons (Analyze log, Review MR) on the dashboard',
    ],
  },

  analyst: {
    id: 'analyst',
    name: 'Log Analyst',
    description: 'AI-powered manufacturing error log analysis with approve/reject learning loop.',
    version: '2.0.0',
    route: '/analyst',
    features: [
      'Log entry textarea with Analyze button',
      'AI severity badge (RED / AMBER / GREEN)',
      'Root cause hypothesis and recommended action display',
      'Approve / Reject & Teach buttons with feedback textarea',
      'Rejection feedback ingested into vector RAG memory',
    ],
    improvementHints: [
      'Add drag-and-drop log file upload (.txt / .log)',
      'Add batch analysis mode — paste multiple log entries',
      'Add history panel showing the last 10 analyses for this session',
      'Add copy-to-clipboard button on every proposal',
      'Add a confidence threshold slider to filter low-confidence results',
      'Add syntax highlighting for structured log formats',
    ],
  },

  developer: {
    id: 'developer',
    name: 'Developer',
    description: 'GitLab MR creation, AI code review (ReAct loop), and pipeline monitoring.',
    version: '2.0.0',
    route: '/developer',
    features: [
      'Create MR from issue (project ID + issue IID + optional branch)',
      'AI code review using multi-step ReAct reasoning loop',
      'Open MR list with pipeline status badges',
      'Pipeline status detail per MR (stages + jobs)',
    ],
    improvementHints: [
      'Add MR unified diff viewer in the browser',
      'Add one-click "Post AI review as GitLab comment" button',
      'Add GitLab project selector populated from API',
      'Add MR review history for the session',
      'Add pipeline re-trigger button',
      'Add a patch proposal form (file path + error description)',
    ],
  },

  audit: {
    id: 'audit',
    name: 'Audit Log',
    description: 'ISO 13485 compliance audit trail with full trace detail and CSV export.',
    version: '2.0.0',
    route: '/audit',
    features: [
      'Paginated table (50 per page) — Timestamp / Actor / Action Type / Trace ID',
      'Filter by actor and action type',
      'Row click → full trace detail modal (input, output, metadata)',
      'Export to CSV',
    ],
    improvementHints: [
      'Add date range filter (from / to date pickers)',
      'Add full-text search across input_context and output_content',
      'Add PDF compliance report generation',
      'Add action type distribution chart (bar chart)',
      'Add actor filter as multi-select dropdown',
      'Add digital signature verification status column',
    ],
  },

  monitor: {
    id: 'monitor',
    name: 'Monitor',
    description: 'Live status of Teams / Metabase / GitLab polling threads.',
    version: '2.0.0',
    route: '/monitor',
    features: [
      'Per-thread running / stopped indicator with colour badge',
      'Last poll timestamp per integration',
      'Event count per source',
      '10-second auto-refresh',
    ],
    improvementHints: [
      'Add event log showing the last 20 detected events',
      'Add manual "Poll Now" trigger button per thread',
      'Add configurable poll interval slider per source',
      'Add alert threshold configuration (e.g. min error count to trigger)',
      'Add thread restart / stop buttons',
      'Add a Teams channel message preview',
    ],
  },

  improvements: {
    id: 'improvements',
    name: 'Improvements',
    description: 'Module improvement request queue and AI-assisted implementation planning.',
    version: '2.0.0',
    route: '/improvements',
    features: [
      'Submit feature requests per module from any page',
      'View all requests with status: pending / approved / in_planning / completed / rejected',
      'Generate AI implementation plan via Planner Agent',
      'Approve / reject requests with reviewer notes',
      'Filter by module and status',
    ],
    improvementHints: [
      'Add voting (upvote) on feature requests',
      'Add comment thread per request',
      'Add auto-create GitLab issue on approval',
      'Add email / Teams notification on status change',
      'Add effort estimation from the Planner plan',
    ],
  },

  agents: {
    id: 'agents',
    name: 'AI Agents',
    description: 'Run solution-defined AI agent roles — any business function defined in prompts.yaml.',
    version: '1.0.0',
    route: '/agents',
    features: [
      'Role selector grid populated from solution prompts.yaml',
      'Task input with optional context field',
      'Structured result cards with severity and confidence badges',
      'Recommendations and next steps display',
      'Human review required on every result',
    ],
    improvementHints: [
      'Add role favourites / pinning',
      'Add result history panel for the session',
      'Add export result to PDF or Markdown',
      'Add multi-role chaining (run task through multiple roles sequentially)',
      'Add role-specific context templates',
    ],
  },

  llm: {
    id: 'llm',
    name: 'LLM Settings',
    description: 'Switch LLM provider and model, view session usage statistics.',
    version: '1.0.0',
    route: '/llm',
    features: [
      'Switch between Gemini CLI, Claude Code CLI, Claude API, and Local Llama',
      'Model selector per provider',
      'Session usage statistics (calls, tokens, errors)',
      'Provider status indicator',
    ],
    improvementHints: [
      'Add provider latency benchmarking',
      'Add token usage chart over time',
      'Add provider health check button',
      'Add cost estimation for API providers',
    ],
  },

  settings: {
    id: 'settings',
    name: 'Settings',
    description: 'Framework and solution configuration management.',
    version: '1.0.0',
    route: '/settings',
    features: [
      'View current solution configuration',
      'Integration status overview',
      'Active module listing',
    ],
    improvementHints: [
      'Add inline config editing',
      'Add integration connection testing',
      'Add backup/restore configuration',
    ],
  },

  'yaml-editor': {
    id: 'yaml-editor',
    name: 'Config Editor',
    description: 'Edit solution YAML configuration files with syntax validation.',
    version: '1.0.0',
    route: '/yaml-editor',
    features: [
      'Edit project.yaml, prompts.yaml, and tasks.yaml',
      'YAML syntax validation before save',
      'Hot-reload backend after save',
    ],
    improvementHints: [
      'Add YAML schema validation per file type',
      'Add diff view showing changes before save',
      'Add version history / undo',
    ],
  },

  'live-console': {
    id: 'live-console',
    name: 'Live Console',
    description: 'Real-time stream of all backend log output — agent activity, LLM calls, approvals.',
    version: '1.0.0',
    route: '/live-console',
    features: [
      'SSE log streaming from Python backend',
      'Filter by text or logger name',
      'Pause and clear controls',
    ],
    improvementHints: [
      'Add log-level filter buttons',
      'Add download log session as text file',
    ],
  },

  queue: {
    id: 'queue',
    name: 'Task Queue',
    description: 'View and monitor all queued tasks from approved implementation plans.',
    version: '1.0.0',
    route: '/queue',
    features: [
      'List all tasks with status: pending / in_progress / completed / failed',
      'Filter by status and source (SAGE framework vs solution)',
      'Color-coded by source: purple for SAGE tasks, orange for solution tasks',
      'Stats bar showing total, pending, in-progress, completed, and failed counts',
      'Auto-refreshes every 5 seconds',
      'Collapsible payload details per task',
      'Links tasks to their originating feature request',
    ],
    improvementHints: [
      'Add ability to cancel pending tasks',
      'Add task retry button for failed tasks',
      'Add task duration display (started_at → completed_at)',
      'Add per-task log viewer showing related console output',
      'Add CSV export of task history',
    ],
  },

  costs: {
    id: 'costs',
    name: 'Cost Tracker',
    description: 'Per-tenant LLM token and cost tracking with budget controls and daily charts.',
    version: '1.0.0',
    route: '/costs',
    features: [
      'Total spend, projected monthly cost, call count, avg cost per call',
      'Daily cost bar chart (inline SVG — no chart library)',
      'Top solutions by cost with proportional bar',
      'Cost breakdown by model (table)',
      'Input/output token totals',
      'Period selector: 7d / 30d / 90d',
      'Auto-refresh every 30 seconds',
    ],
    improvementHints: [
      'Add budget limit configuration UI per solution',
      'Add cost alert email/Slack notification when 80% budget used',
      'Add CSV export of cost history',
      'Add per-request cost drill-down linked to audit log trace_id',
      'Add cost forecast chart with linear regression',
    ],
  },

  org: {
    id: 'org',
    name: 'Organization',
    description: 'Visualize and configure solution hierarchy, knowledge channels, and cross-team routing',
    version: '1.0.0',
    route: '/org-graph',
    features: [
      'React Flow graph visualization of all solutions in the org',
      'Blue edges — knowledge channel flows between producer and consumer solutions',
      'Orange edges — task routing links between solutions',
      'Root solution highlighted with dashed border',
      'Knowledge Channels table listing all channels and their members',
      'Reload button to re-fetch org.yaml at runtime',
    ],
    improvementHints: [
      'Add inline channel creation form in the graph sidebar',
      'Add drag-to-connect interaction for creating routing links',
      'Add per-node click panel showing solution stats',
      'Add animated edge particles to show live data flow',
    ],
  },

  guide: {
    id: 'guide',
    name: 'User Guide',
    description: 'Animated GIF walkthroughs for key SAGE features.',
    version: '1.0.0',
    route: '/guide',
    features: [
      'Six animated GIF walkthrough sections covering core SAGE workflows',
      'Automatic fallback placeholder when a GIF recording is not yet available',
      'Step-by-step instructions alongside each walkthrough',
      'Instructions for adding new GIF recordings',
    ],
    improvementHints: [
      'Add search across guide sections',
      'Add a "mark as read" state per section stored in localStorage',
      'Add video embed support as an alternative to GIFs',
    ],
  },

  organization: {
    id: 'organization',
    name: 'Organization',
    description: 'Company mission, vision, and core values — the root context for all solutions.',
    version: '1.0.0',
    route: '/settings/organization',
    features: [
      'Define company mission statement',
      'Set vision and core values',
      'Context auto-injected into all solution generation',
      'View linked solutions',
    ],
    improvementHints: [],
  },

  build: {
    id: 'build',
    name: 'Build Console',
    description: 'End-to-end product builder: describe → decompose → critic review → build → approve.',
    version: '1.0.0',
    route: '/build',
    features: [
      'Plain-English product description input',
      'AI-powered task decomposition via Planner Agent',
      'Critic Agent adversarial review at every gate (plan, code, integration)',
      'Builder↔Critic loop with score progression tracking',
      'Two HITL approval gates: plan review + final build review',
      'Wave-based parallel agent execution via OpenSWE (3-tier degradation)',
      'Phase stepper showing pipeline progress',
      'Build history with past runs',
    ],
    improvementHints: [
      'Add GitHub PR creation on build approval',
      'Add real-time log streaming per agent task',
      'Add workspace file browser showing generated code',
      'Add cost estimation per build run',
      'Add template library for common product types',
    ],
  },

  'access-control': {
    id: 'access-control',
    name: 'Access Control',
    description: 'Manage API keys and user role assignments for the active solution.',
    version: '1.0.0',
    route: '/access-control',
    features: [
      'Create and revoke API keys (sk-sage-* format, SHA-256 hash stored only)',
      'Assign and list user roles per solution (viewer / operator / approver / admin)',
      'Current user identity card showing provider and role',
      'Role hierarchy reference panel',
      'OIDC-ready (Okta / Azure AD / Google Workspace) with API key fallback',
      'Auth disabled by default — zero impact on existing functionality',
    ],
    improvementHints: [
      'Add last-used timestamp per API key',
      'Add OIDC provider connection wizard',
      'Add role change audit log viewer',
      'Add bulk role import from CSV',
      'Add key expiry / rotation policy',
    ],
  },

}
// ---------------------------------------------------------------------------
// To add solution-specific modules: extend MODULE_REGISTRY above with your
// custom module definition. The framework ships with universal modules only.
// Solution-specific module metadata (names, hints, features) belongs in
// your solution's project.yaml or as an addition to this registry.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Project-scoped module filtering — driven by active_modules from project.yaml
// No hardcoded solution names. Pass the active_modules list from the project config.
// ---------------------------------------------------------------------------
export function getModulesForProject(activeModules: string[]): Record<string, ModuleMetadata> {
  if (!activeModules || activeModules.length === 0) {
    return { ...MODULE_REGISTRY }
  }
  const result: Record<string, ModuleMetadata> = {}
  for (const id of activeModules) {
    if (MODULE_REGISTRY[id]) result[id] = MODULE_REGISTRY[id]
  }
  return result
}

// ---------------------------------------------------------------------------
// Access control hook (pure function — no React dependency)
// ---------------------------------------------------------------------------
export function getModuleAccess(/* userRole?: string */): ImprovementAccess {
  if (IMPROVEMENT_MODE === 'open') {
    return {
      canRequest: true,
      canApprove: true,
      canGeneratePlan: true,
      mode: 'open',
    }
  }

  // ── FUTURE: uncomment and wire to your auth system ──────────────────────
  // if (IMPROVEMENT_MODE === 'role_based') {
  //   const role = userRole ?? 'viewer'
  //   return {
  //     canRequest: ['engineer', 'qa', 'admin'].includes(role),
  //     canApprove: ['qa', 'admin'].includes(role),
  //     canGeneratePlan: ['admin'].includes(role),
  //     mode: 'role_based',
  //   }
  // }
  // ─────────────────────────────────────────────────────────────────────────

  return { canRequest: false, canApprove: false, canGeneratePlan: false, mode: 'disabled' }
}
