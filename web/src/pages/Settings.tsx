import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  setActiveModules, patchProjectTheme,
  type BrandingPayload,
} from '../api/client'
import { useProjectConfig } from '../hooks/useProjectConfig'
import { MODULE_REGISTRY } from '../registry/modules'
import {
  Cpu, Bot, Activity, Search, GitMerge, Lightbulb, Target,
  Database, Shield, Network, Zap, Settings as SettingsIcon,
  BarChart2, FileCode2, Layers, Workflow,
} from 'lucide-react'

// Derived from the full module registry so all modules are always toggleable
const ALL_MODULES = Object.values(MODULE_REGISTRY).map(m => ({
  id: m.id,
  label: m.name,
  description: m.description,
}))

const PRESET_ICONS: { name: string; Icon: any }[] = [
  { name: 'Cpu',       Icon: Cpu },
  { name: 'Bot',       Icon: Bot },
  { name: 'Activity',  Icon: Activity },
  { name: 'Search',    Icon: Search },
  { name: 'GitMerge',  Icon: GitMerge },
  { name: 'Lightbulb', Icon: Lightbulb },
  { name: 'Target',    Icon: Target },
  { name: 'Database',  Icon: Database },
  { name: 'Shield',    Icon: Shield },
  { name: 'Network',   Icon: Network },
  { name: 'Zap',       Icon: Zap },
  { name: 'Settings',  Icon: SettingsIcon },
  { name: 'BarChart2', Icon: BarChart2 },
  { name: 'FileCode2', Icon: FileCode2 },
  { name: 'Layers',    Icon: Layers },
  { name: 'Workflow',  Icon: Workflow },
]

const PRESET_ACCENTS = [
  { label: 'Zinc',    value: '#71717a' },
  { label: 'Blue',    value: '#3b82f6' },
  { label: 'Violet',  value: '#7c3aed' },
  { label: 'Emerald', value: '#f97316' },
  { label: 'Rose',    value: '#e11d48' },
  { label: 'Amber',   value: '#f59e0b' },
  { label: 'Cyan',    value: '#06b6d4' },
  { label: 'Orange',  value: '#f97316' },
]

export default function Settings() {
  const navigate = useNavigate()
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

  // Branding state
  const currentTheme = (projectData as any)?.theme ?? {}
  const [brandName,   setBrandName]   = useState('')
  const [brandIcon,   setBrandIcon]   = useState('')
  const [brandAccent, setBrandAccent] = useState('')
  const [brandSaved,  setBrandSaved]  = useState(false)

  // Initialise from project config
  useEffect(() => {
    if (projectData) {
      setBrandName((projectData as any).name ?? '')
      setBrandIcon(currentTheme.icon_name ?? '')
      setBrandAccent(currentTheme.accent ?? '#71717a')
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectData])

  const brandMutation = useMutation({
    mutationFn: (payload: BrandingPayload) => patchProjectTheme(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project-config'] })
      queryClient.invalidateQueries({ queryKey: ['health'] })
      setBrandSaved(true)
      setTimeout(() => setBrandSaved(false), 2500)
    },
  })

  const handleSaveBranding = () => {
    brandMutation.mutate({
      display_name: brandName || undefined,
      icon_name:    brandIcon || undefined,
      accent:       brandAccent || undefined,
    })
  }

  if (isLoading) return <div className="p-6 text-gray-400 text-sm">Loading settings...</div>

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
                  isOn ? 'border-orange-200 bg-orange-50' : 'border-gray-100 bg-gray-50'
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
                    ${isOn ? 'bg-orange-500' : 'bg-gray-300'}
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

                <span className={`text-xs font-medium shrink-0 ${isOn ? 'text-orange-600' : 'text-gray-400'}`}>
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
            className="flex-1 bg-white hover:bg-gray-700 disabled:opacity-40 text-white
                       text-sm font-medium py-2.5 rounded-lg transition-colors"
          >
            {mutation.isPending ? 'Saving...' : saved ? 'Saved' : 'Apply Changes'}
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

      {/* Solution Branding */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
        <div>
          <h3 className="text-sm font-semibold text-gray-700">Solution Branding</h3>
          <p className="text-xs text-gray-400 mt-0.5">
            Customise the display name, icon, and accent color for this solution.
            Changes are written directly to project.yaml.
          </p>
        </div>

        {/* Live preview */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '12px', background: '#f8fafc', border: '1px solid #e2e8f0' }}>
          <div style={{
            width: 36, height: 36, background: brandAccent || '#71717a',
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
          }}>
            {(() => {
              const found = PRESET_ICONS.find(i => i.name === brandIcon)
              return found
                ? <found.Icon size={18} color="#fff" />
                : <span style={{ fontSize: '12px', fontWeight: 700, color: '#fff' }}>{(brandName || 'S').slice(0, 2).toUpperCase()}</span>
            })()}
          </div>
          <div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#0f172a' }}>{brandName || 'Solution Name'}</div>
            <div style={{ fontSize: '11px', color: '#64748b' }}>Preview</div>
          </div>
        </div>

        {/* Display name */}
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Display Name</label>
          <input
            type="text"
            value={brandName}
            onChange={e => setBrandName(e.target.value)}
            placeholder="My Solution"
            className="w-full border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-gray-400"
          />
        </div>

        {/* Icon picker */}
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-2">Icon</label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(8, 1fr)', gap: '6px' }}>
            {PRESET_ICONS.map(({ name, Icon }) => (
              <button
                key={name}
                type="button"
                onClick={() => setBrandIcon(name === brandIcon ? '' : name)}
                title={name}
                style={{
                  padding: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  border: `2px solid ${brandIcon === name ? brandAccent || '#3b82f6' : '#e2e8f0'}`,
                  background: brandIcon === name ? `${brandAccent || '#3b82f6'}15` : 'transparent',
                  cursor: 'pointer',
                }}
              >
                <Icon size={16} color={brandIcon === name ? brandAccent || '#3b82f6' : '#64748b'} />
              </button>
            ))}
          </div>
        </div>

        {/* Accent color */}
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-2">Accent Color</label>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '8px' }}>
            {PRESET_ACCENTS.map(({ label, value }) => (
              <button
                key={value}
                type="button"
                onClick={() => setBrandAccent(value)}
                title={label}
                style={{
                  width: 24, height: 24, background: value, cursor: 'pointer', border: 'none',
                  outline: brandAccent === value ? '3px solid #0f172a' : '2px solid transparent',
                  outlineOffset: 2,
                }}
              />
            ))}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <input
              type="color"
              value={brandAccent || '#71717a'}
              onChange={e => setBrandAccent(e.target.value)}
              style={{ width: 32, height: 32, padding: 0, border: '1px solid #e2e8f0', cursor: 'pointer' }}
            />
            <input
              type="text"
              value={brandAccent}
              onChange={e => setBrandAccent(e.target.value)}
              placeholder="#71717a"
              style={{ border: '1px solid #e2e8f0', padding: '4px 8px', fontSize: '12px', fontFamily: 'monospace', width: '90px' }}
            />
            <span style={{ fontSize: '11px', color: '#94a3b8' }}>Custom hex</span>
          </div>
        </div>

        {brandMutation.isError && (
          <p className="text-sm text-red-600 bg-red-50 px-3 py-2">
            Failed: {(brandMutation.error as Error).message}
          </p>
        )}

        <button
          onClick={handleSaveBranding}
          disabled={brandMutation.isPending}
          className="w-full bg-white hover:bg-gray-700 disabled:opacity-40 text-white text-sm font-medium py-2.5 transition-colors"
        >
          {brandMutation.isPending ? 'Saving...' : brandSaved ? 'Saved' : 'Save Branding'}
        </button>
      </div>

      {/* Organization */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-sm font-semibold text-gray-700">Organization</h3>
            <p className="text-xs text-gray-400 mt-0.5">
              Company mission, vision, and core values. All solution generation is shaped by this context.
            </p>
          </div>
          <button
            onClick={() => navigate('/settings/organization')}
            className="shrink-0 px-4 py-2 bg-white hover:bg-gray-700 text-white text-xs font-medium transition-colors"
          >
            Configure
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
