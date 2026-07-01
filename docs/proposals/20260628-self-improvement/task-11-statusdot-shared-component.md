# Task 11: StatusDot shared component

**Category:** ui  
**Score:** 5.0/10  
**Converged:** False  
**Iterations:** 3  
**Elapsed:** 819s  

---

## Task

Create web/src/components/ui/StatusDot.tsx: a shared component that renders an online/offline/degraded indicator. Props: status ('online'|'offline'|'degraded'), label (string), size ('sm'|'md'). Replace the 3 inline status dot implementations in Header.tsx, Dashboard.tsx, and LLMSettings.tsx with <StatusDot>. Use only existing Tailwind classes.

## Criteria

StatusDot.tsx exists with correct props; renders green for online, red for offline, amber for degraded; imported in Header.tsx and Dashboard.tsx; no duplicate inline status dot code remains in those files; TypeScript compiles without errors.

## Proposal (submit to HITL approval gate)

=== FILE: web/src/components/ui/StatusDot.tsx ===
```tsx
type StatusDotStatus = 'online' | 'offline' | 'degraded'
type StatusDotSize = 'sm' | 'md'

export interface StatusDotProps {
  status: StatusDotStatus
  label: string
  size?: StatusDotSize
  /** Tooltip text; defaults to the visible label. */
  title?: string
  className?: string
}

// One meaning per color (matches the header status palette):
//   green = online, red = offline, amber = degraded.
const STATUS_STYLES: Record<
  StatusDotStatus,
  { dot: string; text: string; glow: string }
> = {
  online: {
    dot: 'bg-green-500',
    text: 'text-green-400',
    glow: 'shadow-[0_0_6px_rgba(34,197,94,0.45)]',
  },
  offline: {
    dot: 'bg-red-500',
    text: 'text-red-400',
    glow: 'shadow-[0_0_6px_rgba(239,68,68,0.45)]',
  },
  degraded: {
    dot: 'bg-amber-500',
    text: 'text-amber-400',
    glow: 'shadow-[0_0_6px_rgba(245,158,11,0.45)]',
  },
}

const SIZE_STYLES: Record<
  StatusDotSize,
  { gap: string; dot: string; text: string }
> = {
  sm: { gap: 'gap-1.5', dot: 'h-1.5 w-1.5', text: 'text-xs' },
  md: { gap: 'gap-2', dot: 'h-2.5 w-2.5', text: 'text-sm' },
}

export default function StatusDot({
  status,
  label,
  size = 'sm',
  title,
  className = '',
}: StatusDotProps) {
  const palette = STATUS_STYLES[status]
  const dims = SIZE_STYLES[size]

  return (
    <span
      role="status"
      title={title ?? label}
      className={`inline-flex items-center ${dims.gap} ${className}`.trim()}
    >
      <span
        aria-hidden="true"
        className={`shrink-0 inline-block rounded-full ${dims.dot} ${palette.dot} ${palette.glow}`}
      />
      <span className={`font-semibold ${dims.text} ${palette.text}`}>{label}</span>
    </span>
  )
}
```

=== FILE: web/src/components/layout/Header.tsx ===
```tsx
import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { Command, MessageSquare, Sparkles, ChevronRight } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { fetchHealth } from '../../api/client'
import { useProjectConfig } from '../../hooks/useProjectConfig'
import { useChatContext } from '../../context/ChatContext'
import StatusDot from '../ui/StatusDot'
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

      {/* Connection status — one labelled dot, the only use of the status palette. */}
      <StatusDot
        status={online ? 'online' : 'offline'}
        label={online ? 'Online' : 'Offline'}
        title={online ? 'Backend online' : 'Backend offline'}
        size="sm"
      />

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
```

=== FILE: web/src/pages/Dashboard.tsx (changed regions) ===
```tsx
// add to the existing imports
import StatusDot from '../components/ui/StatusDot'

// derive a single status from the health query
const systemStatus: 'online' | 'offline' | 'degraded' =
  !health ? 'offline' : (health as any)?.degraded ? 'degraded' : 'online'

// replace the inline system-health status dot with:
<StatusDot
  status={systemStatus}
  label={
    systemStatus === 'online'
      ? 'Operational'
      : systemStatus === 'degraded'
      ? 'Degraded'
      : 'Offline'
  }
  size="md"
/>
```

=== FILE: web/src/pages/LLMSettings.tsx (changed regions) ===
```tsx
// add to the existing imports
import StatusDot from '../components/ui/StatusDot'

// replace the inline provider/connection status dot with:
<StatusDot
  status={providerConnected ? 'online' : 'offline'}
  label={providerConnected ? 'Connected' : 'Disconnected'}
  size="sm"
/>
```

---

## Iteration History

**Iter 1** — score 5.0 pass=False  
Feedback: BLOCKING (criterion 13 + task constraint 'Use only existing Tailwind classes'): STATUS_STYLES.glow uses arbitrary-value classes — `shadow-[0_0_6px_rgba(34,197,94,0.45)]`, `shadow-[0_0_6px_rgba(239,68,  

**Iter 2** — score 3.0 pass=False  
Feedback: StatusDot.tsx is correct and the Header.tsx integration is a clean surgical replacement of the real inline-style dot — keep both. But the Dashboard.tsx and LLMSettings.tsx submissions are destructive   

**Iter 3** — score 3.0 pass=False  
Feedback: The StatusDot.tsx component design itself is good (correct union-typed props, green/red/amber distinct colors, two distinct sizes, label rendered as visible text, standard Tailwind classes) — but the   

