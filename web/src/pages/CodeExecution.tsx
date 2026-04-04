import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  Code2, Play, CheckCircle2, XCircle, Clock,
  FileCode, GitBranch, Eye, Loader2,
} from 'lucide-react'
import { executeCode, planCode, fetchCodeStatus, approveCodeExecution, fetchRepoMap, fetchSandboxStatus } from '../api/client'

type Tab = 'execute' | 'plan' | 'repomap' | 'history'

export default function CodeExecution() {
  const [tab, setTab] = useState<Tab>('execute')
  const [task, setTask] = useState('')
  const [workspace, setWorkspace] = useState('')
  const [language, setLanguage] = useState('python')
  const [planTask, setPlanTask] = useState('')
  const [planContext, setPlanContext] = useState('')
  const [trackingId, setTrackingId] = useState('')

  const executeMutation = useMutation({
    mutationFn: () => executeCode({ task, workspace: workspace || undefined, language }),
    onSuccess: (data) => {
      if (data?.run_id) setTrackingId(data.run_id)
    },
  })

  const planMutation = useMutation({
    mutationFn: () => planCode({ task: planTask, context: planContext || undefined }),
  })

  const { data: statusData } = useQuery({
    queryKey: ['code-status', trackingId],
    queryFn: () => fetchCodeStatus(trackingId),
    enabled: !!trackingId,
    refetchInterval: trackingId ? 5000 : false,
    retry: false,
  })

  const approveMutation = useMutation({
    mutationFn: (run_id: string) => approveCodeExecution(run_id),
  })

  const { data: repoMap } = useQuery({
    queryKey: ['repo-map'],
    queryFn: () => fetchRepoMap(50),
    retry: false,
    enabled: tab === 'repomap',
  })

  const { data: sandboxStatus } = useQuery({
    queryKey: ['sandbox-status'],
    queryFn: fetchSandboxStatus,
    retry: false,
  })

  const tabs: { id: Tab; label: string; icon: typeof Code2 }[] = [
    { id: 'execute', label: 'Execute', icon: Play },
    { id: 'plan', label: 'Plan', icon: GitBranch },
    { id: 'repomap', label: 'Repo Map', icon: FileCode },
    { id: 'history', label: 'Status', icon: Clock },
  ]

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-lg font-semibold" style={{ color: '#e4e4e7' }}>
          <Code2 size={18} className="inline mr-2" style={{ color: '#3b82f6' }} />
          Code Execution
        </h1>
        <p className="text-xs mt-1" style={{ color: '#71717a' }}>
          Submit autonomous code tasks, plan changes, track execution status
        </p>
      </div>

      <div className="sage-tabs">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} className={`sage-tab ${tab === t.id ? 'sage-tab-active' : ''}`}>
            <t.icon size={12} className="inline mr-1.5" />{t.label}
          </button>
        ))}
      </div>

      {/* Execute */}
      {tab === 'execute' && (
        <div className="space-y-4">
          <div className="sage-card" style={{ background: '#1c1c1e', borderColor: '#2a2a2e' }}>
            <h2 className="text-sm font-semibold mb-3" style={{ color: '#e4e4e7' }}>
              <Play size={14} className="inline mr-1.5" style={{ color: '#10b981' }} />
              Submit Code Task
            </h2>
            <div className="space-y-3">
              <div>
                <label className="block text-xs mb-1" style={{ color: '#71717a' }}>Task Description</label>
                <textarea
                  value={task}
                  onChange={e => setTask(e.target.value)}
                  rows={4}
                  placeholder="Describe the code task... e.g., 'Add input validation to the user registration endpoint'"
                  className="w-full text-sm px-3 py-2"
                  style={{ background: '#111113', color: '#e4e4e7', border: '1px solid #2a2a2e', borderRadius: 8, outline: 'none', resize: 'vertical' }}
                />
              </div>
              <div className="flex gap-3">
                <div className="flex-1">
                  <label className="block text-xs mb-1" style={{ color: '#71717a' }}>Workspace (optional)</label>
                  <input
                    value={workspace}
                    onChange={e => setWorkspace(e.target.value)}
                    placeholder="/path/to/project"
                    className="w-full text-sm px-3 py-2"
                    style={{ background: '#111113', color: '#e4e4e7', border: '1px solid #2a2a2e', borderRadius: 8, outline: 'none' }}
                  />
                </div>
                <div style={{ width: 140 }}>
                  <label className="block text-xs mb-1" style={{ color: '#71717a' }}>Language</label>
                  <select
                    value={language}
                    onChange={e => setLanguage(e.target.value)}
                    className="w-full text-sm px-3 py-2"
                    style={{ background: '#111113', color: '#e4e4e7', border: '1px solid #2a2a2e', borderRadius: 8 }}
                  >
                    <option value="python">Python</option>
                    <option value="typescript">TypeScript</option>
                    <option value="javascript">JavaScript</option>
                    <option value="c">C</option>
                    <option value="cpp">C++</option>
                    <option value="rust">Rust</option>
                    <option value="go">Go</option>
                  </select>
                </div>
              </div>
              <button
                onClick={() => executeMutation.mutate()}
                disabled={!task.trim() || executeMutation.isPending}
                className="sage-btn sage-btn-primary"
              >
                <Play size={12} /> {executeMutation.isPending ? 'Submitting...' : 'Execute'}
              </button>
            </div>
          </div>

          {/* Execution result */}
          {executeMutation.isSuccess && executeMutation.data && (
            <div className="sage-card" style={{ background: '#1c1c1e', borderColor: '#2a2a2e' }}>
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle2 size={14} style={{ color: '#22c55e' }} />
                <span className="text-sm font-medium" style={{ color: '#e4e4e7' }}>Task Submitted</span>
                {executeMutation.data.run_id && (
                  <span className="sage-tag" style={{ fontSize: '10px' }}>ID: {executeMutation.data.run_id}</span>
                )}
              </div>
              <pre className="text-xs p-3 overflow-auto" style={{ background: '#111113', color: '#a1a1aa', borderRadius: 6, maxHeight: 300 }}>
                {JSON.stringify(executeMutation.data, null, 2)}
              </pre>
            </div>
          )}
          {executeMutation.isError && (
            <div className="text-xs p-3" style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444', borderRadius: 8 }}>
              {(executeMutation.error as Error).message}
            </div>
          )}
        </div>
      )}

      {/* Plan */}
      {tab === 'plan' && (
        <div className="sage-card" style={{ background: '#1c1c1e', borderColor: '#2a2a2e' }}>
          <h2 className="text-sm font-semibold mb-3" style={{ color: '#e4e4e7' }}>
            <GitBranch size={14} className="inline mr-1.5" style={{ color: '#a78bfa' }} />
            Plan Code Changes
          </h2>
          <div className="space-y-3">
            <div>
              <label className="block text-xs mb-1" style={{ color: '#71717a' }}>Task</label>
              <textarea
                value={planTask}
                onChange={e => setPlanTask(e.target.value)}
                rows={3}
                placeholder="Describe what you want to accomplish..."
                className="w-full text-sm px-3 py-2"
                style={{ background: '#111113', color: '#e4e4e7', border: '1px solid #2a2a2e', borderRadius: 8, outline: 'none', resize: 'vertical' }}
              />
            </div>
            <div>
              <label className="block text-xs mb-1" style={{ color: '#71717a' }}>Context (optional)</label>
              <textarea
                value={planContext}
                onChange={e => setPlanContext(e.target.value)}
                rows={2}
                placeholder="Additional context, constraints, or relevant code..."
                className="w-full text-sm px-3 py-2"
                style={{ background: '#111113', color: '#e4e4e7', border: '1px solid #2a2a2e', borderRadius: 8, outline: 'none', resize: 'vertical' }}
              />
            </div>
            <button
              onClick={() => planMutation.mutate()}
              disabled={!planTask.trim() || planMutation.isPending}
              className="sage-btn sage-btn-primary"
            >
              <GitBranch size={12} /> {planMutation.isPending ? 'Planning...' : 'Generate Plan'}
            </button>
          </div>

          {planMutation.isSuccess && planMutation.data && (
            <div className="mt-4">
              <h3 className="text-xs font-semibold mb-2" style={{ color: '#71717a' }}>Generated Plan</h3>
              <pre className="text-xs p-3 overflow-auto" style={{ background: '#111113', color: '#a1a1aa', borderRadius: 6, maxHeight: 400 }}>
                {typeof planMutation.data === 'string' ? planMutation.data : JSON.stringify(planMutation.data, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* Repo Map */}
      {tab === 'repomap' && (
        <div className="sage-card" style={{ background: '#1c1c1e', borderColor: '#2a2a2e' }}>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold" style={{ color: '#e4e4e7' }}>
              <FileCode size={14} className="inline mr-1.5" style={{ color: '#a78bfa' }} />
              Repository Map
            </h2>
            {sandboxStatus && (
              <span className="sage-tag" style={{
                fontSize: 10,
                background: sandboxStatus.available ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
                color: sandboxStatus.available ? '#4ade80' : '#f87171',
              }}>
                Sandbox: {sandboxStatus.available ? 'Available' : 'Unavailable'}
              </span>
            )}
          </div>
          {repoMap?.map ? (
            <pre className="text-xs overflow-auto p-3" style={{ background: '#111113', color: '#a1a1aa', borderRadius: 6, maxHeight: 500, whiteSpace: 'pre-wrap' }}>
              {repoMap.map}
            </pre>
          ) : (
            <div className="sage-empty">
              <FileCode size={32} />
              <p className="text-sm">No repo map available. Ensure a solution is loaded.</p>
            </div>
          )}
        </div>
      )}

      {/* Status tracking */}
      {tab === 'history' && (
        <div className="space-y-4">
          <div className="sage-card" style={{ background: '#1c1c1e', borderColor: '#2a2a2e' }}>
            <h2 className="text-sm font-semibold mb-3" style={{ color: '#e4e4e7' }}>
              <Eye size={14} className="inline mr-1.5" style={{ color: '#3b82f6' }} />
              Track Execution
            </h2>
            <div className="flex gap-2">
              <input
                value={trackingId}
                onChange={e => setTrackingId(e.target.value)}
                placeholder="Enter run ID..."
                className="flex-1 text-sm px-3 py-2"
                style={{ background: '#111113', color: '#e4e4e7', border: '1px solid #2a2a2e', borderRadius: 8, outline: 'none' }}
              />
            </div>
          </div>

          {statusData && (
            <div className="sage-card" style={{ background: '#1c1c1e', borderColor: '#2a2a2e' }}>
              <div className="flex items-center gap-2 mb-3">
                {statusData.status === 'completed' ? (
                  <CheckCircle2 size={14} style={{ color: '#22c55e' }} />
                ) : statusData.status === 'error' || statusData.status === 'failed' ? (
                  <XCircle size={14} style={{ color: '#ef4444' }} />
                ) : (
                  <Loader2 size={14} style={{ color: '#f59e0b' }} className="animate-spin" />
                )}
                <span className="text-sm font-medium" style={{ color: '#e4e4e7' }}>
                  Status: {statusData.status}
                </span>
              </div>

              {statusData.status === 'pending_approval' && (
                <button
                  onClick={() => approveMutation.mutate(trackingId)}
                  disabled={approveMutation.isPending}
                  className="sage-btn sage-btn-primary mb-3"
                >
                  <CheckCircle2 size={12} /> {approveMutation.isPending ? 'Approving...' : 'Approve Execution'}
                </button>
              )}

              <pre className="text-xs p-3 overflow-auto" style={{ background: '#111113', color: '#a1a1aa', borderRadius: 6, maxHeight: 300 }}>
                {JSON.stringify(statusData, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
