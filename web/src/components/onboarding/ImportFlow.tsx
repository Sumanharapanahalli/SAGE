import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { scanFolder, saveSolution, switchProject } from '../../api/client'
import type { GeneratedFiles, ScanFolderResponse } from '../../api/client'
import ReviewPanel from './ReviewPanel'
import { useNavigate } from 'react-router-dom'

interface ImportFlowProps {
  llmConnected: boolean
}

type Step = 'input' | 'scanning' | 'review'

export default function ImportFlow({ llmConnected }: ImportFlowProps) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [step, setStep] = useState<Step>('input')
  const [folderPath, setFolderPath] = useState('')
  const [intent, setIntent] = useState('')
  const [solutionName, setSolutionName] = useState('')
  const [scanResult, setScanResult] = useState<ScanFolderResponse | null>(null)
  const [scanError, setScanError] = useState<string | null>(null)

  const scanMutation = useMutation({
    mutationFn: () => scanFolder({ folder_path: folderPath, intent, solution_name: solutionName }),
    onMutate: () => { setStep('scanning'); setScanError(null) },
    onSuccess: (data) => { setScanResult(data); setStep('review') },
    onError: (err: unknown) => {
      const detail = (err as any)?.detail ?? {}
      const code = detail?.error ?? 'unknown'
      const messages: Record<string, string> = {
        folder_not_found: 'Folder not found. Check the path and try again.',
        folder_empty: 'No readable files found in this folder.',
        llm_unavailable: 'Could not reach the LLM. Check Settings -> LLM.',
        generation_failed: 'Generation failed. Try again or use Describe it instead.',
      }
      setScanError(messages[code] ?? 'An error occurred. Please try again.')
      setStep('input')
    },
  })

  const handleAccept = async (files: GeneratedFiles) => {
    try {
      await saveSolution({ solution_name: solutionName, files })
      await switchProject(solutionName)
      qc.invalidateQueries({ queryKey: ['projects'] })
    } catch {
      // files saved even if switch fails
    }
    navigate('/')
  }

  const fieldStyle: React.CSSProperties = {
    background: 'rgba(255,255,255,0.05)',
    color: 'var(--sage-sidebar-active-text, #f1f5f9)',
    border: '1px solid rgba(255,255,255,0.12)',
    padding: '8px 12px',
    borderRadius: 6,
    fontSize: 13,
    fontFamily: 'inherit',
  }

  if (step === 'review' && scanResult) {
    return (
      <ReviewPanel
        result={scanResult}
        onAccept={handleAccept}
        onStartOver={() => { setStep('input'); setScanResult(null) }}
      />
    )
  }

  return (
    <div style={{ maxWidth: 600, display: 'flex', flexDirection: 'column', gap: 18 }}>

      {step === 'scanning' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: '20px 0' }}>
          {['Reading README files', 'Reading docs / specs', 'Reading source files', 'Generating solution YAML...'].map((label, i) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13, color: i < 3 ? 'var(--sage-sidebar-text, #94a3b8)' : 'var(--sage-sidebar-active-text, #f1f5f9)' }}>
              <span style={{ width: 16, textAlign: 'center', color: i < 3 ? '#10b981' : '#6366f1' }}>
                {i < 3 ? '+' : '...'}
              </span>
              {label}
            </div>
          ))}
        </div>
      )}

      {step === 'input' && (
        <>
          {scanError && (
            <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 6, padding: '10px 14px', fontSize: 12, color: '#fca5a5' }}>
              {scanError}
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 11, color: 'var(--sage-sidebar-text, #94a3b8)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Folder path</label>
            <input
              style={{ ...fieldStyle, width: '100%' }}
              value={folderPath}
              onChange={e => setFolderPath(e.target.value)}
              placeholder="C:\projects\my-codebase  or  /home/user/projects/app"
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 11, color: 'var(--sage-sidebar-text, #94a3b8)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>What do you want to build from this?</label>
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)' }}>Be specific — this guides the LLM.</div>
            <textarea
              style={{ ...fieldStyle, height: 72, resize: 'vertical' }}
              value={intent}
              onChange={e => setIntent(e.target.value)}
              placeholder={'e.g. A QA agent that reviews firmware PRs against IEC 62304\ne.g. A documentation agent that generates API docs from source comments'}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 11, color: 'var(--sage-sidebar-text, #94a3b8)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Solution name</label>
            <input
              style={{ ...fieldStyle, width: 260 }}
              value={solutionName}
              onChange={e => setSolutionName(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_'))}
              placeholder="e.g. firmware_qa"
            />
          </div>

          <button
            onClick={() => scanMutation.mutate()}
            disabled={!llmConnected || !folderPath.trim() || !intent.trim() || !solutionName.trim()}
            title={!llmConnected ? 'LLM not connected' : undefined}
            style={{
              background: 'rgba(99,102,241,0.15)',
              color: '#a5b4fc',
              border: '1px solid rgba(99,102,241,0.3)',
              padding: '9px 20px',
              borderRadius: 6,
              fontSize: 13,
              cursor: (!llmConnected || !folderPath.trim() || !intent.trim() || !solutionName.trim()) ? 'not-allowed' : 'pointer',
              width: 'fit-content',
              opacity: (!llmConnected || !folderPath.trim() || !intent.trim() || !solutionName.trim()) ? 0.5 : 1,
            }}
          >
            Scan & generate {'->'}
          </button>
        </>
      )}
    </div>
  )
}
