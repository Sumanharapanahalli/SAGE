# Task 14: Aria-labels on icon-only buttons

**Category:** ui  
**Score:** 9.0/10  
**Converged:** True  
**Iterations:** 2  
**Elapsed:** 396s  

---

## Task

Add aria-label attributes to every icon-only button (a button with no visible text, only an SVG icon) in: web/src/components/layout/Header.tsx, web/src/components/layout/Sidebar.tsx, web/src/components/proposals/ProposalCard.tsx. The aria-label should describe the action, not the icon. Example: aria-label='Approve proposal' not aria-label='Check mark'.

## Criteria

Every icon-only button has aria-label; labels describe the action; no visible text added to the UI; TypeScript compiles.

## Proposal (submit to HITL approval gate)

=== FILE: web/src/components/layout/Header.tsx ===
```tsx
import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { Command, MessageSquare, Sparkles, ChevronRight } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { fetchHealth } from '../../api/client'
import { useProjectConfig } from '../../hooks/useProjectConfig'
import { useChatContext } from '../../context/ChatContext'
import UserMenu from './UserMenu'

const PAGE_TITLES: Record<string, string> = {
  '/':               'Dashboard',
  '/agents':         'AI Agents',
  '/analyst':        'Log Analyst',
  '/developer':      'Developer',
  '/audit':          'Audit Log',
  '/monitor':        'Monitor',
  '/improvements':   'Improvements',
  '/llm':            'LLM Settings',
  '/orchestrator':   'Orchestrator Intelligence',
  '/preflight':      'Preflight Check',
  '/settings':       'Settings',
  '/yaml-editor':    'Config Editor',
  '/build':          'Build Console',
  '/live-console':   'Live Console',
  '/onboarding':     'New Solution',
  '/queue':          'Task Queue',
  '/access-control': 'Access Control',
  '/costs':          'Cost Tracker',
  '/workflows':      'Workflows',
  '/issues':         'Issues',
  '/activity':       'Activity',
  '/goals':          'Goals',
  '/org':            'Org Chart',
  '/approvals':      'Approvals',
  '/knowledge':      'Knowledge Base',
  '/product-backlog': 'Product Backlog',
  '/cds-compliance':  'CDS Compliance',
  '/regulatory':      'Regulatory Compliance',
  '/guide':           'User Guide',
  '/settings/organization': 'Organization',
  // New pages
  '/gym':             'Agent Gym',
  '/safety':          'Safety Analysis',
  '/skills':          'Skills & Tools',
  '/code':            'Code Execution',
  '/chat':            'Chat',
  '/constitution':    'Constitution',
}

const ROUTE_TO_AREA: Record<string, string> = {
  '/':                'Work',
  '/chat':            'Work',
  '/approvals':       'Work',
  '/queue':           'Work',
  '/product-backlog': 'Work',
  '/build':           'Work',
  '/live-console':    'Work',
  '/agents':         'Intelligence',
  '/analyst':        'Intelligence',
  '/developer':      'Intelligence',
  '/monitor':        'Intelligence',
  '/improvements':   'Intelligence',
  '/workflows':      'Intelligence',
  '/goals':          'Intelligence',
  '/gym':            'Intelligence',
  '/code':           'Intelligence',
  '/audit':          'Knowledge',
  '/costs':          'Knowledge',
  '/activity':       'Knowledge',
  '/knowledge':      'Knowledge',
  '/issues':         'Knowledge',
  '/safety':         'Compliance',
  '/org-graph':      'Organization',
  '/onboarding':     'Organization',
  '/llm':            'Admin',
  '/yaml-editor':    'Admin',
  '/access-control': 'Admin',
  '/integrations':   'Admin',
  '/skills':         'Admin',
  '/constitution':            'Admin',
  '/settings':               'Admin',
  '/guide':                  'Admin',
  '/cds-compliance':         'Admin',
  '/regulatory':              'Admin',
  '/settings/organization':  'Admin',
}

interface HeaderProps {
  onOpenPalette?: () => void
}

export default function Header({ onOpenPalette }: HeaderProps) {
  const { pathname } = useLocation()
  const { openChat, panelState } = useChatContext()

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'j') {
        e.preventDefault()
        if (panelState === 'closed' || panelState === 'minimised') {
          openChat()
        }
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [panelState, openChat])

  const { data: healthData, isError: healthError } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  })

  const { data: projectData } = useProjectConfig()

  const online = !healthError && !!healthData
  const provider = (healthData as any)?.llm_provider ?? 'Unknown'
  const model = (healthData as any)?.llm_model ?? ''
  const uiLabels = (projectData as any)?.ui_labels ?? {}
  const UI_LABEL_ROUTES: Record<string, string> = {
    '/analyst':   uiLabels.analyst_page_title,
    '/developer': uiLabels.developer_page_title,
    '/monitor':   uiLabels.monitor_page_title,
  }
  const title = UI_LABEL_ROUTES[pathname] ?? PAGE_TITLES[pathname] ?? 'SAGE[ai]'
  const area = ROUTE_TO_AREA[pathname] ?? 'SAGE'
  const projectName = (projectData as any)?.name ?? 'SAGE Framework'

  return (
    <header
      className="h-12 border-b flex items-center px-4 gap-2 shrink-0"
      style={{ backgroundColor: '#111113', borderColor: '#1e1e22' }}
    >
      {/* Breadcrumb */}
      <div className="flex items-center gap-1.5 flex-1 min-w-0">
        <span style={{ fontSize: '12px', color: '#6b7280', fontWeight: 500 }}>
          {projectName}
        </span>
        <ChevronRight size={10} style={{ color: '#d1d5db' }} />
        <span style={{ fontSize: '12px', color: '#9ca3af' }}>
          {area}
        </span>
        <ChevronRight size={10} style={{ color: '#d1d5db' }} />
        <span style={{ fontSize: '13px', fontWeight: 600, color: '#e4e4e7' }}>
          {title}
        </span>
      </div>

      {/*
        Header color strategy (one meaning per color — see PROPOSAL #4):
          - STATUS palette: green = online, red = offline. Used ONLY for the
            connection indicator below, and always with a text label.
          - SELECTION state: blue = active (the chat toggle when open).
          - METADATA / neutral: grays for the breadcrumb, model badge, palette.
        Green is no longer overloaded onto branding/metadata.
      */}

      {/* Model badge — metadata, neutral (was green-bg + orange-text, incoherent) */}
      {online && (
        <div
          className="flex items-center gap-1.5 px-2.5 py-1"
          style={{
            background: 'rgba(255, 255, 255, 0.04)',
            border: '1px solid #2a2a2e',
            borderRadius: '8px',
            fontSize: '11px',
            color: '#a1a1aa',
            fontWeight: 500,
          }}
          title={`LLM: ${provider}${model ? ` / ${model}` : ''}`}
        >
          <Sparkles size={11} style={{ color: '#a1a1aa' }} />
          <span>{provider}{model ? ` · ${model}` : ''}</span>
        </div>
      )}

      {/* Connection status — one labelled dot, the only use of the status palette.
          Text uses the light-400 shade for >=4.5:1 contrast on the dark header. */}
      <div
        className="flex items-center gap-1.5"
        title={online ? 'Backend online' : 'Backend offline'}
      >
        <span
          style={{
            width: 7, height: 7, borderRadius: '50%',
            backgroundColor: online ? '#22c55e' : '#ef4444',
            display: 'inline-block',
            boxShadow: online ? '0 0 6px rgba(34,197,94,0.45)' : '0 0 6px rgba(239,68,68,0.45)',
          }}
        />
        <span style={{ fontSize: '11px', fontWeight: 600, color: online ? '#4ade80' : '#f87171' }}>
          {online ? 'Online' : 'Offline'}
        </span>
      </div>

      {/* Command palette — renders visible "K" text, so it is not icon-only.
          Accessible name comes from the visible text + title; no aria-label. */}
      <button
        onClick={onOpenPalette}
        className="flex items-center gap-1 text-xs px-2 py-1 transition-colors shrink-0"
        style={{
          color: '#9ca3af',
          border: '1px solid #e5e7eb',
          borderRadius: '6px',
          background: 'rgba(255,255,255,0.02)',
        }}
        title="Command palette (Cmd+K)"
      >
        <Command size={10} />
        <span style={{ fontSize: '10px', fontWeight: 500 }}>K</span>
      </button>

      {/* Chat — icon-only (MessageSquare), needs an accessible name */}
      <button
        onClick={() => openChat()}
        aria-label="Open SAGE chat"
        title="SAGE Chat (Ctrl+J)"
        className="flex items-center gap-1 text-xs px-2 py-1 transition-colors shrink-0"
        style={{
          color: panelState !== 'closed' ? '#3b82f6' : '#52525b',
          border: `1px solid ${panelState !== 'closed' ? '#1d4ed8' : '#e5e7eb'}`,
          borderRadius: '6px',
          background: panelState !== 'closed' ? 'rgba(59,130,246,0.08)' : 'rgba(255,255,255,0.02)',
        }}
      >
        <MessageSquare size={11} />
      </button>

      <UserMenu />
    </header>
  )
}
```

=== FILE: web/src/components/layout/Sidebar.tsx ===
```tsx
import { useState, useEffect } from 'react'
import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, Search, GitMerge, ClipboardList,
  Activity, Lightbulb, Cpu, Settings, FileCode2, Bot,
  Terminal, Wand2, Plug, ListOrdered, ShieldCheck, DollarSign,
  GitBranch, Target, Inbox, Network, Building2,
  CheckSquare, Zap, Database, BookOpen, Shield,
  ChevronDown, ChevronsUpDown, LayoutGrid, Users, type LucideIcon,
  Dumbbell, ShieldAlert, Wrench, Code2, Brain, MessageSquare,
} from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchProjects, fetchHealth, switchProject } from '../../api/client'
import { useProjectConfig } from '../../hooks/useProjectConfig'
import Tooltip from './Tooltip'
import StatsStrip from './StatsStrip'
import { useTourContext } from '../../context/TourContext'
import OnboardingWizard from '../onboarding/OnboardingWizard'
import SolutionPicker from '../ui/SolutionPicker'

// ---------------------------------------------------------------------------
const SAGE_VERSION = 'v0.1.0-alpha'

function initials(id: string): string {
  const words = id.split(/[_\s-]+/).filter(Boolean)
  if (words.length === 1) return id.slice(0, 2).toUpperCase()
  return (words[0][0] + words[1][0]).toUpperCase()
}

// ---------------------------------------------------------------------------
interface NavItem {
  to: string; icon: LucideIcon; label: string; moduleId: string; tooltip: string
}
interface NavArea {
  id: string; label: string; icon: LucideIcon; accent: string; items: NavItem[]; tooltip: string
}

const NAV_AREAS: NavArea[] = [
  {
    id: 'work', label: 'Work', icon: CheckSquare, accent: '#ef4444', tooltip: 'View and act on agent proposals, queued tasks, and live activity',
    items: [
      { to: '/chat',            icon: MessageSquare,   label: 'Chat',            moduleId: 'chat',            tooltip: 'Converse with any agent role — Analyst, Developer, Planner, and more' },
      { to: '/approvals',       icon: Inbox,           label: 'Approvals',       moduleId: 'approvals',       tooltip: 'Agent proposals waiting for your review before execution' },
      { to: '/queue',           icon: ListOrdered,     label: 'Task Queue',      moduleId: 'queue',           tooltip: 'Tasks currently queued or running across all agents' },
      { to: '/',                icon: LayoutDashboard, label: 'Dashboard',       moduleId: 'dashboard',       tooltip: 'System health, recent activity, and integration status' },
      { to: '/product-backlog', icon: Users,          label: 'Product Backlog', moduleId: 'product-backlog', tooltip: 'Transform customer inputs into structured product requirements and user stories' },
      { to: '/build',           icon: Wand2,           label: 'Build',           moduleId: 'build',           tooltip: 'End-to-end product builder: describe → decompose → build → approve' },
      { to: '/live-console',    icon: Terminal,        label: 'Live Console',    moduleId: 'live-console',    tooltip: 'Real-time backend log stream' },
    ],
  },
  {
    id: 'intelligence', label: 'Intelligence', icon: Zap, accent: '#a78bfa', tooltip: 'Run agent tasks, review plans, and track improvement goals',
    items: [
      { to: '/agents',       icon: Bot,       label: 'Agents',       moduleId: 'agents',       tooltip: "Submit a task to an agent role defined in this solution's prompts.yaml" },
      { to: '/analyst',      icon: Search,    label: 'Analyst',      moduleId: 'analyst',      tooltip: 'AI triage of log entries and error signals' },
      { to: '/developer',    icon: GitMerge,  label: 'Developer',    moduleId: 'developer',    tooltip: 'Code review and merge request creation via connected GitLab' },
      { to: '/monitor',      icon: Activity,  label: 'Monitor',      moduleId: 'monitor',      tooltip: 'Live status of all configured integration polling threads' },
      { to: '/improvements', icon: Lightbulb, label: 'Improvements', moduleId: 'improvements', tooltip: 'Feature request queue and AI-generated implementation plans' },
      { to: '/workflows',    icon: GitBranch, label: 'Workflows',    moduleId: 'workflows',    tooltip: 'LangGraph workflow definitions and execution history' },
      { to: '/goals',        icon: Target,    label: 'Goals',        moduleId: 'improvements', tooltip: 'High-level objectives tracked against in-progress work' },
      { to: '/gym',          icon: Dumbbell,  label: 'Agent Gym',    moduleId: 'gym',          tooltip: 'Train agents through exercises, track ratings, browse curriculum' },
      { to: '/code',         icon: Code2,     label: 'Code Runner',  moduleId: 'code',         tooltip: 'Submit autonomous code tasks, view execution, approve changes' },
    ],
  },
  {
    id: 'knowledge', label: 'Knowledge', icon: Database, accent: '#f97316', tooltip: 'Vector knowledge base, shared channels, and compliance records',
    items: [
      { to: '/knowledge', icon: Brain,          label: 'Knowledge Base', moduleId: 'knowledge', tooltip: "Search, browse, and manage knowledge base entries" },
      { to: '/activity',  icon: Activity,      label: 'Channels',     moduleId: 'audit',    tooltip: 'Cross-team knowledge channels shared via org configuration' },
      { to: '/audit',     icon: ClipboardList, label: 'Audit Log',    moduleId: 'audit',    tooltip: 'Full compliance audit trail — proposals, approvals, rejections' },
      { to: '/costs',     icon: DollarSign,    label: 'Costs',        moduleId: 'costs',    tooltip: 'LLM token usage and budget controls per solution' },
    ],
  },
  {
    id: 'organization', label: 'Organization', icon: Building2, accent: '#3b82f6', tooltip: 'Visualize and configure the multi-solution org structure',
    items: [
      { to: '/org-graph',  icon: Network, label: 'Org Graph',  moduleId: 'org',        tooltip: 'React Flow graph of solutions, knowledge channels, and task routing' },
      { to: '/onboarding', icon: Wand2,   label: 'Onboarding', moduleId: 'onboarding', tooltip: 'Generate a new solution from a plain-language description' },
    ],
  },
  {
    id: 'admin', label: 'Admin', icon: Shield, accent: '#475569', tooltip: 'Framework-level configuration — not solution-specific',
    items: [
      { to: '/llm',            icon: Cpu,         label: 'LLM Settings',   moduleId: 'llm',            tooltip: 'Switch LLM provider and model; view session token usage' },
      { to: '/yaml-editor',    icon: FileCode2,   label: 'Config Editor',  moduleId: 'yaml-editor',    tooltip: 'Edit solution YAML files with live validation' },
      { to: '/access-control', icon: ShieldCheck, label: 'Access Control', moduleId: 'access-control', tooltip: 'Manage API keys and user role assignments' },
      { to: '/integrations',   icon: Plug,        label: 'Integrations',   moduleId: 'integrations',   tooltip: 'Status and configuration for all connected integrations' },
      { to: '/safety',               icon: ShieldAlert, label: 'Safety Analysis', moduleId: 'safety',         tooltip: 'FMEA, Fault Tree Analysis, ASIL/SIL/IEC 62304 classification' },
      { to: '/cds-compliance',        icon: ShieldCheck, label: 'CDS Compliance', moduleId: 'cds-compliance', tooltip: 'FDA Clinical Decision Support compliance — 4-criterion assessment per 2026 guidance' },
      { to: '/regulatory',            icon: Shield,      label: 'Regulatory',     moduleId: 'regulatory',      tooltip: 'Multi-standard regulatory compliance — FDA, EU MDR, AI Act, IEC 62304, ISO 14971 and more' },
      { to: '/skills',                icon: Wrench,      label: 'Skills & Tools', moduleId: 'skills',          tooltip: 'Manage skill registry, browse MCP tools, configure integrations' },
      { to: '/orchestrator',           icon: Brain,       label: 'Orchestrator',   moduleId: 'orchestrator',   tooltip: 'SOTA orchestration: reflection, consensus, beam search, budget controls, live events' },
      { to: '/constitution',           icon: BookOpen,    label: 'Constitution',   moduleId: 'constitution',   tooltip: 'Solution blue book — principles, constraints, voice, decision rules' },
      { to: '/preflight',             icon: Activity,    label: 'Preflight',      moduleId: 'preflight',      tooltip: 'System preflight check — verify backend, LLM, and knowledge store' },
      { to: '/settings',              icon: Settings,    label: 'Settings',       moduleId: 'settings',       tooltip: 'Framework-wide settings and display preferences' },
      { to: '/settings/organization', icon: Building2,   label: 'Organization',   moduleId: 'organization',   tooltip: 'Company mission, vision and values' },
    ],
  },
]

// ---------------------------------------------------------------------------
// SolutionRail — 44px far-left column
// ---------------------------------------------------------------------------
// Icon lookup for SolutionRail — subset of PRESET_ICONS available in this file
const RAIL_ICONS: Record<string, any> = {
  Cpu, Bot, Activity, Search, GitMerge, Lightbulb, Target,
  Database, Shield, Network, Zap,
}

function SolutionRail({ onOpenWizard }: { onOpenWizard: () => void }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [pickerOpen, setPickerOpen] = useState(false)
  const [pinnedIds, setPinnedIds] = useState<string[]>(() => {
    try { return JSON.parse(localStorage.getItem('sage_pinned_solutions') ?? '[]') } catch { return [] }
  })

  const { data: healthData } = useQuery({ queryKey: ['health'], queryFn: fetchHealth, refetchInterval: 30_000 })
  const activeId = (healthData as any)?.project?.project ?? ''

  const { data: projectsData } = useQuery({ queryKey: ['projects'], queryFn: fetchProjects, staleTime: 60_000 })
  const switchMutation = useMutation({
    mutationFn: (id: string) => switchProject(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['health'] }),
  })

  const { data: projectData } = useProjectConfig()
  const activeTheme = (projectData as any)?.theme ?? {}
  const activeIconName = activeTheme.icon_name ?? ''
  const activeAccent  = activeTheme.accent ?? '#3b82f6'

  const solutions = projectsData?.projects ?? []
  const pinnedToShow = pinnedIds.filter(id => id !== activeId && solutions.some(s => s.id === id))

  const handlePin = (id: string) => {
    if (id === activeId || pinnedIds.includes(id) || pinnedIds.length >= 5) return
    const next = [...pinnedIds, id]
    setPinnedIds(next)
    try { localStorage.setItem('sage_pinned_solutions', JSON.stringify(next)) } catch {}
  }

  const activeSolution = solutions.find(s => s.id === activeId)
  const ActiveIcon = activeIconName ? RAIL_ICONS[activeIconName] : null

  return (
    <>
      <div
        data-tour="solution-rail"
        style={{ width: '44px', display: 'flex', flexDirection: 'column', alignItems: 'center',
                 height: '100%', padding: '8px 0', backgroundColor: 'var(--sage-rail-bg)',
                 borderRight: '1px solid #e5e7eb', flexShrink: 0 }}
      >
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px',
                      overflowY: 'auto', width: '100%', paddingTop: '4px' }}>
          {/* Active solution — icon-only when ActiveIcon renders; labelled for that case */}
          {activeSolution && (
            <Tooltip text={activeSolution.name}>
              <button
                aria-label={`Active solution: ${activeSolution.name}`}
                style={{
                  width: '28px', height: '28px', display: 'flex', alignItems: 'center',
                  justifyContent: 'center', fontSize: '10px', fontWeight: 700, flexShrink: 0,
                  backgroundColor: activeAccent, color: '#fff', cursor: 'default', border: 'none',
                }}
              >
                {ActiveIcon ? <ActiveIcon size={14} color="#fff" /> : initials(activeId)}
              </button>
            </Tooltip>
          )}
          {/* Pinned solutions — render initials() as visible text, so not icon-only */}
          {pinnedToShow.map(id => {
            const sol = solutions.find(s => s.id === id)
            if (!sol) return null
            const solAccent = (sol as any).theme?.accent ?? '#e5e7eb'
            return (
              <Tooltip key={id} text={sol.name}>
                <button
                  onClick={() => switchMutation.mutate(id)}
                  style={{
                    width: '28px', height: '28px', display: 'flex', alignItems: 'center',
                    justifyContent: 'center', fontSize: '10px', fontWeight: 700, flexShrink: 0,
                    backgroundColor: solAccent, color: '#fff', cursor: 'pointer', border: 'none',
                    opacity: 0.75,
                  }}
                >
                  {initials(id)}
                </button>
              </Tooltip>
            )
          })}
        </div>
        {/* Grid/picker button — icon-only */}
        <Tooltip text="Browse all solutions">
          <button
            onClick={() => setPickerOpen(true)}
            aria-label="Browse all solutions"
            style={{ width: '28px', height: '28px', color: '#334155', background: 'none',
                     border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center',
                     justifyContent: 'center', marginBottom: '4px' }}
          >
            <LayoutGrid size={14} />
          </button>
        </Tooltip>
        {/* + button — renders visible "+" text, but is a glyph-only control;
            an action label aids screen readers without conflicting with the symbol */}
        <Tooltip text="Create a new solution">
          <button
            onClick={onOpenWizard}
            aria-label="Create a new solution"
            style={{ width: '28px', height: '28px', color: '#334155', fontSize: '18px',
                     lineHeight: 1, marginBottom: '8px', background: 'none', border: 'none', cursor: 'pointer' }}
          >
            +
          </button>
        </Tooltip>
        {/* Org graph — icon-only */}
        <Tooltip text="View organization graph">
          <button
            onClick={() => navigate('/org-graph')}
            aria-label="View organization graph"
            style={{ width: '32px', height: '32px', color: '#334155', background: 'none',
                     border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          >
            <Building2 size={16} />
          </button>
        </Tooltip>
      </div>
      {pickerOpen && (
        <SolutionPicker
          solutions={solutions}
          activeId={activeId}
          pinnedIds={pinnedIds}
          onPin={handlePin}
          onSwitch={(id) => { switchMutation.mutate(id); setPickerOpen(false) }}
          onClose={() => setPickerOpen(false)}
        />
      )}
    </>
  )
}

// ---------------------------------------------------------------------------
// SolutionSwitcher — dropdown at top of main sidebar
// ---------------------------------------------------------------------------
interface SwitcherProps {
  projectName: string
  solutions: Array<{ id: string; name: string }>
  activeId: string
  onSwitch: (id: string) => void
  showRestartTour: boolean
  onRestartTour: () => void
}

function SolutionSwitcher({ projectName, solutions, activeId, onSwitch, showRestartTour, onRestartTour }: SwitcherProps) {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ position: 'relative', borderBottom: '1px solid #e5e7eb' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{ display: 'flex', width: '100%', alignItems: 'center', gap: '6px',
                 padding: '10px 12px', background: 'none', border: 'none', cursor: 'pointer' }}
      >
        <span style={{ flex: 1, fontSize: '13px', fontWeight: 600, color: '#374151',
                       overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', textAlign: 'left' }}>
          {projectName}
        </span>
        <ChevronsUpDown size={14} style={{ color: '#475569', flexShrink: 0 }} />
      </button>
      {open && (
        <>
          <div style={{ position: 'fixed', inset: 0, zIndex: 10 }} onClick={() => setOpen(false)} />
          <div style={{ position: 'absolute', left: 0, top: '100%', width: '100%', zIndex: 20,
                        backgroundColor: '#ffffff', border: '1px solid #e5e7eb',
                        boxShadow: '0 4px 16px rgba(0,0,0,0.1)' }}>
            {solutions.map(sol => (
              <button
                key={sol.id}
                onClick={() => { onSwitch(sol.id); setOpen(false) }}
                disabled={sol.id === activeId}
                style={{ display: 'block', width: '100%', textAlign: 'left', padding: '8px 12px',
                         fontSize: '12px', color: sol.id === activeId ? '#f1f5f9' : '#64748b',
                         backgroundColor: sol.id === activeId ? '#fff7ed' : 'transparent',
                         border: 'none', cursor: sol.id === activeId ? 'default' : 'pointer' }}
              >
                {sol.name}
              </button>
            ))}
            {showRestartTour && (
              <>
                <div style={{ borderTop: '1px solid #e5e7eb', margin: '4px 0' }} />
                <button
                  onClick={() => { onRestartTour(); setOpen(false) }}
                  style={{ display: 'block', width: '100%', textAlign: 'left', padding: '8px 12px',
                           fontSize: '12px', color: '#64748b', background: 'none',
                           border: 'none', cursor: 'pointer' }}
                >
                  Restart tour
                </button>
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Sidebar export
// ---------------------------------------------------------------------------
export default function Sidebar() {
  const [openArea, setOpenArea] = useState<string>('work')
  const { pathname } = useLocation()
  const queryClient = useQueryClient()
  const { openWizard, wizardOpen, closeWizard, startTour, isToured, restartTour } = useTourContext()

  const { data: healthData } = useQuery({ queryKey: ['health'], queryFn: fetchHealth, refetchInterval: 30_000 })
  const activeId = (healthData as any)?.project?.project ?? ''

  const { data: projectsData } = useQuery({ queryKey: ['projects'], queryFn: fetchProjects, staleTime: 60_000 })
  const switchMutation = useMutation({
    mutationFn: (id: string) => switchProject(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['health'] }),
  })

  const { data: projectData } = useProjectConfig()
  const activeModules: string[] = projectData?.active_modules ?? []
  const projectName = projectData?.name ?? 'SAGE'
  const isVisible = (moduleId: string) =>
    activeModules.length === 0 || activeModules.includes(moduleId)

  // Auto-expand the area containing the active route
  useEffect(() => {
    for (const area of NAV_AREAS) {
      if (area.items.some(item => {
        if (item.to === '/') return pathname === '/'
        return pathname === item.to || pathname.startsWith(item.to + '/')
      })) {
        setOpenArea(area.id)
        return
      }
    }
  }, [pathname])

  const solutions = projectsData?.projects ?? []

  return (
    <aside style={{ display: 'flex', height: '100%', flexShrink: 0 }}>
      <SolutionRail onOpenWizard={openWizard} />
      <div style={{ width: '220px', display: 'flex', flexDirection: 'column', height: '100%',
                    backgroundColor: 'var(--sage-sidebar-bg)', borderRight: '1px solid #e5e7eb' }}>
        <SolutionSwitcher
          projectName={projectName}
          solutions={solutions}
          activeId={activeId}
          onSwitch={(id) => switchMutation.mutate(id)}
          showRestartTour={isToured(activeId)}
          onRestartTour={() => restartTour(activeId)}
        />
        <div data-tour="stats-strip">
          <StatsStrip />
        </div>
        <nav style={{ flex: 1, overflowY: 'auto', padding: '4px 0' }}>
          {NAV_AREAS.map(area => {
            const visibleItems = area.items.filter(({ moduleId }) => isVisible(moduleId))
            if (visibleItems.length === 0) return null
            const isOpen = openArea === area.id
            return (
              <div key={area.id}>
                <Tooltip text={area.tooltip}>
                  <button
                    data-tour={`area-${area.id}`}
                    onClick={() => setOpenArea(isOpen ? '' : area.id)}
                    style={{ display: 'flex', alignItems: 'center', gap: '6px', width: '100%',
                             padding: '6px 12px', background: 'none', border: 'none', cursor: 'pointer' }}
                  >
                    <area.icon size={13} style={{ color: area.accent, flexShrink: 0 }} />
                    <span style={{ flex: 1, fontSize: '11px', fontWeight: 600, color: '#94a3b8',
                                   textAlign: 'left', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                      {area.label}
                    </span>
                    {!isOpen && (
                      <span style={{ fontSize: '10px', color: '#334155' }}>{visibleItems.length}</span>
                    )}
                    <ChevronDown
                      size={12}
                      style={{ color: '#334155', flexShrink: 0,
                               transform: isOpen ? 'rotate(0deg)' : 'rotate(-90deg)', transition: 'transform 0.15s' }}
                    />
                  </button>
                </Tooltip>
                {isOpen && visibleItems.map(item => (
                  <Tooltip key={item.to + item.label} text={item.tooltip}>
                    <NavLink
                      to={item.to}
                      end={item.to === '/'}
                      data-tour={item.label === 'Approvals' ? 'nav-approvals' : item.label === 'Task Queue' ? 'nav-queue' : undefined}
                      style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%',
                               padding: '6px 12px 6px 28px', fontSize: '12px', textDecoration: 'none',
                               borderLeft: `2px solid ${area.accent}20` }}
                      className={({ isActive }) => isActive ? 'sage-nav-item-active' : ''}
                    >
                      {({ isActive }) => (
                        <>
                          <item.icon size={13} />
                          <span style={{ color: isActive ? '#93c5fd' : '#64748b' }}>{item.label}</span>
                        </>
                      )}
                    </NavLink>
                  </Tooltip>
                ))}
              </div>
            )
          })}
        </nav>
        <div style={{ padding: '8px 12px', borderTop: '1px solid #e5e7eb', color: '#334155', fontSize: '11px' }}>
          SAGE {SAGE_VERSION} by Shetty
        </div>
      </div>
      {wizardOpen && (
        <OnboardingWizard
          onClose={closeWizard}
          onTourStart={(solutionId) => { closeWizard(); startTour(solutionId) }}
        />
      )}
    </aside>
  )
}
```

=== FILE: web/src/components/proposals/ProposalCard.tsx ===
```tsx
import { useState } from 'react'
import { CheckCircle, XCircle, AlertTriangle, Clock, ChevronDown, ChevronUp } from 'lucide-react'
import RiskBadge, { RISK_CONFIG } from '../ui/RiskBadge'
import { formatRelativeTime } from '../../lib/date'

interface Proposal {
  trace_id: string
  action_type: string
  risk_class: 'INFORMATIONAL' | 'EPHEMERAL' | 'STATEFUL' | 'EXTERNAL' | 'DESTRUCTIVE'
  reversible: boolean
  proposed_by: string
  description: string
  payload: Record<string, unknown>
  status: string
  created_at: string
}

interface ProposalCardProps {
  proposal: Proposal
  onApprove: (traceId: string, approvedBy?: string, note?: string) => Promise<void>
  onReject: (traceId: string, feedback: string) => Promise<void>
}

export default function ProposalCard({ proposal, onApprove, onReject }: ProposalCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [rejecting, setRejecting] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [note, setNote] = useState('')
  const [loading, setLoading] = useState(false)

  const diff = (proposal.payload as any)?.diff as string | undefined
  const isDestructive = proposal.risk_class === 'DESTRUCTIVE'

  const handleApprove = async () => {
    setLoading(true)
    try {
      await onApprove(proposal.trace_id, 'human', note)
    } finally {
      setLoading(false)
    }
  }

  const handleReject = async () => {
    if (!feedback.trim()) return
    setLoading(true)
    try {
      await onReject(proposal.trace_id, feedback)
    } finally {
      setLoading(false)
      setRejecting(false)
    }
  }

  const relativeTime = formatRelativeTime(proposal.created_at)

  const riskConfig = RISK_CONFIG[proposal.risk_class] || RISK_CONFIG.STATEFUL

  return (
    <div
      className="rounded-lg border p-4"
      style={{
        backgroundColor: riskConfig.bgVar,
        color: riskConfig.colorVar,
        borderColor: riskConfig.borderVar,
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <RiskBadge risk={proposal.risk_class} />
            {!proposal.reversible && (
              <span className="text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded font-medium">
                Irreversible
              </span>
            )}
          </div>
          <div className="text-sm font-medium text-gray-800 leading-snug">
            {proposal.description}
          </div>
          <div className="text-xs text-gray-500 mt-1 flex items-center gap-2">
            <Clock size={11} />
            <span>Proposed by {proposal.proposed_by} · {relativeTime}</span>
          </div>
        </div>
        {diff && (
          <button
            onClick={() => setExpanded(!expanded)}
            aria-expanded={expanded}
            className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1 shrink-0"
          >
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            diff
          </button>
        )}
      </div>

      {expanded && diff && (
        <pre className="mt-3 text-xs bg-gray-900 text-gray-100 rounded p-3 overflow-x-auto max-h-64 overflow-y-auto">
          {diff}
        </pre>
      )}

      {isDestructive && (
        <div className="mt-3 flex items-start gap-2 bg-red-100 rounded p-2">
          <AlertTriangle size={14} className="text-red-600 mt-0.5 shrink-0" />
          <p className="text-xs text-red-700">
            This action is <strong>irreversible</strong>. Provide a reason note before approving.
          </p>
        </div>
      )}

      {isDestructive && (
        <input
          type="text"
          placeholder="Reason for deletion (required)"
          value={note}
          onChange={e => setNote(e.target.value)}
          className="mt-2 w-full text-xs border border-red-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-red-400"
        />
      )}

      {rejecting && (
        <div className="mt-3 space-y-2">
          <textarea
            className="w-full text-xs border rounded px-2 py-1.5 resize-none focus:outline-none focus:ring-1 focus:ring-gray-400"
            placeholder="Reason for rejection..."
            rows={2}
            value={feedback}
            onChange={e => setFeedback(e.target.value)}
          />
          <div className="flex gap-2">
            <button
              onClick={handleReject}
              disabled={!feedback.trim() || loading}
              className="text-xs px-3 py-1.5 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
            >
              Confirm Reject
            </button>
            <button
              onClick={() => setRejecting(false)}
              className="text-xs px-3 py-1.5 text-gray-600 hover:text-gray-800"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {!rejecting && (
        <div className="mt-3 flex gap-2">
          <button
            onClick={handleApprove}
            disabled={loading || (isDestructive && !note.trim())}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-orange-600 text-white rounded hover:bg-orange-700 disabled:opacity-50"
          >
            <CheckCircle size={13} />
            Approve
          </button>
          <button
            onClick={() => setRejecting(true)}
            disabled={loading}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-white border border-gray-300 text-gray-700 rounded hover:bg-gray-50 disabled:opacity-50"
          >
            <XCircle size={13} />
            Reject
          </button>
        </div>
      )}
    </div>
  )
}
```

---

## Iteration History

**Iter 1** — score 7.0 pass=False  
Feedback: Core task is met: every genuinely icon-only button is labeled (Header chat button → 'Open SAGE chat'; Sidebar LayoutGrid → 'Browse all solutions', Building2 → 'View organization graph'; SolutionRail a  

**Iter 2** — score 9.0 pass=True  
Feedback:   

