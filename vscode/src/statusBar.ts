import * as vscode from 'vscode'
import { SageApiClient } from './api'

export class SageStatusBar {
  private item: vscode.StatusBarItem
  private timer: NodeJS.Timeout | undefined
  private client: SageApiClient
  private pendingCount = 0

  constructor(client: SageApiClient) {
    this.client = client
    this.item = vscode.window.createStatusBarItem(
      vscode.StatusBarAlignment.Left,
      100
    )
    this.item.command = 'sage.showLLMStatus'
    this.item.tooltip = 'SAGE[ai] — Smart Agentic-Guided Empowerment\nClick for LLM quota details'
    this.item.show()
  }

  start(intervalSecs: number): void {
    this.refresh()
    const ms = Math.max(5, intervalSecs) * 1000
    this.timer = setInterval(() => this.refresh(), ms)
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer)
      this.timer = undefined
    }
  }

  getPendingCount(): number {
    return this.pendingCount
  }

  async refresh(): Promise<void> {
    try {
      const [llm, improvements] = await Promise.all([
        this.client.llmStatus(),
        this.client.pendingImprovements(),
      ])

      this.pendingCount = improvements.count

      const { calls_today, errors } = llm.session
      const { daily_request_limit, unlimited, model } = llm.model_info

      let quotaText: string
      if (unlimited) {
        quotaText = `local`
      } else {
        const pct = Math.round((calls_today / daily_request_limit) * 100)
        quotaText = `${calls_today}/${daily_request_limit} (${pct}%)`
      }

      const pending = improvements.count > 0 ? ` · ${improvements.count} pending` : ''
      const errBadge = errors > 0 ? ` ⚠${errors}` : ''

      this.item.text = `$(shield) SAGE: ${quotaText}${pending}${errBadge}`

      // Colour-code by quota pressure
      if (!unlimited) {
        const pct = (calls_today / daily_request_limit) * 100
        if (pct >= 90) {
          this.item.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground')
          this.item.tooltip = `SAGE[ai] — QUOTA CRITICAL\n${model}: ${calls_today}/${daily_request_limit} requests used today`
        } else if (pct >= 70) {
          this.item.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground')
          this.item.tooltip = `SAGE[ai] — ${calls_today}/${daily_request_limit} requests today (${Math.round(pct)}%)\nClick for full LLM status`
        } else {
          this.item.backgroundColor = undefined
          this.item.tooltip = `SAGE[ai] — Smart Agentic-Guided Empowerment\n${model}: ${calls_today}/${daily_request_limit} requests today\nClick for full LLM status`
        }
      }
    } catch {
      this.item.text = `$(shield) SAGE: offline`
      this.item.backgroundColor = undefined
      this.item.tooltip = 'SAGE backend unreachable — run: make run PROJECT=<name>'
    }
  }

  dispose(): void {
    this.stop()
    this.item.dispose()
  }
}
