import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useTour } from '../components/onboarding/useTour'

const LS_KEY = 'sage_toured_solutions'

beforeEach(() => localStorage.clear())

describe('useTour', () => {
  it('starts inactive', () => {
    const { result } = renderHook(() => useTour())
    expect(result.current.tourState.active).toBe(false)
    expect(result.current.tourState.currentStop).toBe(0)
  })

  it('startTour activates tour', () => {
    const { result } = renderHook(() => useTour())
    act(() => result.current.startTour('my_solution'))
    expect(result.current.tourState.active).toBe(true)
    expect(result.current.tourState.solutionName).toBe('my_solution')
    expect(result.current.tourState.currentStop).toBe(0)
  })

  it('nextStop increments currentStop', () => {
    const { result } = renderHook(() => useTour())
    act(() => result.current.startTour('sol'))
    act(() => result.current.nextStop())
    expect(result.current.tourState.currentStop).toBe(1)
  })

  it('prevStop decrements currentStop', () => {
    const { result } = renderHook(() => useTour())
    act(() => result.current.startTour('sol'))
    act(() => result.current.nextStop())
    act(() => result.current.prevStop())
    expect(result.current.tourState.currentStop).toBe(0)
  })

  it('prevStop does not go below 0', () => {
    const { result } = renderHook(() => useTour())
    act(() => result.current.startTour('sol'))
    act(() => result.current.prevStop())
    expect(result.current.tourState.currentStop).toBe(0)
  })

  it('skipTour deactivates and marks toured in localStorage using solution id', () => {
    const { result } = renderHook(() => useTour())
    act(() => result.current.startTour('iot_medical'))
    act(() => result.current.skipTour())
    expect(result.current.tourState.active).toBe(false)
    const stored = JSON.parse(localStorage.getItem(LS_KEY) ?? '[]')
    expect(stored).toContain('iot_medical')
  })

  it('isToured returns true for toured solution id', () => {
    localStorage.setItem(LS_KEY, JSON.stringify(['iot_medical']))
    const { result } = renderHook(() => useTour())
    expect(result.current.isToured('iot_medical')).toBe(true)
    expect(result.current.isToured('IoT Medical')).toBe(false) // display name != id
  })
})
