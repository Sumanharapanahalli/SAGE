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
exports.AuditLogProvider = void 0;
/**
 * SAGE Audit Log — VS Code tree view provider
 * Shows the ISO 13485 / QMS compliance audit trail from the backend.
 * Maps to the web UI Audit Log page (/audit).
 */
const vscode = __importStar(require("vscode"));
const ACTION_ICON = {
    ANALYSIS_PROPOSAL: '$(search)',
    AGENT_STREAM: '$(robot)',
    ANALYZE_STREAM: '$(search)',
    APPROVE: '$(check)',
    REJECT: '$(x)',
    CONFIG_SWITCH: '$(settings-gear)',
    LLM_SWITCH: '$(settings-gear)',
    YAML_EDIT: '$(edit)',
    KNOWLEDGE_ADD: '$(database)',
    KNOWLEDGE_DELETE: '$(trash)',
    KNOWLEDGE_IMPORT: '$(cloud-download)',
    ONBOARDING: '$(sparkle)',
};
function iconForAction(actionType) {
    for (const [key, icon] of Object.entries(ACTION_ICON)) {
        if (actionType.includes(key))
            return icon;
    }
    return '$(circle-outline)';
}
function formatTime(iso) {
    try {
        return new Date(iso).toLocaleTimeString();
    }
    catch {
        return iso.slice(11, 19);
    }
}
function formatDate(iso) {
    try {
        return new Date(iso).toLocaleDateString();
    }
    catch {
        return iso.slice(0, 10);
    }
}
// ─── Tree items ───────────────────────────────────────────────────────────────
class AuditEntryItem extends vscode.TreeItem {
    constructor(entry) {
        const icon = iconForAction(entry.action_type);
        super(`${icon} ${entry.action_type} — ${entry.actor}`, vscode.TreeItemCollapsibleState.None);
        this.entry = entry;
        this.description = formatTime(entry.timestamp);
        this.tooltip = new vscode.MarkdownString(`**Time:** ${new Date(entry.timestamp).toLocaleString()}\n\n` +
            `**Actor:** ${entry.actor}\n\n` +
            `**Action:** ${entry.action_type}\n\n` +
            `**Input:** ${entry.input_context?.slice(0, 200) ?? '—'}\n\n` +
            `**Trace ID:** \`${entry.id}\``);
        this.contextValue = 'auditEntry';
        this.command = {
            command: 'sage.showAuditDetail',
            title: 'Show audit detail',
            arguments: [entry],
        };
    }
}
class DateGroupItem extends vscode.TreeItem {
    constructor(label, children) {
        super(label, vscode.TreeItemCollapsibleState.Expanded);
        this.children = children;
        this.contextValue = 'auditGroup';
        this.iconPath = new vscode.ThemeIcon('calendar');
    }
}
// ─── Provider ─────────────────────────────────────────────────────────────────
class AuditLogProvider {
    constructor(client, output) {
        this.client = client;
        this._onDidChangeTreeData = new vscode.EventEmitter();
        this.onDidChangeTreeData = this._onDidChangeTreeData.event;
        this._limit = 50;
        this._output = output;
    }
    refresh() {
        this._onDidChangeTreeData.fire(undefined);
    }
    getTreeItem(element) {
        return element;
    }
    async getChildren(element) {
        if (element instanceof DateGroupItem) {
            return element.children;
        }
        try {
            const { entries, total } = await this.client.auditLog(this._limit);
            if (entries.length === 0) {
                const empty = new vscode.TreeItem('No audit entries yet');
                empty.description = 'Run SAGE: Analyze Selection to create the first entry';
                empty.iconPath = new vscode.ThemeIcon('info');
                return [empty];
            }
            // Group by date
            const byDate = new Map();
            for (const e of entries) {
                const d = formatDate(e.timestamp);
                if (!byDate.has(d))
                    byDate.set(d, []);
                byDate.get(d).push(e);
            }
            const groups = [];
            for (const [date, dayEntries] of byDate) {
                const items = dayEntries.map(e => new AuditEntryItem(e));
                const label = date === new Date().toLocaleDateString() ? `Today (${items.length})` : `${date} (${items.length})`;
                groups.push(new DateGroupItem(label, items));
            }
            // Add "Load more" hint if there are more entries
            if (total > this._limit) {
                const more = new vscode.TreeItem(`… ${total - this._limit} more entries`);
                more.description = 'Open web UI Audit Log to see all';
                more.iconPath = new vscode.ThemeIcon('ellipsis');
                groups.push(more);
            }
            return groups;
        }
        catch {
            const err = new vscode.TreeItem('Backend offline');
            err.description = 'Start SAGE backend to view audit log';
            err.iconPath = new vscode.ThemeIcon('warning');
            return [err];
        }
    }
    showDetail(entry) {
        this._output.show(true);
        this._output.appendLine('');
        this._output.appendLine('─'.repeat(70));
        this._output.appendLine(`AUDIT ENTRY — ${entry.action_type}`);
        this._output.appendLine(`Time:   ${new Date(entry.timestamp).toLocaleString()}`);
        this._output.appendLine(`Actor:  ${entry.actor}`);
        this._output.appendLine(`Trace:  ${entry.id}`);
        this._output.appendLine('');
        this._output.appendLine('INPUT:');
        this._output.appendLine(entry.input_context ?? '—');
        this._output.appendLine('');
        this._output.appendLine('OUTPUT:');
        try {
            const parsed = JSON.parse(entry.output_content);
            this._output.appendLine(JSON.stringify(parsed, null, 2));
        }
        catch {
            this._output.appendLine(entry.output_content ?? '—');
        }
        this._output.appendLine('─'.repeat(70));
    }
}
exports.AuditLogProvider = AuditLogProvider;
//# sourceMappingURL=auditLogProvider.js.map