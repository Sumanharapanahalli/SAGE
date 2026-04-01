/**
 * SAGE Dashboard Webview Panel
 * ==============================
 * Renders the SAGE dashboard inside a VS Code webview panel.
 * This is the key firewall bypass — webview communicates with the backend
 * via localhost internally, no external ports exposed.
 *
 * Architecture:
 *   Webview HTML/JS (sandboxed) <-> postMessage <-> Extension <-> Backend API
 *
 * The webview makes NO direct HTTP calls. All API calls are proxied through
 * the extension host via VS Code's message passing. This ensures:
 *   1. No CORS issues
 *   2. No firewall issues (webview is internal to VS Code process)
 *   3. CSP compliance (no external script loading)
 */

import * as vscode from "vscode";
import { SageApiClient } from "../api";

export class DashboardPanel {
  public static currentPanel: DashboardPanel | undefined;
  private static readonly viewType = "sageDashboard";

  private readonly panel: vscode.WebviewPanel;
  private readonly api: SageApiClient;
  private disposables: vscode.Disposable[] = [];
  private pollTimer: NodeJS.Timeout | undefined;

  public static createOrShow(
    context: vscode.ExtensionContext,
    api: SageApiClient,
    initialRoute: string = "/"
  ) {
    const column = vscode.window.activeTextEditor
      ? vscode.window.activeTextEditor.viewColumn
      : undefined;

    if (DashboardPanel.currentPanel) {
      DashboardPanel.currentPanel.panel.reveal(column);
      DashboardPanel.currentPanel.navigateTo(initialRoute);
      return;
    }

    const panel = vscode.window.createWebviewPanel(
      DashboardPanel.viewType,
      "SAGE Dashboard",
      column || vscode.ViewColumn.One,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [],
      }
    );

    DashboardPanel.currentPanel = new DashboardPanel(panel, api, initialRoute);
  }

  private constructor(
    panel: vscode.WebviewPanel,
    api: SageApiClient,
    initialRoute: string
  ) {
    this.panel = panel;
    this.api = api;

    this.panel.webview.html = this.getHtml(initialRoute);
    this.setupMessageHandler();

    this.panel.onDidDispose(() => this.dispose(), null, this.disposables);

    // Auto-refresh dashboard data every 10 seconds
    this.pollTimer = setInterval(() => {
      this.sendUpdate();
    }, 10000);

    // Initial data load
    this.sendUpdate();
  }

  private navigateTo(route: string) {
    this.panel.webview.postMessage({ type: "navigate", route });
  }

  private async sendUpdate() {
    try {
      const [health, approvals, queue, agents] = await Promise.all([
        this.api.getStatus().catch(() => null),
        this.api.getPendingApprovals().catch(() => []),
        this.api.getQueue().catch(() => []),
        this.api.getAgents().catch(() => []),
      ]);

      // Derive display-friendly fields for the webview
      const projectName = health ? this.api.getProjectName(health) : "";
      const providerName = health ? this.api.getProviderName(health) : "";

      this.panel.webview.postMessage({
        type: "update",
        data: {
          health,
          approvals,
          queue,
          agents,
          projectName,
          providerName,
        },
      });
    } catch {
      // Backend unreachable — webview will show offline state
    }
  }

  private setupMessageHandler() {
    this.panel.webview.onDidReceiveMessage(
      async (msg) => {
        switch (msg.type) {
          case "approve":
            await this.api.approveProposal(msg.traceId, msg.feedback);
            this.sendUpdate();
            break;
          case "reject":
            await this.api.rejectProposal(msg.traceId, msg.feedback);
            this.sendUpdate();
            break;
          case "switchSolution":
            await this.api.switchSolution(msg.solution);
            this.sendUpdate();
            break;
          case "switchLLM":
            await this.api.switchLLM(msg.provider, msg.model);
            this.sendUpdate();
            break;
          case "refresh":
            this.sendUpdate();
            break;
        }
      },
      null,
      this.disposables
    );
  }

  private dispose() {
    DashboardPanel.currentPanel = undefined;
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
    }
    this.panel.dispose();
    this.disposables.forEach((d) => d.dispose());
  }

  private getHtml(initialRoute: string): string {
    return /*html*/ `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline';">
  <title>SAGE Dashboard</title>
  <style>
    :root {
      --sage-green: #10B981;
      --sage-dark: #1F2A37;
      --sage-red: #EF4444;
      --sage-amber: #F59E0B;
      --sage-blue: #3B82F6;
      --bg: var(--vscode-editor-background);
      --fg: var(--vscode-editor-foreground);
      --border: var(--vscode-panel-border);
      --card-bg: var(--vscode-editorWidget-background);
      --btn-bg: var(--vscode-button-background);
      --btn-fg: var(--vscode-button-foreground);
      --btn-hover: var(--vscode-button-hoverBackground);
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: var(--vscode-font-family);
      font-size: var(--vscode-font-size);
      color: var(--fg);
      background: var(--bg);
      padding: 16px;
    }

    h1 { font-size: 1.4em; margin-bottom: 4px; }
    h2 { font-size: 1.1em; margin: 16px 0 8px; color: var(--sage-green); }

    .header {
      display: flex; align-items: center; gap: 12px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 12px; margin-bottom: 16px;
    }
    .header .logo { font-weight: bold; color: var(--sage-green); font-size: 1.5em; }
    .header .status {
      padding: 2px 10px; border-radius: 12px; font-size: 0.8em; font-weight: 600;
    }
    .status.online { background: #065F46; color: #6EE7B7; }
    .status.offline { background: #7F1D1D; color: #FCA5A5; }

    .stats {
      display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 10px; margin-bottom: 16px;
    }
    .stat-card {
      background: var(--card-bg); border: 1px solid var(--border);
      border-radius: 8px; padding: 12px; text-align: center;
    }
    .stat-card .value {
      font-size: 1.8em; font-weight: bold;
    }
    .stat-card .label { font-size: 0.8em; opacity: 0.7; margin-top: 2px; }
    .stat-card.red .value { color: var(--sage-red); }
    .stat-card.amber .value { color: var(--sage-amber); }
    .stat-card.green .value { color: var(--sage-green); }
    .stat-card.blue .value { color: var(--sage-blue); }

    .nav-tabs {
      display: flex; gap: 0; border-bottom: 2px solid var(--border);
      margin-bottom: 12px;
    }
    .nav-tab {
      padding: 8px 16px; cursor: pointer; border: none; background: none;
      color: var(--fg); opacity: 0.6; font-size: 0.9em;
      border-bottom: 2px solid transparent; margin-bottom: -2px;
    }
    .nav-tab:hover { opacity: 0.8; }
    .nav-tab.active {
      opacity: 1; border-bottom-color: var(--sage-green);
      color: var(--sage-green); font-weight: 600;
    }

    .section { display: none; }
    .section.active { display: block; }

    .proposal-card {
      background: var(--card-bg); border: 1px solid var(--border);
      border-radius: 8px; padding: 12px; margin-bottom: 8px;
    }
    .proposal-card .type { font-weight: 600; }
    .proposal-card .meta { font-size: 0.8em; opacity: 0.6; margin: 4px 0; }
    .proposal-card .risk {
      display: inline-block; padding: 1px 8px; border-radius: 4px;
      font-size: 0.75em; font-weight: 600;
    }
    .risk.DESTRUCTIVE { background: #7F1D1D; color: #FCA5A5; }
    .risk.EXTERNAL { background: #1E3A5F; color: #93C5FD; }
    .risk.STATEFUL { background: #064E3B; color: #6EE7B7; }
    .risk.EPHEMERAL { background: #78350F; color: #FDE68A; }
    .risk.INFORMATIONAL { background: #1F2937; color: #9CA3AF; }

    .actions { margin-top: 8px; display: flex; gap: 6px; }
    .btn {
      padding: 4px 12px; border: none; border-radius: 4px; cursor: pointer;
      font-size: 0.85em;
    }
    .btn-approve { background: #065F46; color: #6EE7B7; }
    .btn-approve:hover { background: #047857; }
    .btn-reject { background: #7F1D1D; color: #FCA5A5; }
    .btn-reject:hover { background: #991B1B; }
    .btn-refresh { background: var(--btn-bg); color: var(--btn-fg); }
    .btn-refresh:hover { background: var(--btn-hover); }

    .empty { text-align: center; opacity: 0.5; padding: 24px; }

    .queue-item {
      display: flex; justify-content: space-between; align-items: center;
      padding: 8px 12px; border-bottom: 1px solid var(--border);
    }
    .queue-item .task-type { font-weight: 500; }
    .queue-item .task-status { font-size: 0.8em; opacity: 0.7; }
  </style>
</head>
<body>
  <div class="header">
    <span class="logo">SAGE[ai]</span>
    <span class="status offline" id="statusBadge">Connecting...</span>
    <span id="solutionName" style="opacity:0.6; font-size:0.9em;"></span>
    <span style="flex:1;"></span>
    <button class="btn btn-refresh" onclick="refresh()">Refresh</button>
  </div>

  <div class="stats">
    <div class="stat-card red">
      <div class="value" id="approvalCount">-</div>
      <div class="label">APPROVALS</div>
    </div>
    <div class="stat-card amber">
      <div class="value" id="queueCount">-</div>
      <div class="label">QUEUED</div>
    </div>
    <div class="stat-card green">
      <div class="value" id="agentCount">-</div>
      <div class="label">AGENTS</div>
    </div>
    <div class="stat-card blue">
      <div class="value" id="llmProvider">-</div>
      <div class="label">LLM PROVIDER</div>
    </div>
  </div>

  <div class="nav-tabs">
    <button class="nav-tab active" data-tab="approvals">Approvals</button>
    <button class="nav-tab" data-tab="queue">Queue</button>
    <button class="nav-tab" data-tab="info">Info</button>
  </div>

  <div class="section active" id="tab-approvals">
    <div id="approvalsList"></div>
  </div>

  <div class="section" id="tab-queue">
    <div id="queueList"></div>
  </div>

  <div class="section" id="tab-info">
    <div class="proposal-card">
      <div class="type">About this Dashboard</div>
      <div class="meta" style="opacity:1; margin-top:8px;">
        This dashboard runs inside VS Code's webview — no external ports or
        browser needed. All API calls are proxied through the extension host
        via message passing.<br><br>
        <strong>Firewall-safe:</strong> The webview communicates only with
        the extension process. The extension talks to the SAGE backend on
        localhost. No traffic leaves the machine.<br><br>
        <strong>Tip:</strong> Use Command Palette (Ctrl+Shift+P) and type
        "SAGE" to see all available commands.
      </div>
    </div>
  </div>

  <script>
    const vscode = acquireVsCodeApi();
    let currentData = { health: null, approvals: [], queue: [], agents: [], projectName: '', providerName: '' };

    // Tab switching
    document.querySelectorAll('.nav-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
      });
    });

    // Handle messages from extension
    window.addEventListener('message', event => {
      const msg = event.data;
      if (msg.type === 'update') {
        currentData = msg.data;
        render();
      } else if (msg.type === 'navigate') {
        const routeMap = { '/approvals': 'approvals', '/queue': 'queue' };
        const tab = routeMap[msg.route] || 'approvals';
        document.querySelector('[data-tab="' + tab + '"]')?.click();
      }
    });

    function render() {
      const { health, approvals, queue, agents, projectName, providerName } = currentData;

      // Status badge
      const badge = document.getElementById('statusBadge');
      const online = health && (health.status === 'ok' || health.status === 'healthy');
      badge.textContent = online ? 'Online' : 'Offline';
      badge.className = 'status ' + (online ? 'online' : 'offline');

      // Solution name (pre-extracted by extension host)
      document.getElementById('solutionName').textContent = projectName || '';

      // Stats
      document.getElementById('approvalCount').textContent = approvals?.length ?? '-';
      document.getElementById('queueCount').textContent = queue?.length ?? '-';
      document.getElementById('agentCount').textContent = agents?.length ?? '-';
      document.getElementById('llmProvider').textContent = providerName || '-';

      // Approvals list
      const approvalsList = document.getElementById('approvalsList');
      if (!approvals || approvals.length === 0) {
        approvalsList.innerHTML = '<div class="empty">No pending approvals</div>';
      } else {
        approvalsList.innerHTML = approvals.map(p => {
          const pType = p.action_type || p.proposal_type || 'unknown';
          const rClass = p.risk_class || 'INFORMATIONAL';
          return \`
          <div class="proposal-card">
            <div class="type">\${esc(pType)}</div>
            <div class="meta">
              <span class="risk \${esc(rClass)}">\${esc(rClass)}</span>
              &nbsp; \${esc(p.trace_id?.slice(0, 8))}... &nbsp; \${esc(p.created_at || '')}
            </div>
            \${p.summary ? '<div class="meta" style="opacity:0.8;">' + esc(p.summary) + '</div>' : ''}
            <div class="actions">
              <button class="btn btn-approve" onclick="approve('\${esc(p.trace_id)}')">Approve</button>
              <button class="btn btn-reject" onclick="reject('\${esc(p.trace_id)}')">Reject</button>
            </div>
          </div>
        \`}).join('');
      }

      // Queue list
      const queueList = document.getElementById('queueList');
      if (!queue || queue.length === 0) {
        queueList.innerHTML = '<div class="empty">Queue is empty</div>';
      } else {
        queueList.innerHTML = queue.map(q => \`
          <div class="queue-item">
            <span class="task-type">\${esc(q.task_type)}</span>
            <span class="task-status">\${esc(q.status)}</span>
          </div>
        \`).join('');
      }
    }

    function esc(s) {
      if (!s) return '';
      const d = document.createElement('div');
      d.textContent = String(s);
      return d.innerHTML;
    }

    function approve(traceId) {
      vscode.postMessage({ type: 'approve', traceId, feedback: '' });
    }

    function reject(traceId) {
      vscode.postMessage({ type: 'reject', traceId, feedback: 'Rejected from VS Code' });
    }

    function refresh() {
      vscode.postMessage({ type: 'refresh' });
    }

    // Navigate to initial route
    const initialRoute = '${initialRoute}';
    if (initialRoute !== '/') {
      const routeMap = { '/approvals': 'approvals', '/queue': 'queue' };
      const tab = routeMap[initialRoute];
      if (tab) {
        document.querySelector('[data-tab="' + tab + '"]')?.click();
      }
    }
  </script>
</body>
</html>`;
  }
}
