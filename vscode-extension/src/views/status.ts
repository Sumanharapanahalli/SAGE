/**
 * SAGE Status Tree View
 * ======================
 * Shows backend health, active solution, LLM provider, and key stats.
 */

import * as vscode from "vscode";
import { SageApiClient } from "../api";

export class StatusProvider implements vscode.TreeDataProvider<StatusItem> {
  private _onDidChangeTreeData = new vscode.EventEmitter<
    StatusItem | undefined
  >();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  constructor(private api: SageApiClient) {}

  refresh(): void {
    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: StatusItem): vscode.TreeItem {
    return element;
  }

  async getChildren(): Promise<StatusItem[]> {
    try {
      const health = await this.api.getStatus();
      const isOk = health.status === "ok" || health.status === "healthy";
      const items: StatusItem[] = [
        new StatusItem(
          "Backend",
          isOk ? "Running" : "Stopped",
          isOk ? "check" : "error"
        ),
      ];

      const projectName = this.api.getProjectName(health);
      if (projectName) {
        items.push(new StatusItem("Solution", projectName, "folder"));
      }

      const provider = this.api.getProviderName(health);
      if (provider) {
        items.push(new StatusItem("LLM Provider", provider, "hubot"));
      }

      if (health.version) {
        items.push(new StatusItem("Version", health.version, "tag"));
      }

      // Fetch approval count
      const approvals = await this.api.getPendingApprovals();
      if (approvals.length > 0) {
        items.push(
          new StatusItem(
            "Pending Approvals",
            `${approvals.length}`,
            "bell-dot"
          )
        );
      }

      return items;
    } catch {
      return [new StatusItem("Backend", "Not reachable", "circle-slash")];
    }
  }
}

class StatusItem extends vscode.TreeItem {
  constructor(label: string, value: string, icon: string) {
    super(`${label}: ${value}`, vscode.TreeItemCollapsibleState.None);
    this.iconPath = new vscode.ThemeIcon(icon);
    this.tooltip = `${label}: ${value}`;
  }
}
