import { FlaskConical, Box, TrendingUp, Target, Zap, Cpu } from 'lucide-react'

/**
 * PoseEngine-specific dashboard widgets — ML metrics overview,
 * model status summary, and training quick-reference.
 */
export default function PoseEngineDashboard() {
  // In production, these would come from a WandB / MLflow API
  const latestRun = {
    epoch: 45, totalEpochs: 100, trainLoss: 0.0234, valLoss: 0.0312,
    mAP: 0.847, oks: 0.912, fps: 28.4, lr: '1e-4',
  }

  const models = {
    training: 1, exported: 1, deployed: 2, retired: 1,
  }

  const pipelineStatus = {
    ml: 'passed', flutter_android: 'passed', flutter_ios: 'failed', onnx_export: 'running',
  }

  const statusColor = (s: string) =>
    s === 'passed' ? 'bg-green-100 text-green-700' :
    s === 'failed' ? 'bg-red-100 text-red-700' :
    s === 'running' ? 'bg-blue-100 text-blue-700 animate-pulse' :
    'bg-gray-100 text-gray-600'

  return (
    <div className="space-y-4">
      {/* Latest training run */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <FlaskConical size={16} className="text-purple-500" />
          <h3 className="text-sm font-semibold text-gray-700">Latest Training Run</h3>
          <span className="text-xs text-gray-400 ml-auto">Epoch {latestRun.epoch}/{latestRun.totalEpochs}</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-purple-50 rounded-lg p-3 text-center">
            <TrendingUp size={14} className="text-red-500 mx-auto mb-1" />
            <div className="text-lg font-bold text-gray-800 tabular-nums">{latestRun.trainLoss}</div>
            <div className="text-xs text-gray-500">Train Loss</div>
          </div>
          <div className="bg-purple-50 rounded-lg p-3 text-center">
            <TrendingUp size={14} className="text-orange-500 mx-auto mb-1" />
            <div className="text-lg font-bold text-gray-800 tabular-nums">{latestRun.valLoss}</div>
            <div className="text-xs text-gray-500">Val Loss</div>
          </div>
          <div className="bg-purple-50 rounded-lg p-3 text-center">
            <Target size={14} className="text-green-500 mx-auto mb-1" />
            <div className="text-lg font-bold text-gray-800 tabular-nums">{latestRun.mAP}</div>
            <div className="text-xs text-gray-500">mAP</div>
          </div>
          <div className="bg-purple-50 rounded-lg p-3 text-center">
            <Zap size={14} className="text-purple-500 mx-auto mb-1" />
            <div className="text-lg font-bold text-gray-800 tabular-nums">{latestRun.fps}</div>
            <div className="text-xs text-gray-500">FPS</div>
          </div>
        </div>
        {/* Progress bar */}
        <div className="mt-3">
          <div className="flex justify-between text-xs text-gray-400 mb-1">
            <span>Training progress</span>
            <span>{Math.round((latestRun.epoch / latestRun.totalEpochs) * 100)}%</span>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div className="h-full bg-purple-500 rounded-full transition-all" style={{ width: `${(latestRun.epoch / latestRun.totalEpochs) * 100}%` }} />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Model status */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <div className="flex items-center gap-2 mb-3">
            <Box size={16} className="text-purple-500" />
            <h3 className="text-sm font-semibold text-gray-700">Model Registry</h3>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(models).map(([status, count]) => (
              <div key={status} className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2">
                <span className="text-xs text-gray-600 capitalize">{status}</span>
                <span className="text-sm font-bold text-gray-800">{count}</span>
              </div>
            ))}
          </div>
          <a href="/models" className="block text-xs text-purple-600 hover:text-purple-700 mt-2 font-medium">View all models &rarr;</a>
        </div>

        {/* CI/CD Pipelines */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <div className="flex items-center gap-2 mb-3">
            <Cpu size={16} className="text-purple-500" />
            <h3 className="text-sm font-semibold text-gray-700">CI/CD Pipelines</h3>
          </div>
          <div className="space-y-2">
            {Object.entries(pipelineStatus).map(([name, status]) => (
              <div key={name} className="flex items-center justify-between">
                <span className="text-xs text-gray-600">{name.replace(/_/g, ' ')}</span>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${statusColor(status)}`}>{status}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
