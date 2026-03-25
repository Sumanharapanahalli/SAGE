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
      const items: StatusItem[] = [
        new StatusItem(
          "Backend",
          health.status === "ok" || health.status === "healthy"
            ? "Running"
            : "Stopped",
          health.status === "ok" || health.status === "healthy"
            ? "$(check)"
            : "$(error)"
        ),
      ];

      if (health.project) {
        items.push(new StatusItem("Solution", health.project, "$(folder)"));
      }

      if (health.provider) {
        items.push(new StatusItem("LLM Provider", health.provider, "$(hubot)"));
      }

      if (health.endpoints) {
        items.push(
          new StatusItem(
            "Endpoints",
            `${health.endpoints}`,
            "$(symbol-method)"
          )
        );
      }

      // Fetch approval count
      const approvals = await this.api.getPendingApprovals();
      if (approvals.length > 0) {
        items.push(
          new StatusItem(
            "Pending Approvals",
            `${approvals.length}`,
            "$(bell-dot)"
          )
        );
      }

      return items;
    } catch {
      return [new StatusItem("Backend", "Not reachable", "$(circle-slash)")];
    }
  }
}

class StatusItem extends vscode.TreeItem {
  constructor(label: string, value: string, icon: string) {
    super(`${label}: ${value}`, vscode.TreeItemCollapsibleState.None);
    this.iconPath = new vscode.ThemeIcon(icon.replace("$(", "").replace(")", ""));
    this.tooltip = `${label}: ${value}`;
  }
}
