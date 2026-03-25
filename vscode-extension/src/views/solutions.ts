/**
 * SAGE Solutions Tree View
 * =========================
 * Lists available solutions and allows switching.
 */

import * as vscode from "vscode";
import { SageApiClient } from "../api";

export class SolutionsProvider
  implements vscode.TreeDataProvider<SolutionItem>
{
  private _onDidChangeTreeData = new vscode.EventEmitter<
    SolutionItem | undefined
  >();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  constructor(private api: SageApiClient) {}

  refresh(): void {
    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: SolutionItem): vscode.TreeItem {
    return element;
  }

  async getChildren(): Promise<SolutionItem[]> {
    try {
      const solutions = await this.api.getSolutions();
      if (solutions.length === 0) {
        return [new SolutionItem("No solutions found", false)];
      }

      // Get current solution from health
      let current = "";
      try {
        const health = await this.api.getStatus();
        current = health.project || "";
      } catch {}

      return solutions.map((s) => new SolutionItem(s, s === current));
    } catch {
      return [new SolutionItem("Cannot reach backend", false)];
    }
  }
}

class SolutionItem extends vscode.TreeItem {
  constructor(name: string, isActive: boolean) {
    super(name, vscode.TreeItemCollapsibleState.None);
    this.iconPath = new vscode.ThemeIcon(
      isActive ? "folder-opened" : "folder"
    );
    this.description = isActive ? "(active)" : "";
    this.tooltip = isActive ? `${name} — currently active` : `Switch to ${name}`;

    if (!isActive && name !== "Cannot reach backend" && name !== "No solutions found") {
      this.command = {
        command: "sage.switchSolution",
        title: "Switch Solution",
      };
    }
  }
}
