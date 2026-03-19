import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Search, GitMerge, ClipboardList,
  Activity, Lightbulb, Cpu, Settings, FileCode2, Bot,
  Terminal, Wand2, Plug, ListOrdered, ShieldCheck, DollarSign,
  Shield, GitBranch, CircleDot, Radio, Target, Users, Inbox, Network, type LucideIcon,
} from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchFeatureRequests, fetchQueueTasks, fetchProjects, switchProject, fetchHealth, fetchPendingProposals } from '../../api/client'
import { useProjectConfig } from '../../hooks/useProjectConfig'

// ---------------------------------------------------------------------------
// Standard SAGE sidebar links — solution-agnostic.
// Visibility is controlled by active_modules in your solution's project.yaml.
//
// To add solution-specific sidebar links:
//   1. Add the moduleId to active_modules in project.yaml
//   2. Add an entry to this links array in your solution fork/branch
//   3. Register the route in App.tsx
// ---------------------------------------------------------------------------
const SAGE_VERSION = 'v2.1'

interface NavItem {
  to: string
  icon: LucideIcon
  label: string
  moduleId: string
  badge?: boolean
  queueBadge?: boolean
  approvalsBadge?: boolean
}

interface NavGroup {
  label: string
  items: NavItem[]
}

// Nav groups: Paperclip-style grouping
const NAV_GROUPS: NavGroup[] = [
  {
    label: 'WORK',
    items: [
      { to: '/approvals',    icon: Inbox,           label: 'Approvals',     moduleId: 'approvals',    approvalsBadge: true },
      { to: '/',             icon: LayoutDashboard, label: 'Dashboard',     moduleId: 'dashboard' },
      { to: '/queue',        icon: ListOrdered,     label: 'Task Queue',    moduleId: 'queue',        queueBadge: true },
      { to: '/issues',       icon: CircleDot,       label: 'Issues',        moduleId: 'improvements' },
      { to: '/activity',     icon: Radio,           label: 'Activity',      moduleId: 'audit' },
      { to: '/live-console', icon: Terminal,        label: 'Live Console',  moduleId: 'live-console' },
    ],
  },
  {
    label: 'AGENTS',
    items: [
      { to: '/agents',    icon: Bot,      label: 'Agents',      moduleId: 'agents' },
      { to: '/org',       icon: Users,    label: 'Org Chart',   moduleId: 'org-chart' },
      { to: '/org-graph', icon: Network,  label: 'Organization',moduleId: 'org' },
      { to: '/analyst',   icon: Search,   label: 'Analyst',   moduleId: 'analyst' },
      { to: '/developer', icon: GitMerge, label: 'Developer', moduleId: 'developer' },
      { to: '/monitor',   icon: Activity, label: 'Monitor',   moduleId: 'monitor' },
    ],
  },
  {
    label: 'INTELLIGENCE',
    items: [
      { to: '/improvements', icon: Lightbulb,     label: 'Improvements',  moduleId: 'improvements', badge: true },
      { to: '/goals',        icon: Target,        label: 'Goals',         moduleId: 'improvements' },
      { to: '/workflows',    icon: GitBranch,     label: 'Workflows',     moduleId: 'workflows' },
      { to: '/yaml-editor',  icon: FileCode2,     label: 'Config Editor', moduleId: 'yaml-editor' },
      { to: '/audit',        icon: ClipboardList, label: 'Audit Log',     moduleId: 'audit' },
    ],
  },
  {
    label: 'SETTINGS',
    items: [
      { to: '/llm',          icon: Cpu,        label: 'LLM',           moduleId: 'llm' },
      { to: '/integrations', icon: Plug,       label: 'Integrations',  moduleId: 'integrations' },
      { to: '/onboarding',   icon: Wand2,      label: 'New Solution',  moduleId: 'onboarding' },
      { to: '/access-control', icon: ShieldCheck, label: 'Access Control', moduleId: 'access-control' },
      { to: '/costs',        icon: DollarSign, label: 'Costs',         moduleId: 'costs' },
      { to: '/settings',     icon: Settings,   label: 'Settings',      moduleId: 'settings' },
    ],
  },
]

// Starter solutions shown in the CompanyRail when no projects API data
const FALLBACK_SOLUTIONS = [
  { id: 'starter',        initial: 'S', title: 'Starter' },
  { id: 'medtech_team',   initial: 'M', title: 'MedTech' },
  { id: 'four_in_a_line', initial: '4', title: 'Four In A Line' },
]

// ---------------------------------------------------------------------------
// CompanyRail — far-left w-12 column
// ---------------------------------------------------------------------------
function CompanyRail() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: healthData } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  })
  const activeId = (healthData as any)?.project?.project ?? ''

  const { data: projectsData } = useQuery({
    queryKey: ['projects'],
    queryFn: fetchProjects,
    staleTime: 60_000,
  })

  const switchMutation = useMutation({
    mutationFn: (id: string) => switchProject(id),
    onSuccess: () => queryClient.invalidateQueries(),
  })

  const solutions = projectsData?.projects ?? []
  const railSolutions = solutions.length > 0
    ? solutions.map(s => ({ id: s.id, initial: s.name.charAt(0).toUpperCase(), title: s.name }))
    : FALLBACK_SOLUTIONS

  return (
    <div
      className="flex flex-col items-center h-full shrink-0 py-2"
      style={{ width: '48px', backgroundColor: 'var(--sage-rail-bg)', borderRight: '1px solid #27272a' }}
    >
      {/* SAGE icon */}
      <button
        onClick={() => navigate('/')}
        className="flex items-center justify-center mb-3"
        style={{ width: '32px', height: '32px', color: '#71717a' }}
        title="SAGE Framework"
      >
        <Shield size={18} />
      </button>

      {/* Divider */}
      <div style={{ width: '24px', height: '1px', backgroundColor: '#27272a', marginBottom: '8px' }} />

      {/* Solution avatars */}
      <div className="flex flex-col items-center gap-1.5 flex-1 overflow-y-auto" style={{ overflowX: 'hidden' }}>
        {railSolutions.map(sol => {
          const isActive = sol.id === activeId
          return (
            <button
              key={sol.id}
              onClick={() => !isActive && switchMutation.mutate(sol.id)}
              title={sol.title}
              className="flex items-center justify-center text-xs font-bold transition-colors"
              style={{
                width: '28px',
                height: '28px',
                flexShrink: 0,
                backgroundColor: isActive ? '#f4f4f5' : '#27272a',
                color: isActive ? '#09090b' : '#71717a',
                border: isActive ? '1px solid #f4f4f5' : '1px solid #3f3f46',
                cursor: isActive ? 'default' : 'pointer',
              }}
            >
              {sol.initial}
            </button>
          )
        })}
      </div>

      {/* Divider */}
      <div style={{ width: '24px', height: '1px', backgroundColor: '#27272a', margin: '8px 0' }} />

      {/* Settings icon at bottom */}
      <button
        onClick={() => navigate('/settings')}
        className="flex items-center justify-center"
        style={{ width: '32px', height: '32px', color: '#52525b' }}
        title="Settings"
      >
        <Settings size={14} />
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Sidebar
// ---------------------------------------------------------------------------
export default function Sidebar() {
  // Pending improvement-request badge count
  const { data: featureData } = useQuery({
    queryKey: ['feature-requests', '', 'pending'],
    queryFn: () => fetchFeatureRequests(undefined, 'pending'),
    refetchInterval: 60_000,
  })
  const pendingCount = featureData?.count ?? 0

  // Active task queue badge count (pending + in_progress)
  const { data: queueData } = useQuery({
    queryKey: ['queue-tasks-sidebar'],
    queryFn: () => fetchQueueTasks(),
    refetchInterval: 15_000,
  })
  const activeQueueCount = (queueData ?? []).filter(
    t => t.status === 'pending' || t.status === 'in_progress'
  ).length

  // Pending approvals badge count
  const { data: approvalsData } = useQuery({
    queryKey: ['proposals-pending'],
    queryFn: fetchPendingProposals,
    refetchInterval: 10_000,
  })
  const pendingApprovalsCount = approvalsData?.count ?? 0

  // Project-aware module visibility
  const { data: projectData } = useProjectConfig()
  const activeModules: string[] = projectData?.active_modules ?? []
  const projectName = projectData?.name ?? ''

  // If active_modules is empty (fallback / API unreachable), show everything
  const isVisible = (moduleId: string) =>
    activeModules.length === 0 || activeModules.includes(moduleId)

  return (
    <aside className="flex h-full shrink-0">
      {/* CompanyRail */}
      <CompanyRail />

      {/* Main nav sidebar */}
      <div
        className="flex flex-col h-full"
        style={{ width: '200px', backgroundColor: 'var(--sage-sidebar-bg)', borderRight: '1px solid #27272a' }}
      >
        {/* Logo / brand */}
        <div
          className="flex flex-col px-3 py-3"
          style={{ borderBottom: '1px solid #27272a' }}
          title={projectName || 'Smart Agentic-Guided Empowerment'}
        >
          {projectName ? (
            <>
              <span className="text-sm font-bold tracking-tight leading-tight truncate" style={{ color: '#f4f4f5' }}>
                {projectName}
              </span>
              <span className="text-[9px] mt-0.5" style={{ color: '#3f3f46' }}>
                powered by SAGE[ai]
              </span>
            </>
          ) : (
            <span className="text-sm font-bold tracking-tight" style={{ color: '#f4f4f5' }}>
              SAGE<span style={{ color: '#71717a' }}>[ai]</span>
            </span>
          )}
        </div>

        {/* Navigation groups */}
        <nav className="flex-1 overflow-y-auto py-2">
          {NAV_GROUPS.map(group => {
            const visibleItems = group.items.filter(({ moduleId }) => isVisible(moduleId))
            if (visibleItems.length === 0) return null
            return (
              <div key={group.label} className="mb-1">
                <div className="sage-nav-group">{group.label}</div>
                {visibleItems.map(({ to, icon: Icon, label, badge, queueBadge, approvalsBadge, moduleId }) => (
                  <NavLink
                    key={moduleId}
                    to={to}
                    end={to === '/'}
                    className={({ isActive }) =>
                      `sage-nav-item flex items-center gap-2.5 px-3 py-2 text-xs${isActive ? ' sage-nav-item-active' : ''}`
                    }
                    style={({ isActive }) =>
                      isActive
                        ? { color: 'var(--sage-sidebar-active-text)' }
                        : { color: 'var(--sage-sidebar-text)' }
                    }
                  >
                    <Icon size={14} />
                    <span className="flex-1">{label}</span>
                    {badge && pendingCount > 0 && (
                      <span
                        className="text-xs font-bold px-1 py-0.5 min-w-[16px] text-center"
                        style={{ backgroundColor: '#3f3f46', color: '#a1a1aa', fontSize: '10px' }}
                      >
                        {pendingCount}
                      </span>
                    )}
                    {queueBadge && activeQueueCount > 0 && (
                      <span
                        className="text-xs font-bold px-1 py-0.5 min-w-[16px] text-center"
                        style={{ backgroundColor: '#3f3f46', color: '#a1a1aa', fontSize: '10px' }}
                      >
                        {activeQueueCount}
                      </span>
                    )}
                    {approvalsBadge && pendingApprovalsCount > 0 && (
                      <span
                        className="text-xs font-bold px-1 py-0.5 min-w-[16px] text-center"
                        style={{ backgroundColor: '#dc2626', color: '#fff', fontSize: '10px' }}
                      >
                        {pendingApprovalsCount}
                      </span>
                    )}
                  </NavLink>
                ))}
              </div>
            )
          })}
        </nav>

        {/* Footer */}
        <div
          className="px-3 py-2.5 text-xs space-y-0.5"
          style={{ borderTop: '1px solid #27272a', color: '#3f3f46' }}
        >
          {projectName && (
            <div className="font-medium truncate" style={{ color: '#52525b' }}>
              {projectName}
            </div>
          )}
          <div>SAGE Framework {SAGE_VERSION}</div>
        </div>
      </div>
    </aside>
  )
}
