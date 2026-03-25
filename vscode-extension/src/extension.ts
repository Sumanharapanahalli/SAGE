/**
 * SAGE[ai] VS Code Extension — Main Entry Point
 * ================================================
 * Manages the SAGE backend lifecycle and provides an embedded dashboard
 * via VS Code webview panels. No external ports needed for the UI —
 * works behind corporate firewalls.
 *
 * Architecture:
 *   Extension activates → detects .venv + project.yaml
 *   → starts backend as child process (localhost:PORT)
 *   → webview panels communicate with backend internally
 *   → sidebar tree views show live status, approvals, agents
 */

import * as vscode from "vscode";
import { BackendManager } from "./backend";
import { SageApiClient } from "./api";
import { StatusProvider } from "./views/status";
import { ApprovalsProvider } from "./views/approvals";
import { AgentsProvider } from "./views/agents";
import { SolutionsProvider } from "./views/solutions";
import { DashboardPanel } from "./panels/dashboard";

let backend: BackendManager;
let api: SageApiClient;
let statusBar: vscode.StatusBarItem;
let pollTimer: NodeJS.Timeout | undefined;

export function activate(context: vscode.ExtensionContext) {
  const config = vscode.workspace.getConfiguration("sage");
  const port = config.get<number>("backendPort", 8000);

  backend = new BackendManager(context);
  api = new SageApiClient(`http://localhost:${port}`);

  // --- Status bar ---
  statusBar = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Left,
    100
  );
  statusBar.command = "sage.openDashboard";
  statusBar.text = "$(circle-slash) SAGE";
  statusBar.tooltip = "SAGE[ai] — Click to open dashboard";
  statusBar.show();
  context.subscriptions.push(statusBar);

  // --- Tree view providers ---
  const statusProvider = new StatusProvider(api);
  const approvalsProvider = new ApprovalsProvider(api);
  const agentsProvider = new AgentsProvider(api);
  const solutionsProvider = new SolutionsProvider(api);

  vscode.window.registerTreeDataProvider("sage.status", statusProvider);
  vscode.window.registerTreeDataProvider("sage.approvals", approvalsProvider);
  vscode.window.registerTreeDataProvider("sage.agents", agentsProvider);
  vscode.window.registerTreeDataProvider("sage.solutions", solutionsProvider);

  // --- Commands ---
  context.subscriptions.push(
    vscode.commands.registerCommand("sage.startBackend", async () => {
      const solution = config.get<string>("defaultSolution", "starter");
      await backend.start(solution);
      updateStatusBar(true);
      startPolling(statusProvider, approvalsProvider, agentsProvider);
      vscode.window.showInformationMessage(
        `SAGE backend started (solution: ${solution})`
      );
    }),

    vscode.commands.registerCommand("sage.stopBackend", async () => {
      backend.stop();
      updateStatusBar(false);
      stopPolling();
      vscode.window.showInformationMessage("SAGE backend stopped");
    }),

    vscode.commands.registerCommand("sage.openDashboard", () => {
      DashboardPanel.createOrShow(context, api);
    }),

    vscode.commands.registerCommand("sage.openApprovals", () => {
      DashboardPanel.createOrShow(context, api, "/approvals");
    }),

    vscode.commands.registerCommand("sage.openQueue", () => {
      DashboardPanel.createOrShow(context, api, "/queue");
    }),

    vscode.commands.registerCommand("sage.switchSolution", async () => {
      const solutions = await api.getSolutions();
      if (!solutions.length) {
        vscode.window.showWarningMessage("No solutions found");
        return;
      }
      const picked = await vscode.window.showQuickPick(solutions, {
        placeHolder: "Select a solution to switch to",
      });
      if (picked) {
        await api.switchSolution(picked);
        solutionsProvider.refresh();
        statusProvider.refresh();
        vscode.window.showInformationMessage(`Switched to solution: ${picked}`);
      }
    }),

    vscode.commands.registerCommand("sage.switchLLM", async () => {
      const providers = [
        "gemini",
        "claude-code",
        "ollama",
        "local",
        "claude",
        "generic-cli",
      ];
      const picked = await vscode.window.showQuickPick(providers, {
        placeHolder: "Select LLM provider",
      });
      if (picked) {
        await api.switchLLM(picked);
        statusProvider.refresh();
        vscode.window.showInformationMessage(`LLM switched to: ${picked}`);
      }
    }),

    vscode.commands.registerCommand("sage.refreshStatus", () => {
      statusProvider.refresh();
      approvalsProvider.refresh();
      agentsProvider.refresh();
      solutionsProvider.refresh();
    })
  );

  // --- Auto-start if configured ---
  if (config.get<boolean>("autoStart", false)) {
    vscode.commands.executeCommand("sage.startBackend");
  }

  // --- Check if backend is already running ---
  api
    .health()
    .then((ok) => {
      if (ok) {
        updateStatusBar(true);
        startPolling(statusProvider, approvalsProvider, agentsProvider);
      }
    })
    .catch(() => {});
}

export function deactivate() {
  stopPolling();
  backend?.stop();
}

function updateStatusBar(running: boolean) {
  if (running) {
    statusBar.text = "$(check) SAGE";
    statusBar.backgroundColor = undefined;
    statusBar.tooltip = "SAGE[ai] running — Click to open dashboard";
  } else {
    statusBar.text = "$(circle-slash) SAGE";
    statusBar.tooltip = "SAGE[ai] stopped — Click to start";
  }
}

function startPolling(
  status: StatusProvider,
  approvals: ApprovalsProvider,
  agents: AgentsProvider
) {
  stopPolling();
  const interval = vscode.workspace
    .getConfiguration("sage")
    .get<number>("pollIntervalMs", 10000);
  pollTimer = setInterval(() => {
    status.refresh();
    approvals.refresh();
    agents.refresh();
  }, interval);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = undefined;
  }
}
