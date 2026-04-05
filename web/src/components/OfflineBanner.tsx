import { useState, useEffect, useRef } from 'react'

const POLL_INTERVAL = 10_000

export default function OfflineBanner() {
  const [offline, setOffline] = useState(false)
  const timer = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch('/api/health')
        setOffline(!res.ok)
      } catch {
        setOffline(true)
      }
    }

    check()
    timer.current = setInterval(check, POLL_INTERVAL)
    return () => { if (timer.current) clearInterval(timer.current) }
  }, [])

  if (!offline) return null

  return (
    <div
      style={{
        position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 9999,
        background: '#7f1d1d', color: '#fecaca', fontSize: 13, textAlign: 'center',
        padding: '8px 16px',
      }}
    >
      Backend unavailable — features may not work until the server is reachable.
    </div>
  )
}
