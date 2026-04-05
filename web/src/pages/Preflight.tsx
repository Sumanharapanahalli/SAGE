import { useState, useEffect } from 'react'

interface CheckResult {
  name: string
  status: 'checking' | 'ok' | 'warning' | 'error'
  message: string
}

const BASE = '/api'

export default function Preflight() {
  const [checks, setChecks] = useState<CheckResult[]>([
    { name: 'Backend API', status: 'checking', message: 'Connecting...' },
    { name: 'LLM Provider', status: 'checking', message: 'Checking...' },
    { name: 'Knowledge Store', status: 'checking', message: 'Checking...' },
    { name: 'Skill Registry', status: 'checking', message: 'Checking...' },
  ])
  const [allDone, setAllDone] = useState(false)

  const updateCheck = (index: number, result: Partial<CheckResult>) => {
    setChecks(prev => prev.map((c, i) => i === index ? { ...c, ...result } : c))
  }

  useEffect(() => {
    const runChecks = async () => {
      // 1. Backend API
      try {
        const res = await fetch(`${BASE}/health`)
        const data = await res.json()
        updateCheck(0, {
          status: 'ok',
          message: `Connected — ${data.llm_provider || 'unknown provider'}`,
        })
      } catch {
        updateCheck(0, {
          status: 'error',
          message: 'Backend unreachable. Start with: make run',
        })
      }

      // 2. LLM Provider
      try {
        const res = await fetch(`${BASE}/health/llm`)
        const data = await res.json()
        if (data.connected) {
          updateCheck(1, {
            status: 'ok',
            message: `${data.provider} — ${Math.round(data.latency_ms)}ms latency`,
          })
        } else {
          updateCheck(1, {
            status: 'warning',
            message: `${data.provider} configured but not responding`,
          })
        }
      } catch {
        updateCheck(1, {
          status: 'warning',
          message: 'LLM health check failed — provider may not be configured',
        })
      }

      // 3. Knowledge Store
      try {
        const res = await fetch(`${BASE}/knowledge/entries?limit=1`)
        if (res.ok) {
          updateCheck(2, { status: 'ok', message: 'Vector store accessible' })
        } else {
          updateCheck(2, { status: 'warning', message: 'Vector store returned error' })
        }
      } catch {
        updateCheck(2, { status: 'warning', message: 'Knowledge store unreachable' })
      }

      // 4. Skill Registry
      try {
        const res = await fetch(`${BASE}/skills`)
        const data = await res.json()
        const count = data.skills?.length || data.count || 0
        updateCheck(3, { status: 'ok', message: `${count} skills loaded` })
      } catch {
        updateCheck(3, { status: 'warning', message: 'Skill registry unreachable' })
      }

      setAllDone(true)
    }

    runChecks()
  }, [])

  const statusIcon = (status: CheckResult['status']) => {
    switch (status) {
      case 'checking': return '⏳'
      case 'ok': return '✓'
      case 'warning': return '⚠'
      case 'error': return '✗'
    }
  }

  const statusColor = (status: CheckResult['status']) => {
    switch (status) {
      case 'checking': return '#9ca3af'
      case 'ok': return '#22c55e'
      case 'warning': return '#f97316'
      case 'error': return '#ef4444'
    }
  }

  const hasErrors = checks.some(c => c.status === 'error')
  const hasWarnings = checks.some(c => c.status === 'warning')

  return (
    <div style={{ maxWidth: 600, margin: '0 auto', padding: '2rem' }}>
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.5rem', color: '#1f2937' }}>
        System Preflight Check
      </h1>
      <p style={{ color: '#6b7280', marginBottom: '2rem' }}>
        Verifying all SAGE components are operational.
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {checks.map((check, i) => (
          <div
            key={i}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '1rem',
              padding: '1rem',
              borderRadius: '0.5rem',
              border: `1px solid ${check.status === 'checking' ? '#e5e7eb' : statusColor(check.status)}20`,
              background: check.status === 'ok' ? '#f0fdf4' : check.status === 'error' ? '#fef2f2' : check.status === 'warning' ? '#fff7ed' : '#f9fafb',
            }}
          >
            <span
              style={{
                fontSize: '1.25rem',
                color: statusColor(check.status),
                fontWeight: 700,
                width: '1.5rem',
                textAlign: 'center',
              }}
            >
              {statusIcon(check.status)}
            </span>
            <div>
              <div style={{ fontWeight: 600, color: '#1f2937' }}>{check.name}</div>
              <div style={{ fontSize: '0.875rem', color: '#6b7280' }}>{check.message}</div>
            </div>
          </div>
        ))}
      </div>

      {allDone && (
        <div
          style={{
            marginTop: '2rem',
            padding: '1rem',
            borderRadius: '0.5rem',
            background: hasErrors ? '#fef2f2' : hasWarnings ? '#fff7ed' : '#f0fdf4',
            border: `1px solid ${hasErrors ? '#fca5a5' : hasWarnings ? '#fed7aa' : '#86efac'}`,
            textAlign: 'center',
            fontWeight: 600,
            color: hasErrors ? '#dc2626' : hasWarnings ? '#ea580c' : '#16a34a',
          }}
        >
          {hasErrors
            ? 'Some critical checks failed. Fix errors above to proceed.'
            : hasWarnings
            ? 'System operational with warnings. Some features may be limited.'
            : 'All systems operational. SAGE is ready.'}
        </div>
      )}
    </div>
  )
}
