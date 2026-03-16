import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Search, GitMerge, ClipboardList,
  Activity, Shield, Lightbulb, Cpu, Settings, FileCode2, Bot, Terminal, Wand2, Plug, ListOrdered, ShieldCheck,
  DollarSign,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { fetchFeatureRequests, fetchQueueTasks } from '../../api/client'
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

const links = [
  { to: '/',             icon: LayoutDashboard, label: 'Dashboard',     moduleId: 'dashboard' },
  { to: '/agents',       icon: Bot,             label: 'Agents',        moduleId: 'agents' },
  { to: '/analyst',      icon: Search,          label: 'Analyst',       moduleId: 'analyst' },
  { to: '/developer',    icon: GitMerge,        label: 'Developer',     moduleId: 'developer' },
  { to: '/audit',        icon: ClipboardList,   label: 'Audit Log',     moduleId: 'audit' },
  { to: '/monitor',      icon: Activity,        label: 'Monitor',       moduleId: 'monitor' },
  { to: '/queue',        icon: ListOrdered,     label: 'Task Queue',    moduleId: 'queue',        queueBadge: true },
  { to: '/improvements', icon: Lightbulb,       label: 'Improvements',  moduleId: 'improvements', badge: true },
  { to: '/llm',          icon: Cpu,             label: 'LLM',           moduleId: 'llm' },
  { to: '/costs',        icon: DollarSign,      label: 'Costs',          moduleId: 'costs' },
  { to: '/settings',     icon: Settings,        label: 'Settings',      moduleId: 'settings' },
  { to: '/yaml-editor',  icon: FileCode2,       label: 'Config Editor', moduleId: 'yaml-editor' },
  { to: '/live-console', icon: Terminal,        label: 'Live Console',  moduleId: 'live-console' },
  { to: '/onboarding',    icon: Wand2,  label: 'New Solution',  moduleId: 'onboarding' },
  { to: '/integrations',   icon: Plug,        label: 'Integrations',   moduleId: 'integrations' },
  { to: '/access-control', icon: ShieldCheck, label: 'Access Control', moduleId: 'access-control' },
]

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

  // Project-aware module visibility
  const { data: projectData } = useProjectConfig()
  const activeModules: string[] = projectData?.active_modules ?? []
  const projectName = projectData?.name ?? ''

  // If active_modules is empty (fallback / API unreachable), show everything
  const isVisible = (moduleId: string) =>
    activeModules.length === 0 || activeModules.includes(moduleId)

  return (
    <aside
      className="w-56 flex flex-col h-full shrink-0"
      style={{ backgroundColor: 'var(--sage-sidebar-bg)', color: 'var(--sage-sidebar-text)' }}
    >
      {/* Logo */}
      <div
        className="flex items-center gap-2 px-4 py-5 border-b"
        style={{ borderColor: 'rgba(255,255,255,0.1)' }}
        title="Smart Agentic-Guided Empowerment"
      >
        <Shield size={22} style={{ color: 'var(--sage-sidebar-accent)' }} />
        <div>
          <span className="text-lg font-bold tracking-tight" style={{ color: 'var(--sage-sidebar-active-text)' }}>
            SAGE<span style={{ color: 'var(--sage-sidebar-accent)' }}>[ai]</span>
          </span>
          <div className="text-[9px] leading-tight -mt-0.5 tracking-wide uppercase"
               style={{ color: 'var(--sage-sidebar-text)' }}>
            Smart Agentic-Guided Empowerment
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 overflow-y-auto">
        {links.filter(({ moduleId }) => isVisible(moduleId)).map(({ to, icon: Icon, label, badge, queueBadge, moduleId }) => (
          <NavLink
            key={moduleId}
            to={to}
            end={to === '/'}
            className="sage-nav-item flex items-center gap-3 px-4 py-3 text-sm"
            style={({ isActive }) =>
              isActive
                ? {
                    backgroundColor: 'var(--sage-sidebar-active-bg)',
                    color: 'var(--sage-sidebar-active-text)',
                    fontWeight: 500,
                  }
                : { color: 'var(--sage-sidebar-text)' }
            }
          >
            <Icon size={18} />
            <span className="flex-1">{label}</span>
            {badge && pendingCount > 0 && (
              <span
                className="text-xs font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center"
                style={{ backgroundColor: 'var(--sage-sidebar-accent)', color: 'var(--sage-sidebar-bg)' }}
              >
                {pendingCount}
              </span>
            )}
            {queueBadge && activeQueueCount > 0 && (
              <span
                className="text-xs font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center"
                style={{ backgroundColor: 'var(--sage-sidebar-accent)', color: 'var(--sage-sidebar-bg)' }}
              >
                {activeQueueCount}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div
        className="px-4 py-3 border-t text-xs space-y-0.5"
        style={{ borderColor: 'rgba(255,255,255,0.1)', color: 'var(--sage-sidebar-text)' }}
      >
        {projectName && (
          <div className="font-medium truncate" style={{ color: 'var(--sage-sidebar-active-text)', opacity: 0.85 }}>
            {projectName}
          </div>
        )}
        <div>SAGE Framework {SAGE_VERSION}</div>
      </div>
    </aside>
  )
}
