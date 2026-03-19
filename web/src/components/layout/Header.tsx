import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useLocation } from 'react-router-dom'
import { Command } from 'lucide-react'
import { fetchHealth } from '../../api/client'
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

const ROUTE_TO_AREA: Record<string, string> = {
  '/':              'Work',
  '/approvals':     'Work',
  '/queue':         'Work',
  '/live-console':  'Work',
  '/agents':        'Intelligence',
  '/analyst':       'Intelligence',
  '/developer':     'Intelligence',
  '/monitor':       'Intelligence',
  '/improvements':  'Intelligence',
  '/workflows':     'Intelligence',
  '/goals':         'Intelligence',
  '/audit':         'Knowledge',
  '/costs':         'Knowledge',
  '/activity':      'Knowledge',
  '/knowledge':     'Knowledge',
  '/issues':        'Knowledge',
  '/org-graph':     'Organization',
  '/onboarding':    'Organization',
  '/llm':           'Admin',
  '/yaml-editor':   'Admin',
  '/access-control':'Admin',
  '/integrations':  'Admin',
  '/settings':      'Admin',
}

interface HeaderProps {
  onOpenPalette?: () => void
}

export default function Header({ onOpenPalette }: HeaderProps) {
  const { pathname } = useLocation()
  const [confirmStop, setConfirmStop] = useState(false)

  const { data: healthData, isError: healthError } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  })

  const { data: projectData } = useProjectConfig()

  const online = !healthError && !!healthData
  // Use solution ui_labels if available, fall back to generic PAGE_TITLES
  const uiLabels = (projectData as any)?.ui_labels ?? {}
  const UI_LABEL_ROUTES: Record<string, string> = {
    '/analyst': uiLabels.analyst_page_title,
    '/developer': uiLabels.developer_page_title,
    '/monitor': uiLabels.monitor_page_title,
  }
  const title = UI_LABEL_ROUTES[pathname] ?? PAGE_TITLES[pathname] ?? 'SAGE[ai]'
  const projectName = projectData?.name ?? 'SAGE Framework'

  return (
    <header
      className="h-14 border-b flex items-center px-4 gap-3 shrink-0 relative"
      style={{ backgroundColor: '#18181b', borderColor: '#27272a' }}
    >
      {/* Breadcrumb + page title */}
      <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: '11px', color: '#64748b' }}>
          {projectName} / {ROUTE_TO_AREA[pathname] ?? 'SAGE'}
        </div>
        <div style={{ fontSize: '14px', fontWeight: 600, color: '#f1f5f9', marginTop: '1px' }}>
          {title}
        </div>
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
    </header>
  )
}
