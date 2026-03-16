import { useState } from 'react'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import { useLocation } from 'react-router-dom'
import { fetchHealth, fetchProjects, switchProject } from '../../api/client'
import { useProjectConfig } from '../../hooks/useProjectConfig'

async function shutdownSage() {
  await fetch('/api/shutdown', { method: 'POST' })
}

// Standard page titles for framework routes. Solution-specific page titles
// are provided via ui_labels in project.yaml or added here in solution forks.
const PAGE_TITLES: Record<string, string> = {
  '/':             'Dashboard',
  '/agents':       'AI Agents',
  '/analyst':      'Log Analyst',
  '/developer':    'Developer',
  '/audit':        'Audit Log',
  '/monitor':      'Monitor',
  '/improvements': 'Improvements',
  '/llm':          'LLM Settings',
  '/settings':     'Settings',
  '/yaml-editor':  'Config Editor',
  '/live-console': 'Live Console',
  '/onboarding':   'New Solution',
  '/queue':          'Task Queue',
  '/access-control': 'Access Control',
  '/costs':          'Cost Tracker',
}

// Badge color comes from project.yaml dashboard.badge_color — no hardcoded solution names here.
const DEFAULT_BADGE_COLOR = 'bg-gray-100 text-gray-600'

// Domain badge colors for the solution switcher dropdown
const DOMAIN_BADGE_COLORS: Record<string, string> = {
  'medtech':      'bg-blue-100 text-blue-700',
  'medical':      'bg-blue-100 text-blue-700',
  'firmware':     'bg-orange-100 text-orange-700',
  'embedded':     'bg-orange-100 text-orange-700',
  'ml':           'bg-purple-100 text-purple-700',
  'mobile':       'bg-purple-100 text-purple-700',
  'game-dev':     'bg-yellow-100 text-yellow-700',
  'startup':      'bg-green-100 text-green-700',
  'tracking':     'bg-red-100 text-red-700',
  'analytics':    'bg-indigo-100 text-indigo-700',
  'generic':      'bg-gray-100 text-gray-600',
}

export default function Header() {
  const { pathname } = useLocation()
  const queryClient = useQueryClient()
  const [switcherOpen, setSwitcherOpen] = useState(false)
  const [confirmStop, setConfirmStop] = useState(false)

  const { data: healthData, isError: healthError } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  })

  const { data: projectData } = useProjectConfig()

  const { data: projectsData } = useQuery({
    queryKey: ['projects'],
    queryFn: fetchProjects,
    staleTime: 60_000,
  })

  const switchMutation = useMutation({
    mutationFn: (id: string) => switchProject(id),
    onSuccess: () => {
      // Invalidate all cached data so pages re-fetch with new project context
      queryClient.invalidateQueries()
      setSwitcherOpen(false)
    },
  })

  const online = !healthError && !!healthData
  const activeId = (healthData as any)?.project?.project ?? ''
  // Use solution ui_labels if available, fall back to generic PAGE_TITLES
  const uiLabels = (projectData as any)?.ui_labels ?? {}
  const UI_LABEL_ROUTES: Record<string, string> = {
    '/analyst': uiLabels.analyst_page_title,
    '/developer': uiLabels.developer_page_title,
    '/monitor': uiLabels.monitor_page_title,
  }
  const title = UI_LABEL_ROUTES[pathname] ?? PAGE_TITLES[pathname] ?? 'SAGE[ai]'
  const projectName = projectData?.name ?? 'SAGE Framework'
  const domain = projectData?.domain ?? ''
  const dashboardConfig = (projectData as any)?.dashboard ?? {}
  const badgeColor: string = dashboardConfig.badge_color ?? DEFAULT_BADGE_COLOR

  const solutions = projectsData?.projects ?? []

  return (
    <header className="h-14 bg-white border-b border-gray-200 flex items-center px-6 gap-4 shrink-0 relative">
      {/* Page title + project info */}
      <div className="flex items-center gap-2 flex-1 min-w-0">
        <h1 className="text-lg font-semibold text-gray-800 shrink-0">{title}</h1>
        <span className="text-gray-300 select-none">—</span>

        {/* Solution switcher button */}
        <button
          onClick={() => setSwitcherOpen(o => !o)}
          className="flex items-center gap-1.5 text-sm font-medium text-gray-600 hover:text-gray-900
                     px-2 py-1 rounded-md hover:bg-gray-100 transition-colors"
          title="Switch solution"
        >
          <span className="truncate max-w-[160px]">{projectName}</span>
          <svg className="w-3.5 h-3.5 shrink-0 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {domain && (
          <span
            className="text-xs font-medium px-2 py-0.5 rounded-full shrink-0"
            style={{ backgroundColor: 'var(--sage-badge-bg)', color: 'var(--sage-badge-text)' }}
          >
            {domain}
          </span>
        )}

        {switchMutation.isPending && (
          <span className="text-xs text-blue-500 animate-pulse shrink-0">Switching…</span>
        )}
      </div>

      {/* API status */}
      <div className="flex items-center gap-2 text-sm shrink-0">
        <span className={`w-2 h-2 rounded-full ${online ? 'bg-green-500' : 'bg-red-500'}`} />
        <span className="text-gray-500 hidden sm:block">
          {online ? healthData?.llm_provider ?? 'Online' : 'API Unreachable'}
        </span>
      </div>

      {/* Stop SAGE */}
      {!confirmStop ? (
        <button
          onClick={() => setConfirmStop(true)}
          title="Stop SAGE (shuts down backend + frontend)"
          className="shrink-0 flex items-center gap-1.5 text-xs font-medium text-gray-400
                     hover:text-red-600 hover:bg-red-50 px-2.5 py-1.5 rounded-md transition-colors border border-transparent hover:border-red-200"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M5.636 5.636a9 9 0 1012.728 0M12 3v9" />
          </svg>
          Stop
        </button>
      ) : (
        <div className="shrink-0 flex items-center gap-1.5">
          <span className="text-xs text-red-600 font-medium">Stop SAGE?</span>
          <button
            onClick={() => { shutdownSage(); setConfirmStop(false) }}
            className="text-xs bg-red-600 hover:bg-red-700 text-white px-2.5 py-1 rounded font-medium transition-colors"
          >
            Yes
          </button>
          <button
            onClick={() => setConfirmStop(false)}
            className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded transition-colors"
          >
            Cancel
          </button>
        </div>
      )}

      {/* Solution dropdown */}
      {switcherOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setSwitcherOpen(false)}
          />
          <div className="absolute left-6 top-12 z-20 w-80 bg-white rounded-lg shadow-lg border border-gray-200 overflow-hidden">
            <div className="px-4 py-2 bg-gray-50 border-b border-gray-100">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Switch Solution</p>
            </div>
            <div className="max-h-72 overflow-y-auto">
              {solutions.length === 0 && (
                <p className="px-4 py-3 text-sm text-gray-400">No solutions found</p>
              )}
              {solutions.map(sol => {
                const isActive = sol.id === activeId
                const color = DOMAIN_BADGE_COLORS[sol.domain] ?? 'bg-gray-100 text-gray-600'
                return (
                  <button
                    key={sol.id}
                    onClick={() => !isActive && switchMutation.mutate(sol.id)}
                    disabled={isActive || switchMutation.isPending}
                    className={`w-full text-left px-4 py-3 hover:bg-blue-50 transition-colors
                                flex items-start gap-3 border-b border-gray-50 last:border-0
                                ${isActive ? 'bg-blue-50 cursor-default' : 'cursor-pointer'}`}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-800 truncate">{sol.name}</span>
                        {isActive && (
                          <span className="text-xs text-blue-600 font-medium shrink-0">active</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${color}`}>
                          {sol.domain}
                        </span>
                        <span className="text-xs text-gray-400 truncate">v{sol.version}</span>
                      </div>
                      {sol.description && (
                        <p className="text-xs text-gray-500 mt-1 line-clamp-2">{sol.description}</p>
                      )}
                    </div>
                  </button>
                )
              })}
            </div>
          </div>
        </>
      )}
    </header>
  )
}
