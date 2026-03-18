import { useState } from 'react'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import { useLocation } from 'react-router-dom'
import { Command } from 'lucide-react'
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
  '/workflows':      'Workflows',
  '/issues':         'Issues',
  '/activity':       'Activity',
  '/goals':          'Goals',
  '/org':            'Org Chart',
  '/approvals':      'Approvals',
}

// Badge color comes from project.yaml dashboard.badge_color — no hardcoded solution names here.
const DEFAULT_BADGE_COLOR = 'bg-zinc-800 text-zinc-400'

// Domain badge colors for the solution switcher dropdown
const DOMAIN_BADGE_COLORS: Record<string, string> = {
  'medtech':      'bg-blue-900 text-blue-300',
  'medical':      'bg-blue-900 text-blue-300',
  'firmware':     'bg-orange-900 text-orange-300',
  'embedded':     'bg-orange-900 text-orange-300',
  'ml':           'bg-purple-900 text-purple-300',
  'mobile':       'bg-purple-900 text-purple-300',
  'game-dev':     'bg-yellow-900 text-yellow-300',
  'startup':      'bg-green-900 text-green-300',
  'tracking':     'bg-red-900 text-red-300',
  'analytics':    'bg-indigo-900 text-indigo-300',
  'generic':      'bg-zinc-800 text-zinc-400',
}

interface HeaderProps {
  onOpenPalette?: () => void
}

export default function Header({ onOpenPalette }: HeaderProps) {
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
    <header
      className="h-12 border-b flex items-center px-4 gap-3 shrink-0 relative"
      style={{ backgroundColor: '#18181b', borderColor: '#27272a' }}
    >
      {/* Page title + project info */}
      <div className="flex items-center gap-2 flex-1 min-w-0">
        <h1 className="text-sm font-semibold shrink-0" style={{ color: '#f4f4f5' }}>{title}</h1>
        <span style={{ color: '#3f3f46' }} className="select-none text-xs">·</span>

        {/* Solution switcher button */}
        <button
          onClick={() => setSwitcherOpen(o => !o)}
          className="flex items-center gap-1 text-xs font-medium px-2 py-1 transition-colors"
          style={{ color: '#71717a' }}
          title="Switch solution"
        >
          <span className="truncate max-w-[140px]">{projectName}</span>
          <svg className="w-3 h-3 shrink-0" style={{ color: '#52525b' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {domain && (
          <span
            className="text-xs font-medium px-1.5 py-0.5 shrink-0"
            style={{ backgroundColor: 'var(--sage-badge-bg)', color: 'var(--sage-badge-text)' }}
          >
            {domain}
          </span>
        )}

        {switchMutation.isPending && (
          <span className="text-xs animate-pulse shrink-0" style={{ color: '#71717a' }}>Switching…</span>
        )}
      </div>

      {/* Cmd+K command palette trigger */}
      <button
        onClick={onOpenPalette}
        className="flex items-center gap-1.5 text-xs px-2.5 py-1 transition-colors shrink-0"
        style={{ color: '#52525b', border: '1px solid #3f3f46' }}
        title="Open command palette (Cmd+K)"
      >
        <Command size={11} />
        <span>K</span>
      </button>

      {/* API status */}
      <div className="flex items-center gap-1.5 text-xs shrink-0">
        <span
          className="w-1.5 h-1.5"
          style={{ backgroundColor: online ? '#22c55e' : '#ef4444', display: 'inline-block' }}
        />
        <span className="hidden sm:block" style={{ color: '#52525b' }}>
          {online ? healthData?.llm_provider ?? 'Online' : 'API Unreachable'}
        </span>
      </div>

      {/* Stop SAGE */}
      {!confirmStop ? (
        <button
          onClick={() => setConfirmStop(true)}
          title="Stop SAGE (shuts down backend + frontend)"
          className="shrink-0 flex items-center gap-1 text-xs font-medium px-2 py-1 transition-colors"
          style={{ color: '#52525b', border: '1px solid transparent' }}
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M5.636 5.636a9 9 0 1012.728 0M12 3v9" />
          </svg>
          Stop
        </button>
      ) : (
        <div className="shrink-0 flex items-center gap-1.5">
          <span className="text-xs font-medium" style={{ color: '#ef4444' }}>Stop SAGE?</span>
          <button
            onClick={() => { shutdownSage(); setConfirmStop(false) }}
            className="text-xs px-2 py-1 font-medium transition-colors"
            style={{ backgroundColor: '#ef4444', color: '#fff' }}
          >
            Yes
          </button>
          <button
            onClick={() => setConfirmStop(false)}
            className="text-xs px-2 py-1 transition-colors"
            style={{ color: '#71717a' }}
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
          <div
            className="absolute left-4 top-11 z-20 w-80 overflow-hidden"
            style={{ backgroundColor: '#18181b', border: '1px solid #3f3f46', boxShadow: '0 8px 32px rgba(0,0,0,0.5)' }}
          >
            <div className="px-4 py-2" style={{ backgroundColor: '#09090b', borderBottom: '1px solid #27272a' }}>
              <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: '#52525b' }}>Switch Solution</p>
            </div>
            <div className="max-h-72 overflow-y-auto">
              {solutions.length === 0 && (
                <p className="px-4 py-3 text-sm" style={{ color: '#52525b' }}>No solutions found</p>
              )}
              {solutions.map(sol => {
                const isActive = sol.id === activeId
                const color = DOMAIN_BADGE_COLORS[sol.domain] ?? 'bg-zinc-800 text-zinc-400'
                return (
                  <button
                    key={sol.id}
                    onClick={() => !isActive && switchMutation.mutate(sol.id)}
                    disabled={isActive || switchMutation.isPending}
                    className={`w-full text-left px-4 py-3 transition-colors
                                flex items-start gap-3 ${isActive ? 'cursor-default' : 'cursor-pointer'}`}
                    style={{
                      backgroundColor: isActive ? '#27272a' : 'transparent',
                      borderBottom: '1px solid #27272a',
                    }}
                    onMouseEnter={e => { if (!isActive) (e.currentTarget as HTMLElement).style.backgroundColor = '#27272a' }}
                    onMouseLeave={e => { if (!isActive) (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent' }}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium truncate" style={{ color: '#f4f4f5' }}>{sol.name}</span>
                        {isActive && (
                          <span className="text-xs font-medium shrink-0" style={{ color: '#71717a' }}>active</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className={`text-xs px-1.5 py-0.5 font-medium ${color}`}>
                          {sol.domain}
                        </span>
                        <span className="text-xs truncate" style={{ color: '#52525b' }}>v{sol.version}</span>
                      </div>
                      {sol.description && (
                        <p className="text-xs mt-1 line-clamp-2" style={{ color: '#71717a' }}>{sol.description}</p>
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
