import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { fetchOrg, fetchHealth, fetchLLMHealth } from '../api/client'
import OnboardingWizard from '../components/onboarding/OnboardingWizard'
import ImportFlow from '../components/onboarding/ImportFlow'
import { useTourContext } from '../context/TourContext'

export default function Onboarding() {
  const navigate = useNavigate()
  const { startTour } = useTourContext()
  const [mode, setMode] = useState<'describe' | 'import'>('describe')

  const { data: orgData } = useQuery({ queryKey: ['org'], queryFn: fetchOrg })
  useQuery({ queryKey: ['health'], queryFn: fetchHealth, refetchInterval: 10_000 })
  const { data: llmHealth } = useQuery({
    queryKey: ['health', 'llm'],
    queryFn: fetchLLMHealth,
    refetchInterval: 10_000,
  })

  const org = orgData?.org ?? {}
  const llmConnected = llmHealth?.connected ?? false

  return (
    <div style={{ minHeight: '100vh', background: 'var(--sage-sidebar-bg, #0f172a)', padding: '32px 24px' }}>

      {/* LLM gate banner */}
      {!llmConnected && (
        <div style={{
          background: 'rgba(251,191,36,0.08)',
          border: '1px solid rgba(251,191,36,0.25)',
          borderRadius: 8,
          padding: '10px 16px',
          marginBottom: 20,
          fontSize: 13,
          color: '#fbbf24',
          display: 'flex',
          gap: 8,
          alignItems: 'center',
        }}>
          LLM is not connected — generation is disabled.
          <a href="/llm" style={{ color: '#fbbf24', textDecoration: 'underline', marginLeft: 4 }}>Go to Settings → LLM</a>
        </div>
      )}

      {/* Mission banner */}
      {org.mission && (
        <div style={{
          background: 'rgba(99,102,241,0.08)',
          border: '1px solid rgba(99,102,241,0.2)',
          borderLeft: '3px solid var(--sage-sidebar-accent, #6366f1)',
          borderRadius: 6,
          padding: '10px 16px',
          marginBottom: 24,
        }}>
          <div style={{ fontSize: 10, color: '#818cf8', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 2 }}>
            Building under — {org.name || 'Your Organization'}
          </div>
          <div style={{ fontSize: 13, color: 'var(--sage-sidebar-active-text, #f1f5f9)' }}>{org.mission}</div>
        </div>
      )}

      {/* Mode toggle */}
      <div style={{ display: 'flex', gap: 0, border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6, overflow: 'hidden', width: 'fit-content', marginBottom: 28 }}>
        {(['describe', 'import'] as const).map(m => (
          <button
            key={m}
            onClick={() => setMode(m)}
            style={{
              padding: '8px 20px',
              background: mode === m ? 'rgba(99,102,241,0.2)' : 'transparent',
              color: mode === m ? '#a5b4fc' : '#64748b',
              border: 'none',
              borderRight: m === 'describe' ? '1px solid rgba(255,255,255,0.1)' : 'none',
              cursor: 'pointer',
              fontSize: 13,
            }}
          >
            {m === 'describe' ? 'Describe it' : 'Import from folder'}
          </button>
        ))}
      </div>

      {/* Content */}
      {mode === 'describe' ? (
        <OnboardingWizard
          onClose={() => navigate('/')}
          onTourStart={(id) => { startTour(id); navigate('/') }}
          llmConnected={llmConnected}
          inline
        />
      ) : (
        <ImportFlow llmConnected={llmConnected} />
      )}
    </div>
  )
}
