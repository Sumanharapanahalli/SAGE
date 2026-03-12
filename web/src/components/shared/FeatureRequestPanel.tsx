import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { X, Send, Lightbulb, CheckCircle } from 'lucide-react'
import { submitFeatureRequest } from '../../api/client'
import type { ModuleMetadata } from '../../types/module'
import type { Priority } from '../../types/module'

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
 * Slide-in drawer from the right. Pre-filled with the module context.
 * Improvement idea hints are clickable — clicking one pre-fills the title.
 */
export default function FeatureRequestPanel({ module, onClose }: Props) {
  const [title, setTitle]           = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority]     = useState<Priority>('medium')
  const [requestedBy, setRequestedBy] = useState('')
  const [submitted, setSubmitted]   = useState(false)

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
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['feature-requests'] })
      setSubmitted(true)
    },
  })

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/30 z-40"
        onClick={onClose}
        aria-hidden
      />

      {/* Panel */}
      <div className="fixed right-0 top-0 h-full w-[440px] bg-white shadow-2xl z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 bg-amber-50 shrink-0">
          <div className="flex items-center gap-2">
            <Lightbulb size={18} className="text-amber-500" />
            <div>
              <div className="font-semibold text-gray-800 text-sm">Request Improvement</div>
              <div className="text-xs text-amber-600 font-medium">{module.name} module</div>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 transition-colors">
            <X size={20} />
          </button>
        </div>

        {/* Success state */}
        {submitted ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center gap-4">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center">
              <CheckCircle size={32} className="text-green-600" />
            </div>
            <div>
              <div className="font-semibold text-gray-800 mb-1 text-lg">Request Submitted!</div>
              <p className="text-sm text-gray-500 leading-relaxed">
                Your improvement idea for <strong>{module.name}</strong> has been recorded.
                The engineering team will review, plan, and implement it.
              </p>
            </div>
            <button
              onClick={onClose}
              className="mt-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium px-8 py-2.5 rounded-lg transition-colors"
            >
              Done
            </button>
          </div>
        ) : (
          <>
            {/* Form body */}
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {/* Seed hints */}
              <div className="bg-amber-50 border border-amber-200 rounded-xl p-3">
                <div className="text-xs font-semibold text-amber-700 uppercase tracking-wide mb-2">
                  Click an idea to pre-fill
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {module.improvementHints.slice(0, 4).map((hint, i) => (
                    <button
                      key={i}
                      onClick={() => setTitle(hint)}
                      className="text-xs text-amber-700 bg-white border border-amber-200 hover:bg-amber-100 rounded-full px-2.5 py-1 transition-colors text-left"
                    >
                      {hint}
                    </button>
                  ))}
                </div>
              </div>

              {/* Requestor name */}
              <div>
                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1 block">
                  Your name / team <span className="font-normal text-gray-400">(optional)</span>
                </label>
                <input
                  type="text"
                  value={requestedBy}
                  onChange={(e) => setRequestedBy(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"
                  placeholder="e.g. QA Team, Jane D."
                />
              </div>

              {/* Title */}
              <div>
                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1 block">
                  Feature title <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"
                  placeholder="e.g. Add drag-and-drop log file upload"
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
                  className="w-full h-28 border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-amber-400"
                  placeholder="What should it do? Why would it help your workflow?"
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
            </div>

            {/* Footer */}
            <div className="p-5 border-t border-gray-100 shrink-0">
              <button
                disabled={isPending || !title.trim() || !description.trim()}
                onClick={() => mutate()}
                className="w-full flex items-center justify-center gap-2 bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-white font-semibold py-2.5 rounded-lg transition-colors text-sm"
              >
                <Send size={14} />
                {isPending ? 'Submitting…' : 'Submit Improvement Request'}
              </button>
              <p className="text-xs text-gray-400 text-center mt-2">
                Reviewed by engineering → AI plans → implemented in next sprint.
              </p>
            </div>
          </>
        )}
      </div>
    </>
  )
}
