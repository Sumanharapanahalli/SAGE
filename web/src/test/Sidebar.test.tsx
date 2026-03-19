import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import Sidebar from '../components/layout/Sidebar'

vi.mock('../api/client', () => ({
  fetchPendingProposals: vi.fn().mockResolvedValue({ proposals: [], count: 0 }),
  fetchQueueTasks: vi.fn().mockResolvedValue([]),
  fetchProjects: vi.fn().mockResolvedValue({ projects: [
    { id: 'iot_medical', name: 'IoT Medical', domain: 'medical', version: '1.0', description: '' }
  ], active: 'iot_medical' }),
  fetchHealth: vi.fn().mockResolvedValue({ project: { project: 'iot_medical' }, llm_provider: 'gemini' }),
  switchProject: vi.fn().mockResolvedValue({ status: 'switched' }),
}))

vi.mock('../hooks/useProjectConfig', () => ({
  useProjectConfig: () => ({ data: { name: 'IoT Medical', active_modules: [] } }),
}))

vi.mock('../context/TourContext', () => ({
  useTourContext: () => ({
    openWizard: vi.fn(),
    closeWizard: vi.fn(),
    wizardOpen: false,
    startTour: vi.fn(),
    isToured: vi.fn(() => false),
    restartTour: vi.fn(),
    tourState: { active: false, currentStop: 0, solutionName: '' },
    nextStop: vi.fn(), prevStop: vi.fn(), skipTour: vi.fn(),
  }),
}))

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/']}>{children}</MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Sidebar', () => {
  it('renders all 5 area headers', () => {
    render(<Sidebar />, { wrapper: Wrapper })
    expect(screen.getByText('Work')).toBeInTheDocument()
    expect(screen.getByText('Intelligence')).toBeInTheDocument()
    expect(screen.getByText('Knowledge')).toBeInTheDocument()
    expect(screen.getByText('Organization')).toBeInTheDocument()
    expect(screen.getByText('Admin')).toBeInTheDocument()
  })

  it('Work area is open by default', () => {
    render(<Sidebar />, { wrapper: Wrapper })
    expect(screen.getByText('Approvals')).toBeInTheDocument()
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
  })

  it('Intelligence area is collapsed by default', () => {
    render(<Sidebar />, { wrapper: Wrapper })
    expect(screen.queryByText('Analyst')).not.toBeInTheDocument()
  })

  it('clicking Intelligence header expands it and collapses Work', () => {
    render(<Sidebar />, { wrapper: Wrapper })
    fireEvent.click(screen.getByText('Intelligence'))
    expect(screen.getByText('Analyst')).toBeInTheDocument()
    expect(screen.queryByText('Approvals')).not.toBeInTheDocument()
  })

  it('solution switcher shows active solution name', () => {
    render(<Sidebar />, { wrapper: Wrapper })
    expect(screen.getByText('IoT Medical')).toBeInTheDocument()
  })

  it('stats strip tiles are rendered', () => {
    render(<Sidebar />, { wrapper: Wrapper })
    expect(screen.getByText('APPROVALS')).toBeInTheDocument()
    expect(screen.getByText('QUEUED')).toBeInTheDocument()
    expect(screen.getByText('AGENTS')).toBeInTheDocument()
  })
})
