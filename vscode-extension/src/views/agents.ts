/**
 * SAGE Agents Tree View
 * ======================
 * Shows registered agent roles and their status.
 */

import * as vscode from "vscode";
import { SageApiClient } from "../api";

export class AgentsProvider implements vscode.TreeDataProvider<AgentItem> {
  private _onDidChangeTreeData = new vscode.EventEmitter<
    AgentItem | undefined
  >();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  constructor(private api: SageApiClient) {}

  refresh(): void {
    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: AgentItem): vscode.TreeItem {
    return element;
  }

  async getChildren(): Promise<AgentItem[]> {
    try {
      const agents = await this.api.getAgents();
      if (agents.length === 0) {
        return [new AgentItem("No agents loaded", "idle", "$(circle-slash)")];
      }
      return agents.map(
        (a) =>
          new AgentItem(
            a.role,
            a.status || "idle",
            a.status === "active" ? "$(play)" : "$(circle-large-outline)"
          )
      );
    } catch {
      return [new AgentItem("Cannot reach backend", "", "$(warning)")];
    }
  }
}

class AgentItem extends vscode.TreeItem {
  constructor(role: string, status: string, icon: string) {
    super(role, vscode.TreeItemCollapsibleState.None);
    this.description = status;
    this.iconPath = new vscode.ThemeIcon(
      icon.replace("$(", "").replace(")", "")
    );
    this.tooltip = `Agent: ${role} (${status})`;
  }
}
