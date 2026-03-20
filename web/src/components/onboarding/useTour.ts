import { useState, useCallback } from 'react'

const LS_KEY = 'sage_toured_solutions'

export interface TourState {
  active: boolean
  currentStop: number
  solutionName: string  // solution id (e.g. 'iot_medical'), not display name
}

export function useTour() {
  const [tourState, setTourState] = useState<TourState>({
    active: false,
    currentStop: 0,
    solutionName: '',
  })

  const getToured = (): string[] => {
    try { return JSON.parse(localStorage.getItem(LS_KEY) ?? '[]') } catch { return [] }
  }

  const markToured = (solutionId: string) => {
    const existing = getToured()
    if (!existing.includes(solutionId)) {
      localStorage.setItem(LS_KEY, JSON.stringify([...existing, solutionId]))
    }
  }

  const clearToured = (solutionId: string) => {
    const existing = getToured().filter(s => s !== solutionId)
    localStorage.setItem(LS_KEY, JSON.stringify(existing))
  }

  const startTour = useCallback((solutionId: string) => {
    setTourState({ active: true, currentStop: 0, solutionName: solutionId })
  }, [])

  const nextStop = useCallback(() => {
    setTourState(prev => ({ ...prev, currentStop: prev.currentStop + 1 }))
  }, [])

  const prevStop = useCallback(() => {
    setTourState(prev => ({ ...prev, currentStop: Math.max(0, prev.currentStop - 1) }))
  }, [])

  const skipTour = useCallback(() => {
    setTourState(prev => {
      markToured(prev.solutionName)
      return { active: false, currentStop: 0, solutionName: prev.solutionName }
    })
  }, [])

  const isToured = useCallback((solutionId: string): boolean => {
    return getToured().includes(solutionId)
  }, [])

  const restartTour = useCallback((solutionId: string) => {
    clearToured(solutionId)
    setTourState({ active: true, currentStop: 0, solutionName: solutionId })
  }, [])

  return { tourState, startTour, nextStop, prevStop, skipTour, isToured, restartTour }
}
