import { useState, useEffect } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { fetchProjects, switchProject } from '../../api/client'
import { Check, Loader2 } from 'lucide-react'

const API_BASE = (import.meta as any).env?.VITE_API_URL ?? 'http://localhost:8000'

interface GenerateRequest {
  description: string; solution_name: string
  compliance_standards: string[]; integrations: string[]
  parent_solution?: string; org_name?: string
}
interface GenerateResponse {
  solution_name: string; path: string; status: 'created' | 'exists'
  files: Record<string, string>; message: string; suggested_routes: string[]
}

async function callGenerate(body: GenerateRequest): Promise<GenerateResponse> {
  const res = await fetch(`${API_BASE}/onboarding/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const msg = await res.text()
    throw new Error(msg || 'Generation failed')
  }
  return res.json()
}

function ProgressBar({ step }: { step: number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', padding: '16px 24px' }}>
      {[1,2,3,4,5].map((n, i) => (
        <div key={n} style={{ display: 'flex', alignItems: 'center', flex: i < 4 ? 1 : 'none' }}>
          <div style={{
            width: 28, height: 28, borderRadius: '50%', display: 'flex', alignItems: 'center',
            justifyContent: 'center', fontSize: '12px', fontWeight: 700, flexShrink: 0,
            backgroundColor: n < step ? '#10b981' : n === step ? '#3b82f6' : '#1e293b',
            color: n <= step ? '#fff' : '#475569',
          }}>
            {n < step ? <Check size={14} /> : n}
          </div>
          {i < 4 && (
            <div style={{ flex: 1, height: '2px', backgroundColor: n < step ? '#10b981' : '#1e293b' }} />
          )}
        </div>
      ))}
    </div>
  )
}

interface Props {
  onClose: () => void
  onTourStart: (solutionId: string) => void
}

const YAML_FILES = ['project.yaml', 'prompts.yaml', 'tasks.yaml']
const COMPLIANCE_OPTIONS = ['ISO 13485', 'IEC 62304', 'ISO 9001', 'FDA 21 CFR Part 11', 'None']
const INTEGRATION_OPTIONS = ['GitLab', 'Slack', 'GitHub', 'None']

export default function OnboardingWizard({ onClose, onTourStart }: Props) {
  const navigate = useNavigate()
  const [step, setStep] = useState(1)
  const [form, setForm] = useState({ description: '', solution_name: '', parent_solution: '', org_name: '' })
  const [compliance, setCompliance] = useState<string[]>([])
  const [integrations, setIntegrations] = useState<string[]>([])
  const [generateResult, setGenerateResult] = useState<GenerateResponse | null>(null)
  const [generateError, setGenerateError] = useState<string | null>(null)
  const [activeYamlTab, setActiveYamlTab] = useState('project.yaml')

  const { data: projectsData } = useQuery({ queryKey: ['projects'], queryFn: fetchProjects, staleTime: 60_000 })
  const solutions = projectsData?.projects ?? []

  useEffect(() => {
    if (form.description && !form.solution_name) {
      const slug = form.description.toLowerCase()
        .replace(/[^a-z0-9\s]/g, '').trim().replace(/\s+/g, '_').slice(0, 40)
      setForm(f => ({ ...f, solution_name: slug }))
    }
  }, [form.description])

  const generateMutation = useMutation({
    mutationFn: () => callGenerate({
      description: form.description, solution_name: form.solution_name,
      compliance_standards: compliance.filter(c => c !== 'None'),
      integrations: integrations.filter(i => i !== 'None').map(i => i.toLowerCase()),
      parent_solution: form.parent_solution || undefined,
      org_name: form.org_name || undefined,
    }),
    onSuccess: (res) => { setGenerateResult(res); setStep(4) },
    onError: (err: Error) => setGenerateError(err.message),
  })

  const switchMutation = useMutation({ mutationFn: (id: string) => switchProject(id) })

  useEffect(() => {
    if (step === 3 && !generateMutation.isPending && !generateResult && !generateError) {
      generateMutation.mutate()
    }
  }, [step])

  const toggleList = (list: string[], setList: (v: string[]) => void, val: string) => {
    setList(list.includes(val) ? list.filter(x => x !== val) : [...list, val])
  }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 100, background: 'rgba(0,0,0,0.75)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ maxWidth: '560px', width: '100%', background: '#0f172a', borderRadius: '12px',
                    border: '1px solid #1e293b', overflow: 'hidden' }}>
        <ProgressBar step={step} />

        {step === 1 && (
          <div style={{ padding: '0 24px 24px' }}>
            <h2 style={{ fontSize: '16px', fontWeight: 700, color: '#f1f5f9', marginBottom: '16px' }}>
              Describe your solution
            </h2>
            <div style={{ marginBottom: '12px' }}>
              <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>
                What does this solution do?
              </label>
              <textarea
                placeholder="Describe your solution..."
                rows={3}
                value={form.description}
                onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                style={{ width: '100%', background: '#1e293b', border: '1px solid #334155',
                         borderRadius: '6px', padding: '8px', color: '#f1f5f9', fontSize: '13px',
                         resize: 'none', boxSizing: 'border-box' }}
              />
            </div>
            <div style={{ marginBottom: '12px' }}>
              <label htmlFor="solution-name" style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>
                Solution name
              </label>
              <input
                id="solution-name"
                aria-label="Solution name"
                value={form.solution_name}
                onChange={e => setForm(f => ({ ...f, solution_name: e.target.value }))}
                style={{ width: '100%', background: '#1e293b', border: '1px solid #334155',
                         borderRadius: '6px', padding: '8px', color: '#f1f5f9', fontSize: '13px',
                         boxSizing: 'border-box' }}
              />
            </div>
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>
                Parent solution (optional)
              </label>
              <select
                value={form.parent_solution}
                onChange={e => setForm(f => ({ ...f, parent_solution: e.target.value }))}
                style={{ width: '100%', background: '#1e293b', border: '1px solid #334155',
                         borderRadius: '6px', padding: '8px', color: '#f1f5f9', fontSize: '13px' }}
              >
                <option value="">None</option>
                {solutions.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button onClick={onClose}
                style={{ padding: '8px 16px', color: '#64748b', background: 'none', border: 'none', cursor: 'pointer', fontSize: '13px' }}>
                Cancel
              </button>
              <button
                onClick={() => setStep(2)}
                disabled={!form.description.trim() || !form.solution_name.trim()}
                style={{ padding: '8px 20px', background: '#3b82f6', color: '#fff', borderRadius: '6px',
                         fontSize: '13px', cursor: 'pointer', opacity: (!form.description.trim() || !form.solution_name.trim()) ? 0.4 : 1 }}
              >
                Next
              </button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div style={{ padding: '0 24px 24px' }}>
            <h2 style={{ fontSize: '16px', fontWeight: 700, color: '#f1f5f9', marginBottom: '16px' }}>
              Compliance and integrations
            </h2>
            <div style={{ marginBottom: '16px' }}>
              <p style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '8px' }}>Compliance standards</p>
              {COMPLIANCE_OPTIONS.map(opt => (
                <label key={opt} style={{ display: 'flex', alignItems: 'center', gap: '8px',
                                          marginBottom: '6px', fontSize: '13px', color: '#cbd5e1', cursor: 'pointer' }}>
                  <input type="checkbox" checked={compliance.includes(opt)}
                    onChange={() => toggleList(compliance, setCompliance, opt)} />
                  {opt}
                </label>
              ))}
            </div>
            <div style={{ marginBottom: '16px' }}>
              <p style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '8px' }}>Integrations</p>
              {INTEGRATION_OPTIONS.map(opt => (
                <label key={opt} style={{ display: 'flex', alignItems: 'center', gap: '8px',
                                          marginBottom: '6px', fontSize: '13px', color: '#cbd5e1', cursor: 'pointer' }}>
                  <input type="checkbox" checked={integrations.includes(opt)}
                    onChange={() => toggleList(integrations, setIntegrations, opt)} />
                  {opt}
                </label>
              ))}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <button onClick={() => setStep(3)} style={{ fontSize: '13px', color: '#64748b', background: 'none', border: 'none', cursor: 'pointer' }}>
                Skip
              </button>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button onClick={() => setStep(1)} style={{ padding: '8px 16px', color: '#64748b', background: 'none', border: 'none', cursor: 'pointer', fontSize: '13px' }}>
                  Back
                </button>
                <button onClick={() => setStep(3)}
                  style={{ padding: '8px 20px', background: '#3b82f6', color: '#fff', borderRadius: '6px', fontSize: '13px', cursor: 'pointer' }}>
                  Next
                </button>
              </div>
            </div>
          </div>
        )}

        {step === 3 && (
          <div style={{ padding: '32px 24px', textAlign: 'center' }}>
            {generateError ? (
              <>
                <div style={{ color: '#ef4444', marginBottom: '12px', fontSize: '13px' }}>{generateError}</div>
                <button
                  onClick={() => { setGenerateError(null); generateMutation.mutate() }}
                  style={{ padding: '8px 16px', background: '#3b82f6', color: '#fff', borderRadius: '6px', fontSize: '13px', cursor: 'pointer' }}
                >
                  Try again
                </button>
              </>
            ) : (
              <>
                <Loader2 size={24} style={{ color: '#3b82f6', margin: '0 auto 16px', display: 'block',
                                            animation: 'spin 1s linear infinite' }} />
                {['Generating project.yaml', 'Generating prompts.yaml', 'Generating tasks.yaml'].map(msg => (
                  <div key={msg} style={{ fontSize: '13px', color: '#64748b', marginBottom: '6px' }}>{msg}</div>
                ))}
              </>
            )}
          </div>
        )}

        {step === 4 && generateResult && (
          <div style={{ padding: '0 24px 24px' }}>
            <h2 style={{ fontSize: '16px', fontWeight: 700, color: '#f1f5f9', marginBottom: '12px' }}>
              Review generated YAML
            </h2>
            <div style={{ display: 'flex', gap: '4px', marginBottom: '8px' }}>
              {YAML_FILES.map(f => (
                <button key={f} onClick={() => setActiveYamlTab(f)}
                  style={{ padding: '4px 10px', fontSize: '11px', borderRadius: '4px', cursor: 'pointer',
                           background: activeYamlTab === f ? '#1e293b' : 'transparent',
                           color: activeYamlTab === f ? '#f1f5f9' : '#64748b', border: 'none' }}>
                  {f}
                </button>
              ))}
            </div>
            <pre style={{ fontFamily: 'monospace', fontSize: '12px', background: '#020617', borderRadius: '6px',
                          padding: '12px', overflowY: 'auto', maxHeight: '280px', color: '#94a3b8', margin: 0 }}>
              {generateResult.files[activeYamlTab] ?? ''}
            </pre>
            <div style={{ display: 'flex', gap: '8px', marginTop: '12px', alignItems: 'center' }}>
              <button
                onClick={() => { onClose(); navigate(`/yaml-editor?file=${activeYamlTab}`) }}
                style={{ padding: '6px 12px', background: '#1e293b', color: '#94a3b8',
                         borderRadius: '6px', fontSize: '12px', border: '1px solid #334155', cursor: 'pointer' }}
              >
                Open in Config Editor
              </button>
              <button onClick={() => setStep(5)}
                style={{ padding: '8px 20px', background: '#3b82f6', color: '#fff', borderRadius: '6px', fontSize: '13px', cursor: 'pointer' }}>
                Looks good
              </button>
            </div>
          </div>
        )}

        {step === 5 && generateResult && (
          <div style={{ padding: '24px' }}>
            <h2 style={{ fontSize: '16px', fontWeight: 700, color: '#f1f5f9', marginBottom: '12px' }}>
              Solution ready
            </h2>
            <p style={{ color: '#94a3b8', marginBottom: '8px', fontSize: '13px' }}>
              Solution <strong style={{ color: '#f1f5f9' }}>{generateResult.solution_name}</strong> created.
              {generateResult.suggested_routes.length > 0 &&
                ` Suggested routes: ${generateResult.suggested_routes.join(', ')}.`}
            </p>
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginTop: '16px' }}>
              <button
                onClick={async () => {
                  await switchMutation.mutateAsync(generateResult.solution_name)
                  onTourStart(generateResult.solution_name)
                }}
                style={{ padding: '8px 20px', background: '#3b82f6', color: '#fff', borderRadius: '6px', fontSize: '13px', cursor: 'pointer' }}
              >
                Start tour
              </button>
              <button
                onClick={async () => {
                  await switchMutation.mutateAsync(generateResult.solution_name)
                  onClose()
                  navigate('/')
                }}
                style={{ fontSize: '13px', color: '#64748b', background: 'none', border: 'none', cursor: 'pointer' }}
              >
                Go to dashboard
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
