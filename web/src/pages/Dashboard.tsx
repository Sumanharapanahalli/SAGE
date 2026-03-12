import { useQuery } from '@tanstack/react-query'
import { fetchHealth, fetchAudit } from '../api/client'
import { useProjectConfig } from '../hooks/useProjectConfig'
import SystemHealthCard from '../components/dashboard/SystemHealthCard'
import ActiveAlertsPanel from '../components/dashboard/ActiveAlertsPanel'
import ErrorTrendChart from '../components/dashboard/ErrorTrendChart'
import ModuleWrapper from '../components/shared/ModuleWrapper'
import { Loader2 } from 'lucide-react'
import PoseEngineDashboard from '../components/dashboard/poseengine/PoseEngineDashboard'
import DFSDashboard from '../components/dashboard/dfs/DFSDashboard'

// ---------------------------------------------------------------------------
// Domain-specific dashboard context cards
// ---------------------------------------------------------------------------
const DOMAIN_CARDS: Record<string, { title: string; subtitle: string; items: { label: string; description: string }[]; color: string }> = {
  'medtech': {
    title: 'Medical Device Manufacturing',
    subtitle: 'ISO 13485 Compliant',
    color: 'border-blue-200 bg-blue-50',
    items: [
      { label: 'Compliance', description: 'ISO 13485, IEC 62304, ISO 14971, FDA 21 CFR Part 11' },
      { label: 'Agents', description: 'Quality Engineer, Regulatory Specialist, Risk Engineer, Clinical Engineer' },
      { label: 'Key Focus', description: 'Firmware safety, audit trail integrity, traceability' },
    ],
  },
  'cv-tracking': {
    title: 'Human Tracking & Analytics',
    subtitle: 'GDPR Compliant',
    color: 'border-green-200 bg-green-50',
    items: [
      { label: 'Compliance', description: 'GDPR Article 9, IEEE 730, ISO/IEC 25010' },
      { label: 'Agents', description: 'Privacy Officer, Deployment Engineer, Tracking Analyst, Solutions Architect' },
      { label: 'Key Focus', description: 'Tracking accuracy (MOTA/IDF1), privacy, edge deployment' },
    ],
  },
  'ml-mobile': {
    title: 'ML + Flutter Mobile',
    subtitle: 'Pose Estimation Pipeline',
    color: 'border-purple-200 bg-purple-50',
    items: [
      { label: 'Stack', description: 'PyTorch, ONNX, TFLite/CoreML, Flutter/Dart' },
      { label: 'Agents', description: 'ML Engineer, Mobile Developer, Data Scientist, DevOps Engineer' },
      { label: 'Key Focus', description: 'Model accuracy, inference latency, mobile performance' },
    ],
  },
  'firmware-embedded': {
    title: 'Embedded Firmware',
    subtitle: 'STM32H7 / FreeRTOS',
    color: 'border-orange-200 bg-orange-50',
    items: [
      { label: 'Stack', description: 'STM32H7, FreeRTOS, BLE, Bootloader, J-Link' },
      { label: 'Agents', description: 'Firmware Engineer, Test Engineer, Production Support, Systems Architect' },
      { label: 'Key Focus', description: 'Flash safety, RTOS stability, BLE sync, production triage' },
    ],
  },
  'startup': {
    title: 'Startup Workspace',
    subtitle: 'Full Business Operations',
    color: 'border-indigo-200 bg-indigo-50',
    items: [
      { label: 'Functions', description: 'Product, Marketing, Sales, Legal, Finance, HR, Growth, CS' },
      { label: 'Agents', description: '9 AI roles covering all startup business functions' },
      { label: 'Key Focus', description: 'GTM strategy, unit economics, hiring, compliance' },
    ],
  },
}

// Quick actions per domain
const DOMAIN_ACTIONS: Record<string, { label: string; route: string; description: string }[]> = {
  'medtech': [
    { label: 'Analyze Log', route: '/analyst', description: 'Triage firmware error' },
    { label: 'Review MR', route: '/developer', description: 'IEC 62304 code review' },
    { label: 'Risk Assessment', route: '/agents', description: 'ISO 14971 analysis' },
    { label: 'Audit Trail', route: '/audit', description: 'Compliance records' },
  ],
  'cv-tracking': [
    { label: 'Tracking Log', route: '/analyst', description: 'Analyze accuracy report' },
    { label: 'Privacy Check', route: '/agents', description: 'GDPR compliance review' },
    { label: 'Pipeline Health', route: '/monitor', description: 'Camera & tracking status' },
    { label: 'Review Code', route: '/developer', description: 'CV pipeline review' },
  ],
  'ml-mobile': [
    { label: 'Training Log', route: '/analyst', description: 'Analyze ML metrics' },
    { label: 'Review Code', route: '/developer', description: 'PyTorch / Flutter review' },
    { label: 'ML Architecture', route: '/agents', description: 'Model design advice' },
    { label: 'CI/CD Status', route: '/monitor', description: 'Pipeline monitoring' },
  ],
  'firmware-embedded': [
    { label: 'Crash Log', route: '/analyst', description: 'Firmware error triage' },
    { label: 'Review MR', route: '/developer', description: 'Embedded code review' },
    { label: 'Flash Ops', route: '/agents', description: 'Firmware engineering' },
    { label: 'Monitor', route: '/monitor', description: 'Production alerts' },
  ],
  'startup': [
    { label: 'Product Brief', route: '/agents', description: 'Write a PRD' },
    { label: 'GTM Strategy', route: '/agents', description: 'Go-to-market planning' },
    { label: 'Legal Review', route: '/agents', description: 'Contract analysis' },
    { label: 'Financial Model', route: '/agents', description: 'Unit economics' },
  ],
}

export default function Dashboard() {
  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  })
  const { data: audit } = useQuery({
    queryKey: ['audit', 0],
    queryFn: () => fetchAudit(100, 0),
    refetchInterval: 30_000,
  })
  const { data: projectData } = useProjectConfig()

  if (healthLoading) return (
    <div className="flex items-center justify-center h-64 text-gray-400 gap-2">
      <Loader2 className="animate-spin" size={20} /> Loading…
    </div>
  )

  const domain = projectData?.domain ?? ''
  const domainCard = DOMAIN_CARDS[domain]
  const actions = DOMAIN_ACTIONS[domain] ?? []

  return (
    <ModuleWrapper moduleId="dashboard">
      <div className="space-y-6">
        {/* Domain context card */}
        {domainCard && (
          <div className={`rounded-xl border p-5 ${domainCard.color}`}>
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-base font-semibold text-gray-800">{domainCard.title}</h3>
                <span className="text-xs text-gray-500">{domainCard.subtitle}</span>
              </div>
              {projectData?.name && (
                <span className="text-xs font-medium bg-white/70 px-2.5 py-1 rounded-full text-gray-600">
                  {projectData.name} v{projectData.version}
                </span>
              )}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {domainCard.items.map(item => (
                <div key={item.label} className="bg-white/60 rounded-lg px-3 py-2">
                  <div className="text-xs font-semibold text-gray-600 mb-0.5">{item.label}</div>
                  <div className="text-xs text-gray-500">{item.description}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Quick actions */}
        {actions.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-gray-600 mb-2">Quick Actions</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {actions.map(action => (
                <a
                  key={action.label}
                  href={action.route}
                  className="bg-white rounded-lg border border-gray-200 px-4 py-3 hover:bg-gray-50
                             hover:border-gray-300 transition-colors group"
                >
                  <div className="text-sm font-medium text-gray-800 group-hover:text-blue-600">{action.label}</div>
                  <div className="text-xs text-gray-400 mt-0.5">{action.description}</div>
                </a>
              ))}
            </div>
          </div>
        )}

        {/* Solution-specific widgets */}
        {domain === 'ml-mobile' && <PoseEngineDashboard />}
        {domain === 'firmware-embedded' && <DFSDashboard />}

        {/* Standard dashboard cards */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {health && <SystemHealthCard data={health} />}
          <ActiveAlertsPanel entries={audit?.entries ?? []} />
          <ErrorTrendChart entries={audit?.entries ?? []} />
        </div>
      </div>
    </ModuleWrapper>
  )
}
