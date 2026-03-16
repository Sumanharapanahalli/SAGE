/**
 * SAGE Live Console — streams Python backend logs to a VS Code Output Channel.
 * Maps to the web UI Live Console page (/live-console).
 * Uses Node.js http module to connect to the SSE endpoint GET /logs/stream.
 */
import * as http from 'http'
import * as https from 'https'
import * as vscode from 'vscode'

interface LogEntry {
  level:   string
  name:    string
  message: string
  ts:      string
}

const LEVEL_PREFIX: Record<string, string> = {
  DEBUG:    '[DBG]',
  INFO:     '[INF]',
  WARNING:  '[WRN]',
  ERROR:    '[ERR]',
  CRITICAL: '[CRT]',
}

export class LiveConsole implements vscode.Disposable {
  private _output: vscode.OutputChannel
  private _req:    http.ClientRequest | null = null
  private _active  = false
  private _reconnectTimer: NodeJS.Timeout | null = null

  constructor(output: vscode.OutputChannel) {
    this._output = output
  }

  get isActive(): boolean { return this._active }

  start(apiUrl: string): void {
    if (this._active) return
    this._active = true
    this._connect(apiUrl)
    this._output.show(false)
    this._output.appendLine(`[SAGE Live Console] Connecting to ${apiUrl}/logs/stream …`)
  }

  stop(): void {
    this._active = false
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer)
      this._reconnectTimer = null
    }
    if (this._req) {
      this._req.destroy()
      this._req = null
    }
    this._output.appendLine('[SAGE Live Console] Stopped.')
  }

  private _connect(apiUrl: string): void {
    if (!this._active) return

    const url = new URL('/logs/stream', apiUrl)
    const lib = url.protocol === 'https:' ? https : http

    const options: http.RequestOptions = {
      hostname: url.hostname,
      port:     url.port || (url.protocol === 'https:' ? 443 : 80),
      path:     url.pathname,
      method:   'GET',
      headers:  { Accept: 'text/event-stream' },
    }

    try {
      this._req = lib.request(options, (res) => {
        if (res.statusCode !== 200) {
          this._output.appendLine(`[SAGE Live Console] HTTP ${res.statusCode} — retrying in 5s`)
          this._scheduleReconnect(apiUrl)
          return
        }

        let buffer = ''
        res.on('data', (chunk: Buffer) => {
          buffer += chunk.toString('utf8')
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''

          for (const line of lines) {
            if (!line.startsWith('data:')) continue
            const json = line.slice(5).trim()
            if (!json) continue
            try {
              const entry: LogEntry = JSON.parse(json)
              const time   = entry.ts?.slice(11, 23) ?? ''
              const prefix = LEVEL_PREFIX[entry.level] ?? '[   ]'
              const name   = entry.name?.slice(0, 20).padEnd(20) ?? ''
              this._output.appendLine(`${time} ${prefix} ${name} ${entry.message}`)
            } catch {
              // ignore malformed lines
            }
          }
        })

        res.on('end', () => {
          if (this._active) {
            this._output.appendLine('[SAGE Live Console] Connection closed — retrying in 5s')
            this._scheduleReconnect(apiUrl)
          }
        })

        res.on('error', () => {
          if (this._active) this._scheduleReconnect(apiUrl)
        })
      })

      this._req.on('error', () => {
        if (this._active) {
          this._scheduleReconnect(apiUrl)
        }
      })

      this._req.end()
    } catch {
      if (this._active) this._scheduleReconnect(apiUrl)
    }
  }

  private _scheduleReconnect(apiUrl: string): void {
    if (!this._active) return
    this._reconnectTimer = setTimeout(() => this._connect(apiUrl), 5000)
  }

  dispose(): void {
    this.stop()
  }
}
