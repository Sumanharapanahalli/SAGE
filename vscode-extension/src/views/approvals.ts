/**
 * SAGE Approvals Tree View
 * =========================
 * Shows pending proposals with risk class, type, and approve/reject actions.
 */

import * as vscode from "vscode";
import { SageApiClient, Proposal } from "../api";

export class ApprovalsProvider
  implements vscode.TreeDataProvider<ApprovalItem>
{
  private _onDidChangeTreeData = new vscode.EventEmitter<
    ApprovalItem | undefined
  >();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  constructor(private api: SageApiClient) {}

  refresh(): void {
    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: ApprovalItem): vscode.TreeItem {
    return element;
  }

  async getChildren(): Promise<ApprovalItem[]> {
    try {
      const proposals = await this.api.getPendingApprovals();
      if (proposals.length === 0) {
        return [new ApprovalItem("No pending approvals", "", "", "check")];
      }
      return proposals.map((p) => {
        // Backend uses action_type; fall back to proposal_type for compat
        const proposalType = p.action_type || p.proposal_type || "unknown";
        const riskClass = p.risk_class || "INFORMATIONAL";
        const item = new ApprovalItem(
          proposalType,
          riskClass,
          p.trace_id,
          riskIcon(riskClass)
        );
        item.description = `${riskClass} — ${timeAgo(p.created_at)}`;
        item.tooltip = new vscode.MarkdownString(
          `**${proposalType}**\n\n` +
            `Risk: ${riskClass}\n\n` +
            `ID: \`${p.trace_id}\`\n\n` +
            `Created: ${p.created_at}`
        );
        return item;
      });
    } catch {
      return [new ApprovalItem("Cannot reach backend", "", "", "warning")];
    }
  }
}

class ApprovalItem extends vscode.TreeItem {
  constructor(
    label: string,
    public readonly riskClass: string,
    public readonly traceId: string,
    icon: string
  ) {
    super(label, vscode.TreeItemCollapsibleState.None);
    this.iconPath = new vscode.ThemeIcon(icon);
    if (traceId) {
      this.contextValue = "approval";
    }
  }
}

function riskIcon(risk: string): string {
  switch (risk?.toUpperCase()) {
    case "DESTRUCTIVE":
      return "flame";
    case "EXTERNAL":
      return "globe";
    case "STATEFUL":
      return "database";
    case "EPHEMERAL":
      return "clock";
    case "INFORMATIONAL":
      return "info";
    default:
      return "question";
  }
}

function timeAgo(dateStr: string): string {
  try {
    const now = Date.now();
    const then = new Date(dateStr).getTime();
    const diffMin = Math.floor((now - then) / 60000);
    if (diffMin < 1) {
      return "just now";
    }
    if (diffMin < 60) {
      return `${diffMin}m ago`;
    }
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) {
      return `${diffHr}h ago`;
    }
    return `${Math.floor(diffHr / 24)}d ago`;
  } catch {
    return "";
  }
}
