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
exports.analyzeSelection = analyzeSelection;
exports.analyzeFile = analyzeFile;
exports.reviewDiff = reviewDiff;
exports.approveProposal = approveProposal;
exports.rejectProposal = rejectProposal;
exports.approveFromTree = approveFromTree;
exports.rejectFromTree = rejectFromTree;
exports.showProposalDetail = showProposalDetail;
exports.submitImprovement = submitImprovement;
exports.switchSolution = switchSolution;
exports.showLLMStatus = showLLMStatus;
const vscode = __importStar(require("vscode"));
const cp = __importStar(require("child_process"));
const util = __importStar(require("util"));
const proposalsProvider_1 = require("./proposalsProvider");
const exec = util.promisify(cp.exec);
// Shared output channel for all SAGE results
let _outputChannel;
function outputChannel() {
    if (!_outputChannel) {
        _outputChannel = vscode.window.createOutputChannel('SAGE[ai]');
    }
    return _outputChannel;
}
function severityIcon(sev) {
    return { RED: '🔴', AMBER: '🟡', GREEN: '🟢' }[sev] ?? '⚪';
}
function printProposal(proposal) {
    const ch = outputChannel();
    ch.appendLine('');
    ch.appendLine('━'.repeat(70));
    ch.appendLine(`${severityIcon(proposal.severity)} SEVERITY: ${proposal.severity}`);
    ch.appendLine(`TRACE ID:  ${proposal.trace_id}`);
    ch.appendLine('');
    ch.appendLine('ROOT CAUSE');
    ch.appendLine('  ' + proposal.root_cause_hypothesis);
    ch.appendLine('');
    ch.appendLine('RECOMMENDED ACTION');
    ch.appendLine('  ' + proposal.recommended_action);
    if (proposal.confidence) {
        ch.appendLine('');
        ch.appendLine(`CONFIDENCE: ${proposal.confidence}`);
    }
    ch.appendLine('━'.repeat(70));
    ch.show(true); // show without stealing focus
}
// ─── Analyze selection / file ─────────────────────────────────────────────────
async function analyzeSelection(client, refresh) {
    const editor = vscode.window.activeTextEditor;
    let text = editor?.document.getText(editor.selection);
    if (!text?.trim()) {
        text = await vscode.window.showInputBox({
            prompt: 'Paste log entry or error text to analyze',
            placeHolder: 'e.g. ERROR: NAND flash bad block at 0x1A000000',
            ignoreFocusOut: true,
        });
    }
    if (!text?.trim()) {
        return;
    }
    await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: 'SAGE: Analyzing…', cancellable: false }, async () => {
        try {
            const proposal = await client.analyze(text);
            (0, proposalsProvider_1.storeProposal)(proposal);
            refresh();
            printProposal(proposal);
            // Notification with quick actions
            const sev = proposal.severity;
            const icon = severityIcon(sev);
            const msg = `${icon} SAGE ${sev}: ${proposal.root_cause_hypothesis.slice(0, 80)}`;
            const notifyFn = sev === 'RED'
                ? vscode.window.showErrorMessage
                : sev === 'AMBER'
                    ? vscode.window.showWarningMessage
                    : vscode.window.showInformationMessage;
            const choice = await notifyFn(msg, 'Approve', 'Reject', 'Show Detail');
            if (choice === 'Approve') {
                await approveProposal(client, proposal.trace_id, refresh);
            }
            else if (choice === 'Reject') {
                await rejectProposal(client, proposal.trace_id, refresh);
            }
            else if (choice === 'Show Detail') {
                printProposal(proposal);
                outputChannel().show();
            }
        }
        catch (err) {
            vscode.window.showErrorMessage(`SAGE analyze failed: ${err.message}`);
        }
    });
}
async function analyzeFile(client, refresh) {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showWarningMessage('No active file.');
        return;
    }
    const text = editor.document.getText();
    if (!text.trim()) {
        vscode.window.showWarningMessage('File is empty.');
        return;
    }
    // Use only the first 8000 chars to stay within sensible prompt size
    const truncated = text.length > 8000
        ? text.slice(0, 8000) + '\n… (truncated)'
        : text;
    await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: `SAGE: Analyzing ${editor.document.fileName.split(/[\\/]/).pop()}…`, cancellable: false }, async () => {
        try {
            const proposal = await client.analyze(truncated);
            (0, proposalsProvider_1.storeProposal)(proposal);
            refresh();
            printProposal(proposal);
            vscode.window.showInformationMessage(`${severityIcon(proposal.severity)} SAGE: ${proposal.severity} — see SAGE[ai] output panel`);
        }
        catch (err) {
            vscode.window.showErrorMessage(`SAGE analyze failed: ${err.message}`);
        }
    });
}
// ─── Review current git diff ──────────────────────────────────────────────────
async function reviewDiff(client, refresh) {
    const folders = vscode.workspace.workspaceFolders;
    if (!folders?.length) {
        vscode.window.showWarningMessage('No workspace folder open.');
        return;
    }
    const cwd = folders[0].uri.fsPath;
    let diff;
    let branch = 'unknown';
    try {
        const { stdout: branchOut } = await exec('git rev-parse --abbrev-ref HEAD', { cwd });
        branch = branchOut.trim();
        const { stdout: diffOut } = await exec('git diff HEAD', { cwd });
        diff = diffOut.trim();
    }
    catch {
        vscode.window.showErrorMessage('Could not run git diff — is this a git repository?');
        return;
    }
    if (!diff) {
        vscode.window.showInformationMessage('No uncommitted changes to review.');
        return;
    }
    // Cap diff size
    const payload = diff.length > 12000 ? diff.slice(0, 12000) + '\n… (truncated)' : diff;
    const context = `Git diff on branch: ${branch}\n\n${payload}`;
    await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: `SAGE: Reviewing diff on ${branch}…`, cancellable: false }, async () => {
        try {
            const proposal = await client.analyze(context);
            (0, proposalsProvider_1.storeProposal)(proposal);
            refresh();
            printProposal(proposal);
            vscode.window.showInformationMessage(`${severityIcon(proposal.severity)} SAGE diff review: ${proposal.severity} — see output panel`);
        }
        catch (err) {
            vscode.window.showErrorMessage(`SAGE review failed: ${err.message}`);
        }
    });
}
// ─── Approve / Reject ─────────────────────────────────────────────────────────
async function approveProposal(client, traceId, refresh) {
    try {
        await client.approve(traceId);
        (0, proposalsProvider_1.removeProposal)(traceId);
        refresh();
        vscode.window.showInformationMessage(`✅ SAGE proposal approved (${traceId.slice(0, 8)}…)`);
    }
    catch (err) {
        vscode.window.showErrorMessage(`Approve failed: ${err.message}`);
    }
}
async function rejectProposal(client, traceId, refresh) {
    const feedback = await vscode.window.showInputBox({
        prompt: 'Feedback for SAGE (what was wrong / what is the real cause?)',
        placeHolder: 'e.g. This is a known transient BLE disconnect, not a firmware bug.',
        ignoreFocusOut: true,
    });
    if (feedback === undefined) {
        return;
    } // cancelled
    try {
        await client.reject(traceId, feedback || 'No feedback provided');
        (0, proposalsProvider_1.removeProposal)(traceId);
        refresh();
        vscode.window.showInformationMessage(`❌ SAGE proposal rejected — feedback recorded.`);
    }
    catch (err) {
        vscode.window.showErrorMessage(`Reject failed: ${err.message}`);
    }
}
// Called from tree view item click
async function approveFromTree(client, item, refresh) {
    await approveProposal(client, item.proposal.trace_id, refresh);
}
async function rejectFromTree(client, item, refresh) {
    await rejectProposal(client, item.proposal.trace_id, refresh);
}
// ─── Show proposal detail ─────────────────────────────────────────────────────
function showProposalDetail(proposal) {
    printProposal(proposal);
    outputChannel().show();
}
// ─── Submit improvement request ───────────────────────────────────────────────
async function submitImprovement(client) {
    const title = await vscode.window.showInputBox({
        prompt: 'Improvement title',
        placeHolder: 'e.g. Add BLE reconnect context to analyst prompt',
        ignoreFocusOut: true,
    });
    if (!title?.trim()) {
        return;
    }
    const description = await vscode.window.showInputBox({
        prompt: 'Describe the improvement',
        placeHolder: 'What should change and why?',
        ignoreFocusOut: true,
    });
    if (!description?.trim()) {
        return;
    }
    const priority = await vscode.window.showQuickPick(['low', 'medium', 'high', 'critical'], { placeHolder: 'Select priority' });
    if (!priority) {
        return;
    }
    try {
        await client.submitImprovement({
            module_id: 'vscode-extension',
            module_name: 'VS Code Extension',
            title,
            description,
            priority,
        });
        vscode.window.showInformationMessage(`💡 Improvement request submitted: "${title}"`);
    }
    catch (err) {
        vscode.window.showErrorMessage(`Submit failed: ${err.message}`);
    }
}
// ─── Switch solution ──────────────────────────────────────────────────────────
async function switchSolution(client) {
    let solutions = [];
    try {
        const { projects } = await client.listSolutions();
        solutions = projects;
    }
    catch {
        vscode.window.showErrorMessage('Cannot reach SAGE backend.');
        return;
    }
    const items = solutions.map(s => ({
        label: s.name,
        description: `${s.id} · ${s.domain}`,
        id: s.id,
    }));
    const pick = await vscode.window.showQuickPick(items, { placeHolder: 'Select SAGE solution' });
    if (!pick) {
        return;
    }
    try {
        await client.switchSolution(pick.id);
        vscode.window.showInformationMessage(`SAGE solution switched to: ${pick.label}`);
    }
    catch (err) {
        vscode.window.showErrorMessage(`Switch failed: ${err.message}`);
    }
}
// ─── LLM status detail ────────────────────────────────────────────────────────
async function showLLMStatus(client) {
    try {
        const status = await client.llmStatus();
        const { model_info, session } = status;
        const ch = outputChannel();
        ch.appendLine('');
        ch.appendLine('─── SAGE LLM Status ─────────────────────────────────────────');
        ch.appendLine(`Provider:    ${status.provider}`);
        ch.appendLine(`Model:       ${model_info.model}`);
        if (!model_info.unlimited) {
            const pct = Math.round((session.calls_today / model_info.daily_request_limit) * 100);
            ch.appendLine(`Today:       ${session.calls_today} / ${model_info.daily_request_limit} requests (${pct}%)`);
            ch.appendLine(`Remaining:   ${model_info.daily_request_limit - session.calls_today} requests`);
        }
        else {
            ch.appendLine(`Daily limit: unlimited (local model)`);
        }
        ch.appendLine(`Session:     ${session.calls_made} total calls · ${session.errors} errors`);
        ch.appendLine(`Est. tokens: ${session.estimated_tokens.toLocaleString()}`);
        ch.appendLine(`Started:     ${new Date(session.started_at).toLocaleString()}`);
        ch.appendLine('─────────────────────────────────────────────────────────────');
        ch.show(true);
    }
    catch (err) {
        vscode.window.showErrorMessage(`Cannot reach SAGE backend: ${err.message}`);
    }
}
//# sourceMappingURL=commands.js.map