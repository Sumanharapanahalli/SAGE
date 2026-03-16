import * as vscode from 'vscode'
import { SageApiClient, Proposal } from './api'

// In-memory store of proposals created this session (trace_id → proposal)
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

// ─── Tree item ────────────────────────────────────────────────────────────────

const SEVERITY_ICON: Record<string, string> = {
  RED:     '$(error)',
  AMBER:   '$(warning)',
  GREEN:   '$(pass)',
  UNKNOWN: '$(question)',
}

class ProposalItem extends vscode.TreeItem {
  constructor(public readonly proposal: Proposal) {
    super(
      `${SEVERITY_ICON[proposal.severity] ?? '$(circle-outline)'} ${proposal.severity} — ${proposal.root_cause_hypothesis.slice(0, 60)}`,
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

    // Root — build sections
    const items: vscode.TreeItem[] = []

    // ── Pending proposals (in-memory, created this session)
    const proposals = Array.from(_proposals.values())
    if (proposals.length > 0) {
      const sorted = [...proposals].sort((a, b) => {
        const order: Record<string, number> = { RED: 0, AMBER: 1, GREEN: 2, UNKNOWN: 3 }
        return (order[a.severity] ?? 3) - (order[b.severity] ?? 3)
      })
      items.push(new SectionItem(`Pending Proposals (${proposals.length})`, sorted.map(p => new ProposalItem(p))))
    } else {
      const empty = new vscode.TreeItem('No pending proposals')
      empty.description = 'Run SAGE: Analyze Selection to create one'
      empty.iconPath = new vscode.ThemeIcon('check')
      items.push(empty)
    }

    // ── Pending improvement requests from backend
    try {
      const { requests } = await this.client.pendingImprovements()
      if (requests.length > 0) {
        const improvementItems = requests.map(r => {
          const item = new vscode.TreeItem(`${r.title} [${r.priority}]`)
          item.description = r.module_name
          item.iconPath = new vscode.ThemeIcon('lightbulb')
          item.tooltip = r.description
          return item
        })
        items.push(new SectionItem(`Improvement Requests (${requests.length})`, improvementItems))
      }
    } catch {
      // backend offline — skip silently
    }

    return items
  }
}
