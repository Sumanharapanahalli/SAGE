import * as vscode from 'vscode'
import { SageApiClient } from './api'
import { SageStatusBar } from './statusBar'
import { ProposalsProvider, BackendProposalItem } from './proposalsProvider'
import { AuditLogProvider } from './auditLogProvider'
import { LiveConsole } from './liveConsole'
import { DashboardPanel } from './dashboardPanel'
import * as cmds from './commands'

export function activate(context: vscode.ExtensionContext): void {
  // ── Config ────────────────────────────────────────────────────────────────
  const cfg = () => vscode.workspace.getConfiguration('sage')
  const getApiUrl = () => cfg().get<string>('apiUrl', 'http://localhost:8000')
  const getPollInterval = () => cfg().get<number>('pollInterval', 15)

  // ── Shared output channel ─────────────────────────────────────────────────
  const output = vscode.window.createOutputChannel('SAGE[ai]')

  // ── Client + UI ────────────────────────────────────────────────────────────
  let client = new SageApiClient(getApiUrl())
  const statusBar    = new SageStatusBar(client)
  const proposals    = new ProposalsProvider(client)
  const auditLog     = new AuditLogProvider(client, output)
  const liveConsole  = new LiveConsole(output)

  const refresh = () => { proposals.refresh(); statusBar.refresh(); auditLog.refresh() }

  statusBar.start(getPollInterval())

  // ── Tree views ─────────────────────────────────────────────────────────────
  const proposalsView = vscode.window.createTreeView('sageProposals', {
    treeDataProvider: proposals,
    showCollapseAll: false,
  })

  const auditView = vscode.window.createTreeView('sageAuditLog', {
    treeDataProvider: auditLog,
    showCollapseAll: true,
  })

  // ── Rebuild client when settings change ───────────────────────────────────
  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration(e => {
      if (e.affectsConfiguration('sage')) {
        if (liveConsole.isActive) {
          liveConsole.stop()
        }
        statusBar.stop()
        client = new SageApiClient(getApiUrl())
        statusBar.start(getPollInterval())
        refresh()
        if (liveConsole.isActive) {
          liveConsole.start(getApiUrl())
        }
      }
    })
  )

  // ── Register commands ──────────────────────────────────────────────────────
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const reg = (cmd: string, fn: (...args: any[]) => unknown) =>
    context.subscriptions.push(vscode.commands.registerCommand(cmd, fn))

  // Existing analysis commands
  reg('sage.analyzeSelection', () => cmds.analyzeSelection(client, refresh))
  reg('sage.analyzeFile',      () => cmds.analyzeFile(client, refresh))
  reg('sage.reviewDiff',       () => cmds.reviewDiff(client, refresh))
  reg('sage.showDashboard',    () => DashboardPanel.show(client, context.extensionUri))
  reg('sage.refreshProposals', () => refresh())
  reg('sage.submitImprovement',() => cmds.submitImprovement(client))
  reg('sage.switchSolution',   () => cmds.switchSolution(client))
  reg('sage.showLLMStatus',    () => cmds.showLLMStatus(client))

  // Session analyst proposal approve/reject
  reg('sage.approveProposal', (item: any) => {
    if (item?.proposal?.trace_id) cmds.approveFromTree(client, item, refresh)
  })
  reg('sage.rejectProposal', (item: any) => {
    if (item?.proposal?.trace_id) cmds.rejectFromTree(client, item, refresh)
  })
  reg('sage.showProposalDetail', (proposal: any) => cmds.showProposalDetail(proposal))

  // Backend proposal approve/reject (from ProposalStore)
  reg('sage.approveBackendProposal', (item: any) => {
    if (item instanceof BackendProposalItem) {
      cmds.approveBackendProposal(client, item.backendProposal, refresh)
    }
  })
  reg('sage.rejectBackendProposal', (item: any) => {
    if (item instanceof BackendProposalItem) {
      cmds.rejectBackendProposal(client, item.backendProposal, refresh)
    }
  })
  reg('sage.showBackendProposalDetail', (proposal: any) =>
    cmds.showBackendProposalDetail(proposal)
  )

  // Audit log
  reg('sage.refreshAuditLog',  () => auditLog.refresh())
  reg('sage.showAuditDetail',  (entry: any) => auditLog.showDetail(entry))

  // Live Console
  reg('sage.startLiveConsole', () => {
    liveConsole.start(getApiUrl())
    vscode.window.showInformationMessage('SAGE Live Console started — see SAGE[ai] Output channel')
  })
  reg('sage.stopLiveConsole', () => {
    liveConsole.stop()
    vscode.window.showInformationMessage('SAGE Live Console stopped.')
  })

  // ── Disposables ────────────────────────────────────────────────────────────
  context.subscriptions.push(statusBar, proposalsView, auditView, liveConsole, output)

  // ── Startup ───────────────────────────────────────────────────────────────
  client.health().then(h => {
    vscode.window.setStatusBarMessage(`$(shield) SAGE connected — ${h.project.name}`, 5000)
    // Auto-start live console if enabled in settings (default: true)
    const autoStart = cfg().get<boolean>('autoStartLiveConsole', true)
    if (autoStart) liveConsole.start(getApiUrl())
  }).catch(() => {
    // Silently skip if backend isn't running
  })
}

export function deactivate(): void {
  // VS Code disposes context.subscriptions automatically
}
