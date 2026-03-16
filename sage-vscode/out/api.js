"use strict";
/**
 * SAGE Framework — VS Code Extension API Client
 * Thin wrapper around the SAGE FastAPI backend.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.SageApiClient = void 0;
class SageApiClient {
    constructor(baseUrl) {
        this.baseUrl = baseUrl.replace(/\/$/, '');
    }
    async get(path) {
        const res = await fetch(`${this.baseUrl}${path}`, {
            signal: AbortSignal.timeout(8000),
        });
        if (!res.ok) {
            throw new Error(`GET ${path} → ${res.status} ${res.statusText}`);
        }
        return res.json();
    }
    async post(path, body) {
        const res = await fetch(`${this.baseUrl}${path}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: body ? JSON.stringify(body) : undefined,
            signal: AbortSignal.timeout(120000), // LLM calls can be slow
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail ?? `POST ${path} → ${res.status}`);
        }
        return res.json();
    }
    async health() {
        return this.get('/health');
    }
    async llmStatus() {
        return this.get('/llm/status');
    }
    async analyze(logEntry) {
        return this.post('/analyze', { log_entry: logEntry });
    }
    async approve(traceId) {
        await this.post(`/approve/${traceId}`);
    }
    async reject(traceId, feedback) {
        await this.post(`/reject/${traceId}`, { feedback });
    }
    async auditLog(limit = 20) {
        return this.get(`/audit?limit=${limit}`);
    }
    async pendingProposals() {
        return this.get('/proposals/pending');
    }
    async pendingImprovements() {
        return this.get('/feedback/feature-requests?status=pending');
    }
    async submitImprovement(payload) {
        return this.post('/feedback/feature-request', {
            ...payload,
            requested_by: 'vscode-extension',
        });
    }
    async listSolutions() {
        return this.get('/config/projects');
    }
    async switchSolution(project) {
        await this.post('/config/switch', { project });
    }
}
exports.SageApiClient = SageApiClient;
//# sourceMappingURL=api.js.map