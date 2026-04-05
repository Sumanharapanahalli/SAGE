import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchComposioStatus, fetchComposioTools, connectComposioApp } from '../api/client'
import { Loader2, Plug, CheckCircle2, AlertTriangle, ExternalLink, Plus, Wrench } from 'lucide-react'

// ---------------------------------------------------------------------------
// Popular Composio apps with display metadata
// ---------------------------------------------------------------------------
const POPULAR_APPS: { id: string; label: string; icon: string; category: string }[] = [
  { id: 'github',      label: 'GitHub',        icon: '🐙', category: 'Engineering' },
  { id: 'gitlab',      label: 'GitLab',        icon: '🦊', category: 'Engineering' },
  { id: 'jira',        label: 'Jira',          icon: '📋', category: 'Engineering' },
  { id: 'linear',      label: 'Linear',        icon: '📐', category: 'Engineering' },
  { id: 'slack',       label: 'Slack',         icon: '💬', category: 'Communication' },
  { id: 'notion',      label: 'Notion',        icon: '📝', category: 'Knowledge' },
  { id: 'confluence',  label: 'Confluence',    icon: '📚', category: 'Knowledge' },
  { id: 'googledocs',  label: 'Google Docs',   icon: '📄', category: 'Knowledge' },
  { id: 'gdrive',      label: 'Google Drive',  icon: '📁', category: 'Knowledge' },
  { id: 'gmail',       label: 'Gmail',         icon: '✉️', category: 'Communication' },
  { id: 'gcal',        label: 'Google Cal',    icon: '📅', category: 'Communication' },
  { id: 'salesforce',  label: 'Salesforce',    icon: '☁️', category: 'Business' },
  { id: 'hubspot',     label: 'HubSpot',       icon: '🔶', category: 'Business' },
  { id: 'asana',       label: 'Asana',         icon: '🎯', category: 'Business' },
  { id: 'zendesk',     label: 'Zendesk',       icon: '🎧', category: 'Business' },
  { id: 'stripe',      label: 'Stripe',        icon: '💳', category: 'Finance' },
  { id: 'postgres',    label: 'PostgreSQL',    icon: '🐘', category: 'Data' },
  { id: 'mysql',       label: 'MySQL',         icon: '🗄️', category: 'Data' },
  { id: 'discord',     label: 'Discord',       icon: '🎮', category: 'Communication' },
  { id: 'figma',       label: 'Figma',         icon: '🎨', category: 'Design' },
]

const CATEGORIES = Array.from(new Set(POPULAR_APPS.map(a => a.category)))

// ---------------------------------------------------------------------------
// Connect App Modal
// ---------------------------------------------------------------------------
function ConnectModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const [selectedApp, setSelectedApp] = useState('')
  const [customApp, setCustomApp] = useState('')
  const [activeCategory, setActiveCategory] = useState('All')
  const [result, setResult] = useState<{ url: string; app: string; trace_id: string } | null>(null)

  const { mutate, isPending, error } = useMutation({
    mutationFn: () => connectComposioApp(customApp.trim() || selectedApp),
    onSuccess: (res) => {
      setResult({ url: res.connection_url, app: res.app, trace_id: res.trace_id })
      qc.invalidateQueries({ queryKey: ['composio-status'] })
    },
  })

  const filteredApps = POPULAR_APPS.filter(a =>
    activeCategory === 'All' || a.category === activeCategory
  )
  const appToConnect = customApp.trim() || selectedApp

  if (result) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-white/50 p-4">
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8 text-center space-y-4">
          <div className="text-4xl">🔗</div>
          <h3 className="text-lg font-semibold text-gray-800">Connection URL Ready</h3>
          <p className="text-sm text-gray-600">
            Visit the link below to authorise <strong>{result.app}</strong>, then return here
            and approve the proposal on the Dashboard.
          </p>
          <a
            href={result.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-2 w-full bg-blue-600 hover:bg-blue-700
                       text-white rounded-lg py-2.5 text-sm font-medium transition-colors"
          >
            <ExternalLink size={14} /> Authorise {result.app} →
          </a>
          <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-xs text-amber-700 text-left">
            <p className="font-semibold mb-1">After authorising:</p>
            <p>Go to Dashboard → Pending Approvals and approve the <strong>Composio Connect</strong> proposal.</p>
            <p className="mt-1 font-mono text-amber-500">trace: {result.trace_id.slice(0, 16)}…</p>
          </div>
          <button onClick={onClose} className="w-full border border-gray-200 text-gray-600 rounded-lg py-2 text-sm hover:bg-gray-50">
            Close
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-white/50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <Plug size={18} className="text-blue-600" />
            <h2 className="text-base font-semibold text-gray-800">Connect an App</h2>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none">×</button>
        </div>

        <div className="px-6 py-5 space-y-4">
          {/* Category filter */}
          <div className="flex flex-wrap gap-1.5">
            {['All', ...CATEGORIES].map(cat => (
              <button
                key={cat}
                onClick={() => setActiveCategory(cat)}
                className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                  activeCategory === cat
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'border-gray-200 text-gray-600 hover:border-blue-300'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          {/* App grid */}
          <div className="grid grid-cols-4 gap-2">
            {filteredApps.map(app => (
              <button
                key={app.id}
                onClick={() => { setSelectedApp(app.id); setCustomApp('') }}
                className={`flex flex-col items-center gap-1 p-2.5 rounded-xl border transition-all ${
                  selectedApp === app.id && !customApp
                    ? 'border-blue-400 bg-blue-50'
                    : 'border-gray-200 hover:border-blue-300 hover:bg-blue-50/50'
                }`}
              >
                <span className="text-xl">{app.icon}</span>
                <span className="text-[10px] text-gray-600 text-center leading-tight">{app.label}</span>
              </button>
            ))}
          </div>

          {/* Custom app */}
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1.5">
              Or enter any Composio app name
            </label>
            <input
              value={customApp}
              onChange={e => { setCustomApp(e.target.value); setSelectedApp('') }}
              placeholder="e.g. trello, shopify, intercom, twilio…"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </div>

          {error && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {(error as Error).message}
            </p>
          )}
        </div>

        <div className="flex gap-3 px-6 pb-6">
          <button onClick={onClose} className="flex-1 border border-gray-200 text-gray-600 rounded-lg py-2.5 text-sm hover:bg-gray-50">
            Cancel
          </button>
          <button
            onClick={() => mutate()}
            disabled={isPending || !appToConnect}
            className="flex-1 flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700
                       disabled:opacity-40 text-white rounded-lg py-2.5 text-sm font-medium transition-colors"
          >
            {isPending
              ? <><Loader2 size={14} className="animate-spin" /> Connecting…</>
              : <><Plug size={14} /> Connect {appToConnect || '…'}</>
            }
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function Integrations() {
  const [showConnect, setShowConnect] = useState(false)

  const { data: statusData, isLoading: statusLoading } = useQuery({
    queryKey: ['composio-status'],
    queryFn: fetchComposioStatus,
    retry: false,
  })

  const { data: toolsData, isLoading: toolsLoading } = useQuery({
    queryKey: ['composio-tools'],
    queryFn: fetchComposioTools,
    retry: false,
  })

  const connectedApps = statusData?.connected_apps ?? []

  return (
    <div className="space-y-6 max-w-4xl">
      {showConnect && <ConnectModal onClose={() => setShowConnect(false)} />}

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">Integrations</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Connect external tools via Composio — 100+ apps, OAuth handled automatically.
            Connected tools become available to all agents in this solution.
          </p>
        </div>
        <button
          onClick={() => setShowConnect(true)}
          disabled={!statusData?.api_key_set}
          className="flex items-center gap-1.5 shrink-0 bg-blue-600 hover:bg-blue-700
                     disabled:opacity-40 disabled:cursor-not-allowed
                     text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          <Plus size={15} /> Connect App
        </button>
      </div>

      {/* Setup card — shown when Composio is not configured */}
      {!statusLoading && !statusData?.api_key_set && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-5">
          <div className="flex items-start gap-3">
            <AlertTriangle size={18} className="text-amber-500 mt-0.5 shrink-0" />
            <div>
              <h3 className="text-sm font-semibold text-amber-800 mb-1">Composio API key required</h3>
              <p className="text-sm text-amber-700 mb-3">
                Add <code className="bg-amber-100 px-1 rounded">COMPOSIO_API_KEY</code> to your <code className="bg-amber-100 px-1 rounded">.env</code> file
                to enable the Composio integration layer. Get a free key at{' '}
                <a href="https://app.composio.dev" target="_blank" rel="noopener noreferrer"
                   className="underline font-medium">app.composio.dev</a>.
              </p>
              <div className="bg-amber-100 rounded-lg p-3 font-mono text-xs text-amber-900 space-y-1">
                <p># .env</p>
                <p>COMPOSIO_API_KEY=your_key_here</p>
                <p className="mt-2 text-amber-600"># Then install the package:</p>
                <p>pip install composio-langchain</p>
                <p className="mt-2 text-amber-600"># Connect your first app (one-time OAuth):</p>
                <p>composio add github</p>
              </div>
              <p className="text-xs text-amber-600 mt-3">
                After adding the key, restart the backend with <code className="bg-amber-100 px-1 rounded">make run PROJECT=your_solution</code>.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Connected apps */}
      {statusData?.api_key_set && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
            <Plug size={14} className="text-blue-500" />
            Connected Apps
            <span className="text-xs font-normal text-gray-400">({connectedApps.length})</span>
          </h3>

          {statusLoading && (
            <div className="flex items-center gap-1.5 text-sm text-gray-400">
              <Loader2 size={14} className="animate-spin" /> Loading…
            </div>
          )}

          {!statusLoading && connectedApps.length === 0 && (
            <div className="text-sm text-gray-500 py-2">
              No apps connected yet. Click <strong>Connect App</strong> to add your first integration.
            </div>
          )}

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {connectedApps.map(app => {
              const meta = POPULAR_APPS.find(a => a.id === app.app.toLowerCase())
              return (
                <div
                  key={app.connected_account_id}
                  className="flex items-center gap-2 p-3 rounded-lg border border-orange-200 bg-orange-50"
                >
                  <span className="text-lg">{meta?.icon ?? '🔌'}</span>
                  <div className="min-w-0">
                    <div className="text-xs font-medium text-gray-700 truncate">
                      {meta?.label ?? app.app}
                    </div>
                    <div className="flex items-center gap-1 mt-0.5">
                      <CheckCircle2 size={10} className="text-orange-500" />
                      <span className="text-[10px] text-orange-600">{app.status}</span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Active tools for current solution */}
      {statusData?.api_key_set && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-1 flex items-center gap-2">
            <Wrench size={14} className="text-indigo-500" />
            Tools Active in This Solution
          </h3>
          <p className="text-xs text-gray-400 mb-3">
            Declared via <code className="bg-gray-100 px-1 rounded">composio:*</code> entries in this solution's{' '}
            <code className="bg-gray-100 px-1 rounded">project.yaml integrations:</code>
          </p>

          {toolsLoading && (
            <div className="flex items-center gap-1.5 text-sm text-gray-400">
              <Loader2 size={14} className="animate-spin" /> Loading tools…
            </div>
          )}

          {!toolsLoading && toolsData?.message && !toolsData.tools?.length && (
            <div className="text-sm text-gray-500 bg-gray-50 rounded-lg p-3">
              {toolsData.message}
              <p className="mt-1 text-xs text-gray-400">
                Add <code className="bg-gray-100 px-1 rounded">composio:github</code> (or any app) to your{' '}
                <code className="bg-gray-100 px-1 rounded">project.yaml</code> integrations list.
              </p>
            </div>
          )}

          {!toolsLoading && toolsData?.tools && toolsData.tools.length > 0 && (
            <div className="space-y-1.5">
              {toolsData.tools.map(tool => (
                <div key={tool.name} className="flex items-start gap-2 text-sm">
                  <span className="text-indigo-400 font-mono text-xs mt-0.5 shrink-0">fn</span>
                  <div>
                    <span className="font-mono text-xs text-gray-700">{tool.name}</span>
                    {tool.description && (
                      <p className="text-xs text-gray-500 mt-0.5">{tool.description}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* How it works */}
      <div className="bg-gray-50 rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">How it works</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs text-gray-600">
          <div className="flex gap-2">
            <span className="bg-blue-100 text-blue-700 font-bold rounded-full w-5 h-5 flex items-center justify-center shrink-0">1</span>
            <div>
              <p className="font-medium text-gray-700">Connect an app</p>
              <p className="mt-0.5 text-gray-500">Click Connect App, pick your tool, authorise via OAuth. Composio handles all credential storage.</p>
            </div>
          </div>
          <div className="flex gap-2">
            <span className="bg-blue-100 text-blue-700 font-bold rounded-full w-5 h-5 flex items-center justify-center shrink-0">2</span>
            <div>
              <p className="font-medium text-gray-700">Declare in project.yaml</p>
              <p className="mt-0.5 text-gray-500">Add <code className="bg-gray-100 px-1 rounded">composio:github</code> to your solution's integrations list in the YAML Editor.</p>
            </div>
          </div>
          <div className="flex gap-2">
            <span className="bg-blue-100 text-blue-700 font-bold rounded-full w-5 h-5 flex items-center justify-center shrink-0">3</span>
            <div>
              <p className="font-medium text-gray-700">Agents use the tools</p>
              <p className="mt-0.5 text-gray-500">All agent roles in this solution gain access to the tool functions automatically — no code changes needed.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
