import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Play, Pause, Square, Target, Clock, TrendingUp, Beaker,
  Users, Hash, Activity, AlertCircle, Plus
} from 'lucide-react'
import { fetchEvolutionExperiments, getEvolutionStatus, EvolutionExperiment } from '../api/client'
import ExperimentControls from '../components/evolution/ExperimentControls'
import FitnessChart from '../components/evolution/FitnessChart'

function formatDuration(createdAt: string): string {
  const now = new Date()
  const created = new Date(createdAt)
  const diffMs = now.getTime() - created.getTime()
  const hours = Math.floor(diffMs / (1000 * 60 * 60))
  const minutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60))

  if (hours > 0) {
    return `${hours}h ${minutes}m`
  }
  return `${minutes}m`
}

function getStatusIcon(status: string) {
  switch (status) {
    case 'running': return <Play className="h-4 w-4 text-green-500" />
    case 'paused': return <Pause className="h-4 w-4 text-yellow-500" />
    case 'complete': return <Target className="h-4 w-4 text-blue-500" />
    case 'failed': return <Square className="h-4 w-4 text-red-500" />
    default: return <Clock className="h-4 w-4 text-gray-500" />
  }
}

function ExperimentList({
  experiments,
  selectedId,
  onSelect,
  onNewExperiment
}: {
  experiments: EvolutionExperiment[]
  selectedId: string | null
  onSelect: (id: string) => void
  onNewExperiment: () => void
}) {
  if (experiments.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center p-6">
        <Beaker className="h-12 w-12 text-gray-400 mb-4" />
        <h3 className="text-lg font-medium text-gray-300 mb-2">No experiments running</h3>
        <p className="text-gray-400 text-sm mb-4">
          Create your first evolution experiment to optimize prompts, code, or build processes
        </p>
        <button
          onClick={onNewExperiment}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
        >
          <Plus className="h-4 w-4" />
          Start New Experiment
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {experiments.map((exp) => (
        <div
          key={exp.experiment_id}
          onClick={() => onSelect(exp.experiment_id)}
          className={`p-4 rounded-lg cursor-pointer transition-colors border-2 ${
            selectedId === exp.experiment_id
              ? 'bg-gray-700 border-blue-500'
              : 'bg-gray-800 border-transparent hover:bg-gray-700'
          }`}
        >
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              {getStatusIcon(exp.status)}
              <span className="font-medium text-gray-200">{exp.experiment_id}</span>
            </div>
            <span className="text-xs text-gray-400">
              {formatDuration(exp.created_at)}
            </span>
          </div>
          <div className="text-sm text-gray-400">
            Gen {exp.current_generation}/{exp.max_generations} • Fitness {exp.best_fitness.toFixed(3)}
          </div>
        </div>
      ))}
    </div>
  )
}

function StatusCard({
  icon: Icon,
  label,
  value,
  color = 'text-gray-300'
}: {
  icon: any
  label: string
  value: string | number
  color?: string
}) {
  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <div className="flex items-center gap-3">
        <Icon className={`h-5 w-5 ${color}`} />
        <div>
          <div className="text-sm text-gray-400">{label}</div>
          <div className={`font-medium ${color}`}>{value}</div>
        </div>
      </div>
    </div>
  )
}

export default function Evolution() {
  const [selectedExperimentId, setSelectedExperimentId] = useState<string | null>(null)
  const [showNewExperiment, setShowNewExperiment] = useState(false)

  // Fetch experiments list every 5 seconds
  const { data: experimentsData, isLoading: experimentsLoading } = useQuery({
    queryKey: ['evolution', 'experiments'],
    queryFn: fetchEvolutionExperiments,
    refetchInterval: 5000,
  })

  // Fetch selected experiment status every 2 seconds
  const { data: statusData } = useQuery({
    queryKey: ['evolution', 'status', selectedExperimentId],
    queryFn: () => selectedExperimentId ? getEvolutionStatus(selectedExperimentId) : null,
    enabled: !!selectedExperimentId,
    refetchInterval: 2000,
  })

  const experiments = experimentsData?.experiments || []
  const selectedExperiment = experiments.find(exp => exp.experiment_id === selectedExperimentId)

  // Auto-select first experiment if none selected
  useEffect(() => {
    if (!selectedExperimentId && experiments.length > 0) {
      setSelectedExperimentId(experiments[0].experiment_id)
    }
  }, [experiments, selectedExperimentId])

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Evolution Experiments</h1>
          <p className="text-gray-400">Genetic algorithm optimization for prompts, code, and build processes</p>
        </div>
        <button
          onClick={() => setShowNewExperiment(true)}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
        >
          <Plus className="h-4 w-4" />
          Start New Experiment
        </button>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Experiment List - 1/3 width */}
        <div className="col-span-4 bg-gray-900 rounded-lg border border-gray-700">
          <div className="p-4 border-b border-gray-700">
            <h2 className="font-medium text-gray-200">Experiments</h2>
          </div>
          <div className="p-4 h-96 overflow-y-auto">
            {experimentsLoading ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-gray-400">Loading experiments...</div>
              </div>
            ) : (
              <ExperimentList
                experiments={experiments}
                selectedId={selectedExperimentId}
                onSelect={setSelectedExperimentId}
                onNewExperiment={() => setShowNewExperiment(true)}
              />
            )}
          </div>
        </div>

        {/* Experiment Details - 2/3 width */}
        <div className="col-span-8 space-y-6">
          {selectedExperiment ? (
            <>
              {/* Status Cards */}
              <div className="grid grid-cols-4 gap-4">
                <StatusCard
                  icon={Hash}
                  label="Generation"
                  value={`${statusData?.current_generation || selectedExperiment.current_generation}/${selectedExperiment.max_generations}`}
                />
                <StatusCard
                  icon={TrendingUp}
                  label="Best Fitness"
                  value={(statusData?.best_fitness?.toFixed(3) || selectedExperiment.best_fitness.toFixed(3))}
                  color="text-blue-400"
                />
                <StatusCard
                  icon={Activity}
                  label="Health"
                  value={statusData?.population_health ? (statusData.population_health.charAt(0).toUpperCase() + statusData.population_health.slice(1)) : 'Unknown'}
                  color="text-green-400"
                />
                <StatusCard
                  icon={Users}
                  label="Status"
                  value={statusData?.status ? (statusData.status.charAt(0).toUpperCase() + statusData.status.slice(1)) : (selectedExperiment.status.charAt(0).toUpperCase() + selectedExperiment.status.slice(1))}
                  color={
                    (statusData?.status || selectedExperiment.status) === 'running' ? 'text-green-400' :
                    (statusData?.status || selectedExperiment.status) === 'paused' ? 'text-yellow-400' :
                    (statusData?.status || selectedExperiment.status) === 'complete' ? 'text-blue-400' :
                    'text-red-400'
                  }
                />
              </div>

              {/* Fitness Chart */}
              <div className="bg-gray-900 rounded-lg border border-gray-700">
                <div className="p-4 border-b border-gray-700">
                  <h3 className="font-medium text-gray-200">Fitness Progression</h3>
                </div>
                <div className="p-4">
                  <FitnessChart experimentId={selectedExperiment.experiment_id} />
                </div>
              </div>

              {/* Experiment Controls */}
              <div className="bg-gray-900 rounded-lg border border-gray-700">
                <div className="p-4 border-b border-gray-700">
                  <h3 className="font-medium text-gray-200">Controls</h3>
                </div>
                <div className="p-4">
                  <ExperimentControls
                    experiment={selectedExperiment}
                    isNewExperiment={false}
                  />
                </div>
              </div>
            </>
          ) : (
            <div className="bg-gray-900 rounded-lg border border-gray-700 flex items-center justify-center h-96">
              <div className="text-center">
                <Beaker className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-400">Select an experiment to view details</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* New Experiment Modal */}
      {showNewExperiment && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-gray-900 rounded-lg border border-gray-700 p-6 max-w-md w-full mx-4">
            <h2 className="text-xl font-bold text-gray-100 mb-4">Start New Experiment</h2>
            <ExperimentControls
              isNewExperiment={true}
              onCancel={() => setShowNewExperiment(false)}
              onSuccess={() => {
                setShowNewExperiment(false)
                // Experiments will auto-refresh due to query interval
              }}
            />
          </div>
        </div>
      )}
    </div>
  )
}