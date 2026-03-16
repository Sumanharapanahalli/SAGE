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
exports.LiveConsole = void 0;
/**
 * SAGE Live Console — streams Python backend logs to a VS Code Output Channel.
 * Maps to the web UI Live Console page (/live-console).
 * Uses Node.js http module to connect to the SSE endpoint GET /logs/stream.
 */
const http = __importStar(require("http"));
const https = __importStar(require("https"));
const LEVEL_PREFIX = {
    DEBUG: '[DBG]',
    INFO: '[INF]',
    WARNING: '[WRN]',
    ERROR: '[ERR]',
    CRITICAL: '[CRT]',
};
class LiveConsole {
    constructor(output) {
        this._req = null;
        this._active = false;
        this._reconnectTimer = null;
        this._output = output;
    }
    get isActive() { return this._active; }
    start(apiUrl) {
        if (this._active)
            return;
        this._active = true;
        this._connect(apiUrl);
        this._output.show(false);
        this._output.appendLine(`[SAGE Live Console] Connecting to ${apiUrl}/logs/stream …`);
    }
    stop() {
        this._active = false;
        if (this._reconnectTimer) {
            clearTimeout(this._reconnectTimer);
            this._reconnectTimer = null;
        }
        if (this._req) {
            this._req.destroy();
            this._req = null;
        }
        this._output.appendLine('[SAGE Live Console] Stopped.');
    }
    _connect(apiUrl) {
        if (!this._active)
            return;
        const url = new URL('/logs/stream', apiUrl);
        const lib = url.protocol === 'https:' ? https : http;
        const options = {
            hostname: url.hostname,
            port: url.port || (url.protocol === 'https:' ? 443 : 80),
            path: url.pathname,
            method: 'GET',
            headers: { Accept: 'text/event-stream' },
        };
        try {
            this._req = lib.request(options, (res) => {
                if (res.statusCode !== 200) {
                    this._output.appendLine(`[SAGE Live Console] HTTP ${res.statusCode} — retrying in 5s`);
                    this._scheduleReconnect(apiUrl);
                    return;
                }
                let buffer = '';
                res.on('data', (chunk) => {
                    buffer += chunk.toString('utf8');
                    const lines = buffer.split('\n');
                    buffer = lines.pop() ?? '';
                    for (const line of lines) {
                        if (!line.startsWith('data:'))
                            continue;
                        const json = line.slice(5).trim();
                        if (!json)
                            continue;
                        try {
                            const entry = JSON.parse(json);
                            const time = entry.ts?.slice(11, 23) ?? '';
                            const prefix = LEVEL_PREFIX[entry.level] ?? '[   ]';
                            const name = entry.name?.slice(0, 20).padEnd(20) ?? '';
                            this._output.appendLine(`${time} ${prefix} ${name} ${entry.message}`);
                        }
                        catch {
                            // ignore malformed lines
                        }
                    }
                });
                res.on('end', () => {
                    if (this._active) {
                        this._output.appendLine('[SAGE Live Console] Connection closed — retrying in 5s');
                        this._scheduleReconnect(apiUrl);
                    }
                });
                res.on('error', () => {
                    if (this._active)
                        this._scheduleReconnect(apiUrl);
                });
            });
            this._req.on('error', () => {
                if (this._active) {
                    this._scheduleReconnect(apiUrl);
                }
            });
            this._req.end();
        }
        catch {
            if (this._active)
                this._scheduleReconnect(apiUrl);
        }
    }
    _scheduleReconnect(apiUrl) {
        if (!this._active)
            return;
        this._reconnectTimer = setTimeout(() => this._connect(apiUrl), 5000);
    }
    dispose() {
        this.stop();
    }
}
exports.LiveConsole = LiveConsole;
//# sourceMappingURL=liveConsole.js.map