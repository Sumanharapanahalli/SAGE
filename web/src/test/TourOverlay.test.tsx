import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import TourOverlay from '../components/onboarding/TourOverlay'

const mockSkipTour = vi.fn()
const mockNextStop = vi.fn()
const mockPrevStop = vi.fn()

vi.mock('../context/TourContext', () => ({
  useTourContext: vi.fn(() => ({
    tourState: { active: true, currentStop: 0, solutionName: 'my_app' },
    nextStop: mockNextStop,
    prevStop: mockPrevStop,
    skipTour: mockSkipTour,
    startTour: vi.fn(), isToured: vi.fn(() => false), restartTour: vi.fn(),
    wizardOpen: false, openWizard: vi.fn(), closeWizard: vi.fn(),
  })),
}))

import { useTourContext } from '../context/TourContext'

describe('TourOverlay', () => {
  beforeEach(() => {
    mockSkipTour.mockReset()
    mockNextStop.mockReset()
    mockPrevStop.mockReset()
    vi.spyOn(document, 'querySelector').mockReturnValue(null)
  })

  it('renders stop 1 heading', () => {
    render(<TourOverlay />)
    expect(screen.getByText('Your live dashboard')).toBeInTheDocument()
  })

  it('shows step counter "1 of 6"', () => {
    render(<TourOverlay />)
    expect(screen.getByText('1 of 6')).toBeInTheDocument()
  })

  it('calls nextStop on Next click', () => {
    render(<TourOverlay />)
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(mockNextStop).toHaveBeenCalled()
  })

  it('calls skipTour on Skip click', () => {
    render(<TourOverlay />)
    fireEvent.click(screen.getByText('Skip'))
    expect(mockSkipTour).toHaveBeenCalled()
  })

  it('shows Done at last stop (index 5)', () => {
    vi.mocked(useTourContext).mockReturnValue({
      tourState: { active: true, currentStop: 5, solutionName: 'my_app' },
      nextStop: mockNextStop, prevStop: mockPrevStop, skipTour: mockSkipTour,
      startTour: vi.fn(), isToured: vi.fn(() => false), restartTour: vi.fn(),
      wizardOpen: false, openWizard: vi.fn(), closeWizard: vi.fn(),
    })
    render(<TourOverlay />)
    expect(screen.getByRole('button', { name: 'Done' })).toBeInTheDocument()
  })

  it('returns null when tour inactive', () => {
    vi.mocked(useTourContext).mockReturnValue({
      tourState: { active: false, currentStop: 0, solutionName: '' },
      nextStop: vi.fn(), prevStop: vi.fn(), skipTour: vi.fn(),
      startTour: vi.fn(), isToured: vi.fn(() => false), restartTour: vi.fn(),
      wizardOpen: false, openWizard: vi.fn(), closeWizard: vi.fn(),
    })
    const { container } = render(<TourOverlay />)
    expect(container.firstChild).toBeNull()
  })
})
