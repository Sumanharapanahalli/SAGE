import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Play, Pause, Square, Settings, X } from 'lucide-react'
import { startEvolutionExperiment, EvolutionExperiment } from '../../api/client'

interface ExperimentControlsProps {
  experiment?: EvolutionExperiment
  isNewExperiment: boolean
  onCancel?: () => void
  onSuccess?: () => void
}

export default function ExperimentControls({
  experiment,
  isNewExperiment,
  onCancel,
  onSuccess
}: ExperimentControlsProps) {
  const [formData, setFormData] = useState({
    solution_name: '',
    target_type: 'prompt' as 'prompt' | 'code' | 'build',
    population_size: 20,
    max_generations: 50,
    mutation_rate: 0.1,
    crossover_rate: 0.7
  })

  const queryClient = useQueryClient()

  const startExperimentMutation = useMutation({
    mutationFn: startEvolutionExperiment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['evolution'] })
      onSuccess?.()
    },
  })

  const handleStartExperiment = () => {
    if (!formData.solution_name.trim()) {
      return
    }

    startExperimentMutation.mutate(formData)
  }

  const handleInputChange = (field: keyof typeof formData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  if (isNewExperiment) {
    return (
      <div className="space-y-4">
        {/* Solution Name */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Solution Name
          </label>
          <input
            type="text"
            value={formData.solution_name}
            onChange={(e) => handleInputChange('solution_name', e.target.value)}
            placeholder="Enter solution name"
            className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-gray-100 placeholder-gray-400 focus:border-blue-500 focus:outline-none"
            required
          />
        </div>

        {/* Target Type */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Target Type
          </label>
          <select
            value={formData.target_type}
            onChange={(e) => handleInputChange('target_type', e.target.value)}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-gray-100 focus:border-blue-500 focus:outline-none"
          >
            <option value="prompt">Prompt</option>
            <option value="code">Code</option>
            <option value="build">Build</option>
          </select>
        </div>

        {/* Population Size */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Population Size
          </label>
          <input
            type="number"
            value={formData.population_size}
            onChange={(e) => handleInputChange('population_size', parseInt(e.target.value) || 0)}
            min="5"
            max="100"
            className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-gray-100 focus:border-blue-500 focus:outline-none"
          />
        </div>

        {/* Max Generations */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Max Generations
          </label>
          <input
            type="number"
            value={formData.max_generations}
            onChange={(e) => handleInputChange('max_generations', parseInt(e.target.value) || 0)}
            min="10"
            max="200"
            className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-gray-100 focus:border-blue-500 focus:outline-none"
          />
        </div>

        {/* Mutation Rate */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Mutation Rate
          </label>
          <input
            type="number"
            step="0.01"
            value={formData.mutation_rate}
            onChange={(e) => handleInputChange('mutation_rate', parseFloat(e.target.value) || 0)}
            min="0.01"
            max="0.5"
            className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-gray-100 focus:border-blue-500 focus:outline-none"
          />
        </div>

        {/* Crossover Rate */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Crossover Rate
          </label>
          <input
            type="number"
            step="0.01"
            value={formData.crossover_rate}
            onChange={(e) => handleInputChange('crossover_rate', parseFloat(e.target.value) || 0)}
            min="0.1"
            max="1.0"
            className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-gray-100 focus:border-blue-500 focus:outline-none"
          />
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-4">
          <button
            onClick={handleStartExperiment}
            disabled={!formData.solution_name.trim() || startExperimentMutation.isPending}
            className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
          >
            <Play className="h-4 w-4" />
            {startExperimentMutation.isPending ? 'Starting...' : 'Start Experiment'}
          </button>
          {onCancel && (
            <button
              onClick={onCancel}
              className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-gray-200 rounded-lg font-medium transition-colors flex items-center gap-2"
            >
              <X className="h-4 w-4" />
              Cancel
            </button>
          )}
        </div>

        {startExperimentMutation.error && (
          <div className="text-red-400 text-sm">
            Error: {startExperimentMutation.error.message}
          </div>
        )}
      </div>
    )
  }

  // Existing experiment controls
  return (
    <div className="flex gap-3">
      <button
        onClick={() => {/* TODO: Resume experiment */}}
        className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
      >
        <Play className="h-4 w-4" />
        Resume
      </button>
      <button
        onClick={() => {/* TODO: Pause experiment */}}
        className="px-4 py-2 bg-yellow-600 hover:bg-yellow-700 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
      >
        <Pause className="h-4 w-4" />
        Pause
      </button>
      <button
        onClick={() => {/* TODO: Stop experiment */}}
        className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
      >
        <Square className="h-4 w-4" />
        Stop
      </button>
      <button
        onClick={() => {/* TODO: Configure experiment */}}
        className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
      >
        <Settings className="h-4 w-4" />
        Configure
      </button>
    </div>
  )
}