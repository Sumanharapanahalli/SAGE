import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLLMHealth } from '../../hooks/useLLMHealth'

export default function LLMDisconnectedBanner() {
  const { connected, provider, detail, isChecking } = useLLMHealth()
  const [dismissed, setDismissed] = useState(false)
  const navigate = useNavigate()

  // connected === null means first check not done yet — don't show anything
  if (connected === null || connected === true || dismissed) return null

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 24,
        right: 24,
        zIndex: 10000,
        width: 340,
        background: '#1c0a0a',
        border: '1px solid #7f1d1d',
        boxShadow: '0 8px 32px rgba(0,0,0,0.7)',
        padding: '16px',
      }}
      role="alert"
      aria-live="assertive"
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{
            width: 8, height: 8, borderRadius: '50%', background: '#ef4444', display: 'inline-block', flexShrink: 0,
          }} />
          <span style={{ fontSize: '13px', fontWeight: 600, color: '#fca5a5' }}>
            LLM Connection Lost
          </span>
        </div>
        <button
          onClick={() => setDismissed(true)}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#7f1d1d', fontSize: '16px', lineHeight: 1, padding: '0 2px' }}
          aria-label="Dismiss"
        >
          x
        </button>
      </div>

      {/* Body */}
      <p style={{ fontSize: '12px', color: '#fca5a5', marginBottom: '4px' }}>
        Provider <strong>{provider || 'unknown'}</strong> is not responding.
      </p>
      {detail && (
        <p style={{ fontSize: '11px', color: '#991b1b', marginBottom: '10px', wordBreak: 'break-word' }}>
          {detail}
        </p>
      )}

      {/* Actions */}
      <div style={{ display: 'flex', gap: '8px', marginTop: '10px' }}>
        <button
          onClick={() => { navigate('/llm'); setDismissed(true) }}
          style={{
            flex: 1, padding: '6px 12px', fontSize: '12px', fontWeight: 600,
            background: '#ef4444', color: '#fff', border: 'none', cursor: 'pointer',
          }}
        >
          Open LLM Settings
        </button>
        <button
          onClick={() => setDismissed(true)}
          style={{
            padding: '6px 12px', fontSize: '12px',
            background: 'transparent', color: '#fca5a5',
            border: '1px solid #7f1d1d', cursor: 'pointer',
          }}
        >
          Dismiss
        </button>
      </div>

      {isChecking && (
        <p style={{ fontSize: '10px', color: '#7f1d1d', marginTop: '8px' }}>Rechecking...</p>
      )}
    </div>
  )
}
