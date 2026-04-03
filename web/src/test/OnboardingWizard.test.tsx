import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, useNavigate } from 'react-router-dom'
import OnboardingWizard from '../components/onboarding/OnboardingWizard'

// Mock fetch globally
const mockFetch = vi.fn()
;(globalThis as any).fetch = mockFetch

vi.mock('../api/client', () => ({
  fetchProjects: vi.fn().mockResolvedValue({ projects: [], active: '' }),
  switchProject: vi.fn().mockResolvedValue({ status: 'switched' }),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: vi.fn(() => vi.fn()) }
})

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  )
}

const defaultProps = { onClose: vi.fn(), onTourStart: vi.fn() }

beforeEach(() => {
  mockFetch.mockReset()
  defaultProps.onClose.mockReset()
  defaultProps.onTourStart.mockReset()
})

describe('OnboardingWizard', () => {
  it('renders step 1 by default', () => {
    render(<OnboardingWizard {...defaultProps} />, { wrapper: Wrapper })
    expect(screen.getByText(/What does this solution do/)).toBeInTheDocument()
  })

  it('shows 5 step circles', () => {
    render(<OnboardingWizard {...defaultProps} />, { wrapper: Wrapper })
    for (let i = 1; i <= 5; i++) {
      expect(screen.getByText(String(i))).toBeInTheDocument()
    }
  })

  it('Next disabled when description empty', () => {
    render(<OnboardingWizard {...defaultProps} />, { wrapper: Wrapper })
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
  })

  it('Next enabled when description and solution_name filled', () => {
    render(<OnboardingWizard {...defaultProps} />, { wrapper: Wrapper })
    fireEvent.change(screen.getByPlaceholderText(/Describe your solution/i), {
      target: { value: 'A monitoring platform' },
    })
    fireEvent.change(screen.getByLabelText(/Solution name/i), {
      target: { value: 'mon_platform' },
    })
    expect(screen.getByRole('button', { name: 'Next' })).toBeEnabled()
  })

  it('step 2 has Skip link', async () => {
    render(<OnboardingWizard {...defaultProps} />, { wrapper: Wrapper })
    fireEvent.change(screen.getByPlaceholderText(/Describe your solution/i), {
      target: { value: 'A monitoring platform' },
    })
    fireEvent.change(screen.getByLabelText(/Solution name/i), {
      target: { value: 'mon_platform' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Skip')).toBeInTheDocument()
  })

  it('calls POST /onboarding/generate when reaching step 3', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        solution_name: 'mon_platform', path: '/solutions/mon_platform', status: 'created',
        files: { 'project.yaml': 'name: mon\n', 'prompts.yaml': '# prompts', 'tasks.yaml': '# tasks' },
        message: 'ok', suggested_routes: [],
      }),
    })

    render(<OnboardingWizard {...defaultProps} />, { wrapper: Wrapper })
    fireEvent.change(screen.getByPlaceholderText(/Describe your solution/i), { target: { value: 'A platform' } })
    fireEvent.change(screen.getByLabelText(/Solution name/i), { target: { value: 'my_app' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Skip')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Skip'))

    await waitFor(() =>
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/onboarding/generate'),
        expect.objectContaining({ method: 'POST' })
      )
    )
  })

  it('step 4 shows YAML tabs and Open in Config Editor button', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        solution_name: 'my_app', path: '/solutions/my_app', status: 'created',
        files: { 'project.yaml': 'name: my_app\n', 'prompts.yaml': '# prompts', 'tasks.yaml': '# tasks' },
        message: 'ok', suggested_routes: [],
      }),
    })

    render(<OnboardingWizard {...defaultProps} />, { wrapper: Wrapper })
    fireEvent.change(screen.getByPlaceholderText(/Describe your solution/i), { target: { value: 'A platform' } })
    fireEvent.change(screen.getByLabelText(/Solution name/i), { target: { value: 'my_app' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    fireEvent.click(await screen.findByText('Skip'))

    // Wait for step 4
    expect(await screen.findByText('project.yaml')).toBeInTheDocument()
    expect(screen.getByText('prompts.yaml')).toBeInTheDocument()
    expect(screen.getByText('tasks.yaml')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Open in Config Editor/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Looks good' })).toBeInTheDocument()
  })

  it('step 5 calls switchProject and onTourStart when Start tour clicked', async () => {
    const { switchProject } = await import('../api/client')
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        solution_name: 'my_app', path: '/solutions/my_app', status: 'created',
        files: { 'project.yaml': 'name: my_app\n', 'prompts.yaml': '# prompts', 'tasks.yaml': '# tasks' },
        message: 'ok', suggested_routes: [],
      }),
    })

    render(<OnboardingWizard {...defaultProps} />, { wrapper: Wrapper })
    fireEvent.change(screen.getByPlaceholderText(/Describe your solution/i), { target: { value: 'A platform' } })
    fireEvent.change(screen.getByLabelText(/Solution name/i), { target: { value: 'my_app' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    fireEvent.click(await screen.findByText('Skip'))
    expect(await screen.findByText('project.yaml')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Looks good' }))
    expect(await screen.findByText('Solution ready')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Start tour' }))
    await waitFor(() => expect(switchProject).toHaveBeenCalledWith('my_app'))
    await waitFor(() => expect(defaultProps.onTourStart).toHaveBeenCalledWith('my_app'))
  })

  it('shows error message when switchProject fails', async () => {
    const { switchProject } = await import('../api/client')
    ;(switchProject as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error('Switch error'))
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        solution_name: 'my_app', path: '/solutions/my_app', status: 'created',
        files: { 'project.yaml': 'name: my_app\n', 'prompts.yaml': '# prompts', 'tasks.yaml': '# tasks' },
        message: 'ok', suggested_routes: [],
      }),
    })

    render(<OnboardingWizard {...defaultProps} />, { wrapper: Wrapper })
    fireEvent.change(screen.getByPlaceholderText(/Describe your solution/i), { target: { value: 'A platform' } })
    fireEvent.change(screen.getByLabelText(/Solution name/i), { target: { value: 'my_app' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    fireEvent.click(await screen.findByText('Skip'))
    expect(await screen.findByText('project.yaml')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Looks good' }))
    expect(await screen.findByText('Solution ready')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Start tour' }))
    expect(await screen.findByText('Switch error')).toBeInTheDocument()
  })
})
