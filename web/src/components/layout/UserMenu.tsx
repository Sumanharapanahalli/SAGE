import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { BookOpen, MessageCircle } from 'lucide-react'
import { fetchHealth } from '../../api/client'
import { useAuth } from '../../context/AuthContext'
import { useUserPrefs, COLOR_COMBOS, UserPrefs, applyPrefs } from '../../context/UserPrefsContext'
import { useProjectConfig } from '../../hooks/useProjectConfig'
import { useChatContext } from '../../context/ChatContext'
import KeyboardShortcutsModal from '../ui/KeyboardShortcutsModal'

async function shutdownSage() {
  await fetch('/api/shutdown', { method: 'POST' })
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

function ComboSwatch({ comboKey, active, onClick, onPreview, onPreviewEnd }: {
  comboKey: UserPrefs['colorCombo']; active: boolean; onClick: () => void
  onPreview: (key: UserPrefs['colorCombo']) => void
  onPreviewEnd: () => void
}) {
  const c = COLOR_COMBOS[comboKey]
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => onPreview(comboKey)}
      onMouseLeave={onPreviewEnd}
      title={c.label}
      style={{
        width: 28, height: 28, cursor: 'pointer', padding: 0, border: 'none',
        outline: active ? `2px solid ${c.accent}` : '2px solid #d1d5db',
        outlineOffset: 2, overflow: 'hidden', display: 'inline-flex',
        flexDirection: 'column', background: 'none', flexShrink: 0,
        borderRadius: 4,
      }}
    >
      {/* Top half: sidebar color */}
      <div style={{ width: 28, height: 14, background: c.sidebarBg }} />
      {/* Bottom half: accent color */}
      <div style={{ width: 28, height: 14, background: c.accent }} />
    </button>
  )
}

export default function UserMenu() {
  const [open, setOpen] = useState(false)
  const [showShortcuts, setShowShortcuts] = useState(false)
  const [confirmStop, setConfirmStop] = useState(false)
  const [previewCombo, setPreviewCombo] = useState<UserPrefs['colorCombo'] | null>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const [panelPos, setPanelPos] = useState({ top: 0, right: 0 })
  const navigate = useNavigate()
  const { openChat } = useChatContext()

  const { user, devUsers, switchDevUser, isDevMode } = useAuth()
  const { prefs, updatePref, resetPrefs } = useUserPrefs()

  const handlePreview = useCallback((key: UserPrefs['colorCombo']) => {
    setPreviewCombo(key)
    applyPrefs({ ...prefs, colorCombo: key })
  }, [prefs])

  const handlePreviewEnd = useCallback(() => {
    setPreviewCombo(null)
    applyPrefs(prefs)
  }, [prefs])
  const { data: projectData } = useProjectConfig()
  const { data: healthData } = useQuery({ queryKey: ['health'], queryFn: fetchHealth, refetchInterval: 30_000 })

  useEffect(() => {
    if (!open) return
    function handle(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node) &&
          buttonRef.current && !buttonRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [open])

  useEffect(() => {
    if (!open) return
    function handle(e: KeyboardEvent) { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('keydown', handle)
    return () => document.removeEventListener('keydown', handle)
  }, [open])

  const toggleOpen = useCallback(() => {
    if (!open && buttonRef.current) {
      const r = buttonRef.current.getBoundingClientRect()
      setPanelPos({ top: r.bottom + 4, right: window.innerWidth - r.right })
    }
    setOpen(o => !o)
  }, [open])

  const displayName = user?.name ?? 'Guest'
  const displayEmail = user?.email ?? ''
  const displayRole = user?.role ?? 'viewer'
  const avatarBg = devUsers.find(u => u.id === user?.sub)?.avatar_color ?? '#52525b'
  const solutionName = (projectData as any)?.name ?? 'SAGE Framework'
  const llmInfo = (healthData as any)?.llm_provider ?? 'unknown'

  const roleBadgeColor: Record<string, string> = {
    admin: '#6366f1', approver: '#f97316', operator: '#f59e0b', viewer: '#64748b',
  }

  const fontFamilyOptions: { value: UserPrefs['fontFamily']; label: string }[] = [
    { value: 'inter',          label: 'Inter' },
    { value: 'jetbrains-mono', label: 'JetBrains Mono' },
    { value: 'system-ui',      label: 'System UI' },
    { value: 'geist',          label: 'Geist' },
    { value: 'roboto',         label: 'Roboto' },
  ]

  const comboKeys = Object.keys(COLOR_COMBOS) as UserPrefs['colorCombo'][]

  const sel: React.CSSProperties = {
    background: '#e5e7eb', border: '1px solid #d1d5db', color: '#e4e4e7',
    fontSize: '11px', padding: '3px 6px', cursor: 'pointer', width: '100%',
  }
  const row: React.CSSProperties = {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    marginBottom: '6px', gap: '8px',
  }
  const lbl: React.CSSProperties = { fontSize: '11px', color: '#9ca3af', flexShrink: 0, width: '60px' }
  const div: React.CSSProperties = { borderTop: '1px solid #e5e7eb', margin: '8px 0' }
  const sec: React.CSSProperties = { padding: '10px 14px' }
  const act: React.CSSProperties = {
    display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 14px',
    cursor: 'pointer', fontSize: '12px', color: '#6b7280',
  }

  return (
    <>
      <button
        ref={buttonRef}
        onClick={toggleOpen}
        style={{
          width: 28, height: 28, borderRadius: '50%', border: 'none',
          background: avatarBg, color: '#fff', fontSize: '11px', fontWeight: 700,
          cursor: 'pointer', flexShrink: 0, display: 'flex', alignItems: 'center',
          justifyContent: 'center', letterSpacing: '0.02em',
        }}
        title={`${displayName} (${displayRole})`}
      >
        {initials(displayName)}
      </button>

      {open && (
        <div
          ref={panelRef}
          style={{
            position: 'fixed', top: panelPos.top, right: panelPos.right,
            width: 300, zIndex: 9999,
            background: '#ffffff', border: '1px solid #e5e7eb',
            boxShadow: '0 20px 40px rgba(0,0,0,0.6)',
            overflowY: 'auto', maxHeight: 'calc(100vh - 60px)',
          }}
        >
          {/* Identity */}
          <div style={{ ...sec, paddingBottom: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
              <div style={{
                width: 32, height: 32, borderRadius: '50%', background: avatarBg,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '12px', fontWeight: 700, color: '#fff', flexShrink: 0,
              }}>
                {initials(displayName)}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ fontSize: '13px', fontWeight: 600, color: '#374151', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {displayName}
                  </span>
                  <span style={{
                    fontSize: '9px', fontWeight: 700, textTransform: 'uppercase',
                    padding: '1px 5px', letterSpacing: '0.08em',
                    background: `${roleBadgeColor[displayRole] ?? '#52525b'}22`,
                    color: roleBadgeColor[displayRole] ?? '#a1a1aa',
                    border: `1px solid ${roleBadgeColor[displayRole] ?? '#52525b'}44`,
                    flexShrink: 0,
                  }}>
                    {displayRole}
                  </span>
                </div>
                <div style={{ fontSize: '11px', color: '#9ca3af', marginTop: '1px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {displayEmail}
                </div>
              </div>
            </div>
            <div style={{ fontSize: '10px', color: '#d1d5db', marginTop: '2px', paddingLeft: '42px' }}>
              {solutionName}
            </div>
          </div>

          <div style={div} />

          {/* Switch Identity */}
          {isDevMode && (
            <>
              <div style={sec}>
                <div style={{ fontSize: '10px', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#9ca3af', marginBottom: '6px' }}>
                  Switch Identity
                </div>
                <select style={sel} value={user?.sub ?? ''} onChange={e => switchDevUser(e.target.value)}>
                  {devUsers.map(u => (
                    <option key={u.id} value={u.id}>{u.name} -- {u.role}</option>
                  ))}
                </select>
              </div>
              <div style={div} />
            </>
          )}

          {/* Display settings */}
          <div style={sec}>
            <div style={{ fontSize: '10px', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#9ca3af', marginBottom: '8px' }}>
              Display
            </div>
            <div style={row}>
              <span style={lbl}>Theme</span>
              <select style={sel} value={prefs.theme} onChange={e => updatePref('theme', e.target.value as UserPrefs['theme'])}>
                <option value="dark">Dark</option>
                <option value="light">Light</option>
                <option value="system">System</option>
              </select>
            </div>
            <div style={{ marginBottom: '8px' }}>
              <span style={{ ...lbl, display: 'block', marginBottom: '6px' }}>Colors</span>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '6px' }}>
                {comboKeys.map(k => (
                  <div key={k} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '3px' }}>
                    <ComboSwatch comboKey={k} active={(previewCombo ?? prefs.colorCombo) === k} onClick={() => updatePref('colorCombo', k)} onPreview={handlePreview} onPreviewEnd={handlePreviewEnd} />
                    <span style={{ fontSize: '9px', color: prefs.colorCombo === k ? '#e4e4e7' : '#52525b', textAlign: 'center', lineHeight: 1 }}>
                      {COLOR_COMBOS[k].label}
                    </span>
                  </div>
                ))}
              </div>
            </div>
            <div style={row}>
              <span style={lbl}>Font</span>
              <select style={sel} value={prefs.fontFamily} onChange={e => updatePref('fontFamily', e.target.value as UserPrefs['fontFamily'])}>
                {fontFamilyOptions.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
              </select>
            </div>
            <div style={row}>
              <span style={lbl}>Size</span>
              <select style={sel} value={prefs.fontSize} onChange={e => updatePref('fontSize', e.target.value as UserPrefs['fontSize'])}>
                <option value="sm">Small</option>
                <option value="md">Medium</option>
                <option value="lg">Large</option>
              </select>
            </div>
            <div style={row}>
              <span style={lbl}>Density</span>
              <select style={sel} value={prefs.density} onChange={e => updatePref('density', e.target.value as UserPrefs['density'])}>
                <option value="compact">Compact</option>
                <option value="comfortable">Comfortable</option>
              </select>
            </div>
            <div style={row}>
              <span style={lbl}>Timezone</span>
              <select style={sel} value={prefs.timezone} onChange={e => updatePref('timezone', e.target.value)}>
                <option value="UTC">UTC</option>
                <option value="America/New_York">Eastern (ET)</option>
                <option value="America/Chicago">Central (CT)</option>
                <option value="America/Denver">Mountain (MT)</option>
                <option value="America/Los_Angeles">Pacific (PT)</option>
                <option value="Europe/London">London (GMT)</option>
                <option value="Europe/Berlin">Berlin (CET)</option>
                <option value="Asia/Kolkata">India (IST)</option>
                <option value="Asia/Tokyo">Tokyo (JST)</option>
                <option value="Australia/Sydney">Sydney (AEST)</option>
              </select>
            </div>
            <button onClick={resetPrefs} style={{ fontSize: '10px', color: '#d1d5db', background: 'none', border: 'none', cursor: 'pointer', padding: '2px 0', marginTop: '2px' }}>
              Reset to defaults
            </button>
          </div>

          <div style={div} />

          {/* Keyboard shortcuts */}
          <div
            style={act}
            onClick={() => { setShowShortcuts(true); setOpen(false) }}
            onMouseEnter={e => (e.currentTarget.style.background = '#e5e7eb')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            <span style={{ fontSize: '13px' }}>K</span>
            <span>Keyboard shortcuts</span>
          </div>

          {/* User Guide */}
          <div
            style={act}
            onClick={() => { navigate('/guide'); setOpen(false) }}
            onMouseEnter={e => (e.currentTarget.style.background = '#e5e7eb')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            <BookOpen size={13} style={{ color: '#6b7280' }} />
            <span>User Guide</span>
          </div>

          {/* Help & Ask SAGE */}
          <div
            style={act}
            onClick={() => { openChat('I want to understand the SAGE framework — where do I start?'); setOpen(false) }}
            onMouseEnter={e => (e.currentTarget.style.background = '#e5e7eb')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            <MessageCircle size={13} style={{ color: '#6b7280' }} />
            <span>Help & Ask SAGE</span>
          </div>

          <div style={div} />

          {/* About */}
          <div style={{ ...sec, paddingTop: '8px', paddingBottom: '8px' }}>
            <div style={{ fontSize: '10px', color: '#9ca3af' }}>SAGE v0.1.0-alpha by Shetty · {llmInfo}</div>
          </div>

          <div style={div} />

          {/* Actions */}
          <div
            style={act}
            onClick={() => { navigate('/access-control'); setOpen(false) }}
            onMouseEnter={e => (e.currentTarget.style.background = '#e5e7eb')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            <span>Access Control</span>
          </div>

          {!confirmStop ? (
            <div
              style={{ ...act, color: '#ef4444' }}
              onClick={() => setConfirmStop(true)}
              onMouseEnter={e => (e.currentTarget.style.background = '#e5e7eb')}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
            >
              <span>Stop SAGE</span>
            </div>
          ) : (
            <div style={{ ...sec, paddingTop: '6px', paddingBottom: '6px' }}>
              <div style={{ fontSize: '12px', color: '#ef4444', marginBottom: '6px', fontWeight: 600 }}>Stop SAGE?</div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={() => { shutdownSage(); setConfirmStop(false); setOpen(false) }}
                  style={{ fontSize: '11px', padding: '4px 12px', background: '#ef4444', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 600 }}
                >Yes</button>
                <button
                  onClick={() => setConfirmStop(false)}
                  style={{ fontSize: '11px', padding: '4px 12px', background: '#e5e7eb', color: '#6b7280', border: '1px solid #d1d5db', cursor: 'pointer' }}
                >Cancel</button>
              </div>
            </div>
          )}

          <div style={div} />

          {/* Logout */}
          <div
            style={{ ...act, paddingBottom: '10px' }}
            onClick={() => { if (devUsers.length > 0) switchDevUser(devUsers[0].id); setOpen(false) }}
            onMouseEnter={e => (e.currentTarget.style.background = '#e5e7eb')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            <span>{isDevMode ? `Switch to ${devUsers[0]?.name ?? 'default'}` : 'Logout'}</span>
          </div>
        </div>
      )}

      {showShortcuts && <KeyboardShortcutsModal onClose={() => setShowShortcuts(false)} />}
    </>
  )
}
