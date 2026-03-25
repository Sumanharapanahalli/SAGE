/**
 * SAGE Backend Manager
 * =====================
 * Spawns and manages the SAGE FastAPI backend as a child process.
 * Auto-detects .venv location (Linux/Mac vs Windows).
 */

import * as vscode from "vscode";
import * as cp from "child_process";
import * as path from "path";
import * as fs from "fs";

export class BackendManager {
  private process: cp.ChildProcess | undefined;
  private outputChannel: vscode.OutputChannel;
  private context: vscode.ExtensionContext;

  constructor(context: vscode.ExtensionContext) {
    this.context = context;
    this.outputChannel = vscode.window.createOutputChannel("SAGE Backend");
  }

  /**
   * Find the project root (directory containing src/interface/api.py).
   */
  private findProjectRoot(): string | undefined {
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders) {
      return undefined;
    }

    for (const folder of workspaceFolders) {
      const apiPath = path.join(
        folder.uri.fsPath,
        "src",
        "interface",
        "api.py"
      );
      if (fs.existsSync(apiPath)) {
        return folder.uri.fsPath;
      }
    }
    return workspaceFolders[0].uri.fsPath;
  }

  /**
   * Resolve Python executable — checks config, then .venv.
   */
  private findPython(projectRoot: string): string {
    const config = vscode.workspace.getConfiguration("sage");
    const configured = config.get<string>("pythonPath", "");
    if (configured && fs.existsSync(configured)) {
      return configured;
    }

    // Platform-aware .venv detection
    const isWindows = process.platform === "win32";
    const venvPython = isWindows
      ? path.join(projectRoot, ".venv", "Scripts", "python.exe")
      : path.join(projectRoot, ".venv", "bin", "python");

    if (fs.existsSync(venvPython)) {
      return venvPython;
    }

    return "python3";
  }

  /**
   * Start the SAGE backend.
   */
  async start(solution: string = "starter"): Promise<void> {
    if (this.process) {
      vscode.window.showWarningMessage(
        "SAGE backend is already running. Stop it first."
      );
      return;
    }

    const projectRoot = this.findProjectRoot();
    if (!projectRoot) {
      vscode.window.showErrorMessage(
        "Could not find SAGE project root (expected src/interface/api.py)"
      );
      return;
    }

    const python = this.findPython(projectRoot);
    const port = vscode.workspace
      .getConfiguration("sage")
      .get<number>("backendPort", 8000);

    this.outputChannel.show(true);
    this.outputChannel.appendLine(
      `Starting SAGE backend (solution: ${solution}, port: ${port})`
    );
    this.outputChannel.appendLine(`Python: ${python}`);
    this.outputChannel.appendLine(`Project root: ${projectRoot}`);

    const env = {
      ...process.env,
      PROJECT: solution,
      PYTHONPATH: projectRoot,
    };

    this.process = cp.spawn(
      python,
      [
        "-m",
        "uvicorn",
        "src.interface.api:app",
        "--host",
        "127.0.0.1",
        "--port",
        port.toString(),
        "--reload",
      ],
      {
        cwd: projectRoot,
        env,
        stdio: ["ignore", "pipe", "pipe"],
      }
    );

    this.process.stdout?.on("data", (data: Buffer) => {
      this.outputChannel.append(data.toString());
    });

    this.process.stderr?.on("data", (data: Buffer) => {
      this.outputChannel.append(data.toString());
    });

    this.process.on("close", (code) => {
      this.outputChannel.appendLine(`\nSAGE backend exited (code: ${code})`);
      this.process = undefined;
    });

    this.process.on("error", (err) => {
      this.outputChannel.appendLine(`\nFailed to start backend: ${err.message}`);
      vscode.window.showErrorMessage(
        `Failed to start SAGE backend: ${err.message}`
      );
      this.process = undefined;
    });

    // Wait briefly for startup
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }

  /**
   * Stop the SAGE backend.
   */
  stop(): void {
    if (this.process) {
      this.outputChannel.appendLine("Stopping SAGE backend...");
      this.process.kill("SIGTERM");
      // Force kill after 5 seconds if still running
      setTimeout(() => {
        if (this.process) {
          this.process.kill("SIGKILL");
          this.process = undefined;
        }
      }, 5000);
    }
  }

  /**
   * Check if the backend process is running.
   */
  isRunning(): boolean {
    return this.process !== undefined && this.process.exitCode === null;
  }
}
