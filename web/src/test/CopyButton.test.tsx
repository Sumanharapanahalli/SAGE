import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CopyButton from '../components/ui/CopyButton'

/** jsdom exposes navigator.clipboard as a getter-only prop, so stub it via defineProperty. */
function stubClipboard() {
  const writeText = vi.fn().mockResolvedValue(undefined)
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText },
    configurable: true,
    writable: true,
  })
  return writeText
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('CopyButton', () => {
  it('copies the given text to the clipboard on click', async () => {
    const user = userEvent.setup()
    const writeText = stubClipboard() // stub AFTER setup so our spy wins over userEvent's

    render(<CopyButton text="diff-payload" />)
    await user.click(screen.getByRole('button', { name: /copy to clipboard/i }))

    expect(writeText).toHaveBeenCalledWith('diff-payload')
  })

  it('flips its accessible label to "Copied" after a successful copy', async () => {
    const user = userEvent.setup()
    stubClipboard()

    render(<CopyButton text="x" />)
    await user.click(screen.getByRole('button', { name: /copy to clipboard/i }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /copied/i })).toBeInTheDocument()
    )
  })

  it('always exposes an accessible label (icon-only button stays labelled)', () => {
    stubClipboard()
    render(<CopyButton text="x" />)
    // Queryable by role+name => the icon-only button is not an unlabelled control.
    expect(screen.getByRole('button', { name: /copy to clipboard/i })).toBeInTheDocument()
  })
})
