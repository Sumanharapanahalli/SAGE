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
exports.SageStatusBar = void 0;
const vscode = __importStar(require("vscode"));
class SageStatusBar {
    constructor(client) {
        this.pendingCount = 0;
        this.client = client;
        this.item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
        this.item.command = 'sage.showLLMStatus';
        this.item.tooltip = 'SAGE[ai] — Smart Agentic-Guided Empowerment\nClick for LLM quota details';
        this.item.show();
    }
    start(intervalSecs) {
        this.refresh();
        const ms = Math.max(5, intervalSecs) * 1000;
        this.timer = setInterval(() => this.refresh(), ms);
    }
    stop() {
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = undefined;
        }
    }
    getPendingCount() {
        return this.pendingCount;
    }
    async refresh() {
        try {
            const [llm, improvements] = await Promise.all([
                this.client.llmStatus(),
                this.client.pendingImprovements(),
            ]);
            this.pendingCount = improvements.count;
            const { calls_today, errors } = llm.session;
            const { daily_request_limit, unlimited, model } = llm.model_info;
            let quotaText;
            if (unlimited) {
                quotaText = `local`;
            }
            else {
                const pct = Math.round((calls_today / daily_request_limit) * 100);
                quotaText = `${calls_today}/${daily_request_limit} (${pct}%)`;
            }
            const pending = improvements.count > 0 ? ` · ${improvements.count} pending` : '';
            const errBadge = errors > 0 ? ` ⚠${errors}` : '';
            this.item.text = `$(shield) SAGE: ${quotaText}${pending}${errBadge}`;
            // Colour-code by quota pressure
            if (!unlimited) {
                const pct = (calls_today / daily_request_limit) * 100;
                if (pct >= 90) {
                    this.item.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
                    this.item.tooltip = `SAGE[ai] — QUOTA CRITICAL\n${model}: ${calls_today}/${daily_request_limit} requests used today`;
                }
                else if (pct >= 70) {
                    this.item.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
                    this.item.tooltip = `SAGE[ai] — ${calls_today}/${daily_request_limit} requests today (${Math.round(pct)}%)\nClick for full LLM status`;
                }
                else {
                    this.item.backgroundColor = undefined;
                    this.item.tooltip = `SAGE[ai] — Smart Agentic-Guided Empowerment\n${model}: ${calls_today}/${daily_request_limit} requests today\nClick for full LLM status`;
                }
            }
        }
        catch {
            this.item.text = `$(shield) SAGE: offline`;
            this.item.backgroundColor = undefined;
            this.item.tooltip = 'SAGE backend unreachable — run: make run PROJECT=<name>';
        }
    }
    dispose() {
        this.stop();
        this.item.dispose();
    }
}
exports.SageStatusBar = SageStatusBar;
//# sourceMappingURL=statusBar.js.map