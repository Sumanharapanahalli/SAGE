import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { fetchAudit, analyzeLog, type AnalysisResponse, type AuditEntry } from '../../../api/client'
import { Loader2, Play, TrendingUp, Target, Zap, AlertTriangle } from 'lucide-react'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function extractMetrics(text: string): Record<string, string> {
  const metrics: Record<string, string> = {}
  const patterns = [
    /(?:loss|train_loss)\s*[:=]\s*([\d.]+)/i,
    /(?:val_loss)\s*[:=]\s*([\d.]+)/i,
    /(?:mAP|map)\s*[:=]\s*([\d.]+)/i,
    /(?:accuracy|acc)\s*[:=]\s*([\d.]+)/i,
    /(?:epoch)\s*[:=]\s*(\d+)/i,
    /(?:lr|learning.rate)\s*[:=]\s*([\d.eE+-]+)/i,
    /(?:fps|FPS)\s*[:=]\s*([\d.]+)/i,
    /(?:OKS)\s*[:=]\s*([\d.]+)/i,
    /(?:PCKh)\s*[:=]\s*([\d.]+)/i,
  ]
  const labels = ['Loss', 'Val Loss', 'mAP', 'Accuracy', 'Epoch', 'Learning Rate', 'FPS', 'OKS', 'PCKh']
  patterns.forEach((pat, i) => {
    const m = text.match(pat)
    if (m) metrics[labels[i]] = m[1]
  })
  return metrics
}

function MetricCard({ label, value, icon: Icon, color }: {
  label: string; value: string; icon: typeof TrendingUp; color: string
}) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="flex items-center gap-2 mb-1">
        <Icon size={14} className={color} />
        <span className="text-xs font-medium text-gray-500 uppercase">{label}</span>
      </div>
      <div className="text-2xl font-bold text-gray-800 tabular-nums">{value}</div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function TrainingRuns() {
  const [logInput, setLogInput] = useState('')
  const [result, setResult] = useState<AnalysisResponse | null>(null)
  const [parsedMetrics, setParsedMetrics] = useState<Record<string, string>>({})

  const { data: auditData, isLoading } = useQuery({
    queryKey: ['audit-training', 0],
    queryFn: () => fetchAudit(50, 0),
    refetchInterval: 30_000,
  })

  const analyzeMutation = useMutation({
    mutationFn: () => analyzeLog(logInput),
    onSuccess: (data) => {
      setResult(data)
      setParsedMetrics(extractMetrics(logInput))
    },
  })

  // Filter audit entries for ML-related actions
  const trainingEntries = (auditData?.entries ?? []).filter((e: AuditEntry) =>
    /ANALYZE|TRAINING|MODEL|ML|INFERENCE/i.test(e.action_type)
  )

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-800">Training Runs</h2>
          <p className="text-sm text-gray-500 mt-0.5">Analyze ML training logs, track metrics, and monitor model performance</p>
        </div>
      </div>

      {/* Quick metrics strip (populated after analysis) */}
      {Object.keys(parsedMetrics).length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 gap-3">
          {parsedMetrics['Epoch'] && <MetricCard label="Epoch" value={parsedMetrics['Epoch']} icon={Play} color="text-blue-500" />}
          {parsedMetrics['Loss'] && <MetricCard label="Train Loss" value={parsedMetrics['Loss']} icon={TrendingUp} color="text-red-500" />}
          {parsedMetrics['Val Loss'] && <MetricCard label="Val Loss" value={parsedMetrics['Val Loss']} icon={TrendingUp} color="text-orange-500" />}
          {parsedMetrics['mAP'] && <MetricCard label="mAP" value={parsedMetrics['mAP']} icon={Target} color="text-green-500" />}
          {parsedMetrics['Accuracy'] && <MetricCard label="Accuracy" value={parsedMetrics['Accuracy']} icon={Target} color="text-green-500" />}
          {parsedMetrics['FPS'] && <MetricCard label="FPS" value={parsedMetrics['FPS']} icon={Zap} color="text-purple-500" />}
          {parsedMetrics['OKS'] && <MetricCard label="OKS" value={parsedMetrics['OKS']} icon={Target} color="text-teal-500" />}
          {parsedMetrics['Learning Rate'] && <MetricCard label="LR" value={parsedMetrics['Learning Rate']} icon={TrendingUp} color="text-gray-500" />}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Training log input */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Analyze Training Output</h3>
          <textarea
            className="w-full h-48 border border-gray-200 rounded-lg p-3 text-sm font-mono resize-none
                       focus:outline-none focus:ring-2 focus:ring-purple-500"
            placeholder={`Paste training log output here, e.g.:\n\nEpoch 45/100\ntrain_loss: 0.0234  val_loss: 0.0312\nmAP: 0.847  OKS: 0.912\nlr: 0.0001  fps: 28.4`}
            value={logInput}
            onChange={e => setLogInput(e.target.value)}
          />
          {analyzeMutation.isError && (
            <p className="text-sm text-red-500 mt-1">{String((analyzeMutation.error as Error)?.message)}</p>
          )}
          <button
            disabled={analyzeMutation.isPending || !logInput.trim()}
            onClick={() => analyzeMutation.mutate()}
            className="mt-3 flex items-center gap-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-50
                       text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            {analyzeMutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
            {analyzeMutation.isPending ? 'Analyzing...' : 'Analyze Training Log'}
          </button>
        </div>

        {/* Analysis result */}
        <div className="space-y-4">
          {result ? (
            <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-gray-700">Analysis Result</h3>
                <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                  result.severity === 'RED' ? 'bg-red-100 text-red-700' :
                  result.severity === 'AMBER' ? 'bg-amber-100 text-amber-700' :
                  'bg-green-100 text-green-700'
                }`}>{result.severity}</span>
              </div>
              <div>
                <div className="text-xs font-medium text-gray-500 mb-1">Root Cause</div>
                <p className="text-sm text-gray-800">{result.root_cause_hypothesis}</p>
              </div>
              <div>
                <div className="text-xs font-medium text-gray-500 mb-1">Recommendation</div>
                <p className="text-sm text-gray-800">{result.recommended_action}</p>
              </div>
              <div className="text-xs text-gray-400 pt-2 border-t border-gray-100">
                Trace: {result.trace_id}
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-dashed border-gray-300 p-8 flex flex-col items-center justify-center text-gray-400 text-sm gap-2">
              <TrendingUp size={24} />
              <span>Training analysis results will appear here</span>
            </div>
          )}

          {/* Training tips */}
          <div className="bg-purple-50 border border-purple-200 rounded-xl p-4 text-xs text-purple-700 space-y-1">
            <p className="font-semibold">Supported metrics:</p>
            <p>loss, val_loss, mAP, accuracy, epoch, learning_rate, fps, OKS, PCKh</p>
            <p className="text-purple-500 mt-1">Paste raw training output — metrics are extracted automatically.</p>
          </div>
        </div>
      </div>

      {/* Recent training-related audit entries */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Recent Training Activity</h3>
        {isLoading ? (
          <div className="flex items-center gap-2 text-gray-400 text-sm py-4">
            <Loader2 size={16} className="animate-spin" /> Loading...
          </div>
        ) : trainingEntries.length === 0 ? (
          <p className="text-sm text-gray-400 py-4">No training-related activity yet. Analyze a training log to get started.</p>
        ) : (
          <div className="divide-y divide-gray-100">
            {trainingEntries.slice(0, 10).map((entry: AuditEntry) => (
              <div key={entry.id} className="py-2.5 flex items-center gap-3">
                <span className="text-xs font-mono text-gray-400 shrink-0">
                  {new Date(entry.timestamp).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                </span>
                <span className="text-xs font-medium text-purple-600 bg-purple-50 px-2 py-0.5 rounded shrink-0">
                  {entry.action_type}
                </span>
                <span className="text-sm text-gray-600 truncate">{entry.input_context.slice(0, 100)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
