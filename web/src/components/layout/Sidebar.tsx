import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Search, GitMerge, ClipboardList,
  Activity, Shield, Lightbulb, Cpu, Settings, FileCode2, Bot, Terminal,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { fetchFeatureRequests } from '../../api/client'
import { useProjectConfig } from '../../hooks/useProjectConfig'

// ---------------------------------------------------------------------------
// Standard SAGE sidebar links — solution-agnostic.
// Visibility is controlled by active_modules in your solution's project.yaml.
//
// To add solution-specific sidebar links:
//   1. Add the moduleId to active_modules in project.yaml
//   2. Add an entry to this links array in your solution fork/branch
//   3. Register the route in App.tsx
//
// These additions belong in your solution, not in the community framework.
// ---------------------------------------------------------------------------
const links = [
  { to: '/',             icon: LayoutDashboard, label: 'Dashboard',     moduleId: 'dashboard' },
  { to: '/agents',       icon: Bot,             label: 'Agents',        moduleId: 'agents' },
  { to: '/analyst',      icon: Search,          label: 'Analyst',       moduleId: 'analyst' },
  { to: '/developer',    icon: GitMerge,        label: 'Developer',     moduleId: 'developer' },
  { to: '/audit',        icon: ClipboardList,   label: 'Audit Log',     moduleId: 'audit' },
  { to: '/monitor',      icon: Activity,        label: 'Monitor',       moduleId: 'monitor' },
  { to: '/improvements', icon: Lightbulb,       label: 'Improvements',  moduleId: 'improvements', badge: true },
  { to: '/llm',          icon: Cpu,             label: 'LLM',           moduleId: 'llm' },
  { to: '/settings',     icon: Settings,        label: 'Settings',      moduleId: 'settings' },
  { to: '/yaml-editor',   icon: FileCode2,  label: 'Config Editor', moduleId: 'yaml-editor' },
  { to: '/live-console',  icon: Terminal,   label: 'Live Console',  moduleId: 'live-console' },
]

export default function Sidebar() {
  // Pending improvement-request badge count
  const { data: featureData } = useQuery({
    queryKey: ['feature-requests', '', 'pending'],
    queryFn: () => fetchFeatureRequests(undefined, 'pending'),
    refetchInterval: 60_000,
  })
  const pendingCount = featureData?.count ?? 0

  // Project-aware module visibility
  const { data: projectData } = useProjectConfig()
  const activeModules: string[] = projectData?.active_modules ?? []
  const projectName = projectData?.name ?? ''

  // If active_modules is empty (fallback / API unreachable), show everything
  const isVisible = (moduleId: string) =>
    activeModules.length === 0 || activeModules.includes(moduleId)

  return (
    <aside className="w-56 bg-gray-900 text-white flex flex-col h-full">
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 py-5 border-b border-gray-700"
           title="Smart Agentic-Guided Empowerment">
        <Shield className="text-green-400" size={22} />
        <div>
          <span className="text-lg font-bold tracking-tight">
            SAGE<span className="text-green-400">[ai]</span>
          </span>
          <div className="text-[9px] text-gray-500 leading-tight -mt-0.5 tracking-wide uppercase">
            Smart Agentic-Guided Empowerment
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4">
        {links.filter(({ moduleId }) => isVisible(moduleId)).map(({ to, icon: Icon, label, badge, moduleId }) => (
          <NavLink
            key={moduleId}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 text-sm transition-colors ${
                isActive
                  ? 'bg-green-700 text-white font-medium'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-white'
              }`
            }
          >
            <Icon size={18} />
            <span className="flex-1">{label}</span>
            {badge && pendingCount > 0 && (
              <span className="bg-amber-500 text-white text-xs font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center">
                {pendingCount}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-gray-700 text-xs text-gray-500 space-y-0.5">
        {projectName && (
          <div className="text-gray-400 font-medium truncate">{projectName}</div>
        )}
        <div>SAGE Framework v2</div>
      </div>
    </aside>
  )
}
