import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchConstitution,
  fetchConstitutionStats,
  fetchConstitutionPreamble,
  fetchConstitutionHistory,
  validateConstitution,
  addPrinciple,
  updatePrinciple,
  deletePrinciple,
  addConstraint,
  updateVoice,
  updateDecisions,
  saveConstitution,
} from '../api/client'
import {
  BookOpen, Shield, Scale, MessageCircle, Settings2,
  History, Plus, Trash2, Save, Check, AlertTriangle,
  Eye, ChevronDown, ChevronRight,
} from 'lucide-react'

const card = {
  background: '#18181b',
  border: '1px solid #27272a',
  borderRadius: '10px',
  padding: '20px',
}

const btn = (variant: 'primary' | 'ghost' | 'danger' = 'ghost') => ({
  padding: '6px 14px',
  borderRadius: '6px',
  fontSize: '12px',
  fontWeight: 600 as const,
  cursor: 'pointer' as const,
  border: variant === 'primary'
    ? '1px solid #3b82f6'
    : variant === 'danger'
    ? '1px solid #ef4444'
    : '1px solid #3f3f46',
  background: variant === 'primary'
    ? 'rgba(59,130,246,0.15)'
    : variant === 'danger'
    ? 'rgba(239,68,68,0.1)'
    : 'rgba(255,255,255,0.03)',
  color: variant === 'primary' ? '#60a5fa' : variant === 'danger' ? '#f87171' : '#a1a1aa',
})

const input = {
  padding: '8px 12px',
  borderRadius: '6px',
  border: '1px solid #3f3f46',
  background: '#09090b',
  color: '#e4e4e7',
  fontSize: '13px',
  width: '100%',
}

const TABS = ['Overview', 'Principles', 'Constraints', 'Voice & Decisions', 'Preview', 'History'] as const
type Tab = typeof TABS[number]

export default function Constitution() {
  const [tab, setTab] = useState<Tab>('Overview')
  const qc = useQueryClient()

  const { data: constitution } = useQuery({ queryKey: ['constitution'], queryFn: fetchConstitution })
  const { data: stats } = useQuery({ queryKey: ['constitution-stats'], queryFn: fetchConstitutionStats })
  const { data: preamble } = useQuery({ queryKey: ['constitution-preamble'], queryFn: fetchConstitutionPreamble })
  const { data: history } = useQuery({ queryKey: ['constitution-history'], queryFn: fetchConstitutionHistory })
  const { data: validation } = useQuery({ queryKey: ['constitution-validate'], queryFn: validateConstitution })

  const saveMut = useMutation({
    mutationFn: () => saveConstitution('web-ui'),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['constitution'] })
      qc.invalidateQueries({ queryKey: ['constitution-stats'] })
      qc.invalidateQueries({ queryKey: ['constitution-history'] })
      qc.invalidateQueries({ queryKey: ['constitution-validate'] })
      qc.invalidateQueries({ queryKey: ['constitution-preamble'] })
    },
  })

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <BookOpen size={20} style={{ color: '#a78bfa' }} />
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 700, color: '#e4e4e7', margin: 0 }}>
              Solution Constitution
            </h1>
            <span style={{ fontSize: 12, color: '#71717a' }}>
              {stats ? `v${(stats as any).version} - ${(stats as any).principle_count} principles, ${(stats as any).constraint_count} constraints` : 'Loading...'}
            </span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {validation && !(validation as any).valid && (
            <span style={{ fontSize: 11, color: '#f59e0b', display: 'flex', alignItems: 'center', gap: 4 }}>
              <AlertTriangle size={12} /> {(validation as any).errors?.length} issues
            </span>
          )}
          {validation && (validation as any).valid && (
            <span style={{ fontSize: 11, color: '#22c55e', display: 'flex', alignItems: 'center', gap: 4 }}>
              <Check size={12} /> Valid
            </span>
          )}
          <button style={btn('primary')} onClick={() => saveMut.mutate()}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <Save size={12} /> Save
            </span>
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 2, marginBottom: 20, borderBottom: '1px solid #27272a', paddingBottom: 1 }}>
        {TABS.map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: '8px 16px',
              fontSize: 12,
              fontWeight: 500,
              background: tab === t ? 'rgba(167,139,250,0.1)' : 'transparent',
              color: tab === t ? '#a78bfa' : '#71717a',
              border: 'none',
              borderBottom: tab === t ? '2px solid #a78bfa' : '2px solid transparent',
              cursor: 'pointer',
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'Overview' && <OverviewTab stats={stats as any} constitution={constitution as any} />}
      {tab === 'Principles' && <PrinciplesTab constitution={constitution as any} qc={qc} />}
      {tab === 'Constraints' && <ConstraintsTab constitution={constitution as any} qc={qc} />}
      {tab === 'Voice & Decisions' && <VoiceDecisionsTab constitution={constitution as any} qc={qc} />}
      {tab === 'Preview' && <PreviewTab preamble={(preamble as any)?.preamble} />}
      {tab === 'History' && <HistoryTab history={(history as any)?.history} />}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Overview Tab
// ---------------------------------------------------------------------------

function OverviewTab({ stats, constitution }: { stats: any; constitution: any }) {
  if (!stats) return <div style={{ color: '#71717a' }}>Loading...</div>
  const items = [
    { icon: <Scale size={16} />, label: 'Principles', value: stats.principle_count, color: '#a78bfa' },
    { icon: <Shield size={16} />, label: 'Constraints', value: stats.constraint_count, color: '#f59e0b' },
    { icon: <AlertTriangle size={16} />, label: 'Non-Negotiable', value: stats.non_negotiable_count, color: '#ef4444' },
    { icon: <MessageCircle size={16} />, label: 'Voice', value: stats.has_voice ? 'Set' : 'Not set', color: '#22c55e' },
    { icon: <Settings2 size={16} />, label: 'Decisions', value: stats.has_decisions ? 'Set' : 'Not set', color: '#3b82f6' },
    { icon: <History size={16} />, label: 'Version', value: `v${stats.version}`, color: '#71717a' },
  ]

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 }}>
        {items.map(it => (
          <div key={it.label} style={card}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <span style={{ color: it.color }}>{it.icon}</span>
              <span style={{ fontSize: 11, color: '#71717a', fontWeight: 500 }}>{it.label}</span>
            </div>
            <div style={{ fontSize: 22, fontWeight: 700, color: '#e4e4e7' }}>{it.value}</div>
          </div>
        ))}
      </div>

      {stats.is_empty && (
        <div style={{ ...card, textAlign: 'center' as const, padding: 40 }}>
          <BookOpen size={32} style={{ color: '#3f3f46', margin: '0 auto 12px' }} />
          <div style={{ color: '#a1a1aa', fontSize: 14, marginBottom: 8 }}>No constitution defined yet</div>
          <div style={{ color: '#71717a', fontSize: 12 }}>
            Add principles, constraints, and voice to shape how agents behave in this solution.
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Principles Tab
// ---------------------------------------------------------------------------

function PrinciplesTab({ constitution, qc }: { constitution: any; qc: any }) {
  const [showAdd, setShowAdd] = useState(false)
  const [newId, setNewId] = useState('')
  const [newText, setNewText] = useState('')
  const [newWeight, setNewWeight] = useState('0.5')

  const addMut = useMutation({
    mutationFn: () => addPrinciple({ id: newId, text: newText, weight: parseFloat(newWeight) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['constitution'] })
      qc.invalidateQueries({ queryKey: ['constitution-stats'] })
      setNewId(''); setNewText(''); setNewWeight('0.5'); setShowAdd(false)
    },
  })

  const delMut = useMutation({
    mutationFn: (id: string) => deletePrinciple(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['constitution'] })
      qc.invalidateQueries({ queryKey: ['constitution-stats'] })
    },
  })

  const principles = constitution?.principles || []

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <span style={{ fontSize: 13, color: '#a1a1aa' }}>{principles.length} principles defined</span>
        <button style={btn('primary')} onClick={() => setShowAdd(!showAdd)}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><Plus size={12} /> Add</span>
        </button>
      </div>

      {showAdd && (
        <div style={{ ...card, marginBottom: 16 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 3fr 80px auto', gap: 8, alignItems: 'end' }}>
            <div>
              <label style={{ fontSize: 11, color: '#71717a', display: 'block', marginBottom: 4 }}>ID</label>
              <input style={input} value={newId} onChange={e => setNewId(e.target.value)} placeholder="safety-first" />
            </div>
            <div>
              <label style={{ fontSize: 11, color: '#71717a', display: 'block', marginBottom: 4 }}>Text</label>
              <input style={input} value={newText} onChange={e => setNewText(e.target.value)} placeholder="Patient safety overrides all..." />
            </div>
            <div>
              <label style={{ fontSize: 11, color: '#71717a', display: 'block', marginBottom: 4 }}>Weight</label>
              <input style={{ ...input, width: 70 }} type="number" min="0" max="1" step="0.1" value={newWeight} onChange={e => setNewWeight(e.target.value)} />
            </div>
            <button style={btn('primary')} onClick={() => addMut.mutate()}>Add</button>
          </div>
        </div>
      )}

      {principles.map((p: any) => (
        <div key={p.id} style={{ ...card, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: p.weight >= 1.0 ? '#ef4444' : p.weight >= 0.8 ? '#f59e0b' : '#22c55e',
            flexShrink: 0,
          }} />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, color: '#e4e4e7', fontWeight: 500 }}>
              {p.text}
              {p.weight >= 1.0 && <span style={{ fontSize: 10, color: '#ef4444', marginLeft: 8 }}>NON-NEGOTIABLE</span>}
            </div>
            <div style={{ fontSize: 11, color: '#71717a', marginTop: 2 }}>
              ID: {p.id} | Weight: {p.weight}
            </div>
          </div>
          <button style={btn('danger')} onClick={() => delMut.mutate(p.id)}>
            <Trash2 size={12} />
          </button>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Constraints Tab
// ---------------------------------------------------------------------------

function ConstraintsTab({ constitution, qc }: { constitution: any; qc: any }) {
  const [newConstraint, setNewConstraint] = useState('')

  const addMut = useMutation({
    mutationFn: () => addConstraint(newConstraint),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['constitution'] })
      qc.invalidateQueries({ queryKey: ['constitution-stats'] })
      setNewConstraint('')
    },
  })

  const constraints = constitution?.constraints || []

  return (
    <div>
      <div style={{ ...card, marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            style={{ ...input, flex: 1 }}
            value={newConstraint}
            onChange={e => setNewConstraint(e.target.value)}
            placeholder="e.g., Never deploy on Fridays"
            onKeyDown={e => e.key === 'Enter' && newConstraint && addMut.mutate()}
          />
          <button style={btn('primary')} onClick={() => newConstraint && addMut.mutate()}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><Plus size={12} /> Add</span>
          </button>
        </div>
      </div>

      {constraints.map((c: string, i: number) => (
        <div key={i} style={{ ...card, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 12 }}>
          <Shield size={14} style={{ color: '#f59e0b', flexShrink: 0 }} />
          <span style={{ fontSize: 13, color: '#e4e4e7', flex: 1 }}>{c}</span>
        </div>
      ))}

      {constraints.length === 0 && (
        <div style={{ ...card, textAlign: 'center' as const, color: '#71717a', fontSize: 13 }}>
          No constraints defined. Add hard rules that agents must never violate.
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Voice & Decisions Tab
// ---------------------------------------------------------------------------

function VoiceDecisionsTab({ constitution, qc }: { constitution: any; qc: any }) {
  const voice = constitution?.voice || {}
  const decisions = constitution?.decisions || {}
  const [tone, setTone] = useState(voice.tone || '')
  const [avoid, setAvoid] = useState((voice.avoid || []).join(', '))
  const [tier, setTier] = useState(decisions.default_approval_tier || 'human')
  const [autoCats, setAutoCats] = useState((decisions.auto_approve_categories || []).join(', '))
  const [keywords, setKeywords] = useState((decisions.escalation_keywords || []).join(', '))

  const voiceMut = useMutation({
    mutationFn: () => updateVoice({ tone, avoid: avoid.split(',').map((s: string) => s.trim()).filter(Boolean) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['constitution'] }),
  })

  const decMut = useMutation({
    mutationFn: () => updateDecisions({
      default_approval_tier: tier,
      auto_approve_categories: autoCats.split(',').map((s: string) => s.trim()).filter(Boolean),
      escalation_keywords: keywords.split(',').map((s: string) => s.trim()).filter(Boolean),
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['constitution'] }),
  })

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      {/* Voice */}
      <div style={card}>
        <h3 style={{ fontSize: 14, color: '#e4e4e7', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
          <MessageCircle size={14} style={{ color: '#22c55e' }} /> Agent Voice
        </h3>
        <div style={{ marginBottom: 12 }}>
          <label style={{ fontSize: 11, color: '#71717a', display: 'block', marginBottom: 4 }}>Tone</label>
          <input style={input} value={tone} onChange={e => setTone(e.target.value)} placeholder="precise, clinical, evidence-based" />
        </div>
        <div style={{ marginBottom: 12 }}>
          <label style={{ fontSize: 11, color: '#71717a', display: 'block', marginBottom: 4 }}>Avoid (comma-separated)</label>
          <input style={input} value={avoid} onChange={e => setAvoid(e.target.value)} placeholder="marketing speak, vague estimates" />
        </div>
        <button style={btn('primary')} onClick={() => voiceMut.mutate()}>Update Voice</button>
      </div>

      {/* Decisions */}
      <div style={card}>
        <h3 style={{ fontSize: 14, color: '#e4e4e7', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Settings2 size={14} style={{ color: '#3b82f6' }} /> Decision Rules
        </h3>
        <div style={{ marginBottom: 12 }}>
          <label style={{ fontSize: 11, color: '#71717a', display: 'block', marginBottom: 4 }}>Default Approval Tier</label>
          <select
            style={{ ...input, cursor: 'pointer' }}
            value={tier}
            onChange={e => setTier(e.target.value)}
          >
            <option value="human">Human (requires approval)</option>
            <option value="auto">Auto (agent decides)</option>
          </select>
        </div>
        <div style={{ marginBottom: 12 }}>
          <label style={{ fontSize: 11, color: '#71717a', display: 'block', marginBottom: 4 }}>Auto-approve categories (comma-separated)</label>
          <input style={input} value={autoCats} onChange={e => setAutoCats(e.target.value)} placeholder="docs, tests, formatting" />
        </div>
        <div style={{ marginBottom: 12 }}>
          <label style={{ fontSize: 11, color: '#71717a', display: 'block', marginBottom: 4 }}>Escalation keywords (comma-separated)</label>
          <input style={input} value={keywords} onChange={e => setKeywords(e.target.value)} placeholder="safety, regulatory, patient" />
        </div>
        <button style={btn('primary')} onClick={() => decMut.mutate()}>Update Decisions</button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Preview Tab
// ---------------------------------------------------------------------------

function PreviewTab({ preamble }: { preamble?: string }) {
  return (
    <div style={card}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <Eye size={14} style={{ color: '#a78bfa' }} />
        <span style={{ fontSize: 13, color: '#a1a1aa' }}>This preamble is injected into every agent system prompt:</span>
      </div>
      <pre style={{
        background: '#09090b',
        border: '1px solid #27272a',
        borderRadius: '6px',
        padding: 16,
        fontSize: 12,
        color: '#d4d4d8',
        whiteSpace: 'pre-wrap',
        lineHeight: 1.6,
        maxHeight: 500,
        overflow: 'auto',
      }}>
        {preamble || '(No constitution defined — no preamble injected)'}
      </pre>
    </div>
  )
}

// ---------------------------------------------------------------------------
// History Tab
// ---------------------------------------------------------------------------

function HistoryTab({ history }: { history?: any[] }) {
  if (!history || history.length === 0) {
    return (
      <div style={{ ...card, textAlign: 'center' as const, color: '#71717a', fontSize: 13 }}>
        No version history yet. Changes are tracked after the first save.
      </div>
    )
  }

  return (
    <div>
      {history.slice().reverse().map((h: any, i: number) => (
        <div key={i} style={{ ...card, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 12 }}>
          <History size={14} style={{ color: '#71717a' }} />
          <div style={{ flex: 1 }}>
            <span style={{ fontSize: 13, color: '#e4e4e7', fontWeight: 500 }}>Version {h.version}</span>
            <span style={{ fontSize: 11, color: '#71717a', marginLeft: 12 }}>
              by {h.changed_by} at {new Date(h.timestamp).toLocaleString()}
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}
