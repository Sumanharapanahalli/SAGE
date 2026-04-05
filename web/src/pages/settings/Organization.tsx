// web/src/pages/settings/Organization.tsx
import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchOrg, saveOrg } from '../../api/client'

export default function Organization() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['org'], queryFn: fetchOrg })

  const [name, setName] = useState<string>('')
  const [mission, setMission] = useState<string>('')
  const [vision, setVision] = useState<string>('')
  const [values, setValues] = useState<string>('')
  const [initialised, setInitialised] = useState(false)
  const [saved, setSaved] = useState(false)

  // Populate fields once data loads
  useEffect(() => {
    if (!isLoading && !initialised && data) {
      const o = data?.org ?? {}
      setName(o.name ?? '')
      setMission(o.mission ?? '')
      setVision(o.vision ?? '')
      setValues((o.core_values ?? []).join('\n'))
      setInitialised(true)
    }
  }, [isLoading, data, initialised])

  const mutation = useMutation({
    mutationFn: () => saveOrg({
      name: name.trim() || undefined,
      mission: mission.trim() || undefined,
      vision: vision.trim() || undefined,
      core_values: values.trim() ? values.split('\n').map(v => v.trim()).filter(Boolean) : undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['org'] })
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    },
  })

  const linkedSolutions: string[] = data?.org?.solutions ?? []

  const fieldStyle: React.CSSProperties = {
    width: '100%',
    background: 'rgba(255,255,255,0.05)',
    color: 'var(--sage-sidebar-active-text, #f1f5f9)',
    border: '1px solid rgba(255,255,255,0.12)',
    padding: '8px 12px',
    borderRadius: '6px',
    fontSize: '13px',
    fontFamily: 'inherit',
  }

  if (isLoading) return <div style={{ padding: 32, color: 'var(--sage-sidebar-text, #94a3b8)' }}>Loading...</div>

  return (
    <div style={{ maxWidth: 640, margin: '0 auto', padding: '32px 24px', display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--sage-sidebar-active-text, #f1f5f9)', margin: 0 }}>Organization</h1>
        <p style={{ fontSize: 13, color: 'var(--sage-sidebar-text, #94a3b8)', marginTop: 4 }}>
          Define your company mission and values. All solution generation will be shaped by this context.
        </p>
      </div>

      {/* Name */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <label style={{ fontSize: 11, color: 'var(--sage-sidebar-text, #94a3b8)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          Organization Name
        </label>
        <input
          style={{ ...fieldStyle, width: 320 }}
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="Acme Corp"
        />
      </div>

      {/* Mission */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <label style={{ fontSize: 11, color: 'var(--sage-sidebar-text, #94a3b8)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          Mission <span style={{ color: '#ef4444' }}>*</span>
        </label>
        <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)', margin: 0 }}>Why the company exists — the root all solutions branch from.</p>
        <textarea
          style={{ ...fieldStyle, height: 72, resize: 'vertical' }}
          value={mission}
          onChange={e => setMission(e.target.value)}
          placeholder="We help end unnecessary diabetic amputations through AI-assisted early detection."
        />
      </div>

      {/* Vision */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <label style={{ fontSize: 11, color: 'var(--sage-sidebar-text, #94a3b8)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          Vision
        </label>
        <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)', margin: 0 }}>Where you are going in 10 years.</p>
        <textarea
          style={{ ...fieldStyle, height: 64, resize: 'vertical' }}
          value={vision}
          onChange={e => setVision(e.target.value)}
          placeholder="A world where no patient loses a limb due to a late or missed diagnosis."
        />
      </div>

      {/* Core Values */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <label style={{ fontSize: 11, color: 'var(--sage-sidebar-text, #94a3b8)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          Core Values
        </label>
        <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)', margin: 0 }}>One per line — guides how every agent reasons.</p>
        <textarea
          style={{ ...fieldStyle, height: 88, resize: 'vertical' }}
          value={values}
          onChange={e => setValues(e.target.value)}
          placeholder={'Patient safety above all\nEvidence-based, never experimental\nTransparency with clinicians'}
        />
      </div>

      {/* Save */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          style={{
            background: 'var(--sage-sidebar-accent, #6366f1)',
            color: '#fff',
            border: 'none',
            padding: '9px 22px',
            borderRadius: 6,
            fontSize: 13,
            fontWeight: 500,
            cursor: mutation.isPending ? 'not-allowed' : 'pointer',
            opacity: mutation.isPending ? 0.7 : 1,
          }}
        >
          {mutation.isPending ? 'Saving...' : 'Save Organization'}
        </button>
        {saved && <span style={{ fontSize: 12, color: '#f97316' }}>Saved</span>}
        {mutation.isError && <span style={{ fontSize: 12, color: '#ef4444' }}>Save failed — try again</span>}
      </div>

      {/* Linked solutions */}
      {linkedSolutions.length > 0 && (
        <div style={{ borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 20 }}>
          <div style={{ fontSize: 11, color: 'var(--sage-sidebar-text, #94a3b8)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>
            Linked Solutions
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {linkedSolutions.map(s => (
              <span key={s} style={{
                background: 'rgba(255,255,255,0.05)',
                color: 'var(--sage-sidebar-text, #94a3b8)',
                padding: '4px 12px',
                borderRadius: 12,
                fontSize: 12,
                border: '1px solid rgba(255,255,255,0.1)',
              }}>{s}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
