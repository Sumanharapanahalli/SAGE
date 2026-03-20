import {
  createContext, useContext, useEffect, useState, useCallback, ReactNode
} from 'react'
import { useAuth } from './AuthContext'

export interface UserPrefs {
  theme:      'dark' | 'light' | 'system'
  colorCombo: 'zinc' | 'night' | 'forest' | 'ocean' | 'slate' | 'rose'
  fontFamily: 'inter' | 'jetbrains-mono' | 'system-ui' | 'geist' | 'roboto'
  fontSize:   'sm' | 'md' | 'lg'
  density:    'compact' | 'comfortable'
  timezone:   string
}

export const DEFAULT_PREFS: UserPrefs = {
  theme: 'dark', colorCombo: 'zinc', fontFamily: 'inter',
  fontSize: 'md', density: 'comfortable', timezone: 'UTC',
}

export const COLOR_COMBOS: Record<UserPrefs['colorCombo'], {
  label: string
  sidebarBg: string; sidebarText: string; contentBg: string
  accent: string; accentHover: string
}> = {
  zinc:   { label: 'Zinc',   sidebarBg: '#18181b', sidebarText: '#a1a1aa', contentBg: '#fafafa', accent: '#71717a', accentHover: '#52525b' },
  night:  { label: 'Night',  sidebarBg: '#0f172a', sidebarText: '#94a3b8', contentBg: '#ffffff', accent: '#3b82f6', accentHover: '#2563eb' },
  forest: { label: 'Forest', sidebarBg: '#052e16', sidebarText: '#86efac', contentBg: '#fefce8', accent: '#16a34a', accentHover: '#15803d' },
  ocean:  { label: 'Ocean',  sidebarBg: '#042f2e', sidebarText: '#99f6e4', contentBg: '#f0fdfa', accent: '#0d9488', accentHover: '#0f766e' },
  slate:  { label: 'Slate',  sidebarBg: '#1e293b', sidebarText: '#94a3b8', contentBg: '#f8fafc', accent: '#6366f1', accentHover: '#4f46e5' },
  rose:   { label: 'Rose',   sidebarBg: '#1c0a0a', sidebarText: '#fca5a5', contentBg: '#fff1f2', accent: '#e11d48', accentHover: '#be123c' },
}

export const FONT_FAMILIES: Record<UserPrefs['fontFamily'], string> = {
  'inter':          "'Inter', sans-serif",
  'jetbrains-mono': "'JetBrains Mono', monospace",
  'system-ui':      'system-ui, sans-serif',
  'geist':          "'Geist', sans-serif",
  'roboto':         "'Roboto', sans-serif",
}

const FONT_SIZES: Record<UserPrefs['fontSize'], string> = {
  sm: '13px', md: '14px', lg: '16px',
}

const DENSITIES: Record<UserPrefs['density'], string> = {
  compact: '0.75rem', comfortable: '1rem',
}

interface UserPrefsAdapter {
  load(userId: string): UserPrefs | null
  save(userId: string, prefs: UserPrefs): void
}

const localStorageAdapter: UserPrefsAdapter = {
  load: (userId) => {
    try {
      const raw = localStorage.getItem(`sage_user_prefs_${userId}`)
      return raw ? { ...DEFAULT_PREFS, ...JSON.parse(raw) } : null
    } catch { return null }
  },
  save: (userId, prefs) => {
    try {
      localStorage.setItem(`sage_user_prefs_${userId}`, JSON.stringify(prefs))
    } catch { /* storage full */ }
  },
}

export function applyPrefs(prefs: UserPrefs) {
  const root = document.documentElement

  if (prefs.theme === 'dark') {
    root.classList.add('dark')
  } else if (prefs.theme === 'light') {
    root.classList.remove('dark')
  } else {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    root.classList.toggle('dark', prefersDark)
  }

  const combo = COLOR_COMBOS[prefs.colorCombo]
  root.style.setProperty('--sage-sidebar-bg',   combo.sidebarBg)
  root.style.setProperty('--sage-sidebar-text',  combo.sidebarText)
  root.style.setProperty('--sage-content-bg',    combo.contentBg)
  root.style.setProperty('--sage-user-accent',   combo.accent)
  root.style.setProperty('--sage-accent-hover',  combo.accentHover)

  root.style.setProperty('--sage-font-family',    FONT_FAMILIES[prefs.fontFamily])
  root.style.setProperty('--sage-font-size-base', FONT_SIZES[prefs.fontSize])
  root.style.setProperty('--sage-density',        DENSITIES[prefs.density])
}

interface UserPrefsContextValue {
  prefs:      UserPrefs
  updatePref: <K extends keyof UserPrefs>(key: K, value: UserPrefs[K]) => void
  resetPrefs: () => void
}

export const UserPrefsContext = createContext<UserPrefsContextValue>({
  prefs:      DEFAULT_PREFS,
  updatePref: () => {},
  resetPrefs: () => {},
})

export function UserPrefsProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const userId = user?.sub ?? 'anonymous'

  const [prefs, setPrefs] = useState<UserPrefs>(() => {
    return localStorageAdapter.load(userId) ?? DEFAULT_PREFS
  })

  useEffect(() => {
    const loaded = localStorageAdapter.load(userId) ?? DEFAULT_PREFS
    setPrefs(loaded)
    applyPrefs(loaded)
  }, [userId])

  useEffect(() => { applyPrefs(prefs) }, [])

  const updatePref = useCallback(<K extends keyof UserPrefs>(key: K, value: UserPrefs[K]) => {
    setPrefs(prev => {
      const next = { ...prev, [key]: value }
      localStorageAdapter.save(userId, next)
      applyPrefs(next)
      return next
    })
  }, [userId])

  const resetPrefs = useCallback(() => {
    setPrefs(DEFAULT_PREFS)
    localStorageAdapter.save(userId, DEFAULT_PREFS)
    applyPrefs(DEFAULT_PREFS)
  }, [userId])

  return (
    <UserPrefsContext.Provider value={{ prefs, updatePref, resetPrefs }}>
      {children}
    </UserPrefsContext.Provider>
  )
}

export function useUserPrefs(): UserPrefsContextValue {
  return useContext(UserPrefsContext)
}
