import * as vscode from 'vscode'
import { SageApiClient } from './api'

const WEB_UI_URL = 'http://localhost:5173'

export class DashboardPanel {
  private static current: DashboardPanel | undefined
  private readonly panel: vscode.WebviewPanel

  private constructor(panel: vscode.WebviewPanel) {
    this.panel = panel
    this.panel.onDidDispose(() => this.dispose())
    this.panel.webview.html = this.buildHtml()

    // Listen for reload messages from the webview
    this.panel.webview.onDidReceiveMessage(msg => {
      if (msg.command === 'reload') {
        this.panel.webview.html = this.buildHtml()
      }
    })
  }

  static show(client: SageApiClient, extensionUri: vscode.Uri): void {
    if (DashboardPanel.current) {
      DashboardPanel.current.panel.reveal()
      return
    }
    const panel = vscode.window.createWebviewPanel(
      'sageDashboard',
      'SAGE[ai] Dashboard',
      vscode.ViewColumn.Beside,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
      }
    )
    DashboardPanel.current = new DashboardPanel(panel)
  }

  private buildHtml(): string {
    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy"
      content="default-src 'none';
               frame-src http://localhost:* https://localhost:*;
               style-src 'unsafe-inline';
               script-src 'unsafe-inline';">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { height: 100vh; overflow: hidden; background: #111827; }

  #frame-wrap { width: 100%; height: 100vh; }
  iframe { width: 100%; height: 100%; border: none; display: block; }

  #offline {
    display: none;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100vh;
    gap: 16px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #111827;
    color: #f9fafb;
    text-align: center;
    padding: 40px;
  }
  #offline h2 { font-size: 18px; color: #f87171; margin-bottom: 4px; }
  #offline p  { font-size: 13px; color: #9ca3af; }
  code {
    background: #1f2937; color: #34d399;
    padding: 10px 20px; border-radius: 6px;
    font-size: 12px; font-family: monospace;
    border: 1px solid #374151;
  }
  button {
    margin-top: 8px;
    background: #22c55e; color: #fff;
    border: none; padding: 9px 24px;
    border-radius: 6px; cursor: pointer;
    font-size: 13px; font-weight: 600;
  }
  button:hover { background: #16a34a; }
</style>
</head>
<body>

<div id="frame-wrap">
  <iframe id="frame" src="${WEB_UI_URL}" title="SAGE[ai] Dashboard"></iframe>
</div>

<div id="offline">
  <div style="font-size:32px">⚡</div>
  <h2>SAGE[ai] Web UI not running</h2>
  <p>Start SAGE first — double-click the bat file or run in terminal:</p>
  <code>make ui</code>
  <p style="margin-top:4px">Backend: <code style="font-size:11px">make run PROJECT=dfs</code></p>
  <button onclick="retry()">↺ Retry</button>
</div>

<script>
  const frame   = document.getElementById('frame')
  const offline = document.getElementById('offline')
  const wrap    = document.getElementById('frame-wrap')

  let loaded = false

  frame.onload = function() {
    loaded = true
    // If we were showing offline, switch back
    if (offline.style.display === 'flex') {
      offline.style.display = 'none'
      wrap.style.display = 'block'
    }
  }

  // Show offline page if the iframe fails to load within 6 seconds
  setTimeout(function() {
    if (!loaded) showOffline()
  }, 6000)

  function showOffline() {
    wrap.style.display = 'none'
    offline.style.display = 'flex'
  }

  function retry() {
    loaded = false
    offline.style.display = 'none'
    wrap.style.display = 'block'
    // Force reload by appending a cache-busting param
    frame.src = '${WEB_UI_URL}?t=' + Date.now()
    setTimeout(function() { if (!loaded) showOffline() }, 6000)
  }
</script>
</body>
</html>`
  }

  private dispose(): void {
    DashboardPanel.current = undefined
  }
}
