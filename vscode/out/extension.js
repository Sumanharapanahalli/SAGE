"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const api_1 = require("./api");
const statusBar_1 = require("./statusBar");
const proposalsProvider_1 = require("./proposalsProvider");
const dashboardPanel_1 = require("./dashboardPanel");
const cmds = __importStar(require("./commands"));
function activate(context) {
    // ── Config ────────────────────────────────────────────────────────────────
    const cfg = () => vscode.workspace.getConfiguration('sage');
    const getApiUrl = () => cfg().get('apiUrl', 'http://localhost:8000');
    const getPollInterval = () => cfg().get('pollInterval', 15);
    // ── Client + UI ────────────────────────────────────────────────────────────
    let client = new api_1.SageApiClient(getApiUrl());
    const statusBar = new statusBar_1.SageStatusBar(client);
    const provider = new proposalsProvider_1.ProposalsProvider(client);
    const refresh = () => { provider.refresh(); statusBar.refresh(); };
    statusBar.start(getPollInterval());
    // ── Tree view ──────────────────────────────────────────────────────────────
    const treeView = vscode.window.createTreeView('sageProposals', {
        treeDataProvider: provider,
        showCollapseAll: false,
    });
    // ── Rebuild client when settings change ───────────────────────────────────
    context.subscriptions.push(vscode.workspace.onDidChangeConfiguration(e => {
        if (e.affectsConfiguration('sage')) {
            statusBar.stop();
            client = new api_1.SageApiClient(getApiUrl());
            statusBar.start(getPollInterval());
            refresh();
        }
    }));
    // ── Register commands ──────────────────────────────────────────────────────
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const reg = (cmd, fn) => context.subscriptions.push(vscode.commands.registerCommand(cmd, fn));
    reg('sage.analyzeSelection', () => cmds.analyzeSelection(client, refresh));
    reg('sage.analyzeFile', () => cmds.analyzeFile(client, refresh));
    reg('sage.reviewDiff', () => cmds.reviewDiff(client, refresh));
    reg('sage.showDashboard', () => dashboardPanel_1.DashboardPanel.show(client, context.extensionUri));
    reg('sage.refreshProposals', () => refresh());
    reg('sage.approveProposal', (item) => {
        if (item?.proposal?.trace_id) {
            cmds.approveFromTree(client, item, refresh);
        }
    });
    reg('sage.rejectProposal', (item) => {
        if (item?.proposal?.trace_id) {
            cmds.rejectFromTree(client, item, refresh);
        }
    });
    reg('sage.showProposalDetail', (proposal) => cmds.showProposalDetail(proposal));
    reg('sage.submitImprovement', () => cmds.submitImprovement(client));
    reg('sage.switchSolution', () => cmds.switchSolution(client));
    reg('sage.showLLMStatus', () => cmds.showLLMStatus(client));
    // ── Disposables ────────────────────────────────────────────────────────────
    context.subscriptions.push(statusBar, treeView);
    // ── Startup notification ───────────────────────────────────────────────────
    client.health().then(h => {
        vscode.window.setStatusBarMessage(`$(shield) SAGE connected — ${h.project.name}`, 5000);
    }).catch(() => {
        // Silently skip if backend isn't running yet
    });
}
function deactivate() {
    // VS Code disposes context.subscriptions automatically
}
//# sourceMappingURL=extension.js.map