import { createContext, useContext } from 'react'

const TourContext = createContext<any>(null)

export function TourProvider({ children }: { children: React.ReactNode }) {
  return <TourContext.Provider value={{}}>{children}</TourContext.Provider>
}

export function useTourContext() {
  return useContext(TourContext)
}
