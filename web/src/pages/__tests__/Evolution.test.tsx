import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest'
import Evolution from '../Evolution'

const createTestClient = () => new QueryClient({
  defaultOptions: {
    queries: { retry: false },
    mutations: { retry: false }
  }
})

describe('Evolution', () => {
  beforeEach(() => {
    global.fetch = vi.fn()
  })

  afterEach(() => {
    vi.resetAllMocks()
  })

  test('renders evolution dashboard with experiment list', () => {
    // Mock empty experiments list
    vi.mocked(global.fetch).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ experiments: [] })
    })

    const queryClient = createTestClient()

    render(
      <QueryClientProvider client={queryClient}>
        <Evolution />
      </QueryClientProvider>
    )

    expect(screen.getByText('Evolution Experiments')).toBeInTheDocument()
    expect(screen.getByText('Start New Experiment')).toBeInTheDocument()
  })

  test('renders empty state when no experiments exist', async () => {
    vi.mocked(global.fetch).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ experiments: [] })
    })

    const queryClient = createTestClient()

    render(
      <QueryClientProvider client={queryClient}>
        <Evolution />
      </QueryClientProvider>
    )

    // Wait for loading to complete
    await waitFor(() => {
      expect(screen.getByText('No experiments running')).toBeInTheDocument()
    })

    expect(screen.getByText('Create your first evolution experiment to optimize prompts, code, or build processes')).toBeInTheDocument()
  })
})