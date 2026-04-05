import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

// Will be created in implementation step
import ErrorBoundary from '../components/ErrorBoundary'

function ThrowingChild({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) throw new Error('Test explosion')
  return <div>Child OK</div>
}

describe('ErrorBoundary', () => {
  // Suppress React error boundary console.error in test output
  const originalError = console.error
  beforeEach(() => { console.error = vi.fn() })
  afterEach(() => { console.error = originalError })

  it('renders children when no error', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild shouldThrow={false} />
      </ErrorBoundary>
    )
    expect(screen.getByText('Child OK')).toBeInTheDocument()
  })

  it('renders fallback UI on error', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild shouldThrow={true} />
      </ErrorBoundary>
    )
    expect(screen.queryByText('Child OK')).not.toBeInTheDocument()
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
  })

  it('shows a retry button that resets state', () => {
    const { rerender } = render(
      <ErrorBoundary>
        <ThrowingChild shouldThrow={true} />
      </ErrorBoundary>
    )
    const retryBtn = screen.getByRole('button', { name: /retry/i })
    expect(retryBtn).toBeInTheDocument()
  })
})
