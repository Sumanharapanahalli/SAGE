import { createContext, useContext, type ReactNode } from 'react'
import type { TourState } from '../components/onboarding/useTour'

interface TourContextValue {
  tourState: TourState
  startTour: (solutionName: string) => void
  nextStop: () => void
  prevStop: () => void
  skipTour: () => void
  isToured: (solutionName: string) => boolean
  restartTour: (solutionName: string) => void
  wizardOpen: boolean
  openWizard: () => void
  closeWizard: () => void
}

const defaultValue: TourContextValue = {
  tourState: { active: false, currentStop: 0, solutionName: '' },
  startTour: () => {},
  nextStop: () => {},
  prevStop: () => {},
  skipTour: () => {},
  isToured: () => false,
  restartTour: () => {},
  wizardOpen: false,
  openWizard: () => {},
  closeWizard: () => {},
}

const TourContext = createContext<TourContextValue>(defaultValue)

export function TourProvider({ children }: { children: ReactNode }) {
  return <TourContext.Provider value={defaultValue}>{children}</TourContext.Provider>
}

export function useTourContext() {
  return useContext(TourContext)
}
