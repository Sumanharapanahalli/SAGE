import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { refineGeneration } from '../../api/client'
import type { ScanFolderResponse, GeneratedFiles, ScanSummary } from '../../api/client'

interface ReviewPanelProps {
  result: ScanFolderResponse
  onAccept: (files: GeneratedFiles) => void
  onStartOver: () => void
}

export default function ReviewPanel({ result, onAccept, onStartOver }: ReviewPanelProps) {
  const [viewTab, setViewTab] = useState<'summary' | 'yaml'>('summary')
  const [yamlSubTab, setYamlSubTab] = useState<keyof GeneratedFiles>('project.yaml')
  const [files, setFiles] = useState<GeneratedFiles>(result.files)
  const [summary, setSummary] = useState<ScanSummary>(result.summary)
  const [feedback, setFeedback] = useState('')

  const refineMutation = useMutation({
    mutationFn: () => refineGeneration({
      solution_name: result.solution_name,
      current_files: files,
      feedback,
    }),
    onSuccess: (data) => {
      setFiles(data.files)
      setSummary(data.summary)
      setFeedback('')
    },
  })

  const tabBtn = (label: string, active: boolean, onClick: () => void) => (
    <button onClick={onClick} style={{
      padding: '6px 16px',
      background: 'transparent',
      color: active ? '#a5b4fc' : '#64748b',
      border: 'none',
      borderBottom: active ? '2px solid #6366f1' : '2px solid transparent',
      cursor: 'pointer',
      fontSize: 12,
    }}>{label}</button>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 700 }}>

      {/* Tab bar */}
      <div style={{ display: 'flex', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
        {tabBtn('Summary', viewTab === 'summary', () => setViewTab('summary'))}
        {tabBtn('YAML', viewTab === 'yaml', () => setViewTab('yaml'))}
      </div>

      {/* Summary tab */}
      {viewTab === 'summary' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, background: 'rgba(255,255,255,0.03)', borderRadius: 8, padding: 16 }}>
            <div style={{ width: 36, height: 36, background: 'rgba(99,102,241,0.2)', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#a5b4fc', fontSize: 16, fontWeight: 700, flexShrink: 0 }}>
              {(summary.name || result.solution_name)[0]?.toUpperCase()}
            </div>
            <div>
              <div style={{ color: 'var(--sage-sidebar-active-text, #f1f5f9)', fontSize: 14, fontWeight: 600, marginBottom: 4 }}>{summary.name || result.solution_name}</div>
              <div style={{ color: 'var(--sage-sidebar-text, #94a3b8)', fontSize: 12, lineHeight: 1.5 }}>{summary.description}</div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 8, padding: 14 }}>
              <div style={{ fontSize: 10, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>What it can do</div>
              {summary.task_types.length > 0 ? summary.task_types.map(t => (
                <div key={t.name} style={{ display: 'flex', gap: 8, fontSize: 12, color: 'var(--sage-sidebar-text, #94a3b8)', marginBottom: 4 }}>
                  <span style={{ color: '#10b981' }}>+</span> {t.name}
                </div>
              )) : <div style={{ fontSize: 12, color: '#475569' }}>No task types defined yet</div>}
            </div>
            <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 8, padding: 14 }}>
              {summary.compliance_standards.length > 0 && (
                <>
                  <div style={{ fontSize: 10, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>Compliance</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
                    {summary.compliance_standards.map(s => (
                      <span key={s} style={{ background: 'rgba(99,102,241,0.15)', color: '#a5b4fc', padding: '3px 10px', borderRadius: 12, fontSize: 11 }}>{s}</span>
                    ))}
                  </div>
                </>
              )}
              {summary.integrations.length > 0 && (
                <>
                  <div style={{ fontSize: 10, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>Integrations</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {summary.integrations.map(i => (
                      <span key={i} style={{ background: 'rgba(16,185,129,0.1)', color: '#6ee7b7', padding: '3px 10px', borderRadius: 12, fontSize: 11 }}>{i}</span>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* YAML tab */}
      {viewTab === 'yaml' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', gap: 6 }}>
            {(['project.yaml', 'prompts.yaml', 'tasks.yaml'] as const).map(k => (
              <button key={k} onClick={() => setYamlSubTab(k)} style={{
                background: yamlSubTab === k ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.04)',
                color: yamlSubTab === k ? '#a5b4fc' : '#64748b',
                border: 'none',
                padding: '4px 12px',
                borderRadius: 12,
                fontSize: 11,
                cursor: 'pointer',
              }}>{k}</button>
            ))}
          </div>
          <textarea
            value={files[yamlSubTab]}
            onChange={e => setFiles(prev => ({ ...prev, [yamlSubTab]: e.target.value }))}
            style={{
              width: '100%',
              height: 200,
              background: 'rgba(255,255,255,0.03)',
              color: '#a5b4fc',
              border: '1px solid rgba(255,255,255,0.08)',
              padding: '10px 12px',
              borderRadius: 6,
              fontSize: 12,
              fontFamily: 'monospace',
              resize: 'vertical',
            }}
          />
        </div>
      )}

      {/* Refine box */}
      <div style={{ background: 'rgba(251,191,36,0.05)', border: '1px solid rgba(251,191,36,0.2)', borderRadius: 6, padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ fontSize: 11, color: '#fbbf24' }}>Not quite right? Tell SAGE what to change:</div>
        <textarea
          value={feedback}
          onChange={e => setFeedback(e.target.value)}
          placeholder="e.g. Focus only on the embedded C code, ignore Python tooling"
          style={{ width: '100%', height: 52, background: 'rgba(255,255,255,0.05)', color: 'var(--sage-sidebar-active-text, #f1f5f9)', border: '1px solid rgba(255,255,255,0.1)', padding: '8px 10px', borderRadius: 6, fontSize: 12, resize: 'vertical', fontFamily: 'inherit' }}
        />
        <button
          onClick={() => refineMutation.mutate()}
          disabled={!feedback.trim() || refineMutation.isPending}
          style={{ background: 'rgba(251,191,36,0.1)', color: '#fbbf24', border: '1px solid rgba(251,191,36,0.25)', padding: '7px 16px', borderRadius: 6, fontSize: 12, cursor: (!feedback.trim() || refineMutation.isPending) ? 'not-allowed' : 'pointer', width: 'fit-content', opacity: (!feedback.trim() || refineMutation.isPending) ? 0.6 : 1 }}
        >
          {refineMutation.isPending ? 'Regenerating...' : 'Regenerate ->'}
        </button>
        {refineMutation.isError && <span style={{ fontSize: 11, color: '#ef4444' }}>Regeneration failed — try again</span>}
      </div>

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: 10 }}>
        <button
          onClick={() => onAccept(files)}
          style={{ background: '#16a34a', color: '#fff', border: 'none', padding: '9px 22px', borderRadius: 6, fontSize: 13, cursor: 'pointer' }}
        >
          Looks good — continue
        </button>
        <button
          onClick={onStartOver}
          style={{ background: 'transparent', color: 'var(--sage-sidebar-text, #94a3b8)', border: '1px solid rgba(255,255,255,0.1)', padding: '9px 22px', borderRadius: 6, fontSize: 13, cursor: 'pointer' }}
        >
          Start over
        </button>
      </div>
    </div>
  )
}
