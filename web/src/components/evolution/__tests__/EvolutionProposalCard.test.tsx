import { render, screen } from '@testing-library/react'
import EvolutionProposalCard from '../EvolutionProposalCard'

test('renders evolution metadata panel', () => {
  const proposal = {
    trace_id: 'evo-001',
    action_type: 'evolution_candidate',
    metadata: {
      generation: 15,
      fitness_score: 0.87,
      mutation_type: 'crossover',
      parent_ids: ['candidate-247'],
      evaluator_scores: {
        test_driven: 0.91,
        semantic: 0.85,
        integration: 0.84
      }
    }
  }

  render(<EvolutionProposalCard proposal={proposal} />)

  expect(screen.getByText('Generation 15')).toBeInTheDocument()
  expect(screen.getByText('Fitness: 0.87')).toBeInTheDocument()
  expect(screen.getByText('Crossover')).toBeInTheDocument()
})

test('displays risk badge based on fitness score', () => {
  const highFitnessProposal = {
    trace_id: 'evo-002',
    action_type: 'evolution_candidate',
    metadata: {
      generation: 20,
      fitness_score: 0.95,
      mutation_type: 'mutation',
      parent_ids: ['candidate-123'],
      evaluator_scores: {
        test_driven: 0.96,
        semantic: 0.94,
        integration: 0.95
      }
    }
  }

  render(<EvolutionProposalCard proposal={highFitnessProposal} />)

  expect(screen.getByText('VALIDATED')).toBeInTheDocument()
})

test('displays evaluator scores with labels', () => {
  const proposal = {
    trace_id: 'evo-003',
    action_type: 'evolution_candidate',
    metadata: {
      generation: 5,
      fitness_score: 0.72,
      mutation_type: 'crossover',
      parent_ids: ['candidate-456'],
      evaluator_scores: {
        test_driven: 0.80,
        semantic: 0.75,
        integration: 0.61
      }
    }
  }

  render(<EvolutionProposalCard proposal={proposal} />)

  expect(screen.getByText('Test Driven: 0.80')).toBeInTheDocument()
  expect(screen.getByText('Semantic: 0.75')).toBeInTheDocument()
  expect(screen.getByText('Integration: 0.61')).toBeInTheDocument()
})

test('displays changes summary when present', () => {
  const proposal = {
    trace_id: 'evo-004',
    action_type: 'evolution_candidate',
    metadata: {
      generation: 8,
      fitness_score: 0.68,
      mutation_type: 'mutation',
      parent_ids: ['candidate-789'],
      evaluator_scores: {
        test_driven: 0.70,
        semantic: 0.68,
        integration: 0.66
      },
      changes: {
        added: ['new_function.py'],
        modified: ['main.py', 'utils.py'],
        removed: ['deprecated.py']
      }
    }
  }

  render(<EvolutionProposalCard proposal={proposal} />)

  expect(screen.getByText('+ new_function.py')).toBeInTheDocument()
  expect(screen.getByText('~ main.py')).toBeInTheDocument()
  expect(screen.getByText('- deprecated.py')).toBeInTheDocument()
})