import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

import OfflineBanner from '../components/OfflineBanner'

describe('OfflineBanner', () => {
  let fetchSpy: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchSpy = vi.fn()
    vi.stubGlobal('fetch', fetchSpy)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('shows nothing when backend is reachable', async () => {
    fetchSpy.mockResolvedValue({ ok: true, json: () => Promise.resolve({}) })
    render(<OfflineBanner />)
    await waitFor(() => expect(fetchSpy).toHaveBeenCalled())
    expect(screen.queryByText(/backend unavailable/i)).not.toBeInTheDocument()
  })

  it('shows banner when backend is unreachable', async () => {
    fetchSpy.mockRejectedValue(new Error('Network error'))
    render(<OfflineBanner />)
    await waitFor(() => {
      expect(screen.getByText(/backend unavailable/i)).toBeInTheDocument()
    })
  })
})
