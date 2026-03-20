import { useState, useEffect } from 'react'
import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, Search, GitMerge, ClipboardList,
  Activity, Lightbulb, Cpu, Settings, FileCode2, Bot,
  Terminal, Wand2, Plug, ListOrdered, ShieldCheck, DollarSign,
  GitBranch, Target, Inbox, Network, Building2,
  CheckSquare, Zap, Database, BookOpen, Shield,
  ChevronDown, ChevronsUpDown, type LucideIcon,
} from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchProjects, fetchHealth, switchProject } from '../../api/client'
import { useProjectConfig } from '../../hooks/useProjectConfig'
import Tooltip from './Tooltip'
import StatsStrip from './StatsStrip'
import { useTourContext } from '../../context/TourContext'
import OnboardingWizard from '../onboarding/OnboardingWizard'

// ---------------------------------------------------------------------------
const SAGE_VERSION = 'v2.1'

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
      { to: '/approvals',    icon: Inbox,           label: 'Approvals',    moduleId: 'approvals',    tooltip: 'Agent proposals waiting for your review before execution' },
      { to: '/queue',        icon: ListOrdered,     label: 'Task Queue',   moduleId: 'queue',        tooltip: 'Tasks currently queued or running across all agents' },
      { to: '/',             icon: LayoutDashboard, label: 'Dashboard',    moduleId: 'dashboard',    tooltip: 'System health, recent activity, and integration status' },
      { to: '/live-console', icon: Terminal,        label: 'Live Console', moduleId: 'live-console', tooltip: 'Real-time backend log stream' },
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
    ],
  },
  {
    id: 'knowledge', label: 'Knowledge', icon: Database, accent: '#10b981', tooltip: 'Vector knowledge base, shared channels, and compliance records',
    items: [
      { to: '/knowledge', icon: BookOpen,      label: 'Vector Store', moduleId: 'knowledge', tooltip: "Search and manage entries in this solution's knowledge base" },
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
      { to: '/settings',       icon: Settings,    label: 'Settings',       moduleId: 'settings',       tooltip: 'Framework-wide settings and display preferences' },
      { to: '/guide',          icon: BookOpen,    label: 'User Guide',     moduleId: 'guide',          tooltip: 'Animated GIF walkthroughs for key SAGE features' },
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

  return (
    <div
      data-tour="solution-rail"
      style={{ width: '44px', display: 'flex', flexDirection: 'column', alignItems: 'center',
               height: '100%', padding: '8px 0', backgroundColor: '#020617',
               borderRight: '1px solid #0f172a', flexShrink: 0 }}
    >
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px',
                    overflowY: 'auto', width: '100%', paddingTop: '4px' }}>
        {solutions.map(sol => {
          const isActive = sol.id === activeId
          const RailIcon = isActive && activeIconName ? RAIL_ICONS[activeIconName] : null
          return (
            <Tooltip key={sol.id} text={sol.name}>
              <button
                onClick={() => !isActive && switchMutation.mutate(sol.id)}
                style={{
                  width: '28px', height: '28px', display: 'flex', alignItems: 'center',
                  justifyContent: 'center', fontSize: '10px', fontWeight: 700, flexShrink: 0,
                  backgroundColor: isActive ? activeAccent : '#1e293b',
                  color: isActive ? '#fff' : '#64748b',
                  cursor: isActive ? 'default' : 'pointer',
                  border: 'none',
                }}
              >
                {RailIcon ? <RailIcon size={14} color="#fff" /> : initials(sol.id)}
              </button>
            </Tooltip>
          )
        })}
      </div>
      <Tooltip text="Create a new solution">
        <button
          onClick={onOpenWizard}
          style={{ width: '28px', height: '28px', color: '#334155', fontSize: '18px',
                   lineHeight: 1, marginBottom: '8px', background: 'none', border: 'none', cursor: 'pointer' }}
        >
          +
        </button>
      </Tooltip>
      <Tooltip text="View organization graph">
        <button
          onClick={() => navigate('/org-graph')}
          style={{ width: '32px', height: '32px', color: '#334155', background: 'none',
                   border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        >
          <Building2 size={16} />
        </button>
      </Tooltip>
    </div>
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
    <div style={{ position: 'relative', borderBottom: '1px solid #1e293b' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{ display: 'flex', width: '100%', alignItems: 'center', gap: '6px',
                 padding: '10px 12px', background: 'none', border: 'none', cursor: 'pointer' }}
      >
        <span style={{ flex: 1, fontSize: '13px', fontWeight: 600, color: '#f1f5f9',
                       overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', textAlign: 'left' }}>
          {projectName}
        </span>
        <ChevronsUpDown size={14} style={{ color: '#475569', flexShrink: 0 }} />
      </button>
      {open && (
        <>
          <div style={{ position: 'fixed', inset: 0, zIndex: 10 }} onClick={() => setOpen(false)} />
          <div style={{ position: 'absolute', left: 0, top: '100%', width: '100%', zIndex: 20,
                        backgroundColor: '#0f172a', border: '1px solid #1e293b',
                        boxShadow: '0 8px 32px rgba(0,0,0,0.5)' }}>
            {solutions.map(sol => (
              <button
                key={sol.id}
                onClick={() => { onSwitch(sol.id); setOpen(false) }}
                disabled={sol.id === activeId}
                style={{ display: 'block', width: '100%', textAlign: 'left', padding: '8px 12px',
                         fontSize: '12px', color: sol.id === activeId ? '#f1f5f9' : '#64748b',
                         backgroundColor: sol.id === activeId ? '#172033' : 'transparent',
                         border: 'none', cursor: sol.id === activeId ? 'default' : 'pointer' }}
              >
                {sol.name}
              </button>
            ))}
            {showRestartTour && (
              <>
                <div style={{ borderTop: '1px solid #1e293b', margin: '4px 0' }} />
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
                    backgroundColor: 'var(--sage-sidebar-bg)', borderRight: '1px solid #1e293b' }}>
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
        <div style={{ padding: '8px 12px', borderTop: '1px solid #1e293b', color: '#334155', fontSize: '11px' }}>
          SAGE Framework {SAGE_VERSION}
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
