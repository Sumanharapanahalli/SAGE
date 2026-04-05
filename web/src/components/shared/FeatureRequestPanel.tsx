import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { X, Send, Lightbulb, CheckCircle, Layers, Wrench } from 'lucide-react'
import { submitFeatureRequest } from '../../api/client'
import { useProjectConfig } from '../../hooks/useProjectConfig'
import type { ModuleMetadata, Priority, RequestScope } from '../../types/module'

interface Props {
  module: ModuleMetadata
  onClose: () => void
}

const PRIORITY_STYLES: Record<Priority, string> = {
  low:      'bg-gray-600 text-white border-gray-600',
  medium:   'bg-amber-500 text-white border-amber-500',
  high:     'bg-orange-500 text-white border-orange-500',
  critical: 'bg-red-600  text-white border-red-600',
}
const PRIORITY_IDLE = 'bg-white text-gray-500 border-gray-200 hover:border-gray-400'

/**
 * FeatureRequestPanel
 *
 * Slide-in drawer from the right. The user first picks scope:
 *   "solution" — build a feature in their own application
 *   "sage"     — suggest an improvement to the SAGE framework itself
 *
 * This distinction is engraved here so it is impossible to confuse the two backlogs.
 */
export default function FeatureRequestPanel({ module, onClose }: Props) {
  const { data: projectData } = useProjectConfig()
  const projectName = projectData?.name ?? 'your solution'

  const [scope, setScope]             = useState<RequestScope | null>(null)
  const [title, setTitle]             = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority]       = useState<Priority>('medium')
  const [requestedBy, setRequestedBy] = useState('')
  const [submitted, setSubmitted]     = useState(false)

  const qc = useQueryClient()

  const { mutate, isPending, isError, error } = useMutation({
    mutationFn: () =>
      submitFeatureRequest({
        module_id:    module.id,
        module_name:  module.name,
        title:        title.trim(),
        description:  description.trim(),
        priority,
        requested_by: requestedBy.trim() || 'anonymous',
        scope:        scope ?? 'solution',
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['feature-requests'] })
      setSubmitted(true)
    },
  })

  const isSage     = scope === 'sage'
  const headerBg   = isSage ? 'bg-blue-50'  : 'bg-amber-50'
  const headerBorder = isSage ? 'border-blue-200' : 'border-amber-200'
  const accent     = isSage ? 'text-blue-600' : 'text-amber-600'
  const ringColor  = isSage ? 'focus:ring-blue-400' : 'focus:ring-amber-400'
  const btnColor   = isSage
    ? 'bg-blue-600 hover:bg-blue-700'
    : 'bg-amber-500 hover:bg-amber-600'

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-white/30 z-40" onClick={onClose} aria-hidden />

      {/* Panel */}
      <div className="fixed right-0 top-0 h-full w-[460px] bg-white shadow-2xl z-50 flex flex-col">

        {/* Header */}
        <div className={`flex items-center justify-between px-5 py-4 border-b ${headerBorder} ${headerBg} shrink-0`}>
          <div className="flex items-center gap-2">
            <Lightbulb size={18} className={accent} />
            <div>
              <div className="font-semibold text-gray-800 text-sm">
                {scope === null ? 'Request Improvement' : scope === 'solution' ? 'Solution Backlog' : 'SAGE Framework Idea'}
              </div>
              <div className={`text-xs font-medium ${accent}`}>{module.name} module</div>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 transition-colors">
            <X size={20} />
          </button>
        </div>

        {/* Success state */}
        {submitted ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center gap-4">
            <div className="w-16 h-16 bg-orange-100 rounded-full flex items-center justify-center">
              <CheckCircle size={32} className="text-orange-600" />
            </div>
            <div>
              <div className="font-semibold text-gray-800 mb-1 text-lg">
                {scope === 'sage' ? 'SAGE Idea Logged!' : 'Added to Solution Backlog!'}
              </div>
              <p className="text-sm text-gray-500 leading-relaxed">
                {scope === 'sage'
                  ? 'Your SAGE framework idea has been recorded. Consider also opening a GitHub Issue on the SAGE repo so the community can track it.'
                  : `Your feature request for ${projectName} has been added to the solution backlog for planning.`}
              </p>
            </div>
            <button
              onClick={onClose}
              className="mt-2 bg-orange-600 hover:bg-orange-700 text-white text-sm font-medium px-8 py-2.5 rounded-lg transition-colors"
            >
              Done
            </button>
          </div>
        ) : (
          <>
            <div className="flex-1 overflow-y-auto p-5 space-y-4">

              {/* ── SCOPE SELECTOR ── always shown first, most prominent element */}
              <div>
                <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                  What are you improving?
                </div>
                <div className="grid grid-cols-2 gap-3">
                  {/* Solution option */}
                  <button
                    onClick={() => setScope('solution')}
                    className={`flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all text-left ${
                      scope === 'solution'
                        ? 'border-amber-400 bg-amber-50 shadow-sm'
                        : 'border-gray-200 hover:border-amber-300 hover:bg-amber-50/50'
                    }`}
                  >
                    <Layers size={22} className={scope === 'solution' ? 'text-amber-500' : 'text-gray-400'} />
                    <div>
                      <div className="text-xs font-bold text-gray-800">My Solution</div>
                      <div className="text-[11px] text-gray-500 leading-tight mt-0.5">
                        Build a feature in <span className="font-medium text-gray-700">{projectName}</span>
                      </div>
                    </div>
                  </button>

                  {/* SAGE option */}
                  <button
                    onClick={() => setScope('sage')}
                    className={`flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all text-left ${
                      scope === 'sage'
                        ? 'border-blue-400 bg-blue-50 shadow-sm'
                        : 'border-gray-200 hover:border-blue-300 hover:bg-blue-50/50'
                    }`}
                  >
                    <Wrench size={22} className={scope === 'sage' ? 'text-blue-500' : 'text-gray-400'} />
                    <div>
                      <div className="text-xs font-bold text-gray-800">SAGE Framework</div>
                      <div className="text-[11px] text-gray-500 leading-tight mt-0.5">
                        Improve the <span className="font-medium text-gray-700">SAGE platform</span> itself
                      </div>
                    </div>
                  </button>
                </div>

                {scope === 'sage' && (
                  <div className="mt-2 text-[11px] text-blue-600 bg-blue-50 border border-blue-200 rounded-lg px-3 py-2">
                    SAGE ideas are logged here and shared with the community. For visibility, also open a GitHub Issue on the SAGE repo.
                  </div>
                )}
              </div>

              {/* Only show the rest of the form once scope is chosen */}
              {scope !== null && (
                <>
                  {/* Seed hints */}
                  <div className={`border rounded-xl p-3 ${isSage ? 'bg-blue-50 border-blue-200' : 'bg-amber-50 border-amber-200'}`}>
                    <div className={`text-xs font-semibold uppercase tracking-wide mb-2 ${isSage ? 'text-blue-700' : 'text-amber-700'}`}>
                      Click an idea to pre-fill
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {module.improvementHints.slice(0, 4).map((hint, i) => (
                        <button
                          key={i}
                          onClick={() => setTitle(hint)}
                          className={`text-xs border hover:opacity-80 rounded-full px-2.5 py-1 transition-colors text-left ${
                            isSage
                              ? 'text-blue-700 bg-white border-blue-200 hover:bg-blue-100'
                              : 'text-amber-700 bg-white border-amber-200 hover:bg-amber-100'
                          }`}
                        >
                          {hint}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Requestor */}
                  <div>
                    <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1 block">
                      Your name / team <span className="font-normal text-gray-400">(optional)</span>
                    </label>
                    <input
                      type="text"
                      value={requestedBy}
                      onChange={(e) => setRequestedBy(e.target.value)}
                      className={`w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 ${ringColor}`}
                      placeholder="e.g. QA Team, Jane D."
                    />
                  </div>

                  {/* Title */}
                  <div>
                    <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1 block">
                      Title <span className="text-red-400">*</span>
                    </label>
                    <input
                      type="text"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      className={`w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 ${ringColor}`}
                      placeholder={
                        scope === 'sage'
                          ? 'e.g. Add dark mode toggle to the UI'
                          : 'e.g. Add voice pack to Flutter coaching screen'
                      }
                    />
                  </div>

                  {/* Description */}
                  <div>
                    <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1 block">
                      Description <span className="text-red-400">*</span>
                    </label>
                    <textarea
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      className={`w-full h-28 border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 ${ringColor}`}
                      placeholder={
                        scope === 'sage'
                          ? 'What should SAGE do differently? Which users benefit and how?'
                          : 'What should be built in your solution? Why does it matter to your users?'
                      }
                    />
                  </div>

                  {/* Priority */}
                  <div>
                    <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5 block">
                      Priority
                    </label>
                    <div className="grid grid-cols-4 gap-2">
                      {(['low', 'medium', 'high', 'critical'] as Priority[]).map((p) => (
                        <button
                          key={p}
                          onClick={() => setPriority(p)}
                          className={`py-1.5 text-xs font-medium rounded-lg border transition-colors capitalize ${
                            priority === p ? PRIORITY_STYLES[p] : PRIORITY_IDLE
                          }`}
                        >
                          {p}
                        </button>
                      ))}
                    </div>
                  </div>

                  {isError && (
                    <p className="text-xs text-red-500">
                      {String((error as Error)?.message ?? 'Submission failed.')}
                    </p>
                  )}
                </>
              )}
            </div>

            {/* Footer */}
            {scope !== null && (
              <div className="p-5 border-t border-gray-100 shrink-0">
                <button
                  disabled={isPending || !title.trim() || !description.trim()}
                  onClick={() => mutate()}
                  className={`w-full flex items-center justify-center gap-2 disabled:opacity-50 text-white font-semibold py-2.5 rounded-lg transition-colors text-sm ${btnColor}`}
                >
                  <Send size={14} />
                  {isPending ? 'Submitting…' : scope === 'sage' ? 'Log SAGE Idea' : 'Add to Solution Backlog'}
                </button>
                <p className="text-xs text-gray-400 text-center mt-2">
                  {scope === 'sage'
                    ? 'Logged for the SAGE community · Also raise a GitHub Issue for tracking'
                    : 'Added to your solution backlog · AI can generate an implementation plan'}
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </>
  )
}
