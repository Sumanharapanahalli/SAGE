import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import {
  ShieldAlert, AlertTriangle, GitBranch, Gauge,
  Plus, Trash2, Play, Info,
} from 'lucide-react'
import { runFMEA, classifyASIL, classifySIL, classifyIEC62304 } from '../api/client'

type Tab = 'fmea' | 'asil' | 'sil' | 'iec62304'

interface FMEAEntry {
  component: string; failure_mode: string; effect: string
  severity: number; occurrence: number; detection: number
}

const EMPTY_ENTRY: FMEAEntry = { component: '', failure_mode: '', effect: '', severity: 5, occurrence: 3, detection: 3 }

export default function SafetyAnalysis() {
  const [tab, setTab] = useState<Tab>('fmea')

  // FMEA state
  const [entries, setEntries] = useState<FMEAEntry[]>([{ ...EMPTY_ENTRY }])
  const fmeaMutation = useMutation({ mutationFn: () => runFMEA(entries) })

  const addEntry = () => setEntries(prev => [...prev, { ...EMPTY_ENTRY }])
  const removeEntry = (i: number) => setEntries(prev => prev.filter((_, idx) => idx !== i))
  const updateEntry = (i: number, field: keyof FMEAEntry, value: string | number) => {
    setEntries(prev => prev.map((e, idx) => idx === i ? { ...e, [field]: value } : e))
  }

  // ASIL state
  const [asilS, setAsilS] = useState('S3')
  const [asilE, setAsilE] = useState('E4')
  const [asilC, setAsilC] = useState('C3')
  const asilMutation = useMutation({ mutationFn: () => classifyASIL(asilS, asilE, asilC) })

  // SIL state
  const [silRate, setSilRate] = useState('1e-7')
  const silMutation = useMutation({ mutationFn: () => classifySIL(parseFloat(silRate)) })

  // IEC 62304 state
  const [iecRisk, setIecRisk] = useState('death_possible')
  const iecMutation = useMutation({ mutationFn: () => classifyIEC62304(iecRisk) })

  const tabs: { id: Tab; label: string; icon: typeof AlertTriangle }[] = [
    { id: 'fmea', label: 'FMEA', icon: AlertTriangle },
    { id: 'asil', label: 'ASIL (ISO 26262)', icon: Gauge },
    { id: 'sil', label: 'SIL (IEC 61508)', icon: ShieldAlert },
    { id: 'iec62304', label: 'IEC 62304', icon: GitBranch },
  ]

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-lg font-semibold" style={{ color: '#e4e4e7' }}>
          <ShieldAlert size={18} className="inline mr-2" style={{ color: '#ef4444' }} />
          Safety Analysis
        </h1>
        <p className="text-xs mt-1" style={{ color: '#71717a' }}>
          FMEA builder, ASIL/SIL classification, IEC 62304 software safety class
        </p>
      </div>

      <div className="sage-tabs">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} className={`sage-tab ${tab === t.id ? 'sage-tab-active' : ''}`}>
            <t.icon size={12} className="inline mr-1.5" />{t.label}
          </button>
        ))}
      </div>

      {/* FMEA Builder */}
      {tab === 'fmea' && (
        <div>
          <div className="sage-card mb-4" style={{ background: '#1c1c1e', borderColor: '#2a2a2e' }}>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold" style={{ color: '#e4e4e7' }}>
                Failure Mode & Effects Analysis
              </h2>
              <button onClick={addEntry} className="sage-btn sage-btn-secondary" style={{ fontSize: '11px' }}>
                <Plus size={11} /> Add Row
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="sage-table" style={{ minWidth: 800 }}>
                <thead>
                  <tr>
                    <th>Component</th>
                    <th>Failure Mode</th>
                    <th>Effect</th>
                    <th style={{ width: 60 }}>Sev</th>
                    <th style={{ width: 60 }}>Occ</th>
                    <th style={{ width: 60 }}>Det</th>
                    <th style={{ width: 60 }}>RPN</th>
                    <th style={{ width: 40 }}></th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((e, i) => {
                    const rpn = e.severity * e.occurrence * e.detection
                    const rpnColor = rpn >= 200 ? '#ef4444' : rpn >= 100 ? '#f59e0b' : '#22c55e'
                    return (
                      <tr key={i}>
                        <td><input value={e.component} onChange={ev => updateEntry(i, 'component', ev.target.value)} className="w-full text-xs px-1.5 py-1" style={{ background: '#111113', color: '#e4e4e7', border: '1px solid #2a2a2e', borderRadius: 4 }} /></td>
                        <td><input value={e.failure_mode} onChange={ev => updateEntry(i, 'failure_mode', ev.target.value)} className="w-full text-xs px-1.5 py-1" style={{ background: '#111113', color: '#e4e4e7', border: '1px solid #2a2a2e', borderRadius: 4 }} /></td>
                        <td><input value={e.effect} onChange={ev => updateEntry(i, 'effect', ev.target.value)} className="w-full text-xs px-1.5 py-1" style={{ background: '#111113', color: '#e4e4e7', border: '1px solid #2a2a2e', borderRadius: 4 }} /></td>
                        <td><input type="number" min={1} max={10} value={e.severity} onChange={ev => updateEntry(i, 'severity', +ev.target.value)} className="w-full text-xs px-1 py-1 text-center" style={{ background: '#111113', color: '#e4e4e7', border: '1px solid #2a2a2e', borderRadius: 4 }} /></td>
                        <td><input type="number" min={1} max={10} value={e.occurrence} onChange={ev => updateEntry(i, 'occurrence', +ev.target.value)} className="w-full text-xs px-1 py-1 text-center" style={{ background: '#111113', color: '#e4e4e7', border: '1px solid #2a2a2e', borderRadius: 4 }} /></td>
                        <td><input type="number" min={1} max={10} value={e.detection} onChange={ev => updateEntry(i, 'detection', +ev.target.value)} className="w-full text-xs px-1 py-1 text-center" style={{ background: '#111113', color: '#e4e4e7', border: '1px solid #2a2a2e', borderRadius: 4 }} /></td>
                        <td style={{ color: rpnColor, fontWeight: 600, textAlign: 'center', fontSize: '12px' }}>{rpn}</td>
                        <td>
                          {entries.length > 1 && (
                            <button onClick={() => removeEntry(i)} style={{ color: '#71717a', background: 'none', border: 'none', cursor: 'pointer' }}>
                              <Trash2 size={12} />
                            </button>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <div className="mt-3 flex items-center gap-3">
              <button
                onClick={() => fmeaMutation.mutate()}
                disabled={fmeaMutation.isPending || entries.every(e => !e.component)}
                className="sage-btn sage-btn-primary"
              >
                <Play size={12} />
                {fmeaMutation.isPending ? 'Analyzing...' : 'Run FMEA'}
              </button>
              <span className="text-xs" style={{ color: '#71717a' }}>
                {entries.length} entries, max RPN: {Math.max(...entries.map(e => e.severity * e.occurrence * e.detection))}
              </span>
            </div>
          </div>

          {/* FMEA Result */}
          {fmeaMutation.isSuccess && fmeaMutation.data && (
            <div className="sage-card" style={{ background: '#1c1c1e', borderColor: '#2a2a2e' }}>
              <h3 className="text-sm font-semibold mb-2" style={{ color: '#e4e4e7' }}>FMEA Results</h3>
              <pre className="text-xs overflow-auto p-3" style={{ background: '#111113', color: '#a1a1aa', borderRadius: 6, maxHeight: 300 }}>
                {JSON.stringify(fmeaMutation.data, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* ASIL Classification */}
      {tab === 'asil' && (
        <div className="max-w-lg">
          <div className="sage-card" style={{ background: '#1c1c1e', borderColor: '#2a2a2e' }}>
            <h2 className="text-sm font-semibold mb-4" style={{ color: '#e4e4e7' }}>
              ASIL Classification (ISO 26262)
            </h2>
            <div className="space-y-3">
              <div>
                <label className="block text-xs mb-1" style={{ color: '#71717a' }}>Severity (S0-S3)</label>
                <select value={asilS} onChange={e => setAsilS(e.target.value)} className="w-full text-sm px-3 py-2" style={{ background: '#111113', color: '#e4e4e7', border: '1px solid #2a2a2e', borderRadius: 8 }}>
                  <option value="S0">S0 — No injuries</option>
                  <option value="S1">S1 — Light/moderate injuries</option>
                  <option value="S2">S2 — Severe/life-threatening injuries</option>
                  <option value="S3">S3 — Life-threatening/fatal injuries</option>
                </select>
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: '#71717a' }}>Exposure (E1-E4)</label>
                <select value={asilE} onChange={e => setAsilE(e.target.value)} className="w-full text-sm px-3 py-2" style={{ background: '#111113', color: '#e4e4e7', border: '1px solid #2a2a2e', borderRadius: 8 }}>
                  <option value="E1">E1 — Very low probability</option>
                  <option value="E2">E2 — Low probability</option>
                  <option value="E3">E3 — Medium probability</option>
                  <option value="E4">E4 — High probability</option>
                </select>
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: '#71717a' }}>Controllability (C1-C3)</label>
                <select value={asilC} onChange={e => setAsilC(e.target.value)} className="w-full text-sm px-3 py-2" style={{ background: '#111113', color: '#e4e4e7', border: '1px solid #2a2a2e', borderRadius: 8 }}>
                  <option value="C1">C1 — Simply controllable</option>
                  <option value="C2">C2 — Normally controllable</option>
                  <option value="C3">C3 — Difficult to control</option>
                </select>
              </div>
              <button onClick={() => asilMutation.mutate()} disabled={asilMutation.isPending} className="sage-btn sage-btn-primary mt-2">
                <Play size={12} /> Classify
              </button>
            </div>
            {asilMutation.isSuccess && asilMutation.data && (
              <div className="mt-4 p-3" style={{ background: '#111113', borderRadius: 8 }}>
                <div className="text-center">
                  <span className="text-2xl font-bold" style={{ color: asilMutation.data.asil_level === 'D' ? '#ef4444' : asilMutation.data.asil_level === 'C' ? '#f59e0b' : '#22c55e' }}>
                    ASIL {asilMutation.data.asil_level ?? asilMutation.data.classification}
                  </span>
                  <p className="text-xs mt-1" style={{ color: '#a1a1aa' }}>{asilMutation.data.description ?? ''}</p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* SIL Classification */}
      {tab === 'sil' && (
        <div className="max-w-lg">
          <div className="sage-card" style={{ background: '#1c1c1e', borderColor: '#2a2a2e' }}>
            <h2 className="text-sm font-semibold mb-4" style={{ color: '#e4e4e7' }}>
              SIL Classification (IEC 61508)
            </h2>
            <div className="space-y-3">
              <div>
                <label className="block text-xs mb-1" style={{ color: '#71717a' }}>Target Failure Rate (per hour)</label>
                <select value={silRate} onChange={e => setSilRate(e.target.value)} className="w-full text-sm px-3 py-2" style={{ background: '#111113', color: '#e4e4e7', border: '1px solid #2a2a2e', borderRadius: 8 }}>
                  <option value="1e-5">10^-5 (SIL 1)</option>
                  <option value="1e-6">10^-6 (SIL 2)</option>
                  <option value="1e-7">10^-7 (SIL 3)</option>
                  <option value="1e-8">10^-8 (SIL 4)</option>
                </select>
              </div>
              <button onClick={() => silMutation.mutate()} disabled={silMutation.isPending} className="sage-btn sage-btn-primary">
                <Play size={12} /> Classify
              </button>
            </div>
            {silMutation.isSuccess && silMutation.data && (
              <div className="mt-4 p-3" style={{ background: '#111113', borderRadius: 8 }}>
                <div className="text-center">
                  <span className="text-2xl font-bold" style={{ color: '#a78bfa' }}>
                    SIL {silMutation.data.sil_level ?? silMutation.data.classification}
                  </span>
                  <p className="text-xs mt-1" style={{ color: '#a1a1aa' }}>{silMutation.data.description ?? ''}</p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* IEC 62304 */}
      {tab === 'iec62304' && (
        <div className="max-w-lg">
          <div className="sage-card" style={{ background: '#1c1c1e', borderColor: '#2a2a2e' }}>
            <h2 className="text-sm font-semibold mb-4" style={{ color: '#e4e4e7' }}>
              IEC 62304 Software Safety Classification
            </h2>
            <div className="space-y-3">
              <div>
                <label className="block text-xs mb-1" style={{ color: '#71717a' }}>Risk Level</label>
                <select value={iecRisk} onChange={e => setIecRisk(e.target.value)} className="w-full text-sm px-3 py-2" style={{ background: '#111113', color: '#e4e4e7', border: '1px solid #2a2a2e', borderRadius: 8 }}>
                  <option value="no_injury">No injury possible (Class A)</option>
                  <option value="injury_possible">Non-serious injury possible (Class B)</option>
                  <option value="serious_injury_possible">Serious injury possible (Class C)</option>
                  <option value="death_possible">Death or serious injury (Class C)</option>
                </select>
              </div>
              <button onClick={() => iecMutation.mutate()} disabled={iecMutation.isPending} className="sage-btn sage-btn-primary">
                <Play size={12} /> Classify
              </button>
            </div>
            {iecMutation.isSuccess && iecMutation.data && (
              <div className="mt-4 p-3" style={{ background: '#111113', borderRadius: 8 }}>
                <div className="text-center">
                  <span className="text-2xl font-bold" style={{ color: iecMutation.data.safety_class === 'C' ? '#ef4444' : iecMutation.data.safety_class === 'B' ? '#f59e0b' : '#22c55e' }}>
                    Class {iecMutation.data.safety_class}
                  </span>
                  <p className="text-xs mt-1" style={{ color: '#a1a1aa' }}>{iecMutation.data.description ?? ''}</p>
                  {iecMutation.data.requirements?.length > 0 && (
                    <div className="mt-3 text-left">
                      <p className="text-xs font-semibold mb-1" style={{ color: '#71717a' }}>Requirements:</p>
                      <ul className="text-xs space-y-0.5" style={{ color: '#a1a1aa' }}>
                        {iecMutation.data.requirements.map((r: string, i: number) => (
                          <li key={i}>- {r}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
