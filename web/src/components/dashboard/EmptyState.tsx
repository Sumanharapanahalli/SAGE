import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchOrg } from '../../api/client'

export default function EmptyState() {
  const navigate = useNavigate()
  const { data: orgData } = useQuery({ queryKey: ['org'], queryFn: fetchOrg })
  const hasMission = Boolean(orgData?.org?.mission)

  const cardStyle: React.CSSProperties = {
    background: 'rgba(255,255,255,0.03)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 10,
    padding: '20px 24px',
    display: 'flex',
    alignItems: 'flex-start',
    gap: 16,
  }

  const stepNumStyle = (done: boolean): React.CSSProperties => ({
    width: 28,
    height: 28,
    borderRadius: '50%',
    background: done ? '#16a34a' : 'rgba(255,255,255,0.08)',
    color: done ? '#fff' : 'var(--sage-sidebar-text, #94a3b8)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 13,
    fontWeight: 600,
    flexShrink: 0,
  })

  return (
    <div style={{ maxWidth: 560, margin: '80px auto', padding: '0 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <h2 style={{ fontSize: 20, fontWeight: 600, color: 'var(--sage-sidebar-active-text, #f1f5f9)', margin: 0 }}>Welcome to SAGE</h2>
        <p style={{ fontSize: 13, color: 'var(--sage-sidebar-text, #94a3b8)', marginTop: 6 }}>
          Get started by defining your organization, then create your first solution.
        </p>
      </div>

      {/* Step 1 */}
      <div style={cardStyle}>
        <div style={stepNumStyle(hasMission)}>{hasMission ? '✓' : '1'}</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--sage-sidebar-active-text, #f1f5f9)', marginBottom: 4 }}>
            Define your organization
          </div>
          <p style={{ fontSize: 12, color: 'var(--sage-sidebar-text, #94a3b8)', margin: '0 0 12px' }}>
            Set your company mission, vision, and core values. SAGE uses this as the root context for every solution you build.
          </p>
          {!hasMission && (
            <button
              onClick={() => navigate('/settings/organization')}
              style={{
                background: 'var(--sage-sidebar-accent, #6366f1)',
                color: '#fff',
                border: 'none',
                padding: '7px 16px',
                borderRadius: 6,
                fontSize: 12,
                cursor: 'pointer',
              }}
            >
              Set up organization
            </button>
          )}
          {hasMission && <span style={{ fontSize: 12, color: '#10b981' }}>Done</span>}
        </div>
      </div>

      {/* Step 2 */}
      <div style={cardStyle}>
        <div style={stepNumStyle(false)}>2</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--sage-sidebar-active-text, #f1f5f9)', marginBottom: 4 }}>
            Create your first solution
          </div>
          <p style={{ fontSize: 12, color: 'var(--sage-sidebar-text, #94a3b8)', margin: '0 0 12px' }}>
            Describe a domain or import an existing codebase — SAGE generates the agent configuration for you.
          </p>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <button
              onClick={() => navigate('/onboarding')}
              style={{
                background: 'rgba(99,102,241,0.15)',
                color: '#a5b4fc',
                border: '1px solid rgba(99,102,241,0.3)',
                padding: '7px 16px',
                borderRadius: 6,
                fontSize: 12,
                cursor: 'pointer',
              }}
            >
              Create solution
            </button>
            <button
              onClick={() => navigate('/')}
              style={{ background: 'transparent', color: 'var(--sage-sidebar-text, #94a3b8)', border: 'none', fontSize: 12, cursor: 'pointer' }}
            >
              Skip for now
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
