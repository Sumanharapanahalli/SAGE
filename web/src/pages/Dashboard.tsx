import { useQuery } from '@tanstack/react-query'
import { fetchHealth, fetchAudit } from '../api/client'
import { useProjectConfig } from '../hooks/useProjectConfig'
import SystemHealthCard from '../components/dashboard/SystemHealthCard'
import ActiveAlertsPanel from '../components/dashboard/ActiveAlertsPanel'
import ErrorTrendChart from '../components/dashboard/ErrorTrendChart'
import ModuleWrapper from '../components/shared/ModuleWrapper'
import { Loader2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

// Dashboard content is fully driven by the solution's project.yaml `dashboard:` section.
// No solution-specific logic lives in this file — add dashboard config to your project.yaml.

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
  const navigate = useNavigate()

  if (healthLoading) return (
    <div className="flex items-center justify-center h-64 text-gray-400 gap-2">
      <Loader2 className="animate-spin" size={20} /> Loading…
    </div>
  )

  // All dashboard content comes from project.yaml's `dashboard:` section
  const dashboardConfig = (projectData as any)?.dashboard ?? {}
  const contextItems: { label: string; description: string }[] = dashboardConfig.context_items ?? []
  const quickActions: { label: string; route: string; description: string }[] = dashboardConfig.quick_actions ?? []
  const contextColor: string = dashboardConfig.context_color ?? 'border-gray-200 bg-gray-50'

  return (
    <ModuleWrapper moduleId="dashboard">
      <div className="space-y-6">
        {/* Domain context card — content from project.yaml dashboard.context_items */}
        {(projectData?.name || contextItems.length > 0) && (
          <div className={`rounded-xl border p-5 ${contextColor}`}>
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-base font-semibold text-gray-800">
                  {projectData?.name ?? 'SAGE Framework'}
                </h3>
                <span className="text-xs text-gray-500">
                  {projectData?.description
                    ? String(projectData.description).slice(0, 80)
                    : projectData?.domain ?? 'General purpose AI agent framework'}
                </span>
              </div>
              {projectData?.version && (
                <span className="text-xs font-medium bg-white/70 px-2.5 py-1 rounded-full text-gray-600">
                  v{projectData.version}
                </span>
              )}
            </div>
            {contextItems.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {contextItems.map((item) => (
                  <div key={item.label} className="bg-white/60 rounded-lg px-3 py-2">
                    <div className="text-xs font-semibold text-gray-600 mb-0.5">{item.label}</div>
                    <div className="text-xs text-gray-500">{item.description}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Quick actions — content from project.yaml dashboard.quick_actions */}
        {quickActions.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-gray-600 mb-2">Quick Actions</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {quickActions.map((action) => (
                <button
                  key={action.label}
                  onClick={() => navigate(action.route)}
                  className="bg-white rounded-lg border border-gray-200 px-4 py-3 hover:bg-gray-50
                             hover:border-gray-300 transition-colors group text-left"
                >
                  <div className="text-sm font-medium text-gray-800 group-hover:text-blue-600">
                    {action.label}
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5">{action.description}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Standard dashboard cards — always rendered, solution-agnostic */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {health && <SystemHealthCard data={health} />}
          <ActiveAlertsPanel entries={audit?.entries ?? []} />
          <ErrorTrendChart entries={audit?.entries ?? []} />
        </div>
      </div>
    </ModuleWrapper>
  )
}
