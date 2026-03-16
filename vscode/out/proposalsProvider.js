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
exports.ProposalsProvider = void 0;
exports.storeProposal = storeProposal;
exports.removeProposal = removeProposal;
exports.getProposal = getProposal;
const vscode = __importStar(require("vscode"));
// In-memory store of proposals created this session (trace_id → proposal)
const _proposals = new Map();
function storeProposal(p) {
    _proposals.set(p.trace_id, p);
}
function removeProposal(traceId) {
    _proposals.delete(traceId);
}
function getProposal(traceId) {
    return _proposals.get(traceId);
}
// ─── Tree item ────────────────────────────────────────────────────────────────
const SEVERITY_ICON = {
    RED: '$(error)',
    AMBER: '$(warning)',
    GREEN: '$(pass)',
    UNKNOWN: '$(question)',
};
class ProposalItem extends vscode.TreeItem {
    constructor(proposal) {
        super(`${SEVERITY_ICON[proposal.severity] ?? '$(circle-outline)'} ${proposal.severity} — ${proposal.root_cause_hypothesis.slice(0, 60)}`, vscode.TreeItemCollapsibleState.None);
        this.proposal = proposal;
        this.contextValue = 'proposal';
        this.description = `trace: ${proposal.trace_id.slice(0, 8)}…`;
        this.tooltip = new vscode.MarkdownString(`**Severity:** ${proposal.severity}\n\n` +
            `**Root cause:** ${proposal.root_cause_hypothesis}\n\n` +
            `**Action:** ${proposal.recommended_action}\n\n` +
            `**Trace ID:** \`${proposal.trace_id}\``);
        this.command = {
            command: 'sage.showProposalDetail',
            title: 'Show detail',
            arguments: [proposal],
        };
    }
}
class SectionItem extends vscode.TreeItem {
    constructor(label, children) {
        super(label, vscode.TreeItemCollapsibleState.Expanded);
        this.children = children;
        this.contextValue = 'section';
    }
}
// ─── Provider ─────────────────────────────────────────────────────────────────
class ProposalsProvider {
    constructor(client) {
        this.client = client;
        this._onDidChangeTreeData = new vscode.EventEmitter();
        this.onDidChangeTreeData = this._onDidChangeTreeData.event;
    }
    refresh() {
        this._onDidChangeTreeData.fire(undefined);
    }
    getTreeItem(element) {
        return element;
    }
    async getChildren(element) {
        if (element instanceof SectionItem) {
            return element.children;
        }
        // Root — build sections
        const items = [];
        // ── Pending proposals (in-memory, created this session)
        const proposals = Array.from(_proposals.values());
        if (proposals.length > 0) {
            const sorted = [...proposals].sort((a, b) => {
                const order = { RED: 0, AMBER: 1, GREEN: 2, UNKNOWN: 3 };
                return (order[a.severity] ?? 3) - (order[b.severity] ?? 3);
            });
            items.push(new SectionItem(`Pending Proposals (${proposals.length})`, sorted.map(p => new ProposalItem(p))));
        }
        else {
            const empty = new vscode.TreeItem('No pending proposals');
            empty.description = 'Run SAGE: Analyze Selection to create one';
            empty.iconPath = new vscode.ThemeIcon('check');
            items.push(empty);
        }
        // ── Pending improvement requests from backend
        try {
            const { requests } = await this.client.pendingImprovements();
            if (requests.length > 0) {
                const improvementItems = requests.map(r => {
                    const item = new vscode.TreeItem(`${r.title} [${r.priority}]`);
                    item.description = r.module_name;
                    item.iconPath = new vscode.ThemeIcon('lightbulb');
                    item.tooltip = r.description;
                    return item;
                });
                items.push(new SectionItem(`Improvement Requests (${requests.length})`, improvementItems));
            }
        }
        catch {
            // backend offline — skip silently
        }
        return items;
    }
}
exports.ProposalsProvider = ProposalsProvider;
//# sourceMappingURL=proposalsProvider.js.map