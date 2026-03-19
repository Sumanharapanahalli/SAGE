import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import StatsStrip from '../components/layout/StatsStrip'

vi.mock('../api/client', () => ({
  fetchPendingProposals: vi.fn().mockResolvedValue({ proposals: [], count: 4 }),
  fetchQueueTasks: vi.fn().mockResolvedValue([
    { status: 'pending' },
    { status: 'in_progress' },
    { status: 'in_progress' },
    { status: 'completed' },
  ]),
}))

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  )
}

describe('StatsStrip', () => {
  it('renders three tile labels', () => {
    render(<StatsStrip />, { wrapper: Wrapper })
    expect(screen.getByText('APPROVALS')).toBeInTheDocument()
    expect(screen.getByText('QUEUED')).toBeInTheDocument()
    expect(screen.getByText('AGENTS')).toBeInTheDocument()
  })

  it('shows initial 0 counts before query resolves', () => {
    render(<StatsStrip />, { wrapper: Wrapper })
    // Counts start at 0 before query resolves
    const zeros = screen.getAllByText('0')
    expect(zeros.length).toBeGreaterThanOrEqual(1)
  })
})
