import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import Header from '../components/layout/Header'
import Sidebar from '../components/layout/Sidebar'

// Union of the mocks used by Header.test.tsx and Sidebar.test.tsx so both
// components can render in one file (StatsStrip inside Sidebar needs the
// pending/queue fetchers).
vi.mock('../api/client', () => ({
  fetchHealth: vi.fn().mockResolvedValue({ project: { project: 'iot_medical' }, llm_provider: 'gemini' }),
  fetchProjects: vi.fn().mockResolvedValue({ projects: [
    { id: 'iot_medical', name: 'IoT Medical', domain: 'medical', version: '1.0', description: '' }
  ], active: 'iot_medical' }),
  switchProject: vi.fn().mockResolvedValue({ status: 'switched' }),
  fetchPendingProposals: vi.fn().mockResolvedValue({ proposals: [], count: 0 }),
  fetchQueueTasks: vi.fn().mockResolvedValue([]),
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

function Wrapper({ path = '/', children }: { path?: string; children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>{children}</MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Header icon-only buttons have accessible labels', () => {
  it('Chat button (MessageSquare-only) exposes an aria-label describing the action', () => {
    render(<Header />, { wrapper: (p) => <Wrapper>{p.children}</Wrapper> })
    const chatBtn = screen.getByRole('button', { name: /sage chat/i })
    // The title attribute already yields an accessible name, so we assert on
    // the explicit aria-label to prove an action label was added.
    expect(chatBtn).toHaveAttribute('aria-label')
    expect(chatBtn.getAttribute('aria-label')).toBeTruthy()
  })
})

describe('Sidebar icon-only buttons have accessible labels', () => {
  it('Grid/picker button (LayoutGrid-only) has an action label', () => {
    render(<Sidebar />, { wrapper: (p) => <Wrapper>{p.children}</Wrapper> })
    expect(screen.getByRole('button', { name: /browse all solutions/i })).toBeInTheDocument()
  })

  it('Org-graph button (Building2-only) has an action label', () => {
    render(<Sidebar />, { wrapper: (p) => <Wrapper>{p.children}</Wrapper> })
    expect(screen.getByRole('button', { name: /view organization graph/i })).toBeInTheDocument()
  })
})
