import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface ModelInfo {
  model: string
  daily_request_limit: number
  context_tokens: number
  unlimited: boolean
}

interface PIIFilterStatus {
  enabled: boolean
  mode: string
  entities: string[]
  fail_on_detection: boolean
}

interface DataResidencyStatus {
  enabled: boolean
  region: string
}

interface LLMStatus {
  provider: string
  model_info: ModelInfo
  session: {
    started_at: string
    current_time: string
    calls_made: number
    calls_today: number
    day_started_at: string
    estimated_tokens: number
    errors: number
  }
  config: {
    minimal_mode: boolean
    project: string
  }
  pii_filter?: PIIFilterStatus
  data_residency?: DataResidencyStatus
}

async function fetchLLMStatus(): Promise<LLMStatus> {
  const res = await fetch('/api/llm/status')
  if (!res.ok) throw new Error('Failed to fetch LLM status')
  return res.json()
}

async function switchLLM(body: { provider: string; model?: string; api_key?: string; claude_path?: string; save_as_default?: boolean }) {
  const res = await fetch('/api/llm/switch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Switch failed')
  }
  return res.json()
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function formatDuration(startIso: string): string {
  const diff = Math.floor((Date.now() - new Date(startIso).getTime()) / 1000)
  const h = Math.floor(diff / 3600)
  const m = Math.floor((diff % 3600) / 60)
  const s = diff % 60
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

/** Seconds until next UTC midnight */
function secsUntilMidnightUTC(): number {
  const now = new Date()
  const midnight = new Date(Date.UTC(
    now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1
  ))
  return Math.floor((midnight.getTime() - now.getTime()) / 1000)
}

function formatCountdown(secs: number): string {
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  return `${h}h ${m}m`
}

function pctColor(pct: number): string {
  if (pct >= 90) return 'bg-red-500'
  if (pct >= 70) return 'bg-amber-400'
  return 'bg-orange-500'
}

function pctTextColor(pct: number): string {
  if (pct >= 90) return 'text-red-600'
  if (pct >= 70) return 'text-amber-600'
  return 'text-orange-600'
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function LLMSettings() {
  const queryClient = useQueryClient()
  const [selectedProvider, setSelectedProvider] = useState<'gemini' | 'local' | 'claude-code' | 'claude' | 'ollama'>('gemini')
  const [geminiModel, setGeminiModel] = useState('gemini-2.5-flash')
  const [claudeModel, setClaudeModel] = useState('claude-sonnet-4-6')
  const [claudeApiKey, setClaudeApiKey] = useState('')
  const [localPath, setLocalPath] = useState('')
  const [claudePath, setClaudePath] = useState('')
  const [saveAsDefault, setSaveAsDefault] = useState(false)
  const [switchError, setSwitchError] = useState('')

  const { data, isLoading, isError } = useQuery({
    queryKey: ['llm-status'],
    queryFn: fetchLLMStatus,
    refetchInterval: 10_000,
  })

  const [switchPending, setSwitchPending] = useState<{ trace_id: string; description: string } | null>(null)

  const switchMutation = useMutation({
    mutationFn: switchLLM,
    onSuccess: (resp: any) => {
      setSwitchError('')
      if (resp?.status === 'pending_approval' && resp?.trace_id) {
        setSwitchPending({ trace_id: resp.trace_id, description: resp.description ?? '' })
      } else {
        // Legacy direct-switch response
        queryClient.invalidateQueries({ queryKey: ['llm-status'] })
        queryClient.invalidateQueries({ queryKey: ['health'] })
      }
    },
    onError: (e: Error) => setSwitchError(e.message),
  })

  if (isLoading) return <div className="p-6 text-gray-400 text-sm">Loading LLM status…</div>
  if (isError || !data) return <div className="p-6 text-red-500 text-sm">Could not reach API</div>

  const { session, config, model_info } = data
  const isGemini = data.provider.toLowerCase().includes('gemini')
  const isClaudeCode = data.provider.toLowerCase().includes('claudecodecli')
  const isClaude = data.provider.toLowerCase().includes('claude')
  const secsLeft = secsUntilMidnightUTC()

  // Daily request quota gauge (primary)
  const requestPct = model_info.unlimited || model_info.daily_request_limit === 0
    ? 0
    : Math.min(100, Math.round((session.calls_today / model_info.daily_request_limit) * 100))

  // Token estimate gauge (secondary context-window view)
  const tokenPct = model_info.context_tokens > 0
    ? Math.min(100, Math.round((session.estimated_tokens / model_info.context_tokens) * 100))
    : 0

  return (
    <div className="space-y-6 max-w-2xl">
      <h2 className="text-xl font-semibold text-gray-800">LLM Settings</h2>

      {/* Active provider card */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-700">Active Provider</h3>
          <span className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full font-medium">
            {config.project}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <div className={`w-3 h-3 rounded-full ${isGemini ? 'bg-blue-500' : (isClaude || isClaudeCode) ? 'bg-orange-500' : 'bg-purple-500'}`} />
          <span className="text-base font-medium text-gray-800">{data.provider}</span>
          {config.minimal_mode && (
            <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">
              MINIMAL MODE
            </span>
          )}
        </div>
        <div className="text-xs text-gray-400">
          Session running for {formatDuration(session.started_at)}
          {' · '}
          {session.errors > 0
            ? <span className="text-red-500">{session.errors} error{session.errors !== 1 ? 's' : ''}</span>
            : 'No errors'}
        </div>
      </div>

      {/* ── Daily quota gauge (PRIMARY) ────────────────────────────── */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-700">Daily Request Quota</h3>
          <span className="text-xs text-gray-400 font-mono">{model_info.model}</span>
        </div>

        {model_info.unlimited ? (
          <p className="text-sm text-gray-500">Local model — no daily quota.</p>
        ) : (
          <>
            {/* Big numbers */}
            <div className="flex items-end gap-2">
              <span className={`text-4xl font-bold tabular-nums ${pctTextColor(requestPct)}`}>
                {session.calls_today}
              </span>
              <span className="text-lg text-gray-400 mb-1">/ {model_info.daily_request_limit}</span>
              <span className="text-sm text-gray-400 mb-1.5 ml-1">requests today</span>
              <span className={`ml-auto text-lg font-semibold ${pctTextColor(requestPct)}`}>
                {requestPct}%
              </span>
            </div>

            {/* Bar */}
            <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${pctColor(requestPct)}`}
                style={{ width: `${requestPct}%` }}
              />
            </div>

            {/* Remaining + reset countdown */}
            <div className="flex justify-between text-xs text-gray-400">
              <span>
                <strong className="text-gray-600">
                  {model_info.daily_request_limit - session.calls_today}
                </strong>{' '}
                requests remaining
              </span>
              <span>Resets in <strong className="text-gray-600">{formatCountdown(secsLeft)}</strong> (UTC midnight)</span>
            </div>

            {requestPct >= 90 && (
              <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-xs text-red-700">
                ⚠ Approaching daily limit. Plan remaining tasks carefully or switch to a different model.
              </div>
            )}
            {requestPct >= 70 && requestPct < 90 && (
              <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-xs text-amber-700">
                You've used {requestPct}% of today's quota. {model_info.daily_request_limit - session.calls_today} requests left until reset.
              </div>
            )}
          </>
        )}
      </div>

      {/* ── Session totals (secondary) ─────────────────────────────── */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
        <h3 className="text-sm font-semibold text-gray-700">Session Totals</h3>
        <div className="grid grid-cols-3 gap-4 text-center">
          <div className="bg-gray-50 rounded-lg p-3">
            <div className="text-2xl font-bold text-gray-800 tabular-nums">{session.calls_made}</div>
            <div className="text-xs text-gray-500 mt-0.5">Total Calls</div>
          </div>
          <div className="bg-gray-50 rounded-lg p-3">
            <div className="text-2xl font-bold text-gray-800 tabular-nums">
              {(session.estimated_tokens / 1000).toFixed(1)}K
            </div>
            <div className="text-xs text-gray-500 mt-0.5">Est. Tokens</div>
          </div>
          <div className="bg-gray-50 rounded-lg p-3">
            <div className={`text-2xl font-bold tabular-nums ${session.errors > 0 ? 'text-red-600' : 'text-gray-800'}`}>
              {session.errors}
            </div>
            <div className="text-xs text-gray-500 mt-0.5">Errors</div>
          </div>
        </div>

        {/* Context-window token bar */}
        {!model_info.unlimited && model_info.context_tokens > 0 && (
          <div>
            <div className="flex justify-between text-xs text-gray-400 mb-1">
              <span>Est. context window used (cumulative)</span>
              <span>{tokenPct}% of {(model_info.context_tokens / 1000).toFixed(0)}K</span>
            </div>
            <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${pctColor(tokenPct)}`}
                style={{ width: `${tokenPct}%` }}
              />
            </div>
            <p className="text-xs text-gray-400 mt-1">
              Rough estimate — Gemini CLI does not expose exact token counts.
            </p>
          </div>
        )}
      </div>

      {/* PII Filter status */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-700">PII Filter</h3>
          {data.pii_filter?.enabled ? (
            <span className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full font-medium">
              Active
            </span>
          ) : (
            <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full font-medium">
              Disabled
            </span>
          )}
        </div>

        {data.pii_filter?.enabled ? (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500">Mode</span>
              <span className="font-mono text-xs bg-gray-100 text-gray-700 px-2 py-0.5 rounded">
                {data.pii_filter.mode}
              </span>
            </div>
            {data.pii_filter.fail_on_detection && (
              <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-xs text-amber-700">
                Fail-on-detection enabled — prompts with PII will be rejected.
              </div>
            )}
            {data.pii_filter.entities.length > 0 && (
              <div>
                <div className="text-xs text-gray-500 mb-1.5">Monitored entity types</div>
                <div className="flex flex-wrap gap-1">
                  {data.pii_filter.entities.map(entity => (
                    <span
                      key={entity}
                      className="text-xs bg-blue-50 text-blue-700 border border-blue-100 px-1.5 py-0.5 rounded font-mono"
                    >
                      {entity}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {data.data_residency?.enabled && (
              <div className="flex items-center justify-between text-sm pt-1">
                <span className="text-gray-500">Data Residency</span>
                <span className="font-mono text-xs bg-gray-100 text-gray-700 px-2 py-0.5 rounded uppercase">
                  {data.data_residency.region}
                </span>
              </div>
            )}
          </div>
        ) : (
          <p className="text-xs text-gray-400">
            PII detection is off. Set <code className="font-mono">pii.enabled: true</code> in{' '}
            <code className="font-mono">config/config.yaml</code> to activate scrubbing.
          </p>
        )}
      </div>

      {/* Switch provider */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
        <h3 className="text-sm font-semibold text-gray-700">Switch Provider</h3>

        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => setSelectedProvider('claude-code')}
            className={`py-2.5 rounded-lg border text-sm font-medium transition-colors ${
              selectedProvider === 'claude-code'
                ? 'bg-orange-50 border-orange-400 text-orange-700'
                : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100'
            }`}
          >
            Claude Code CLI
            <div className="text-xs font-normal opacity-70 mt-0.5">Uses Claude Code auth — no key needed</div>
          </button>
          <button
            onClick={() => setSelectedProvider('gemini')}
            className={`py-2.5 rounded-lg border text-sm font-medium transition-colors ${
              selectedProvider === 'gemini'
                ? 'bg-blue-50 border-blue-300 text-blue-700'
                : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100'
            }`}
          >
            Gemini CLI
            <div className="text-xs font-normal opacity-70 mt-0.5">Browser OAuth — no key</div>
          </button>
          <button
            onClick={() => setSelectedProvider('claude')}
            className={`py-2.5 rounded-lg border text-sm font-medium transition-colors ${
              selectedProvider === 'claude'
                ? 'bg-amber-50 border-amber-300 text-amber-700'
                : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100'
            }`}
          >
            Claude API
            <div className="text-xs font-normal opacity-70 mt-0.5">Anthropic API key required</div>
          </button>
          <button
            onClick={() => setSelectedProvider('local')}
            className={`py-2.5 rounded-lg border text-sm font-medium transition-colors ${
              selectedProvider === 'local'
                ? 'bg-purple-50 border-purple-300 text-purple-700'
                : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100'
            }`}
          >
            Local Llama
            <div className="text-xs font-normal opacity-70 mt-0.5">Air-gapped GGUF</div>
          </button>
          <button
            onClick={() => setSelectedProvider('ollama')}
            className={`py-2.5 rounded-lg border text-sm font-medium transition-colors ${
              selectedProvider === 'ollama'
                ? 'bg-teal-50 border-teal-400 text-teal-700'
                : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100'
            }`}
          >
            Ollama
            <div className="text-xs font-normal opacity-70 mt-0.5">Local server — no key</div>
          </button>
        </div>

        {selectedProvider === 'claude-code' && (
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-gray-600 block mb-1.5">Claude model</label>
              <select
                value={claudeModel}
                onChange={e => setClaudeModel(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white"
              >
                <option value="claude-sonnet-4-6">claude-sonnet-4-6 — latest Sonnet (recommended)</option>
                <option value="claude-opus-4-6">claude-opus-4-6 — highest quality</option>
                <option value="claude-haiku-4-5">claude-haiku-4-5 — fastest</option>
                <option value="claude-sonnet-4-5">claude-sonnet-4-5 — previous Sonnet</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 block mb-1.5">
                Claude executable path{' '}
                <span className="text-gray-400 font-normal">(leave default if unsure)</span>
              </label>
              <input
                type="text"
                value={claudePath}
                onChange={e => setClaudePath(e.target.value)}
                placeholder="Auto-detected (e.g. C:\Users\<you>\.local\bin\claude.exe)"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              />
            </div>
            <div className="bg-orange-50 border border-orange-200 rounded-lg px-3 py-2 text-xs text-orange-700">
              Uses your existing Claude Code authentication — no API key needed.
              The path above points to your local Claude Code installation.
            </div>
          </div>
        )}

        {selectedProvider === 'gemini' && (
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1.5">Gemini model</label>
            <select
              value={geminiModel}
              onChange={e => setGeminiModel(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white"
            >
              <option value="gemini-2.5-flash">gemini-2.5-flash — 500 req/day (recommended)</option>
              <option value="gemini-2.5-pro">gemini-2.5-pro — 25 req/day (highest quality)</option>
              <option value="gemini-2.0-flash">gemini-2.0-flash — 1500 req/day</option>
            </select>
            <p className="text-xs text-gray-400 mt-1">Free tier limits. Run <code>gemini auth</code> once in terminal.</p>
          </div>
        )}

        {selectedProvider === 'claude' && (
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-gray-600 block mb-1.5">Claude model</label>
              <select
                value={claudeModel}
                onChange={e => setClaudeModel(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white"
              >
                <option value="claude-sonnet-4-5">claude-sonnet-4-5 — balanced speed/quality (recommended)</option>
                <option value="claude-opus-4-5">claude-opus-4-5 — highest quality</option>
                <option value="claude-haiku-4-5">claude-haiku-4-5 — fastest, lowest cost</option>
                <option value="claude-3-5-sonnet-20241022">claude-3-5-sonnet — previous generation</option>
                <option value="claude-3-haiku-20240307">claude-3-haiku — previous generation, fast</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 block mb-1.5">
                Anthropic API key{' '}
                <span className="text-gray-400 font-normal">(stored in server env for this session)</span>
              </label>
              <input
                type="password"
                value={claudeApiKey}
                onChange={e => setClaudeApiKey(e.target.value)}
                placeholder="sk-ant-api03-…"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              />
              <p className="text-xs text-gray-400 mt-1">
                Get your key at console.anthropic.com. 200K context window, no hard daily limit.
              </p>
            </div>
          </div>
        )}

        {selectedProvider === 'local' && (
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1.5">
              GGUF model path (on server)
            </label>
            <input
              type="text"
              value={localPath}
              onChange={e => setLocalPath(e.target.value)}
              placeholder="/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
            />
            <p className="text-xs text-gray-400 mt-1">
              No daily limit. Ideal when quota is exhausted or air-gapped.
            </p>
          </div>
        )}

        {selectedProvider === 'ollama' && (
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1.5">Model name</label>
            <input
              type="text"
              value={localPath || 'llama3.2'}
              onChange={e => setLocalPath(e.target.value)}
              placeholder="llama3.2"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
            />
            <p className="text-xs text-gray-400 mt-1">
              Requires <code className="font-mono">ollama serve</code> running locally. No API key needed.
            </p>
          </div>
        )}

        {switchPending && (
          <div className="bg-yellow-50 border border-yellow-300 rounded-lg px-3 py-2 text-sm text-yellow-800">
            Switch proposed — approve it in the <a href="/" className="underline font-medium">Dashboard</a>.
            <div className="text-xs text-yellow-600 mt-0.5 font-mono">{switchPending.description}</div>
          </div>
        )}
        {switchError && (
          <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{switchError}</p>
        )}

        {/* Save as default toggle */}
        <label className="flex items-center gap-2.5 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={saveAsDefault}
            onChange={e => setSaveAsDefault(e.target.checked)}
            className="w-4 h-4 rounded border-gray-300 text-blue-600 cursor-pointer"
          />
          <span className="text-sm text-gray-700">
            Save as default{' '}
            <span className="text-xs text-gray-400">(persists to config.yaml — survives restarts)</span>
          </span>
        </label>

        <button
          onClick={() =>
            switchMutation.mutate({
              provider: selectedProvider,
              model: selectedProvider === 'gemini' ? geminiModel
                   : selectedProvider === 'claude-code' ? claudeModel
                   : selectedProvider === 'claude' ? claudeModel
                   : selectedProvider === 'ollama' ? (localPath || 'llama3.2')
                   : localPath || undefined,
              api_key: selectedProvider === 'claude' ? claudeApiKey || undefined : undefined,
              claude_path: selectedProvider === 'claude-code' ? claudePath || undefined : undefined,
              save_as_default: saveAsDefault,
            })
          }
          disabled={
            switchMutation.isPending ||
            (selectedProvider === 'local' && !localPath) ||
            (selectedProvider === 'claude' && !claudeApiKey && !data?.provider.toLowerCase().includes('claude'))
          }
          className="w-full bg-white hover:bg-gray-700 disabled:opacity-40 text-white
                     text-sm font-medium py-2.5 rounded-lg transition-colors"
        >
          {switchMutation.isPending ? 'Proposing switch…'
            : selectedProvider === 'gemini' ? `Switch to Gemini CLI${saveAsDefault ? ' & Save Default' : ''}`
            : selectedProvider === 'claude-code' ? `Switch to Claude Code CLI${saveAsDefault ? ' & Save Default' : ''}`
            : selectedProvider === 'claude' ? `Switch to Claude API${saveAsDefault ? ' & Save Default' : ''}`
            : selectedProvider === 'ollama' ? `Switch to Ollama${saveAsDefault ? ' & Save Default' : ''}`
            : `Switch to Local Llama${saveAsDefault ? ' & Save Default' : ''}`}
        </button>
      </div>

      {/* Notes */}
      <div className="text-xs text-gray-400 space-y-1 bg-gray-50 rounded-lg p-4">
        <p><strong>Claude Code CLI (recommended):</strong> Uses your existing Claude Code auth. No API key needed. Run <code>claude</code> once in terminal to authenticate.</p>
        <p><strong>Gemini CLI:</strong> Free tier (500 req/day). Uses browser OAuth — run <code>gemini auth</code> once.</p>
        <p><strong>Claude API:</strong> Direct Anthropic API key. 200K context, pay-per-token. Best for environments without Claude Code installed.</p>
        <p><strong>Local Llama:</strong> GGUF model on your machine. Zero network, no daily limit. Needs llama-cpp-python + GPU recommended.</p>
      </div>
    </div>
  )
}
