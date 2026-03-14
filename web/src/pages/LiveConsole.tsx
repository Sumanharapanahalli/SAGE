/**
 * LiveConsole — streams Python logging output from the SAGE backend in real time.
 * Uses the GET /logs/stream SSE endpoint.
 *
 * Replaces the need to watch the terminal — all agent activity, LLM calls,
 * approvals, and errors are visible here in the browser.
 */

import { useEffect, useRef, useState, useCallback } from 'react'
import ModuleWrapper from '../components/shared/ModuleWrapper'
import { logsStreamUrl } from '../api/client'

interface LogEntry {
  level:   string
  name:    string
  message: string
  ts:      string
}

const LEVEL_COLOURS: Record<string, string> = {
  DEBUG:    'text-gray-400',
  INFO:     'text-green-400',
  WARNING:  'text-yellow-400',
  ERROR:    'text-red-400',
  CRITICAL: 'text-red-600 font-bold',
}

const MAX_LINES = 500

export default function LiveConsole() {
  const [entries, setEntries]   = useState<LogEntry[]>([])
  const [connected, setConnected] = useState(false)
  const [paused, setPaused]     = useState(false)
  const [filter, setFilter]     = useState('')
  const bottomRef               = useRef<HTMLDivElement>(null)
  const esRef                   = useRef<EventSource | null>(null)
  const pausedRef               = useRef(false)

  pausedRef.current = paused

  const connect = useCallback(() => {
    if (esRef.current) {
      esRef.current.close()
    }
    const es = new EventSource(logsStreamUrl())
    esRef.current = es

    es.onopen = () => setConnected(true)

    es.onmessage = (e) => {
      if (pausedRef.current) return
      try {
        const entry: LogEntry = JSON.parse(e.data)
        setEntries(prev => {
          const next = [...prev, entry]
          return next.length > MAX_LINES ? next.slice(next.length - MAX_LINES) : next
        })
      } catch {
        // ignore parse errors
      }
    }

    es.onerror = () => {
      setConnected(false)
      es.close()
      // Reconnect after 3 s
      setTimeout(connect, 3000)
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      esRef.current?.close()
    }
  }, [connect])

  // Auto-scroll to bottom unless paused
  useEffect(() => {
    if (!paused) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [entries, paused])

  const visible = filter
    ? entries.filter(e =>
        e.message.toLowerCase().includes(filter.toLowerCase()) ||
        e.name.toLowerCase().includes(filter.toLowerCase())
      )
    : entries

  return (
    <ModuleWrapper moduleId="live-console">
      <div className="space-y-3">
        {/* Toolbar */}
        <div className="flex items-center gap-3 flex-wrap">
          <span className={`inline-flex items-center gap-1.5 text-xs font-mono px-2 py-1 rounded ${
            connected ? 'bg-green-900/40 text-green-400' : 'bg-red-900/40 text-red-400'
          }`}>
            <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`} />
            {connected ? 'Connected' : 'Reconnecting…'}
          </span>

          <input
            type="text"
            placeholder="Filter logs…"
            value={filter}
            onChange={e => setFilter(e.target.value)}
            className="flex-1 min-w-[160px] bg-gray-800 border border-gray-600 rounded px-3 py-1 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500"
          />

          <button
            onClick={() => setPaused(p => !p)}
            className={`text-xs px-3 py-1 rounded border ${
              paused
                ? 'border-yellow-500 text-yellow-400 hover:bg-yellow-900/30'
                : 'border-gray-600 text-gray-400 hover:bg-gray-700'
            }`}
          >
            {paused ? 'Resume' : 'Pause'}
          </button>

          <button
            onClick={() => setEntries([])}
            className="text-xs px-3 py-1 rounded border border-gray-600 text-gray-400 hover:bg-gray-700"
          >
            Clear
          </button>

          <span className="text-xs text-gray-500 ml-auto">
            {visible.length} / {MAX_LINES} lines
          </span>
        </div>

        {/* Log output */}
        <div className="bg-gray-950 border border-gray-700 rounded-lg h-[calc(100vh-220px)] overflow-y-auto font-mono text-xs leading-5 p-3">
          {visible.length === 0 && (
            <div className="text-gray-600 text-center mt-8">
              {connected ? 'Waiting for log output…' : 'Not connected — retrying…'}
            </div>
          )}
          {visible.map((entry, i) => (
            <div key={i} className="flex gap-2 hover:bg-gray-900/50 px-1 rounded">
              <span className="text-gray-600 shrink-0 w-[82px] overflow-hidden">
                {entry.ts.slice(11, 23)}
              </span>
              <span className={`shrink-0 w-[56px] ${LEVEL_COLOURS[entry.level] ?? 'text-gray-400'}`}>
                {entry.level}
              </span>
              <span className="text-gray-500 shrink-0 max-w-[140px] truncate">
                {entry.name}
              </span>
              <span className="text-gray-200 break-all">
                {entry.message}
              </span>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      </div>
    </ModuleWrapper>
  )
}
