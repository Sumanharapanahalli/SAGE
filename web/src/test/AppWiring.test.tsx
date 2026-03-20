import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from '../App'

vi.mock('../components/layout/Sidebar', () => ({ default: () => <div>Sidebar</div> }))
vi.mock('../components/layout/Header', () => ({ default: () => <div>Header</div> }))
vi.mock('../components/onboarding/TourOverlay', () => ({ default: () => <div data-testid="tour-overlay" /> }))
vi.mock('../pages/Dashboard', () => ({ default: () => <div>Dashboard</div> }))
vi.mock('../components/CommandPalette', () => ({ default: () => null }))
vi.mock('../components/theme/ThemeProvider', () => ({ default: ({ children }: any) => <>{children}</> }))
vi.mock('../context/AuthContext', () => ({
  AuthProvider: ({ children }: any) => <>{children}</>,
  useAuth: () => ({ user: null, isAuthenticated: false, isLoading: false, refresh: () => {}, isDevMode: false, devUsers: [], switchDevUser: () => {} }),
}))
vi.mock('../api/client', () => ({
  fetchHealth: vi.fn().mockResolvedValue({}),
  fetchProjects: vi.fn().mockResolvedValue({ projects: [], active: '' }),
}))
vi.mock('../hooks/useProjectConfig', () => ({ useProjectConfig: () => ({ data: null }) }))

describe('App wiring', () => {
  it('renders TourOverlay at root', () => {
    render(<App />)
    expect(screen.getByTestId('tour-overlay')).toBeInTheDocument()
  })

  it('renders without crashing', () => {
    render(<App />)
    expect(screen.getByText('Sidebar')).toBeInTheDocument()
  })
})
