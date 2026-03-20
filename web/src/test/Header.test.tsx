import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import Header from '../components/layout/Header'

vi.mock('../api/client', () => ({
  fetchHealth: vi.fn().mockResolvedValue({ project: { project: 'iot_medical' }, llm_provider: 'gemini' }),
  fetchProjects: vi.fn().mockResolvedValue({ projects: [], active: 'iot_medical' }),
  switchProject: vi.fn(),
}))

vi.mock('../hooks/useProjectConfig', () => ({
  useProjectConfig: () => ({
    data: { name: 'IoT Medical', domain: 'medical', active_modules: [], ui_labels: {} }
  }),
}))

vi.mock('../context/ChatContext', () => ({
  ChatProvider: ({ children }: any) => <>{children}</>,
  useChatContext: () => ({
    panelState: 'closed', openChat: () => {}, closeChat: () => {}, minimiseChat: () => {},
    seedMessage: undefined, clearSeedMessage: () => {}, messages: [], isLoading: false,
    unreadCount: 0, addMessage: () => {}, updateLastAssistantMessage: () => {},
    setMessages: () => {}, setIsLoading: () => {}, clearUnread: () => {}, incrementUnread: () => {},
  }),
}))

function Wrapper({ path = '/', children }: { path?: string; children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>{children}</MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Header breadcrumb', () => {
  it('shows solution name and Work area for /', () => {
    render(<Header />, { wrapper: (p) => <Wrapper path="/">{p.children}</Wrapper> })
    expect(screen.getByText(/IoT Medical/)).toBeInTheDocument()
    expect(screen.getByText(/Work/)).toBeInTheDocument()
  })

  it('shows Intelligence area for /analyst', () => {
    render(<Header />, { wrapper: (p) => <Wrapper path="/analyst">{p.children}</Wrapper> })
    expect(screen.getByText(/Intelligence/)).toBeInTheDocument()
  })

  it('shows Admin area for /settings', () => {
    render(<Header />, { wrapper: (p) => <Wrapper path="/settings">{p.children}</Wrapper> })
    expect(screen.getByText(/Admin/)).toBeInTheDocument()
  })

  it('preserves page title on line 2', () => {
    render(<Header />, { wrapper: (p) => <Wrapper path="/analyst">{p.children}</Wrapper> })
    expect(screen.getByText('Log Analyst')).toBeInTheDocument()
  })

  it('does not render solution switcher dropdown button', () => {
    render(<Header />, { wrapper: (p) => <Wrapper path="/">{p.children}</Wrapper> })
    expect(screen.queryByTitle('Switch solution')).not.toBeInTheDocument()
  })
})
