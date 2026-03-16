import * as vscode from 'vscode'
import { SageApiClient } from './api'
import { SageStatusBar } from './statusBar'
import { ProposalsProvider } from './proposalsProvider'
import { DashboardPanel } from './dashboardPanel'
import * as cmds from './commands'

export function activate(context: vscode.ExtensionContext): void {
  // ── Config ────────────────────────────────────────────────────────────────
  const cfg = () => vscode.workspace.getConfiguration('sage')
  const getApiUrl = () => cfg().get<string>('apiUrl', 'http://localhost:8000')
  const getPollInterval = () => cfg().get<number>('pollInterval', 15)

  // ── Client + UI ────────────────────────────────────────────────────────────
  let client = new SageApiClient(getApiUrl())
  const statusBar = new SageStatusBar(client)
  const provider = new ProposalsProvider(client)
  const refresh = () => { provider.refresh(); statusBar.refresh() }

  statusBar.start(getPollInterval())

  // ── Tree view ──────────────────────────────────────────────────────────────
  const treeView = vscode.window.createTreeView('sageProposals', {
    treeDataProvider: provider,
    showCollapseAll: false,
  })

  // ── Rebuild client when settings change ───────────────────────────────────
  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration(e => {
      if (e.affectsConfiguration('sage')) {
        statusBar.stop()
        client = new SageApiClient(getApiUrl())
        statusBar.start(getPollInterval())
        refresh()
      }
    })
  )

  // ── Register commands ──────────────────────────────────────────────────────
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const reg = (cmd: string, fn: (...args: any[]) => unknown) =>
    context.subscriptions.push(vscode.commands.registerCommand(cmd, fn))

  reg('sage.analyzeSelection', () =>
    cmds.analyzeSelection(client, refresh)
  )

  reg('sage.analyzeFile', () =>
    cmds.analyzeFile(client, refresh)
  )

  reg('sage.reviewDiff', () =>
    cmds.reviewDiff(client, refresh)
  )

  reg('sage.showDashboard', () =>
    DashboardPanel.show(client, context.extensionUri)
  )

  reg('sage.refreshProposals', () => refresh())

  reg('sage.approveProposal', (item: any) => {
    if (item?.proposal?.trace_id) {
      cmds.approveFromTree(client, item, refresh)
    }
  })

  reg('sage.rejectProposal', (item: any) => {
    if (item?.proposal?.trace_id) {
      cmds.rejectFromTree(client, item, refresh)
    }
  })

  reg('sage.showProposalDetail', (proposal: any) =>
    cmds.showProposalDetail(proposal)
  )

  reg('sage.submitImprovement', () =>
    cmds.submitImprovement(client)
  )

  reg('sage.switchSolution', () =>
    cmds.switchSolution(client)
  )

  reg('sage.showLLMStatus', () =>
    cmds.showLLMStatus(client)
  )

  // ── Disposables ────────────────────────────────────────────────────────────
  context.subscriptions.push(statusBar, treeView)

  // ── Startup notification ───────────────────────────────────────────────────
  client.health().then(h => {
    vscode.window.setStatusBarMessage(
      `$(shield) SAGE connected — ${h.project.name}`,
      5000
    )
  }).catch(() => {
    // Silently skip if backend isn't running yet
  })
}

export function deactivate(): void {
  // VS Code disposes context.subscriptions automatically
}
