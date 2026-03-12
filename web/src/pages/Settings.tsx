import { useState, useEffect } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { setActiveModules } from '../api/client'
import { useProjectConfig } from '../hooks/useProjectConfig'

// All modules that can appear in the sidebar
const ALL_MODULES = [
  { id: 'dashboard',    label: 'Dashboard',    description: 'System health overview and active alerts' },
  { id: 'analyst',      label: 'Analyst',      description: 'Log analysis, proposals, and approvals' },
  { id: 'developer',    label: 'Developer',    description: 'MR creation, review, and pipeline status' },
  { id: 'audit',        label: 'Audit Log',    description: 'Paginated compliance audit trail' },
  { id: 'monitor',      label: 'Monitor',      description: 'Live integration poller status' },
  { id: 'improvements', label: 'Improvements', description: 'Module self-improvement feature requests' },
  { id: 'llm',          label: 'LLM',          description: 'LLM provider switcher and session usage' },
  { id: 'yaml-editor',  label: 'Config Editor',description: 'Edit solution YAML configs directly in the browser' },
]

export default function Settings() {
  const queryClient = useQueryClient()
  const { data: projectData, isLoading } = useProjectConfig()

  const [enabled, setEnabled] = useState<Set<string>>(new Set())
  const [saved, setSaved] = useState(false)

  // Initialise toggles from project config
  useEffect(() => {
    if (projectData) {
      const active = projectData.active_modules
      // Empty list = all visible (framework default); pre-check all in that case
      setEnabled(
        active.length === 0
          ? new Set(ALL_MODULES.map(m => m.id))
          : new Set(active)
      )
    }
  }, [projectData])

  const mutation = useMutation({
    mutationFn: (modules: string[]) => setActiveModules(modules),
    onSuccess: () => {
      // Invalidate project config so sidebar re-renders
      queryClient.invalidateQueries({ queryKey: ['project-config'] })
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    },
  })

  const toggle = (id: string) => {
    setEnabled(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        // Don't allow disabling the last module
        if (next.size <= 1) return prev
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const handleSave = () => {
    mutation.mutate(Array.from(enabled))
  }

  const handleReset = () => {
    setEnabled(new Set(ALL_MODULES.map(m => m.id)))
  }

  if (isLoading) return <div className="p-6 text-gray-400 text-sm">Loading settings…</div>

  return (
    <div className="space-y-6 max-w-2xl">
      <h2 className="text-xl font-semibold text-gray-800">Settings</h2>

      {/* Module visibility */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
        <div>
          <h3 className="text-sm font-semibold text-gray-700">Module Visibility</h3>
          <p className="text-xs text-gray-400 mt-0.5">
            Choose which modules appear in the sidebar for the active solution.
            Changes are in-memory — reset on backend restart or solution switch.
          </p>
        </div>

        <div className="space-y-2">
          {ALL_MODULES.map(mod => {
            const isOn = enabled.has(mod.id)
            const isLast = enabled.size <= 1 && isOn
            return (
              <label
                key={mod.id}
                className={`flex items-center gap-4 p-3 rounded-lg border transition-colors cursor-pointer ${
                  isOn ? 'border-green-200 bg-green-50' : 'border-gray-100 bg-gray-50'
                } ${isLast ? 'opacity-50 cursor-not-allowed' : 'hover:border-gray-200'}`}
              >
                {/* Toggle switch */}
                <button
                  type="button"
                  role="switch"
                  aria-checked={isOn}
                  disabled={isLast}
                  onClick={() => toggle(mod.id)}
                  className={`relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent
                    transition-colors focus:outline-none
                    ${isOn ? 'bg-green-500' : 'bg-gray-300'}
                    ${isLast ? 'cursor-not-allowed' : 'cursor-pointer'}`}
                >
                  <span
                    className={`pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow
                      transform transition-transform ${isOn ? 'translate-x-4' : 'translate-x-0'}`}
                  />
                </button>

                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-gray-800">{mod.label}</span>
                  <p className="text-xs text-gray-400 truncate">{mod.description}</p>
                </div>

                <span className={`text-xs font-medium shrink-0 ${isOn ? 'text-green-600' : 'text-gray-400'}`}>
                  {isOn ? 'Visible' : 'Hidden'}
                </span>
              </label>
            )
          })}
        </div>

        {mutation.isError && (
          <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">
            Failed to save: {(mutation.error as Error).message}
          </p>
        )}

        <div className="flex gap-3 pt-1">
          <button
            onClick={handleSave}
            disabled={mutation.isPending}
            className="flex-1 bg-gray-900 hover:bg-gray-700 disabled:opacity-40 text-white
                       text-sm font-medium py-2.5 rounded-lg transition-colors"
          >
            {mutation.isPending ? 'Saving…' : saved ? 'Saved ✓' : 'Apply Changes'}
          </button>
          <button
            onClick={handleReset}
            className="px-4 py-2.5 rounded-lg border border-gray-200 text-sm text-gray-600
                       hover:bg-gray-50 transition-colors"
          >
            Show All
          </button>
        </div>
      </div>

      {/* Info */}
      <div className="text-xs text-gray-400 bg-gray-50 rounded-lg p-4 space-y-1">
        <p><strong>Note:</strong> Module visibility is stored in memory only. To make it permanent, edit <code>active_modules</code> in your solution's <code>project.yaml</code>.</p>
        <p>Solutions with an empty <code>active_modules</code> list show all modules by default.</p>
      </div>
    </div>
  )
}
