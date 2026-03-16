import * as vscode from 'vscode'
import { SageApiClient, Proposal, BackendProposal } from './api'

// In-memory store of analyst proposals created this session
const _proposals = new Map<string, Proposal>()

export function storeProposal(p: Proposal): void {
  _proposals.set(p.trace_id, p)
}

export function removeProposal(traceId: string): void {
  _proposals.delete(traceId)
}

export function getProposal(traceId: string): Proposal | undefined {
  return _proposals.get(traceId)
}

// ─── Icons ────────────────────────────────────────────────────────────────────

const SEVERITY_ICON: Record<string, string> = {
  RED:     '$(error)',
  AMBER:   '$(warning)',
  GREEN:   '$(pass)',
  UNKNOWN: '$(question)',
}

const RISK_ICON: Record<string, string> = {
  INFORMATIONAL: '$(info)',
  EPHEMERAL:     '$(clock)',
  STATEFUL:      '$(database)',
  EXTERNAL:      '$(globe)',
  DESTRUCTIVE:   '$(flame)',
}

// ─── Tree items ───────────────────────────────────────────────────────────────

export class ProposalItem extends vscode.TreeItem {
  constructor(public readonly proposal: Proposal) {
    const icon = SEVERITY_ICON[proposal.severity] ?? '$(circle-outline)'
    super(
      `${icon} ${proposal.severity} — ${proposal.root_cause_hypothesis.slice(0, 60)}`,
      vscode.TreeItemCollapsibleState.None
    )
    this.contextValue = 'proposal'
    this.description = `trace: ${proposal.trace_id.slice(0, 8)}…`
    this.tooltip = new vscode.MarkdownString(
      `**Severity:** ${proposal.severity}\n\n` +
      `**Root cause:** ${proposal.root_cause_hypothesis}\n\n` +
      `**Action:** ${proposal.recommended_action}\n\n` +
      `**Trace ID:** \`${proposal.trace_id}\``
    )
    this.command = {
      command: 'sage.showProposalDetail',
      title: 'Show detail',
      arguments: [proposal],
    }
  }
}

export class BackendProposalItem extends vscode.TreeItem {
  constructor(public readonly backendProposal: BackendProposal) {
    const icon = RISK_ICON[backendProposal.risk_class] ?? '$(circle-outline)'
    const label = `${icon} ${backendProposal.risk_class} — ${backendProposal.description.slice(0, 55)}`
    super(label, vscode.TreeItemCollapsibleState.None)
    this.contextValue = 'backendProposal'
    this.description = `by ${backendProposal.requested_by ?? 'system'}`

    const expiryStr = backendProposal.expires_at
      ? `\n\n**Expires:** ${new Date(backendProposal.expires_at).toLocaleString()}`
      : ''
    const irreversibleStr = backendProposal.irreversible ? '\n\n⚠️ **IRREVERSIBLE**' : ''
    this.tooltip = new vscode.MarkdownString(
      `**Action:** ${backendProposal.action_type}\n\n` +
      `**Description:** ${backendProposal.description}` +
      expiryStr + irreversibleStr + `\n\n**Trace ID:** \`${backendProposal.trace_id}\``
    )
    this.command = {
      command: 'sage.showBackendProposalDetail',
      title: 'Show detail',
      arguments: [backendProposal],
    }
  }
}

class SectionItem extends vscode.TreeItem {
  constructor(label: string, public readonly children: vscode.TreeItem[]) {
    super(label, vscode.TreeItemCollapsibleState.Expanded)
    this.contextValue = 'section'
  }
}

// ─── Provider ─────────────────────────────────────────────────────────────────

export class ProposalsProvider implements vscode.TreeDataProvider<vscode.TreeItem> {
  private _onDidChangeTreeData = new vscode.EventEmitter<vscode.TreeItem | undefined>()
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event

  constructor(private client: SageApiClient) {}

  refresh(): void {
    this._onDidChangeTreeData.fire(undefined)
  }

  getTreeItem(element: vscode.TreeItem): vscode.TreeItem {
    return element
  }

  async getChildren(element?: vscode.TreeItem): Promise<vscode.TreeItem[]> {
    if (element instanceof SectionItem) {
      return element.children
    }

    const items: vscode.TreeItem[] = []

    // ── 1. Backend pending approvals (from ProposalStore) ─────────────────────
    try {
      const { proposals } = await this.client.pendingProposals()
      if (proposals.length > 0) {
        const sorted = [...proposals].sort((a, b) => {
          const order: Record<string, number> = {
            DESTRUCTIVE: 0, EXTERNAL: 1, STATEFUL: 2, EPHEMERAL: 3, INFORMATIONAL: 4
          }
          return (order[a.risk_class] ?? 5) - (order[b.risk_class] ?? 5)
        })
        const proposalItems = sorted.map(p => new BackendProposalItem(p))
        items.push(new SectionItem(`Pending Approvals (${proposals.length})`, proposalItems))
      }
    } catch {
      // backend offline — skip
    }

    // ── 2. Analyst proposals created this session ──────────────────────────────
    const sessionProposals = Array.from(_proposals.values())
    if (sessionProposals.length > 0) {
      const sorted = [...sessionProposals].sort((a, b) => {
        const order: Record<string, number> = { RED: 0, AMBER: 1, GREEN: 2, UNKNOWN: 3 }
        return (order[a.severity] ?? 3) - (order[b.severity] ?? 3)
      })
      items.push(new SectionItem(`Analysis Proposals (${sessionProposals.length})`, sorted.map(p => new ProposalItem(p))))
    }

    // ── 3. Pending improvement requests ───────────────────────────────────────
    try {
      const { requests } = await this.client.pendingImprovements()
      if (requests.length > 0) {
        const improvementItems = requests.map(r => {
          const item = new vscode.TreeItem(`$(lightbulb) ${r.title}`)
          item.description = `${r.module_name} · ${r.priority}`
          item.tooltip = r.description
          item.contextValue = 'improvement'
          return item
        })
        items.push(new SectionItem(`Improvement Requests (${requests.length})`, improvementItems))
      }
    } catch {
      // backend offline — skip
    }

    if (items.length === 0) {
      const empty = new vscode.TreeItem('No pending items')
      empty.description = 'Run SAGE: Analyze Selection to create a proposal'
      empty.iconPath = new vscode.ThemeIcon('check')
      items.push(empty)
    }

    return items
  }
}
