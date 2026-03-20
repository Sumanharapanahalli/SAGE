import { createContext, useContext, useState, type ReactNode } from 'react'
import { useTour, type TourState } from '../components/onboarding/useTour'

interface TourContextValue {
  tourState: TourState
  startTour: (solutionId: string) => void
  nextStop: () => void
  prevStop: () => void
  skipTour: () => void
  isToured: (solutionId: string) => boolean
  restartTour: (solutionId: string) => void
  wizardOpen: boolean
  openWizard: () => void
  closeWizard: () => void
}

const TourContext = createContext<TourContextValue | null>(null)

export function TourProvider({ children }: { children: ReactNode }) {
  const tour = useTour()
  const [wizardOpen, setWizardOpen] = useState(false)
  return (
    <TourContext.Provider value={{
      ...tour,
      wizardOpen,
      openWizard: () => setWizardOpen(true),
      closeWizard: () => setWizardOpen(false),
    }}>
      {children}
    </TourContext.Provider>
  )
}

export function useTourContext() {
  const ctx = useContext(TourContext)
  if (!ctx) throw new Error('useTourContext must be used within TourProvider')
  return ctx
}
