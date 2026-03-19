import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import Tooltip from '../components/layout/Tooltip'

describe('Tooltip', () => {
  it('renders children', () => {
    render(<Tooltip text="hello"><span>trigger</span></Tooltip>)
    expect(screen.getByText('trigger')).toBeInTheDocument()
  })

  it('does not show tooltip before 200ms delay', () => {
    const { container } = render(<Tooltip text="Tip text"><span>trigger</span></Tooltip>)
    const wrapper = container.querySelector('div[style*="position: relative"]')!
    fireEvent.mouseEnter(wrapper)
    expect(screen.queryByText('Tip text')).not.toBeInTheDocument()
  })

  it('shows tooltip after 200ms', async () => {
    const { container } = render(<Tooltip text="Tip text"><span>trigger</span></Tooltip>)
    const wrapper = container.querySelector('div[style*="position: relative"]')!
    fireEvent.mouseEnter(wrapper)
    await waitFor(
      () => expect(screen.getByText('Tip text')).toBeInTheDocument(),
      { timeout: 300 }
    )
  })

  it('hides tooltip on mouseleave', async () => {
    const { container } = render(<Tooltip text="Tip text"><span>trigger</span></Tooltip>)
    const wrapper = container.querySelector('div[style*="position: relative"]')!
    fireEvent.mouseEnter(wrapper)
    await waitFor(
      () => expect(screen.getByText('Tip text')).toBeInTheDocument(),
      { timeout: 300 }
    )
    fireEvent.mouseLeave(wrapper)
    expect(screen.queryByText('Tip text')).not.toBeInTheDocument()
  })

  it('accepts side prop without error', () => {
    render(<Tooltip text="Below" side="bottom"><span>t</span></Tooltip>)
    expect(screen.getByText('t')).toBeInTheDocument()
  })
})
