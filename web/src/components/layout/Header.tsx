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

      {/* Model selector badge — Claude-style */}
      {online && (
        <div
          className="flex items-center gap-1.5 px-2.5 py-1 cursor-pointer"
          style={{
            background: 'rgba(16, 185, 129, 0.08)',
            border: '1px solid rgba(16, 185, 129, 0.15)',
            borderRadius: '8px',
            fontSize: '11px',
            color: '#f97316',
            fontWeight: 500,
          }}
          title={`LLM: ${provider}${model ? ` / ${model}` : ''}`}
        >
          <Sparkles size={11} />
          <span>{provider}{model ? ` · ${model}` : ''}</span>
        </div>
      )}

      {/* Status dot */}
      <div className="flex items-center gap-1.5">
        <span
          style={{
            width: 6, height: 6, borderRadius: '50%',
            backgroundColor: online ? '#22c55e' : '#ef4444',
            display: 'inline-block',
            boxShadow: online ? '0 0 6px rgba(34,197,94,0.4)' : '0 0 6px rgba(239,68,68,0.4)',
          }}
        />
      </div>

      {/* Command palette */}
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

      {/* Chat */}
      <button
        onClick={() => openChat()}
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
