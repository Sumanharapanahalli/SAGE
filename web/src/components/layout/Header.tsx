import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { Command, MessageSquare } from 'lucide-react'
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
  '/knowledge':         'Knowledge',
  '/product-backlog':   'Product Backlog',
  '/cds-compliance':    'CDS Compliance',
  '/regulatory':        'Regulatory Compliance',
  '/guide':             'User Guide',
  '/settings/organization': 'Organization',
}

const ROUTE_TO_AREA: Record<string, string> = {
  '/':                'Work',
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
  '/audit':          'Knowledge',
  '/costs':          'Knowledge',
  '/activity':       'Knowledge',
  '/knowledge':      'Knowledge',
  '/issues':         'Knowledge',
  '/org-graph':      'Organization',
  '/onboarding':     'Organization',
  '/llm':            'Admin',
  '/yaml-editor':    'Admin',
  '/access-control': 'Admin',
  '/integrations':   'Admin',
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
  const uiLabels = (projectData as any)?.ui_labels ?? {}
  const UI_LABEL_ROUTES: Record<string, string> = {
    '/analyst':   uiLabels.analyst_page_title,
    '/developer': uiLabels.developer_page_title,
    '/monitor':   uiLabels.monitor_page_title,
  }
  const title = UI_LABEL_ROUTES[pathname] ?? PAGE_TITLES[pathname] ?? 'SAGE[ai]'
  const projectName = (projectData as any)?.name ?? 'SAGE Framework'

  return (
    <header
      className="h-14 border-b flex items-center px-4 gap-3 shrink-0 relative"
      style={{ backgroundColor: '#18181b', borderColor: '#27272a' }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: '11px', color: '#64748b' }}>
          {projectName} / {ROUTE_TO_AREA[pathname] ?? 'SAGE'}
        </div>
        <div style={{ fontSize: '14px', fontWeight: 600, color: '#f1f5f9', marginTop: '1px' }}>
          {title}
        </div>
      </div>

      <button
        onClick={onOpenPalette}
        className="flex items-center gap-1.5 text-xs px-2.5 py-1 transition-colors shrink-0"
        style={{ color: '#52525b', border: '1px solid #3f3f46' }}
        title="Open command palette (Cmd+K)"
      >
        <Command size={11} />
        <span>K</span>
      </button>

      <button
        onClick={() => openChat()}
        title="Open SAGE Chat (Ctrl+J)"
        className="flex items-center gap-1.5 text-xs px-2.5 py-1 transition-colors shrink-0"
        style={{
          color: panelState !== 'closed' ? '#3b82f6' : '#52525b',
          border: `1px solid ${panelState !== 'closed' ? '#1d4ed8' : '#3f3f46'}`,
        }}
      >
        <MessageSquare size={11} />
      </button>

      <div className="flex items-center gap-1.5 text-xs shrink-0">
        <span
          className="w-1.5 h-1.5"
          style={{ backgroundColor: online ? '#22c55e' : '#ef4444', display: 'inline-block' }}
        />
        <span className="hidden sm:block" style={{ color: '#52525b' }}>
          {online ? (healthData as any)?.llm_provider ?? 'Online' : 'API Unreachable'}
        </span>
      </div>

      <UserMenu />
    </header>
  )
}
