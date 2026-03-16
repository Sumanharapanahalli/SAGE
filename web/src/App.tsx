import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Sidebar from './components/layout/Sidebar'
import Header from './components/layout/Header'
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
import ThemeProvider from './components/theme/ThemeProvider'
import { AuthProvider } from './context/AuthContext'

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

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
      <ThemeProvider>
      <div className="flex h-screen overflow-hidden bg-gray-50">
        <Sidebar />
        <div className="flex flex-col flex-1 overflow-hidden">
          <Header />
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
            </Routes>
          </main>
        </div>
      </div>
      </ThemeProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
