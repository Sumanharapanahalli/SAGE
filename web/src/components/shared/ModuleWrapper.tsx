import { useState } from 'react'
import { Lightbulb, Info, X } from 'lucide-react'
import { MODULE_REGISTRY, getModuleAccess } from '../../registry/modules'
import FeatureRequestPanel from './FeatureRequestPanel'

interface Props {
  moduleId: string
  children: React.ReactNode
}

/**
 * ModuleWrapper
 *
 * Wraps every page with:
 *  - A thin header showing module name + version
 *  - An info toggle (current features + improvement ideas)
 *  - A "💡 Request Improvement" button (access-controlled)
 *  - The slide-in FeatureRequestPanel
 *
 * This makes every module independently improvable from the UI itself.
 */
export default function ModuleWrapper({ moduleId, children }: Props) {
  const [showInfo, setShowInfo] = useState(false)
  const [showPanel, setShowPanel] = useState(false)

  const module = MODULE_REGISTRY[moduleId]
  const access = getModuleAccess()

  if (!module) return <>{children}</>

  return (
    <div className="relative">
      {/* ── Module strip ─────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-gray-400 bg-gray-100 px-2 py-0.5 rounded select-none">
            {module.name} <span className="text-gray-300">v{module.version}</span>
          </span>
          <button
            onClick={() => setShowInfo((v) => !v)}
            className="text-gray-400 hover:text-gray-600 transition-colors"
            title="Module info & improvement ideas"
          >
            {showInfo ? <X size={13} /> : <Info size={13} />}
          </button>
        </div>

        {access.canRequest && (
          <button
            onClick={() => setShowPanel(true)}
            className="flex items-center gap-1.5 text-xs text-amber-600 bg-amber-50 hover:bg-amber-100 border border-amber-200 px-3 py-1.5 rounded-lg transition-colors font-medium"
            title="Suggest an improvement to this module"
          >
            <Lightbulb size={13} />
            Request Improvement
          </button>
        )}
      </div>

      {/* ── Info panel ───────────────────────────────────────────────── */}
      {showInfo && (
        <div className="mb-5 bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm animate-in slide-in-from-top-2">
          <div className="font-semibold text-blue-800 mb-0.5">{module.name}</div>
          <p className="text-blue-700 text-xs mb-3">{module.description}</p>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-xs font-semibold text-blue-600 uppercase tracking-wide mb-1">
                Current Features
              </div>
              <ul className="space-y-0.5">
                {module.features.map((f, i) => (
                  <li key={i} className="text-xs text-blue-700 flex items-start gap-1">
                    <span className="text-blue-400 mt-0.5">✓</span> {f}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <div className="text-xs font-semibold text-blue-600 uppercase tracking-wide mb-1">
                Improvement Ideas
              </div>
              <ul className="space-y-0.5">
                {module.improvementHints.map((h, i) => (
                  <li key={i} className="text-xs text-blue-600 flex items-start gap-1">
                    <span className="text-blue-300 mt-0.5">→</span>
                    {access.canRequest ? (
                      <button
                        className="text-left hover:text-blue-900 hover:underline"
                        onClick={() => { setShowPanel(true); setShowInfo(false) }}
                      >
                        {h}
                      </button>
                    ) : (
                      <span>{h}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* ── Page content ─────────────────────────────────────────────── */}
      {children}

      {/* ── Slide-in improvement panel ───────────────────────────────── */}
      {showPanel && (
        <FeatureRequestPanel
          module={module}
          onClose={() => setShowPanel(false)}
        />
      )}
    </div>
  )
}
