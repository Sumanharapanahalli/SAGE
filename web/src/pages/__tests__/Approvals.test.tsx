import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest'
import Approvals from '../Approvals'

// Mock the EvolutionProposalCard component
vi.mock('../../components/evolution/EvolutionProposalCard', () => ({
  default: ({ proposal }: any) => (
    <div data-testid="evolution-proposal-card">
      <div>EVOLUTION CANDIDATE</div>
      <div>Generation: {proposal.metadata?.generation}</div>
      <div>Fitness: {proposal.metadata?.fitness_score}</div>
      <div>Mutation: {proposal.metadata?.mutation_type}</div>
    </div>
  )
}))

const createTestClient = () => new QueryClient({
  defaultOptions: {
    queries: { retry: false },
    mutations: { retry: false }
  }
})

describe('Approvals', () => {
  beforeEach(() => {
    global.fetch = vi.fn()
  })

  afterEach(() => {
    vi.resetAllMocks()
  })

  test('renders evolution proposal with specialized card', async () => {
    const mockProposal = {
      trace_id: 'evo-001',
      action_type: 'evolution_candidate',
      risk_class: 'EPHEMERAL' as const,
      created_at: '2026-04-13T10:00:00Z',
      status: 'pending' as const,
      proposed_by: 'evolution-engine',
      description: 'Crossover mutation of parent candidates',
      reversible: true,
      payload: {},
      decided_by: null,
      decided_at: null,
      feedback: null,
      expires_at: null,
      required_role: null,
      metadata: {
        generation: 15,
        fitness_score: 0.87,
        mutation_type: 'crossover'
      }
    }

    // Mock fetch to return evolution proposal
    vi.mocked(global.fetch).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ proposals: [mockProposal], count: 1 })
    })

    const queryClient = createTestClient()

    render(
      <QueryClientProvider client={queryClient}>
        <Approvals />
      </QueryClientProvider>
    )

    // Wait for the proposal to load and check for evolution card
    await waitFor(() => {
      expect(screen.getByTestId('evolution-proposal-card')).toBeInTheDocument()
    })

    expect(screen.getByText('EVOLUTION CANDIDATE')).toBeInTheDocument()
    expect(screen.getByText('Generation: 15')).toBeInTheDocument()
    expect(screen.getByText('Fitness: 0.87')).toBeInTheDocument()
    expect(screen.getByText('Mutation: crossover')).toBeInTheDocument()
  })

  test('renders regular proposal with standard UI', async () => {
    const mockProposal = {
      trace_id: 'reg-001',
      action_type: 'code_diff',
      risk_class: 'STATEFUL' as const,
      created_at: '2026-04-13T10:00:00Z',
      status: 'pending' as const,
      proposed_by: 'developer-agent',
      description: 'Fix authentication bug',
      reversible: true,
      payload: { diff: '@@ -1,3 +1,3 @@\n-old line\n+new line' },
      decided_by: null,
      decided_at: null,
      feedback: null,
      expires_at: null,
      required_role: null
    }

    // Mock fetch to return regular proposal
    vi.mocked(global.fetch).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ proposals: [mockProposal], count: 1 })
    })

    const queryClient = createTestClient()

    render(
      <QueryClientProvider client={queryClient}>
        <Approvals />
      </QueryClientProvider>
    )

    // Wait for the proposal to load and check for regular UI (no evolution card)
    await waitFor(() => {
      expect(screen.getByText('Code Diff')).toBeInTheDocument()
    })

    expect(screen.queryByTestId('evolution-proposal-card')).not.toBeInTheDocument()
    expect(screen.queryByText('EVOLUTION CANDIDATE')).not.toBeInTheDocument()
  })

  test('handles mixed proposal types correctly', async () => {
    const mockProposals = [
      {
        trace_id: 'evo-001',
        action_type: 'evolution_candidate',
        risk_class: 'EPHEMERAL' as const,
        created_at: '2026-04-13T10:00:00Z',
        status: 'pending' as const,
        proposed_by: 'evolution-engine',
        description: 'Evolution candidate',
        reversible: true,
        payload: {},
        decided_by: null,
        decided_at: null,
        feedback: null,
        expires_at: null,
        required_role: null,
        metadata: {
          generation: 5,
          fitness_score: 0.75,
          mutation_type: 'point_mutation'
        }
      },
      {
        trace_id: 'reg-001',
        action_type: 'yaml_edit',
        risk_class: 'STATEFUL' as const,
        created_at: '2026-04-13T09:00:00Z',
        status: 'pending' as const,
        proposed_by: 'analyst-agent',
        description: 'Update task configuration',
        reversible: true,
        payload: { changes: { added: ['new_task'], modified: [], removed: [] } },
        decided_by: null,
        decided_at: null,
        feedback: null,
        expires_at: null,
        required_role: null
      }
    ]

    // Mock fetch to return mixed proposals
    vi.mocked(global.fetch).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ proposals: mockProposals, count: 2 })
    })

    const queryClient = createTestClient()

    render(
      <QueryClientProvider client={queryClient}>
        <Approvals />
      </QueryClientProvider>
    )

    // Wait for both proposals to load
    await waitFor(() => {
      expect(screen.getByText('Yaml Edit')).toBeInTheDocument()
      expect(screen.getByText('Evolution Candidate')).toBeInTheDocument()
    })

    // Click on the evolution proposal in the left panel to select it
    const user = userEvent.setup()
    const evolutionProposal = screen.getByText('Evolution candidate')
    await user.click(evolutionProposal)

    // Wait for evolution card to be rendered in detail panel
    await waitFor(() => {
      expect(screen.getByTestId('evolution-proposal-card')).toBeInTheDocument()
    })

    // Evolution card should be present
    expect(screen.getByText('EVOLUTION CANDIDATE')).toBeInTheDocument()
    expect(screen.getByText('Generation: 5')).toBeInTheDocument()

    // Regular proposal should also be present in the list
    expect(screen.getByText('Update task configuration')).toBeInTheDocument()
  })
})