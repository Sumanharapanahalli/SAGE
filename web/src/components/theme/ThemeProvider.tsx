/**
 * SAGE ThemeProvider
 *
 * Reads the `theme` block from the active solution's project.yaml (via
 * useProjectConfig) and writes CSS custom properties onto document.documentElement.
 * This makes the variables available globally, so Sidebar, Header, and any
 * component that uses var(--sage-*) reflects the solution's brand instantly —
 * including when the user switches solutions, with no page reload required.
 *
 * Default values are defined in index.css :root so solutions that don't
 * define a theme block get the standard SAGE dark-sidebar/indigo-accent look.
 */
import { useEffect } from 'react'
import { useProjectConfig } from '../../hooks/useProjectConfig'

interface SageTheme {
  sidebar_bg?: string
  sidebar_text?: string
  sidebar_active_bg?: string
  sidebar_active_text?: string
  sidebar_hover_bg?: string
  sidebar_accent?: string
  accent?: string
  accent_hover?: string
  accent_light?: string
  accent_text?: string
  badge_bg?: string
  badge_text?: string
}

const VAR_MAP: Record<keyof SageTheme, string> = {
  sidebar_bg:          '--sage-sidebar-bg',
  sidebar_text:        '--sage-sidebar-text',
  sidebar_active_bg:   '--sage-sidebar-active-bg',
  sidebar_active_text: '--sage-sidebar-active-text',
  sidebar_hover_bg:    '--sage-sidebar-hover-bg',
  sidebar_accent:      '--sage-sidebar-accent',
  accent:              '--sage-accent',
  accent_hover:        '--sage-accent-hover',
  accent_light:        '--sage-accent-light',
  accent_text:         '--sage-accent-text',
  badge_bg:            '--sage-badge-bg',
  badge_text:          '--sage-badge-text',
}

export default function ThemeProvider({ children }: { children: React.ReactNode }) {
  const { data: projectData } = useProjectConfig()

  useEffect(() => {
    const theme = (projectData as any)?.theme as SageTheme | undefined
    if (!theme) {
      // No theme block — remove any previously set overrides so :root defaults apply
      const root = document.documentElement
      Object.values(VAR_MAP).forEach(v => root.style.removeProperty(v))
      return
    }

    const root = document.documentElement
    for (const [key, cssVar] of Object.entries(VAR_MAP)) {
      const value = theme[key as keyof SageTheme]
      if (value) {
        root.style.setProperty(cssVar, value)
      } else {
        root.style.removeProperty(cssVar)   // let :root default apply
      }
    }
  }, [(projectData as any)?.theme])

  return <>{children}</>
}
