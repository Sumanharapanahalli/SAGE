import { GitBranch } from 'lucide-react'
import type { Proposal } from '../../api/client'

interface EvolutionProposalCardProps {
  proposal: Proposal & {
    metadata: {
      generation: number
      fitness_score: number
      mutation_type: string
      parent_ids: string[]
      evaluator_scores: Record<string, number>
      changes?: {
        added: string[]
        modified: string[]
        removed: string[]
      }
    }
  }
}

export default function EvolutionProposalCard({ proposal }: EvolutionProposalCardProps) {
  const { metadata } = proposal

  const getRiskBadge = () => {
    if (metadata.fitness_score >= 0.9) return { label: 'VALIDATED', class: 'bg-green-900 text-green-300' }
    if (metadata.fitness_score >= 0.7) return { label: 'EXPERIMENTAL', class: 'bg-yellow-900 text-yellow-300' }
    return { label: 'REGRESSION', class: 'bg-red-900 text-red-300' }
  }

  const risk = getRiskBadge()

  return (
    <div className="border border-gray-700 bg-gray-800 rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <GitBranch size={16} className="text-purple-400" />
          <span className="text-sm font-medium text-gray-300">EVOLUTION CANDIDATE</span>
        </div>
        <span className={`px-2 py-1 text-xs font-medium rounded ${risk.class}`}>
          {risk.label}
        </span>
      </div>

      {/* Evolution metadata */}
      <div className="flex items-center gap-4 mb-3 text-sm text-gray-400">
        <span>Generation {metadata.generation}</span>
        <span>•</span>
        <span>Fitness: {metadata.fitness_score.toFixed(2)}</span>
        <span>•</span>
        <span className="capitalize">{metadata.mutation_type.charAt(0).toUpperCase() + metadata.mutation_type.slice(1)}</span>
      </div>

      {/* Evaluator scores */}
      <div className="mb-3">
        <div className="text-xs text-gray-500 mb-1">Evaluator Scores:</div>
        <div className="flex gap-4 text-xs">
          {Object.entries(metadata.evaluator_scores).map(([name, score]) => (
            <div key={name} className="flex items-center gap-1">
              <div className="w-2 h-2 bg-blue-400 rounded-full"></div>
              <span className="capitalize">{name.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}: {score.toFixed(2)}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Changes summary */}
      {metadata.changes && (
        <div className="mb-3 text-xs">
          <div className="text-gray-500 mb-1">Changes:</div>
          {metadata.changes.added.map(change => (
            <div key={change} className="text-green-400">+ {change}</div>
          ))}
          {metadata.changes.modified.map(change => (
            <div key={change} className="text-yellow-400">~ {change}</div>
          ))}
          {metadata.changes.removed.map(change => (
            <div key={change} className="text-red-400">- {change}</div>
          ))}
        </div>
      )}

      {/* Parent lineage */}
      <div className="text-xs text-gray-500">
        Parent: {metadata.parent_ids.join(', ')} → {metadata.mutation_type} → This
      </div>
    </div>
  )
}