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
// Solution-specific pages — organized by solution name
import TrainingRuns from './pages/solutions/poseengine/TrainingRuns'
import ModelRegistry from './pages/solutions/poseengine/ModelRegistry'
import DeviceFleet from './pages/solutions/dfs/DeviceFleet'
import SerialConsole from './pages/solutions/dfs/SerialConsole'

export default function App() {
  return (
    <BrowserRouter>
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
              <Route path="/yaml-editor"  element={<YamlEditor />} />
              {/* Solution-specific pages */}
              <Route path="/training"     element={<TrainingRuns />} />
              <Route path="/models"       element={<ModelRegistry />} />
              <Route path="/devices"      element={<DeviceFleet />} />
              <Route path="/serial"       element={<SerialConsole />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  )
}
