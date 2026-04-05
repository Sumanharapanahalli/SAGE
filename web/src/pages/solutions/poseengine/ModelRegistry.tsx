import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { runAgent } from '../../../api/client'
import { Box, Loader2, CheckCircle2, Clock, Archive, Upload, Cpu } from 'lucide-react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface ModelEntry {
  name: string
  version: string
  framework: string
  format: string
  accuracy: string
  size: string
  status: 'training' | 'exported' | 'deployed' | 'retired'
  lastUpdated: string
}

// Placeholder models — in production these would come from an API
const PLACEHOLDER_MODELS: ModelEntry[] = [
  { name: 'PoseNet-HRNet-W48', version: 'v3.2.1', framework: 'PyTorch', format: 'ONNX → TFLite', accuracy: 'mAP 0.847', size: '142 MB', status: 'deployed', lastUpdated: '2026-03-10' },
  { name: 'PoseNet-HRNet-W48', version: 'v3.3.0-rc1', framework: 'PyTorch', format: 'ONNX', accuracy: 'mAP 0.862', size: '148 MB', status: 'exported', lastUpdated: '2026-03-12' },
  { name: 'PoseNet-Lite-MobileV3', version: 'v2.1.0', framework: 'PyTorch', format: 'TFLite + CoreML', accuracy: 'mAP 0.791', size: '18 MB', status: 'deployed', lastUpdated: '2026-02-28' },
  { name: 'PoseNet-ViTPose-B', version: 'v1.0.0', framework: 'PyTorch', format: 'ONNX', accuracy: 'mAP 0.873', size: '340 MB', status: 'training', lastUpdated: '2026-03-11' },
  { name: 'PoseNet-HRNet-W32', version: 'v2.4.3', framework: 'PyTorch', format: 'TFLite', accuracy: 'mAP 0.823', size: '98 MB', status: 'retired', lastUpdated: '2026-01-15' },
]

const STATUS_CONFIG: Record<string, { icon: typeof CheckCircle2; color: string; bg: string }> = {
  training:  { icon: Loader2,      color: 'text-blue-600',   bg: 'bg-blue-50 border-blue-200' },
  exported:  { icon: Upload,       color: 'text-amber-600',  bg: 'bg-amber-50 border-amber-200' },
  deployed:  { icon: CheckCircle2, color: 'text-orange-600',  bg: 'bg-orange-50 border-orange-200' },
  retired:   { icon: Archive,      color: 'text-gray-500',   bg: 'bg-gray-50 border-gray-200' },
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function ModelRegistry() {
  const [selectedModel, setSelectedModel] = useState<ModelEntry | null>(null)
  const [analysisResult, setAnalysisResult] = useState<string | null>(null)

  const analyzeMutation = useMutation({
    mutationFn: (model: ModelEntry) =>
      runAgent('ml_engineer', `Evaluate this model for production readiness: ${model.name} ${model.version}. Framework: ${model.framework}, Format: ${model.format}, Accuracy: ${model.accuracy}, Size: ${model.size}, Status: ${model.status}`,
        `Current production model accuracy threshold is mAP >= 0.80 for full models and mAP >= 0.75 for lite/mobile models. Maximum mobile model size is 25MB for TFLite.`),
    onSuccess: (data) => setAnalysisResult(data.analysis),
  })

  const statusFilter = ['all', 'training', 'exported', 'deployed', 'retired'] as const
  const [filter, setFilter] = useState<string>('all')
  const filtered = filter === 'all' ? PLACEHOLDER_MODELS : PLACEHOLDER_MODELS.filter(m => m.status === filter)

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h2 className="text-xl font-semibold text-gray-800">Model Registry</h2>
        <p className="text-sm text-gray-500 mt-0.5">Track model versions, export formats, and deployment status</p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {(['training', 'exported', 'deployed', 'retired'] as const).map(status => {
          const cfg = STATUS_CONFIG[status]
          const Icon = cfg.icon
          const count = PLACEHOLDER_MODELS.filter(m => m.status === status).length
          return (
            <button
              key={status}
              onClick={() => setFilter(f => f === status ? 'all' : status)}
              className={`rounded-lg border p-3 text-left transition-colors ${
                filter === status ? cfg.bg + ' border-2' : 'bg-white border-gray-200 hover:bg-gray-50'
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <Icon size={14} className={cfg.color + (status === 'training' ? ' animate-spin' : '')} />
                <span className="text-xs font-medium text-gray-500 uppercase">{status}</span>
              </div>
              <div className="text-2xl font-bold text-gray-800">{count}</div>
            </button>
          )
        })}
      </div>

      {/* Model list */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
        <div className="px-5 py-3 bg-gray-50 border-b border-gray-100 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-600">
            {filter === 'all' ? 'All Models' : `${filter.charAt(0).toUpperCase() + filter.slice(1)} Models`}
            <span className="text-gray-400 font-normal ml-2">({filtered.length})</span>
          </h3>
          <div className="flex gap-1">
            {statusFilter.map(s => (
              <button
                key={s}
                onClick={() => setFilter(s)}
                className={`text-xs px-2 py-1 rounded transition-colors ${
                  filter === s ? 'bg-purple-100 text-purple-700 font-medium' : 'text-gray-500 hover:bg-gray-100'
                }`}
              >
                {s === 'all' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
        </div>

        <div className="divide-y divide-gray-100">
          {filtered.map((model, i) => {
            const cfg = STATUS_CONFIG[model.status]
            const Icon = cfg.icon
            const isSelected = selectedModel === model
            return (
              <div
                key={`${model.name}-${model.version}`}
                className={`px-5 py-4 hover:bg-gray-50 cursor-pointer transition-colors ${isSelected ? 'bg-purple-50' : ''}`}
                onClick={() => setSelectedModel(isSelected ? null : model)}
              >
                <div className="flex items-center gap-4">
                  <Box size={20} className="text-purple-400 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-800">{model.name}</span>
                      <span className="text-xs font-mono text-gray-400">{model.version}</span>
                      <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full border ${cfg.bg}`}>
                        <Icon size={10} className={cfg.color + (model.status === 'training' ? ' animate-spin' : '')} />
                        {model.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                      <span>{model.framework}</span>
                      <span className="text-gray-300">|</span>
                      <span>{model.format}</span>
                      <span className="text-gray-300">|</span>
                      <span className="font-medium text-purple-600">{model.accuracy}</span>
                      <span className="text-gray-300">|</span>
                      <span>{model.size}</span>
                    </div>
                  </div>
                  <span className="text-xs text-gray-400 shrink-0">{model.lastUpdated}</span>
                </div>

                {/* Expanded detail */}
                {isSelected && (
                  <div className="mt-3 pt-3 border-t border-gray-100 space-y-3">
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                      <div><span className="text-gray-500">Framework:</span> <span className="font-medium">{model.framework}</span></div>
                      <div><span className="text-gray-500">Export:</span> <span className="font-medium">{model.format}</span></div>
                      <div><span className="text-gray-500">Accuracy:</span> <span className="font-medium text-purple-600">{model.accuracy}</span></div>
                      <div><span className="text-gray-500">Size:</span> <span className="font-medium">{model.size}</span></div>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={(e) => { e.stopPropagation(); analyzeMutation.mutate(model) }}
                        disabled={analyzeMutation.isPending}
                        className="flex items-center gap-1.5 text-xs bg-purple-600 hover:bg-purple-700 disabled:opacity-50
                                   text-white px-3 py-1.5 rounded-lg transition-colors"
                      >
                        <Cpu size={12} />
                        {analyzeMutation.isPending ? 'Analyzing...' : 'AI Readiness Check'}
                      </button>
                    </div>
                    {analysisResult && isSelected && (
                      <div className="bg-purple-50 border border-purple-200 rounded-lg p-3 text-xs text-purple-800 whitespace-pre-wrap">
                        {analysisResult}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Info */}
      <div className="bg-purple-50 border border-purple-200 rounded-xl p-4 text-xs text-purple-700 space-y-1">
        <p className="font-semibold">Model Registry</p>
        <p>Models shown here are placeholders. Connect to your MLflow / WandB / model storage to populate automatically.</p>
        <p>Use the <strong>AI Readiness Check</strong> to evaluate any model against production requirements.</p>
      </div>
    </div>
  )
}
