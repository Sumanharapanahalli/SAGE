# Task 13: Error boundaries for page components

**Category:** ui  
**Score:** 9.5/10  
**Converged:** True  
**Iterations:** 1  
**Elapsed:** 97s  

---

## Task

Add a React error boundary to web/src/App.tsx that wraps each route. On render error, show a fallback card with: the error message, a 'Try again' button (reloads the route), and a 'Go to Dashboard' link. Create web/src/components/ui/ErrorBoundary.tsx as a class component. Do not wrap the Header or Sidebar (only the main content area).

## Criteria

ErrorBoundary.tsx is a React class component; it wraps only the route <Outlet> in App.tsx; renders fallback card with error message and two actions; TypeScript compiles; does not break normal rendering.

## Proposal (submit to HITL approval gate)

=== FILE: web/src/components/ui/ErrorBoundary.tsx ===
```tsx
import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'
import { Link } from 'react-router-dom'

interface ErrorBoundaryProps {
  children: ReactNode
  /**
   * When this value changes, the boundary clears any captured error and
   * re-renders its children. Pass the current route path so navigating to a
   * different page automatically recovers from a previous render error.
   */
  resetKey?: unknown
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

/**
 * Route-level error boundary. Catches render errors thrown by the wrapped
 * page and shows a fallback card instead of crashing the whole app shell.
 */
export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Surface the error for debugging / future telemetry hooks.
    console.error('ErrorBoundary caught an error:', error, info.componentStack)
  }

  componentDidUpdate(prevProps: ErrorBoundaryProps) {
    // Recover automatically when the route (resetKey) changes.
    if (this.state.hasError && prevProps.resetKey !== this.props.resetKey) {
      this.reset()
    }
  }

  reset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children
    }

    const message =
      this.state.error?.message || 'An unexpected error occurred while rendering this page.'

    return (
      <div className="flex items-center justify-center w-full" style={{ minHeight: '60vh' }}>
        <div
          role="alert"
          className="w-full max-w-lg rounded-xl border p-6 shadow-lg"
          style={{
            backgroundColor: '#15151a',
            borderColor: '#3f1d1d',
            color: '#e5e7eb',
          }}
        >
          <div className="flex items-center gap-3 mb-3">
            <span
              className="flex items-center justify-center rounded-full"
              style={{
                width: 36,
                height: 36,
                backgroundColor: '#3f1d1d',
                color: '#fca5a5',
                fontSize: 18,
                flexShrink: 0,
              }}
              aria-hidden="true"
            >
              !
            </span>
            <h2 className="text-lg font-semibold" style={{ color: '#f8fafc' }}>
              Something went wrong
            </h2>
          </div>

          <p
            className="text-sm mb-5 break-words whitespace-pre-wrap font-mono"
            style={{ color: '#fca5a5' }}
          >
            {message}
          </p>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={this.reset}
              className="rounded-md px-4 py-2 text-sm font-medium"
              style={{ backgroundColor: '#3b82f6', color: '#ffffff' }}
            >
              Try again
            </button>
            <Link
              to="/"
              onClick={this.reset}
              className="rounded-md px-4 py-2 text-sm font-medium"
              style={{
                backgroundColor: 'transparent',
                color: '#93c5fd',
                border: '1px solid #1e3a8a',
              }}
            >
              Go to Dashboard
            </Link>
          </div>
        </div>
      </div>
    )
  }
}
```

=== FILE: web/src/App.tsx ===
```tsx
import { useState, useEffect, useRef, useCallback } from 'react'
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom'
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
import BuildConsole from './pages/BuildConsole'
import Organization from './pages/settings/Organization'
import ProductBacklog from './pages/ProductBacklog'
import CDSCompliance from './pages/CDSCompliance'
import RegulatoryCompliance from './pages/RegulatoryCompliance'
import AgentGym from './pages/AgentGym'
import SafetyAnalysis from './pages/SafetyAnalysis'
import KnowledgeBrowser from './pages/KnowledgeBrowser'
import SkillsTools from './pages/SkillsTools'
import CodeExecution from './pages/CodeExecution'
import Chat from './pages/Chat'
import Preflight from './pages/Preflight'
import Orchestrator from './pages/Orchestrator'
import Constitution from './pages/Constitution'
import ErrorBoundary from './components/ErrorBoundary'
import RouteErrorBoundary from './components/ui/ErrorBoundary'
import OfflineBanner from './components/OfflineBanner'
import ThemeProvider from './components/theme/ThemeProvider'
import { AuthProvider } from './context/AuthContext'
import { UserPrefsProvider } from './context/UserPrefsContext'
import { ChatProvider } from './context/ChatContext'
import { ToastProvider } from './context/ToastContext'
import ToastContainer from './components/ui/ToastContainer'

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
  const location = useLocation()

  // Wrap a page element in a route-level error boundary. The current path is
  // used as the reset key so navigating to another route clears any error.
  const boundary = (element: React.ReactNode) => (
    <RouteErrorBoundary resetKey={location.pathname}>{element}</RouteErrorBoundary>
  )

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
      <div className="flex h-screen overflow-hidden" style={{ backgroundColor: '#0a0a0c' }}>
        <Sidebar />
        <SidebarDivider />
        <div className="flex flex-col flex-1 overflow-hidden">
          <Header onOpenPalette={() => setPaletteOpen(true)} />
          <main className="flex-1 overflow-y-auto p-5 sage-page-enter" style={{ backgroundColor: '#0f0f11' }}>
            <Routes>
              <Route path="/"             element={boundary(<Dashboard />)} />
              <Route path="/agents"       element={boundary(<Agents />)} />
              <Route path="/analyst"      element={boundary(<Analyst />)} />
              <Route path="/developer"    element={boundary(<Developer />)} />
              <Route path="/audit"        element={boundary(<AuditLog />)} />
              <Route path="/monitor"      element={boundary(<Monitor />)} />
              <Route path="/improvements" element={boundary(<Improvements />)} />
              <Route path="/llm"          element={boundary(<LLMSettings />)} />
              <Route path="/settings"     element={boundary(<Settings />)} />
              <Route path="/yaml-editor"   element={boundary(<YamlEditor />)} />
              <Route path="/live-console"  element={boundary(<LiveConsole />)} />
              <Route path="/onboarding"     element={boundary(<Onboarding />)} />
              <Route path="/integrations"  element={boundary(<Integrations />)} />
              <Route path="/queue"          element={boundary(<Queue />)} />
              <Route path="/access-control" element={boundary(<AccessControl />)} />
              <Route path="/costs"          element={boundary(<Costs />)} />
              <Route path="/workflows"      element={boundary(<Workflows />)} />
              <Route path="/approvals"      element={boundary(<Approvals />)} />
              <Route path="/goals"          element={boundary(<Goals />)} />
              <Route path="/org-graph"      element={boundary(<OrgGraph />)} />
              <Route path="/issues"         element={boundary(<Issues />)} />
              <Route path="/activity"       element={boundary(<Activity />)} />
              <Route path="/knowledge"      element={boundary(<KnowledgeBrowser />)} />
              <Route path="/guide"          element={boundary(<Guide />)} />
              <Route path="/build"         element={boundary(<BuildConsole />)} />
              <Route path="/product-backlog" element={boundary(<ProductBacklog />)} />
              <Route path="/cds-compliance" element={boundary(<CDSCompliance />)} />
              <Route path="/regulatory" element={boundary(<RegulatoryCompliance />)} />
              <Route path="/gym"            element={boundary(<AgentGym />)} />
              <Route path="/safety"         element={boundary(<SafetyAnalysis />)} />
              <Route path="/skills"         element={boundary(<SkillsTools />)} />
              <Route path="/code"           element={boundary(<CodeExecution />)} />
              <Route path="/chat"           element={boundary(<Chat />)} />
              <Route path="/settings/organization" element={boundary(<Organization />)} />
              <Route path="/preflight"    element={boundary(<Preflight />)} />
              <Route path="/orchestrator" element={boundary(<Orchestrator />)} />
              <Route path="/constitution" element={boundary(<Constitution />)} />
            </Routes>
          </main>
        </div>
      </div>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      <TourOverlay />
      <LLMDisconnectedBanner />
      <ChatPanel />
      <OfflineBanner />
      <ToastContainer />
    </>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
    <BrowserRouter>
      <AuthProvider>
        <UserPrefsProvider>
          <ThemeProvider>
            <TourProvider>
              <ChatProvider>
                <ToastProvider>
                  <AppShell />
                </ToastProvider>
              </ChatProvider>
            </TourProvider>
          </ThemeProvider>
        </UserPrefsProvider>
      </AuthProvider>
    </BrowserRouter>
    </ErrorBoundary>
  )
}
```

---

## Iteration History

**Iter 1** — score 9.5 pass=True  
Feedback:   

