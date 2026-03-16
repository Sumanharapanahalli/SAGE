import * as vscode from 'vscode'
import * as cp from 'child_process'
import * as util from 'util'
import { SageApiClient, Proposal, BackendProposal } from './api'
import { storeProposal, removeProposal, getProposal } from './proposalsProvider'

const exec = util.promisify(cp.exec)

// Shared output channel for all SAGE results
let _outputChannel: vscode.OutputChannel | undefined

function outputChannel(): vscode.OutputChannel {
  if (!_outputChannel) {
    _outputChannel = vscode.window.createOutputChannel('SAGE[ai]')
  }
  return _outputChannel
}

function severityIcon(sev: string): string {
  return { RED: '🔴', AMBER: '🟡', GREEN: '🟢' }[sev] ?? '⚪'
}

function printProposal(proposal: Proposal): void {
  const ch = outputChannel()
  ch.appendLine('')
  ch.appendLine('━'.repeat(70))
  ch.appendLine(`${severityIcon(proposal.severity)} SEVERITY: ${proposal.severity}`)
  ch.appendLine(`TRACE ID:  ${proposal.trace_id}`)
  ch.appendLine('')
  ch.appendLine('ROOT CAUSE')
  ch.appendLine('  ' + proposal.root_cause_hypothesis)
  ch.appendLine('')
  ch.appendLine('RECOMMENDED ACTION')
  ch.appendLine('  ' + proposal.recommended_action)
  if (proposal.confidence) {
    ch.appendLine('')
    ch.appendLine(`CONFIDENCE: ${proposal.confidence}`)
  }
  ch.appendLine('━'.repeat(70))
  ch.show(true) // show without stealing focus
}

// ─── Analyze selection / file ─────────────────────────────────────────────────

export async function analyzeSelection(client: SageApiClient, refresh: () => void): Promise<void> {
  const editor = vscode.window.activeTextEditor
  let text = editor?.document.getText(editor.selection)

  if (!text?.trim()) {
    text = await vscode.window.showInputBox({
      prompt: 'Paste log entry or error text to analyze',
      placeHolder: 'e.g. ERROR: NAND flash bad block at 0x1A000000',
      ignoreFocusOut: true,
    })
  }
  if (!text?.trim()) {
    return
  }

  await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Notification, title: 'SAGE: Analyzing…', cancellable: false },
    async () => {
      try {
        const proposal = await client.analyze(text!)
        storeProposal(proposal)
        refresh()
        printProposal(proposal)

        // Notification with quick actions
        const sev = proposal.severity
        const icon = severityIcon(sev)
        const msg = `${icon} SAGE ${sev}: ${proposal.root_cause_hypothesis.slice(0, 80)}`
        const notifyFn = sev === 'RED'
          ? vscode.window.showErrorMessage
          : sev === 'AMBER'
          ? vscode.window.showWarningMessage
          : vscode.window.showInformationMessage

        const choice = await notifyFn(msg, 'Approve', 'Reject', 'Show Detail')
        if (choice === 'Approve') { await approveProposal(client, proposal.trace_id, refresh) }
        else if (choice === 'Reject') { await rejectProposal(client, proposal.trace_id, refresh) }
        else if (choice === 'Show Detail') { printProposal(proposal); outputChannel().show() }
      } catch (err: unknown) {
        vscode.window.showErrorMessage(`SAGE analyze failed: ${(err as Error).message}`)
      }
    }
  )
}

export async function analyzeFile(client: SageApiClient, refresh: () => void): Promise<void> {
  const editor = vscode.window.activeTextEditor
  if (!editor) {
    vscode.window.showWarningMessage('No active file.')
    return
  }
  const text = editor.document.getText()
  if (!text.trim()) {
    vscode.window.showWarningMessage('File is empty.')
    return
  }
  // Use only the first 8000 chars to stay within sensible prompt size
  const truncated = text.length > 8000
    ? text.slice(0, 8000) + '\n… (truncated)'
    : text

  await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Notification, title: `SAGE: Analyzing ${editor.document.fileName.split(/[\\/]/).pop()}…`, cancellable: false },
    async () => {
      try {
        const proposal = await client.analyze(truncated)
        storeProposal(proposal)
        refresh()
        printProposal(proposal)
        vscode.window.showInformationMessage(
          `${severityIcon(proposal.severity)} SAGE: ${proposal.severity} — see SAGE[ai] output panel`
        )
      } catch (err: unknown) {
        vscode.window.showErrorMessage(`SAGE analyze failed: ${(err as Error).message}`)
      }
    }
  )
}

// ─── Review current git diff ──────────────────────────────────────────────────

export async function reviewDiff(client: SageApiClient, refresh: () => void): Promise<void> {
  const folders = vscode.workspace.workspaceFolders
  if (!folders?.length) {
    vscode.window.showWarningMessage('No workspace folder open.')
    return
  }
  const cwd = folders[0].uri.fsPath

  let diff: string
  let branch = 'unknown'

  try {
    const { stdout: branchOut } = await exec('git rev-parse --abbrev-ref HEAD', { cwd })
    branch = branchOut.trim()
    const { stdout: diffOut } = await exec('git diff HEAD', { cwd })
    diff = diffOut.trim()
  } catch {
    vscode.window.showErrorMessage('Could not run git diff — is this a git repository?')
    return
  }

  if (!diff) {
    vscode.window.showInformationMessage('No uncommitted changes to review.')
    return
  }

  // Cap diff size
  const payload = diff.length > 12_000 ? diff.slice(0, 12_000) + '\n… (truncated)' : diff
  const context = `Git diff on branch: ${branch}\n\n${payload}`

  await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Notification, title: `SAGE: Reviewing diff on ${branch}…`, cancellable: false },
    async () => {
      try {
        const proposal = await client.analyze(context)
        storeProposal(proposal)
        refresh()
        printProposal(proposal)
        vscode.window.showInformationMessage(
          `${severityIcon(proposal.severity)} SAGE diff review: ${proposal.severity} — see output panel`
        )
      } catch (err: unknown) {
        vscode.window.showErrorMessage(`SAGE review failed: ${(err as Error).message}`)
      }
    }
  )
}

// ─── Approve / Reject ─────────────────────────────────────────────────────────

export async function approveProposal(
  client: SageApiClient,
  traceId: string,
  refresh: () => void
): Promise<void> {
  try {
    await client.approve(traceId)
    removeProposal(traceId)
    refresh()
    vscode.window.showInformationMessage(`✅ SAGE proposal approved (${traceId.slice(0, 8)}…)`)
  } catch (err: unknown) {
    vscode.window.showErrorMessage(`Approve failed: ${(err as Error).message}`)
  }
}

export async function rejectProposal(
  client: SageApiClient,
  traceId: string,
  refresh: () => void
): Promise<void> {
  const feedback = await vscode.window.showInputBox({
    prompt: 'Feedback for SAGE (what was wrong / what is the real cause?)',
    placeHolder: 'e.g. This is a known transient BLE disconnect, not a firmware bug.',
    ignoreFocusOut: true,
  })
  if (feedback === undefined) { return } // cancelled

  try {
    await client.reject(traceId, feedback || 'No feedback provided')
    removeProposal(traceId)
    refresh()
    vscode.window.showInformationMessage(`❌ SAGE proposal rejected — feedback recorded.`)
  } catch (err: unknown) {
    vscode.window.showErrorMessage(`Reject failed: ${(err as Error).message}`)
  }
}

// Called from tree view item click
export async function approveFromTree(
  client: SageApiClient,
  item: { proposal: { trace_id: string } },
  refresh: () => void
): Promise<void> {
  await approveProposal(client, item.proposal.trace_id, refresh)
}

export async function rejectFromTree(
  client: SageApiClient,
  item: { proposal: { trace_id: string } },
  refresh: () => void
): Promise<void> {
  await rejectProposal(client, item.proposal.trace_id, refresh)
}

// ─── Show proposal detail ─────────────────────────────────────────────────────

export function showProposalDetail(proposal: Proposal): void {
  printProposal(proposal)
  outputChannel().show()
}

// ─── Submit improvement request ───────────────────────────────────────────────

export async function submitImprovement(client: SageApiClient): Promise<void> {
  const title = await vscode.window.showInputBox({
    prompt: 'Improvement title',
    placeHolder: 'e.g. Add BLE reconnect context to analyst prompt',
    ignoreFocusOut: true,
  })
  if (!title?.trim()) { return }

  const description = await vscode.window.showInputBox({
    prompt: 'Describe the improvement',
    placeHolder: 'What should change and why?',
    ignoreFocusOut: true,
  })
  if (!description?.trim()) { return }

  const priority = await vscode.window.showQuickPick(
    ['low', 'medium', 'high', 'critical'],
    { placeHolder: 'Select priority' }
  )
  if (!priority) { return }

  try {
    await client.submitImprovement({
      module_id: 'vscode-extension',
      module_name: 'VS Code Extension',
      title,
      description,
      priority,
    })
    vscode.window.showInformationMessage(`💡 Improvement request submitted: "${title}"`)
  } catch (err: unknown) {
    vscode.window.showErrorMessage(`Submit failed: ${(err as Error).message}`)
  }
}

// ─── Switch solution ──────────────────────────────────────────────────────────

export async function switchSolution(client: SageApiClient): Promise<void> {
  let solutions: { id: string; name: string; domain: string }[] = []
  try {
    const { projects } = await client.listSolutions()
    solutions = projects
  } catch {
    vscode.window.showErrorMessage('Cannot reach SAGE backend.')
    return
  }

  const items = solutions.map(s => ({
    label: s.name,
    description: `${s.id} · ${s.domain}`,
    id: s.id,
  }))

  const pick = await vscode.window.showQuickPick(items, { placeHolder: 'Select SAGE solution' })
  if (!pick) { return }

  try {
    await client.switchSolution(pick.id)
    vscode.window.showInformationMessage(`SAGE solution switched to: ${pick.label}`)
  } catch (err: unknown) {
    vscode.window.showErrorMessage(`Switch failed: ${(err as Error).message}`)
  }
}

// ─── Backend proposal detail ──────────────────────────────────────────────────

const RISK_EMOJI: Record<string, string> = {
  DESTRUCTIVE:   '🔥',
  EXTERNAL:      '🌐',
  STATEFUL:      '💾',
  EPHEMERAL:     '⏱️',
  INFORMATIONAL: 'ℹ️',
}

export function showBackendProposalDetail(proposal: BackendProposal): void {
  const ch = outputChannel()
  ch.appendLine('')
  ch.appendLine('━'.repeat(70))
  ch.appendLine(`${RISK_EMOJI[proposal.risk_class] ?? '⚪'} PENDING APPROVAL — ${proposal.risk_class}${proposal.irreversible ? ' ⚠️ IRREVERSIBLE' : ''}`)
  ch.appendLine(`ACTION TYPE:  ${proposal.action_type}`)
  ch.appendLine(`DESCRIPTION:  ${proposal.description}`)
  ch.appendLine(`REQUESTED BY: ${proposal.requested_by ?? 'system'}`)
  ch.appendLine(`CREATED:      ${new Date(proposal.created_at).toLocaleString()}`)
  if (proposal.expires_at) {
    ch.appendLine(`EXPIRES:      ${new Date(proposal.expires_at).toLocaleString()}`)
  }
  ch.appendLine(`TRACE ID:     ${proposal.trace_id}`)
  ch.appendLine('')
  ch.appendLine('To approve: use the ✓ button in the SAGE Proposals tree')
  ch.appendLine('Or via web:  Dashboard → Pending Approvals')
  ch.appendLine('━'.repeat(70))
  ch.show(true)
}

export async function approveBackendProposal(
  client: SageApiClient,
  proposal: BackendProposal,
  refresh: () => void
): Promise<void> {
  const confirm = await vscode.window.showWarningMessage(
    `Approve: ${proposal.description}?`,
    { modal: true },
    'Approve'
  )
  if (confirm !== 'Approve') return
  try {
    await client.approve(proposal.trace_id)
    vscode.window.showInformationMessage(`✓ Approved: ${proposal.description.slice(0, 60)}`)
    refresh()
  } catch (err: unknown) {
    vscode.window.showErrorMessage(`Approval failed: ${(err as Error).message}`)
  }
}

export async function rejectBackendProposal(
  client: SageApiClient,
  proposal: BackendProposal,
  refresh: () => void
): Promise<void> {
  const note = await vscode.window.showInputBox({
    prompt: 'Reason for rejection (optional)',
    placeHolder: 'e.g. wrong environment, needs more context',
  })
  try {
    await client.reject(proposal.trace_id, note ?? '')
    vscode.window.showInformationMessage(`✗ Rejected: ${proposal.description.slice(0, 60)}`)
    refresh()
  } catch (err: unknown) {
    vscode.window.showErrorMessage(`Rejection failed: ${(err as Error).message}`)
  }
}

// ─── LLM status detail ────────────────────────────────────────────────────────

export async function showLLMStatus(client: SageApiClient): Promise<void> {
  try {
    const status = await client.llmStatus()
    const { model_info, session } = status
    const ch = outputChannel()
    ch.appendLine('')
    ch.appendLine('─── SAGE LLM Status ─────────────────────────────────────────')
    ch.appendLine(`Provider:    ${status.provider}`)
    ch.appendLine(`Model:       ${model_info.model}`)
    if (!model_info.unlimited) {
      const pct = Math.round((session.calls_today / model_info.daily_request_limit) * 100)
      ch.appendLine(`Today:       ${session.calls_today} / ${model_info.daily_request_limit} requests (${pct}%)`)
      ch.appendLine(`Remaining:   ${model_info.daily_request_limit - session.calls_today} requests`)
    } else {
      ch.appendLine(`Daily limit: unlimited (local model)`)
    }
    ch.appendLine(`Session:     ${session.calls_made} total calls · ${session.errors} errors`)
    ch.appendLine(`Est. tokens: ${session.estimated_tokens.toLocaleString()}`)
    ch.appendLine(`Started:     ${new Date(session.started_at).toLocaleString()}`)
    ch.appendLine('─────────────────────────────────────────────────────────────')
    ch.show(true)
  } catch (err: unknown) {
    vscode.window.showErrorMessage(`Cannot reach SAGE backend: ${(err as Error).message}`)
  }
}
