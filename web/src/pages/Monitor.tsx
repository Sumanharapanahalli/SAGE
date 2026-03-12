import { useQuery } from '@tanstack/react-query'
import { fetchMonitorStatus } from '../api/client'
import MonitorStatusPanel from '../components/monitor/MonitorStatusPanel'
import ModuleWrapper from '../components/shared/ModuleWrapper'
import { Loader2 } from 'lucide-react'

export default function Monitor() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['monitor'],
    queryFn: fetchMonitorStatus,
    refetchInterval: 10_000,
  })

  if (isLoading) return (
    <div className="flex items-center justify-center h-48 text-gray-400 gap-2">
      <Loader2 className="animate-spin" size={18} /> Loading monitor status...
    </div>
  )

  if (isError || !data) return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 text-red-500 text-sm">
      Failed to fetch monitor status. Is the FastAPI server running?
    </div>
  )

  return (
    <ModuleWrapper moduleId="monitor">
      <MonitorStatusPanel data={data} />
    </ModuleWrapper>
  )
}
