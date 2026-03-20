import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import Tooltip from '../components/layout/Tooltip'

describe('Tooltip', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('renders children', () => {
    render(<Tooltip text="hello"><span>trigger</span></Tooltip>)
    expect(screen.getByText('trigger')).toBeInTheDocument()
  })

  it('does not show tooltip before 200ms delay', () => {
    render(<Tooltip text="Tip text"><span>trigger</span></Tooltip>)
    fireEvent.mouseEnter(screen.getByText('trigger').parentElement!)
    expect(screen.queryByText('Tip text')).not.toBeInTheDocument()
  })

  it('shows tooltip after 200ms', () => {
    render(<Tooltip text="Tip text"><span>trigger</span></Tooltip>)
    fireEvent.mouseEnter(screen.getByText('trigger').parentElement!)
    act(() => vi.advanceTimersByTime(200))
    expect(screen.getByText('Tip text')).toBeInTheDocument()
  })

  it('hides tooltip on mouseleave', () => {
    render(<Tooltip text="Tip text"><span>trigger</span></Tooltip>)
    const wrapper = screen.getByText('trigger').parentElement!
    fireEvent.mouseEnter(wrapper)
    act(() => vi.advanceTimersByTime(200))
    expect(screen.getByText('Tip text')).toBeInTheDocument()
    fireEvent.mouseLeave(wrapper)
    expect(screen.queryByText('Tip text')).not.toBeInTheDocument()
  })

  it('accepts side prop without error', () => {
    render(<Tooltip text="Below" side="bottom"><span>t</span></Tooltip>)
    expect(screen.getByText('t')).toBeInTheDocument()
  })
})
