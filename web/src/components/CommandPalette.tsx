import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Search, GitMerge, ClipboardList,
  Activity, Lightbulb, Cpu, Settings, FileCode2, Bot,
  Terminal, Wand2, Plug, ListOrdered, ShieldCheck, DollarSign,
  Command,
} from 'lucide-react'

// ---------------------------------------------------------------------------
// All navigable routes — mirrors Sidebar links
// ---------------------------------------------------------------------------
const ROUTES = [
  { to: '/',              icon: LayoutDashboard, label: 'Dashboard',      group: 'WORK' },
  { to: '/queue',         icon: ListOrdered,     label: 'Task Queue',     group: 'WORK' },
  { to: '/live-console',  icon: Terminal,        label: 'Live Console',   group: 'WORK' },
  { to: '/agents',        icon: Bot,             label: 'Agents',         group: 'AGENTS' },
  { to: '/analyst',       icon: Search,          label: 'Analyst',        group: 'AGENTS' },
  { to: '/developer',     icon: GitMerge,        label: 'Developer',      group: 'AGENTS' },
  { to: '/monitor',       icon: Activity,        label: 'Monitor',        group: 'AGENTS' },
  { to: '/improvements',  icon: Lightbulb,       label: 'Improvements',   group: 'INTELLIGENCE' },
  { to: '/yaml-editor',   icon: FileCode2,       label: 'Config Editor',  group: 'INTELLIGENCE' },
  { to: '/audit',         icon: ClipboardList,   label: 'Audit Log',      group: 'INTELLIGENCE' },
  { to: '/llm',           icon: Cpu,             label: 'LLM Settings',   group: 'SETTINGS' },
  { to: '/integrations',  icon: Plug,            label: 'Integrations',   group: 'SETTINGS' },
  { to: '/onboarding',    icon: Wand2,           label: 'New Solution',   group: 'SETTINGS' },
  { to: '/access-control',icon: ShieldCheck,     label: 'Access Control', group: 'SETTINGS' },
  { to: '/costs',         icon: DollarSign,      label: 'Costs',          group: 'SETTINGS' },
  { to: '/settings',      icon: Settings,        label: 'Settings',       group: 'SETTINGS' },
]

interface CommandPaletteProps {
  open: boolean
  onClose: () => void
}

export default function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [cursor, setCursor] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const filtered = query.trim()
    ? ROUTES.filter(r =>
        r.label.toLowerCase().includes(query.toLowerCase()) ||
        r.group.toLowerCase().includes(query.toLowerCase())
      )
    : ROUTES

  const go = useCallback(
    (to: string) => {
      navigate(to)
      onClose()
      setQuery('')
      setCursor(0)
    },
    [navigate, onClose]
  )

  // Focus input on open
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 10)
      setCursor(0)
    } else {
      setQuery('')
      setCursor(0)
    }
  }, [open])

  // Keyboard navigation
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setCursor(c => Math.min(c + 1, filtered.length - 1))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setCursor(c => Math.max(c - 1, 0))
      } else if (e.key === 'Enter') {
        e.preventDefault()
        if (filtered[cursor]) go(filtered[cursor].to)
      } else if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, cursor, filtered, go, onClose])

  // Keep active item scrolled into view
  useEffect(() => {
    const el = listRef.current?.querySelector(`[data-idx="${cursor}"]`) as HTMLElement | null
    el?.scrollIntoView({ block: 'nearest' })
  }, [cursor])

  if (!open) return null

  return (
    <div className="sage-palette-overlay" onClick={onClose}>
      <div className="sage-palette-box" onClick={e => e.stopPropagation()}>
        {/* Input row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0 1rem', borderBottom: '1px solid #3f3f46' }}>
          <Command size={14} style={{ color: '#52525b', flexShrink: 0 }} />
          <input
            ref={inputRef}
            className="sage-palette-input"
            style={{ borderBottom: 'none', padding: '0.875rem 0' }}
            placeholder="Go to page…"
            value={query}
            onChange={e => { setQuery(e.target.value); setCursor(0) }}
          />
        </div>

        {/* Results */}
        <div ref={listRef} style={{ maxHeight: '360px', overflowY: 'auto' }}>
          {filtered.length === 0 && (
            <div style={{ padding: '1rem', fontSize: '0.8rem', color: '#52525b', textAlign: 'center' }}>
              No results for "{query}"
            </div>
          )}
          {filtered.map((item, idx) => {
            const Icon = item.icon
            const isActive = idx === cursor
            return (
              <div
                key={item.to}
                data-idx={idx}
                className={`sage-palette-result${isActive ? ' active' : ''}`}
                onMouseEnter={() => setCursor(idx)}
                onClick={() => go(item.to)}
              >
                <Icon size={14} style={{ flexShrink: 0, color: isActive ? '#a1a1aa' : '#52525b' }} />
                <span style={{ flex: 1 }}>{item.label}</span>
                <span style={{ fontSize: '0.65rem', color: '#3f3f46', fontWeight: 600, letterSpacing: '0.05em' }}>
                  {item.group}
                </span>
              </div>
            )
          })}
        </div>

        {/* Footer hint */}
        <div style={{
          padding: '0.5rem 1rem',
          borderTop: '1px solid #27272a',
          display: 'flex',
          gap: '1rem',
          fontSize: '0.65rem',
          color: '#52525b',
        }}>
          <span>↑↓ navigate</span>
          <span>↵ open</span>
          <span>esc close</span>
        </div>
      </div>
    </div>
  )
}
