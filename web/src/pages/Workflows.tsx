import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { GitBranch, RefreshCw, Copy, Check, X, AlertCircle } from 'lucide-react'
import { fetchWorkflowDiagrams, type WorkflowDiagram } from '../api/client'

// ---------------------------------------------------------------------------
// Mermaid — loaded lazily via indirect dynamic import so Vite doesn't
// fail the build when the package is absent (no network to install it).
// ---------------------------------------------------------------------------
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let _mermaid: any = null
let _mermaidInit = false

async function getMermaid(): Promise<any> {
  if (_mermaid) return _mermaid
  try {
    const pkg = 'mermaid'
    // Dynamic import via variable — Vite skips static analysis for this form
    const mod = await import(/* @vite-ignore */ /* webpackIgnore: true */ pkg)
    _mermaid = mod.default ?? mod
    if (!_mermaidInit) {
      _mermaid.initialize({
        startOnLoad: false,
        theme: 'dark',
        themeVariables: {
          background: '#09090b',
          primaryColor: '#27272a',
          primaryTextColor: '#f4f4f5',
          primaryBorderColor: '#3f3f46',
          lineColor: '#71717a',
          secondaryColor: '#18181b',
          tertiaryColor: '#18181b',
        },
        flowchart: { curve: 'linear', useMaxWidth: true },
      })
      _mermaidInit = true
    }
    return _mermaid
  } catch {
    return null
  }
}

// ---------------------------------------------------------------------------
// DiagramModal — full-screen overlay with rendered Mermaid SVG
// ---------------------------------------------------------------------------
interface DiagramModalProps {
  wf: WorkflowDiagram
  onClose: () => void
}

function DiagramModal({ wf, onClose }: DiagramModalProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [svg, setSvg] = useState<string>('')
  const [renderError, setRenderError] = useState<string>('')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    const id = `mermaid-modal-${wf.solution}-${wf.workflow_name}`.replace(/[^a-zA-Z0-9-]/g, '-')
    getMermaid().then(m => {
      if (!m) { setRenderError('Mermaid not installed — run: npm install mermaid'); return }
      m.render(id, wf.mermaid_diagram)
        .then(({ svg: rendered }: { svg: string }) => setSvg(rendered))
        .catch((err: unknown) => setRenderError(String(err)))
    })
  }, [wf])

  function handleCopy() {
    navigator.clipboard.writeText(wf.mermaid_diagram).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  // Close on backdrop click
  function handleBackdrop(e: React.MouseEvent) {
    if (e.target === e.currentTarget) onClose()
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: 'rgba(0,0,0,0.75)' }}
      onClick={handleBackdrop}
    >
      <div
        className="flex flex-col w-full max-w-5xl mx-4"
        style={{
          backgroundColor: '#09090b',
          border: '1px solid #3f3f46',
          maxHeight: '90vh',
        }}
      >
        {/* Modal header */}
        <div
          className="flex items-center justify-between px-4 py-3 shrink-0"
          style={{ borderBottom: '1px solid #27272a', backgroundColor: '#18181b' }}
        >
          <div className="flex items-center gap-3">
            <GitBranch size={16} style={{ color: '#71717a' }} />
            <div>
              <span className="text-sm font-semibold" style={{ color: '#f4f4f5' }}>
                {wf.workflow_name}
              </span>
              <span className="ml-2 text-xs" style={{ color: '#71717a' }}>
                {wf.solution}
              </span>
            </div>
            {wf.node_count > 0 && (
              <span
                className="text-xs px-2 py-0.5"
                style={{ backgroundColor: '#27272a', color: '#a1a1aa' }}
              >
                {wf.node_count} nodes
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 transition-colors"
              style={{
                border: '1px solid #3f3f46',
                color: copied ? '#22c55e' : '#a1a1aa',
              }}
              title="Copy Mermaid source"
            >
              {copied ? <Check size={12} /> : <Copy size={12} />}
              {copied ? 'Copied' : 'Copy Mermaid'}
            </button>
            <button
              onClick={onClose}
              className="flex items-center justify-center"
              style={{ color: '#52525b', width: 28, height: 28 }}
              title="Close"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Diagram area */}
        <div className="flex-1 overflow-auto p-6" ref={containerRef}>
          {renderError ? (
            <div
              className="p-4 text-sm"
              style={{ backgroundColor: '#18181b', border: '1px solid #3f3f46', color: '#f87171' }}
            >
              <p className="font-medium mb-2">Render error</p>
              <pre className="text-xs overflow-auto" style={{ color: '#a1a1aa' }}>{renderError}</pre>
              <hr style={{ borderColor: '#27272a', margin: '12px 0' }} />
              <p className="font-medium mb-1" style={{ color: '#a1a1aa' }}>Raw Mermaid source</p>
              <pre className="text-xs overflow-auto" style={{ color: '#71717a' }}>{wf.mermaid_diagram}</pre>
            </div>
          ) : svg ? (
            <div
              className="flex justify-center"
              dangerouslySetInnerHTML={{ __html: svg }}
              style={{ minHeight: 200 }}
            />
          ) : (
            <div className="flex items-center justify-center py-16">
              <div className="text-xs animate-pulse" style={{ color: '#52525b' }}>Rendering…</div>
            </div>
          )}
        </div>

        {/* Description footer */}
        {wf.description && (
          <div
            className="px-4 py-2 text-xs shrink-0"
            style={{ borderTop: '1px solid #27272a', color: '#52525b' }}
          >
            {wf.description}
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// WorkflowCard — summary tile in the grid
// ---------------------------------------------------------------------------
interface WorkflowCardProps {
  wf: WorkflowDiagram
  onClick: () => void
}

function WorkflowCard({ wf, onClick }: WorkflowCardProps) {
  const previewId = useRef(`mermaid-preview-${wf.solution}-${wf.workflow_name}`.replace(/[^a-zA-Z0-9-]/g, '-'))
  const [previewSvg, setPreviewSvg] = useState<string>('')

  useEffect(() => {
    getMermaid().then(m => {
      if (!m) return
      m.render(previewId.current, wf.mermaid_diagram)
        .then(({ svg }: { svg: string }) => setPreviewSvg(svg))
        .catch(() => setPreviewSvg(''))
    })
  }, [wf.mermaid_diagram])

  return (
    <button
      onClick={onClick}
      className="flex flex-col text-left w-full transition-colors"
      style={{
        backgroundColor: '#18181b',
        border: '1px solid #27272a',
      }}
      onMouseEnter={e => {
        ;(e.currentTarget as HTMLElement).style.borderColor = '#3f3f46'
        ;(e.currentTarget as HTMLElement).style.backgroundColor = '#1c1c1f'
      }}
      onMouseLeave={e => {
        ;(e.currentTarget as HTMLElement).style.borderColor = '#27272a'
        ;(e.currentTarget as HTMLElement).style.backgroundColor = '#18181b'
      }}
    >
      {/* Card header */}
      <div
        className="flex items-center justify-between px-3 py-2 shrink-0"
        style={{ borderBottom: '1px solid #27272a' }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <GitBranch size={13} style={{ color: '#52525b', flexShrink: 0 }} />
          <span className="text-xs font-semibold truncate" style={{ color: '#f4f4f5' }}>
            {wf.workflow_name}
          </span>
        </div>
        {wf.node_count > 0 && (
          <span
            className="text-xs px-1.5 py-0.5 shrink-0 ml-2"
            style={{ backgroundColor: '#27272a', color: '#71717a', fontSize: '10px' }}
          >
            {wf.node_count}
          </span>
        )}
      </div>

      {/* Solution badge */}
      <div className="px-3 pt-1.5 pb-1">
        <span
          className="text-xs"
          style={{ color: '#71717a' }}
        >
          {wf.solution}
        </span>
      </div>

      {/* Preview thumbnail */}
      <div
        className="flex items-center justify-center overflow-hidden mx-3 mb-3"
        style={{
          height: 120,
          backgroundColor: '#09090b',
          border: '1px solid #27272a',
        }}
      >
        {previewSvg ? (
          <div
            className="w-full h-full flex items-center justify-center overflow-hidden"
            style={{ transform: 'scale(0.55)', transformOrigin: 'center' }}
            dangerouslySetInnerHTML={{ __html: previewSvg }}
          />
        ) : (
          <div className="text-xs animate-pulse" style={{ color: '#3f3f46' }}>
            Loading…
          </div>
        )}
      </div>

      {/* Description */}
      {wf.description && (
        <p
          className="px-3 pb-3 text-xs line-clamp-2"
          style={{ color: '#52525b' }}
        >
          {wf.description}
        </p>
      )}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Workflows page
// ---------------------------------------------------------------------------
export default function Workflows() {
  const [selected, setSelected] = useState<WorkflowDiagram | null>(null)

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['workflow-diagrams'],
    queryFn: fetchWorkflowDiagrams,
    staleTime: 60_000,
  })

  const workflows = data?.workflows ?? []

  return (
    <div className="space-y-4">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold" style={{ color: '#f4f4f5' }}>
            Workflow Diagrams
          </h2>
          <p className="text-xs mt-0.5" style={{ color: '#52525b' }}>
            Auto-generated from LangGraph StateGraph definitions across all solutions
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 transition-colors"
          style={{
            border: '1px solid #3f3f46',
            color: isFetching ? '#3f3f46' : '#a1a1aa',
            cursor: isFetching ? 'not-allowed' : 'pointer',
          }}
        >
          <RefreshCw size={12} className={isFetching ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* States */}
      {isLoading && (
        <div className="flex items-center gap-2 py-8 text-xs" style={{ color: '#52525b' }}>
          <RefreshCw size={12} className="animate-spin" />
          Discovering workflows…
        </div>
      )}

      {isError && (
        <div
          className="flex items-start gap-2 p-4 text-sm"
          style={{ backgroundColor: '#18181b', border: '1px solid #3f3f46' }}
        >
          <AlertCircle size={14} style={{ color: '#f87171', flexShrink: 0, marginTop: 1 }} />
          <div>
            <p className="font-medium" style={{ color: '#f87171' }}>Failed to load workflows</p>
            <p className="text-xs mt-1" style={{ color: '#71717a' }}>
              {error instanceof Error ? error.message : 'Unknown error'}
            </p>
          </div>
        </div>
      )}

      {!isLoading && !isError && workflows.length === 0 && (
        <div
          className="flex flex-col items-center justify-center py-16 text-center"
          style={{ border: '1px dashed #27272a' }}
        >
          <GitBranch size={32} style={{ color: '#27272a', marginBottom: 12 }} />
          <p className="text-sm font-medium" style={{ color: '#52525b' }}>No workflows found</p>
          <p className="text-xs mt-1 max-w-xs" style={{ color: '#3f3f46' }}>
            Add a LangGraph StateGraph to{' '}
            <code style={{ color: '#52525b' }}>solutions/&lt;name&gt;/workflows/*.py</code>{' '}
            and expose a compiled <code style={{ color: '#52525b' }}>workflow</code> variable.
          </p>
        </div>
      )}

      {!isLoading && workflows.length > 0 && (
        <>
          {/* Count */}
          <p className="text-xs" style={{ color: '#3f3f46' }}>
            {workflows.length} workflow{workflows.length !== 1 ? 's' : ''} discovered
          </p>

          {/* Grid */}
          <div
            className="grid gap-3"
            style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))' }}
          >
            {workflows.map(wf => (
              <WorkflowCard
                key={`${wf.solution}/${wf.workflow_name}`}
                wf={wf}
                onClick={() => setSelected(wf)}
              />
            ))}
          </div>
        </>
      )}

      {/* Modal */}
      {selected && (
        <DiagramModal wf={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
