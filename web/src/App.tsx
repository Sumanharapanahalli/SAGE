import { useState, useEffect, useRef, useCallback } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Sidebar from './components/layout/Sidebar'
import Header from './components/layout/Header'
import CommandPalette from './components/CommandPalette'
import { useProjectConfig } from './hooks/useProjectConfig'
import Dashboard from './pages/Dashboard'
import Analyst from './pages/Analyst'
import Developer from './pages/Developer'
import AuditLog from './pages/AuditLog'
import Monitor from './pages/Monitor'
import Improvements from './pages/Improvements'
import LLMSettings from './pages/LLMSettings'
import Agents from './pages/Agents'
import Settings from './pages/Settings'
import YamlEditor from './pages/YamlEditor'
import LiveConsole from './pages/LiveConsole'
import Onboarding from './pages/Onboarding'
import Integrations from './pages/Integrations'
import Queue from './pages/Queue'
import AccessControl from './pages/AccessControl'
import Costs from './pages/Costs'
import Workflows from './pages/Workflows'
import Approvals from './pages/Approvals'
import Goals from './pages/Goals'
import OrgGraph from './pages/OrgGraph'
import TourOverlay from './components/onboarding/TourOverlay'
import { TourProvider } from './context/TourContext'
import LLMDisconnectedBanner from './components/ui/LLMDisconnectedBanner'
import ChatPanel from './components/ui/ChatPanel'
import Issues from './pages/Issues'
import Activity from './pages/Activity'
import Guide from './pages/Guide'
import Organization from './pages/settings/Organization'
import ThemeProvider from './components/theme/ThemeProvider'
import { AuthProvider } from './context/AuthContext'
import { UserPrefsProvider } from './context/UserPrefsContext'
import { ChatProvider } from './context/ChatContext'

// ---------------------------------------------------------------------------
// Standard SAGE routes — solution-agnostic.
//
// To add solution-specific pages:
//   1. Create web/src/pages/solutions/<name>/MyPage.tsx
//   2. Import it here with a lazy import
//   3. Add the route below
//   4. Add the moduleId to active_modules in your solution's project.yaml
//   5. Add the sidebar entry in components/layout/Sidebar.tsx
//
// These additions belong in your solution fork/branch, not in the community
// framework. The framework ships with universal pages only.
// ---------------------------------------------------------------------------

function SidebarDivider() {
  const dragging = useRef(false)

  const getWidth = (): number => {
    try {
      const s = localStorage.getItem('sage_panel_sidebar')
      return s ? parseFloat(s) : 264
    } catch { return 264 }
  }

  const [width, setWidth] = useState(getWidth)

  useEffect(() => {
    document.documentElement.style.setProperty('--sage-sidebar-width', `${width}px`)
  }, [width])

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    dragging.current = true
    const onMove = (ev: MouseEvent) => {
      if (!dragging.current) return
      const newW = Math.max(200, Math.min(500, ev.clientX))
      setWidth(newW)
      document.documentElement.style.setProperty('--sage-sidebar-width', `${newW}px`)
    }
    const onUp = (ev: MouseEvent) => {
      dragging.current = false
      const newW = Math.max(200, Math.min(500, ev.clientX))
      try { localStorage.setItem('sage_panel_sidebar', newW.toString()) } catch { /* ignore */ }
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }, [])

  return (
    <div
      onMouseDown={onMouseDown}
      style={{
        width: 4,
        height: '100%',
        flexShrink: 0,
        background: '#0f172a',
        cursor: 'col-resize',
        zIndex: 20,
      }}
      onMouseEnter={e => (e.currentTarget.style.background = '#3b82f6')}
      onMouseLeave={e => (e.currentTarget.style.background = '#0f172a')}
    />
  )
}

function AppShell() {
  const [paletteOpen, setPaletteOpen] = useState(false)
  const { data: projectData } = useProjectConfig()

  // Keep browser tab title in sync with active solution
  useEffect(() => {
    document.title = projectData?.name ? projectData.name : 'SAGE[ai]'
  }, [projectData?.name])

  // Cmd+K / Ctrl+K opens the command palette
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setPaletteOpen(prev => !prev)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  return (
    <>
      <div className="flex h-screen overflow-hidden bg-zinc-50">
        <Sidebar />
        <SidebarDivider />
        <div className="flex flex-col flex-1 overflow-hidden">
          <Header onOpenPalette={() => setPaletteOpen(true)} />
          <main className="flex-1 overflow-y-auto p-6">
            <Routes>
              <Route path="/"             element={<Dashboard />} />
              <Route path="/agents"       element={<Agents />} />
              <Route path="/analyst"      element={<Analyst />} />
              <Route path="/developer"    element={<Developer />} />
              <Route path="/audit"        element={<AuditLog />} />
              <Route path="/monitor"      element={<Monitor />} />
              <Route path="/improvements" element={<Improvements />} />
              <Route path="/llm"          element={<LLMSettings />} />
              <Route path="/settings"     element={<Settings />} />
              <Route path="/yaml-editor"   element={<YamlEditor />} />
              <Route path="/live-console"  element={<LiveConsole />} />
              <Route path="/onboarding"     element={<Onboarding />} />
              <Route path="/integrations"  element={<Integrations />} />
              <Route path="/queue"          element={<Queue />} />
              <Route path="/access-control" element={<AccessControl />} />
              <Route path="/costs"          element={<Costs />} />
              <Route path="/workflows"      element={<Workflows />} />
              <Route path="/approvals"      element={<Approvals />} />
              <Route path="/goals"          element={<Goals />} />
              <Route path="/org-graph"      element={<OrgGraph />} />
              <Route path="/issues"         element={<Issues />} />
              <Route path="/activity"       element={<Activity />} />
              <Route path="/knowledge"      element={<AuditLog />} />
              <Route path="/guide"          element={<Guide />} />
              <Route path="/settings/organization" element={<Organization />} />
            </Routes>
          </main>
        </div>
      </div>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      <TourOverlay />
      <LLMDisconnectedBanner />
      <ChatPanel />
    </>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <UserPrefsProvider>
          <ThemeProvider>
            <TourProvider>
              <ChatProvider>
                <AppShell />
              </ChatProvider>
            </TourProvider>
          </ThemeProvider>
        </UserPrefsProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
