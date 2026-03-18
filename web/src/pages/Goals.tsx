import { useState, useEffect } from 'react'
import { Target, ChevronDown, ChevronUp, Plus, X, Check } from 'lucide-react'

// ---------------------------------------------------------------------------
// Data model
// ---------------------------------------------------------------------------
interface KeyResult {
  id: string
  title: string
  current: number
  target: number
  unit: string
  linked_task_ids: string[]
}

interface Objective {
  id: string
  title: string
  quarter: string
  status: 'on_track' | 'at_risk' | 'off_track'
  owner: string
  key_results: KeyResult[]
}

// ---------------------------------------------------------------------------
// Default seed data
// ---------------------------------------------------------------------------
const SEED: Objective[] = [
  {
    id: 'obj-1',
    title: 'Ship the core agent platform',
    quarter: 'Q1-2025',
    status: 'on_track',
    owner: 'AI Team',
    key_results: [
      { id: 'kr-1-1', title: 'Complete SWE workflow', current: 1, target: 1, unit: 'workflow', linked_task_ids: [] },
      { id: 'kr-1-2', title: 'Onboard first solution', current: 1, target: 1, unit: 'solution', linked_task_ids: [] },
      { id: 'kr-1-3', title: 'Pass all framework tests', current: 383, target: 400, unit: 'tests', linked_task_ids: [] },
    ],
  },
  {
    id: 'obj-2',
    title: 'Onboard first enterprise customer',
    quarter: 'Q1-2025',
    status: 'at_risk',
    owner: 'Founder',
    key_results: [
      { id: 'kr-2-1', title: 'Deploy PoseEngine solution', current: 0, target: 1, unit: 'deployment', linked_task_ids: [] },
      { id: 'kr-2-2', title: 'Complete 20 agent tasks', current: 7, target: 20, unit: 'tasks', linked_task_ids: [] },
      { id: 'kr-2-3', title: 'Zero critical bugs in prod', current: 2, target: 0, unit: 'bugs', linked_task_ids: [] },
    ],
  },
]

const STORAGE_KEY = 'sage_okr_objectives'

function loadObjectives(): Objective[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw) as Objective[]
  } catch { /* ignore */ }
  return SEED
}

function saveObjectives(objs: Objective[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(objs))
}

// ---------------------------------------------------------------------------
// Quarter helpers
// ---------------------------------------------------------------------------
function parseQuarter(q: string): { qNum: number; year: number } {
  const [qPart, yearPart] = q.split('-')
  return { qNum: parseInt(qPart.slice(1)), year: parseInt(yearPart) }
}

function formatQuarter(qNum: number, year: number): string {
  return `Q${qNum}-${year}`
}

function prevQuarter(q: string) {
  const { qNum, year } = parseQuarter(q)
  return qNum === 1 ? formatQuarter(4, year - 1) : formatQuarter(qNum - 1, year)
}

function nextQuarter(q: string) {
  const { qNum, year } = parseQuarter(q)
  return qNum === 4 ? formatQuarter(1, year + 1) : formatQuarter(qNum + 1, year)
}

function displayQuarter(q: string) {
  const { qNum, year } = parseQuarter(q)
  return `Q${qNum} ${year}`
}

// ---------------------------------------------------------------------------
// Status helpers
// ---------------------------------------------------------------------------
const STATUS_LABELS: Record<Objective['status'], string> = {
  on_track:  'On Track',
  at_risk:   'At Risk',
  off_track: 'Off Track',
}

const STATUS_COLORS: Record<Objective['status'], { bg: string; text: string; bar: string }> = {
  on_track:  { bg: '#14532d22', text: '#22c55e', bar: '#22c55e' },
  at_risk:   { bg: '#71350022', text: '#eab308', bar: '#eab308' },
  off_track: { bg: '#7f1d1d22', text: '#ef4444', bar: '#ef4444' },
}

function krProgress(kr: KeyResult): number {
  if (kr.target === 0) return kr.current === 0 ? 100 : 0
  return Math.min(100, Math.round((kr.current / kr.target) * 100))
}

function objProgress(obj: Objective): number {
  if (obj.key_results.length === 0) return 0
  const total = obj.key_results.reduce((acc, kr) => acc + krProgress(kr), 0)
  return Math.round(total / obj.key_results.length)
}

function uid() {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

// ---------------------------------------------------------------------------
// Key Result row
// ---------------------------------------------------------------------------
function KRRow({ kr }: { kr: KeyResult }) {
  const pct = krProgress(kr)
  return (
    <div className="flex items-center gap-3 py-2" style={{ borderTop: '1px solid #27272a' }}>
      <div className="flex-1 min-w-0">
        <div className="text-xs" style={{ color: '#a1a1aa' }}>{kr.title}</div>
        <div className="mt-1 h-1 w-full" style={{ backgroundColor: '#27272a' }}>
          <div
            className="h-1 transition-all"
            style={{ width: `${pct}%`, backgroundColor: pct >= 80 ? '#22c55e' : pct >= 40 ? '#eab308' : '#ef4444' }}
          />
        </div>
      </div>
      <div className="text-xs shrink-0 font-mono" style={{ color: '#71717a' }}>
        {kr.current} / {kr.target} {kr.unit}
      </div>
      {kr.linked_task_ids.length > 0 && (
        <span
          className="text-xs px-1.5 py-0.5 shrink-0"
          style={{ backgroundColor: '#27272a', color: '#71717a' }}
        >
          {kr.linked_task_ids.length} tasks
        </span>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Objective card
// ---------------------------------------------------------------------------
function ObjectiveCard({
  obj,
  onDelete,
}: {
  obj: Objective
  onDelete: (id: string) => void
}) {
  const [expanded, setExpanded] = useState(true)
  const pct = objProgress(obj)
  const colors = STATUS_COLORS[obj.status]

  return (
    <div style={{ border: '1px solid #3f3f46', backgroundColor: '#18181b' }}>
      {/* Header row */}
      <div className="px-4 py-3">
        <div className="flex items-start gap-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-semibold" style={{ color: '#f4f4f5' }}>{obj.title}</span>
              <span
                className="text-xs px-1.5 py-0.5 font-medium shrink-0"
                style={{ backgroundColor: colors.bg, color: colors.text }}
              >
                {STATUS_LABELS[obj.status]}
              </span>
            </div>
            <div className="flex items-center gap-3 mt-0.5">
              <span className="text-xs" style={{ color: '#52525b' }}>{obj.owner}</span>
              <span className="text-xs" style={{ color: '#3f3f46' }}>·</span>
              <span className="text-xs" style={{ color: '#52525b' }}>{obj.key_results.length} key results</span>
            </div>
          </div>
          {/* Progress */}
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-sm font-bold font-mono" style={{ color: colors.text }}>{pct}%</span>
            <button
              onClick={() => onDelete(obj.id)}
              className="p-0.5 transition-colors"
              style={{ color: '#3f3f46' }}
              title="Delete objective"
            >
              <X size={12} />
            </button>
            <button
              onClick={() => setExpanded(e => !e)}
              className="p-0.5"
              style={{ color: '#52525b' }}
            >
              {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
          </div>
        </div>

        {/* Progress bar */}
        <div className="mt-2 h-1 w-full" style={{ backgroundColor: '#27272a' }}>
          <div
            className="h-1 transition-all"
            style={{ width: `${pct}%`, backgroundColor: colors.bar }}
          />
        </div>
      </div>

      {/* Key results */}
      {expanded && obj.key_results.length > 0 && (
        <div className="px-4 pb-3">
          {obj.key_results.map(kr => (
            <KRRow key={kr.id} kr={kr} />
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Add-goal inline form
// ---------------------------------------------------------------------------
interface NewKR {
  title: string
  target: string
  unit: string
}

function AddGoalForm({
  quarter,
  onSave,
  onCancel,
}: {
  quarter: string
  onSave: (obj: Objective) => void
  onCancel: () => void
}) {
  const [title, setTitle] = useState('')
  const [owner, setOwner] = useState('AI Team')
  const [status, setStatus] = useState<Objective['status']>('on_track')
  const [krs, setKRs] = useState<NewKR[]>([
    { title: '', target: '1', unit: 'tasks' },
  ])

  function addKR() {
    setKRs(prev => [...prev, { title: '', target: '1', unit: 'tasks' }])
  }

  function removeKR(i: number) {
    setKRs(prev => prev.filter((_, idx) => idx !== i))
  }

  function updateKR(i: number, field: keyof NewKR, value: string) {
    setKRs(prev => prev.map((kr, idx) => idx === i ? { ...kr, [field]: value } : kr))
  }

  function handleSave() {
    if (!title.trim()) return
    const obj: Objective = {
      id: uid(),
      title: title.trim(),
      quarter,
      status,
      owner: owner.trim() || 'AI Team',
      key_results: krs
        .filter(kr => kr.title.trim())
        .map(kr => ({
          id: uid(),
          title: kr.title.trim(),
          current: 0,
          target: Math.max(1, parseInt(kr.target) || 1),
          unit: kr.unit.trim() || 'tasks',
          linked_task_ids: [],
        })),
    }
    onSave(obj)
  }

  const inputStyle = {
    backgroundColor: '#09090b',
    border: '1px solid #3f3f46',
    color: '#f4f4f5',
    padding: '6px 10px',
    fontSize: '12px',
    outline: 'none',
    width: '100%',
  } as React.CSSProperties

  const labelStyle = { color: '#71717a', fontSize: '11px', marginBottom: '4px', display: 'block' } as React.CSSProperties

  return (
    <div style={{ border: '1px solid #3f3f46', backgroundColor: '#18181b', padding: '16px' }}>
      <div className="text-xs font-semibold mb-3" style={{ color: '#f4f4f5' }}>New Objective</div>

      <div className="space-y-3">
        <div>
          <label style={labelStyle}>Objective title</label>
          <input
            style={inputStyle}
            placeholder="e.g. Ship the core agent platform"
            value={title}
            onChange={e => setTitle(e.target.value)}
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label style={labelStyle}>Owner</label>
            <input
              style={inputStyle}
              placeholder="AI Team"
              value={owner}
              onChange={e => setOwner(e.target.value)}
            />
          </div>
          <div>
            <label style={labelStyle}>Status</label>
            <select
              style={{ ...inputStyle }}
              value={status}
              onChange={e => setStatus(e.target.value as Objective['status'])}
            >
              <option value="on_track">On Track</option>
              <option value="at_risk">At Risk</option>
              <option value="off_track">Off Track</option>
            </select>
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <label style={labelStyle}>Key Results</label>
            <button
              onClick={addKR}
              className="flex items-center gap-1 text-xs"
              style={{ color: '#71717a' }}
            >
              <Plus size={11} /> Add KR
            </button>
          </div>
          <div className="space-y-2">
            {krs.map((kr, i) => (
              <div key={i} className="flex items-center gap-2">
                <input
                  style={{ ...inputStyle, flex: 1 }}
                  placeholder="Key result title"
                  value={kr.title}
                  onChange={e => updateKR(i, 'title', e.target.value)}
                />
                <input
                  style={{ ...inputStyle, width: '60px', flex: 'none' }}
                  placeholder="10"
                  value={kr.target}
                  onChange={e => updateKR(i, 'target', e.target.value)}
                  type="number"
                  min="0"
                />
                <input
                  style={{ ...inputStyle, width: '72px', flex: 'none' }}
                  placeholder="tasks"
                  value={kr.unit}
                  onChange={e => updateKR(i, 'unit', e.target.value)}
                />
                <button onClick={() => removeKR(i)} style={{ color: '#52525b', flexShrink: 0 }}>
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 mt-4">
        <button
          onClick={handleSave}
          className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5"
          style={{ backgroundColor: '#3f3f46', color: '#f4f4f5' }}
        >
          <Check size={12} /> Save Objective
        </button>
        <button
          onClick={onCancel}
          className="text-xs px-3 py-1.5"
          style={{ color: '#71717a', border: '1px solid #3f3f46' }}
        >
          Cancel
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Goals page
// ---------------------------------------------------------------------------
export default function Goals() {
  const [objectives, setObjectives] = useState<Objective[]>(loadObjectives)
  const [activeQuarter, setActiveQuarter] = useState('Q1-2025')
  const [adding, setAdding] = useState(false)

  // Persist on change
  useEffect(() => {
    saveObjectives(objectives)
  }, [objectives])

  const filtered = objectives.filter(o => o.quarter === activeQuarter)

  function handleAdd(obj: Objective) {
    setObjectives(prev => [...prev, obj])
    setAdding(false)
  }

  function handleDelete(id: string) {
    setObjectives(prev => prev.filter(o => o.id !== id))
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Target size={18} style={{ color: '#71717a' }} />
          <h1 className="text-base font-semibold" style={{ color: '#f4f4f5' }}>Goals</h1>
        </div>

        {/* Quarter nav */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setActiveQuarter(q => prevQuarter(q))}
            className="text-xs px-2 py-1 transition-colors"
            style={{ color: '#71717a', border: '1px solid #3f3f46' }}
          >
            ‹
          </button>
          <span
            className="text-xs font-semibold px-3 py-1"
            style={{ color: '#f4f4f5', border: '1px solid #3f3f46', backgroundColor: '#18181b' }}
          >
            {displayQuarter(activeQuarter)}
          </span>
          <button
            onClick={() => setActiveQuarter(q => nextQuarter(q))}
            className="text-xs px-2 py-1 transition-colors"
            style={{ color: '#71717a', border: '1px solid #3f3f46' }}
          >
            ›
          </button>

          <button
            onClick={() => setAdding(true)}
            className="flex items-center gap-1.5 text-xs font-medium px-3 py-1 ml-2"
            style={{ backgroundColor: '#3f3f46', color: '#f4f4f5' }}
            disabled={adding}
          >
            <Plus size={12} /> Add Goal
          </button>
        </div>
      </div>

      {/* Quarter summary */}
      {filtered.length > 0 && (
        <div
          className="flex items-center gap-6 px-4 py-2.5 text-xs"
          style={{ backgroundColor: '#18181b', border: '1px solid #27272a' }}
        >
          {(['on_track', 'at_risk', 'off_track'] as const).map(s => {
            const count = filtered.filter(o => o.status === s).length
            return (
              <span key={s} style={{ color: count > 0 ? STATUS_COLORS[s].text : '#3f3f46' }}>
                {count} {STATUS_LABELS[s]}
              </span>
            )
          })}
          <span style={{ color: '#52525b', marginLeft: 'auto' }}>
            Avg {Math.round(filtered.reduce((a, o) => a + objProgress(o), 0) / filtered.length)}% complete
          </span>
        </div>
      )}

      {/* Add goal form */}
      {adding && (
        <AddGoalForm
          quarter={activeQuarter}
          onSave={handleAdd}
          onCancel={() => setAdding(false)}
        />
      )}

      {/* Objectives list */}
      {filtered.length === 0 && !adding ? (
        <div
          className="flex flex-col items-center justify-center py-16 text-center"
          style={{ border: '1px dashed #3f3f46' }}
        >
          <Target size={24} style={{ color: '#3f3f46', marginBottom: '8px' }} />
          <div className="text-sm" style={{ color: '#52525b' }}>No objectives for {displayQuarter(activeQuarter)}</div>
          <button
            onClick={() => setAdding(true)}
            className="mt-3 text-xs px-3 py-1.5"
            style={{ border: '1px solid #3f3f46', color: '#71717a' }}
          >
            Add first objective
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map(obj => (
            <ObjectiveCard key={obj.id} obj={obj} onDelete={handleDelete} />
          ))}
        </div>
      )}
    </div>
  )
}
