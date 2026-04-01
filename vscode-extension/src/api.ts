/**
 * SAGE API Client
 * ================
 * Typed HTTP client for the SAGE FastAPI backend.
 * All communication goes through localhost — no external network needed.
 *
 * Endpoint mapping (extension → backend):
 *   /health              → GET  /health
 *   /llm/status          → GET  /llm/status
 *   /proposals/pending   → GET  /proposals/pending
 *   /approve/{id}        → POST /approve/{trace_id}
 *   /queue/tasks          → GET  /queue/tasks
 *   /config/projects     → GET  /config/projects
 *   /config/switch       → POST /config/switch
 *   /llm/switch          → POST /llm/switch
 *   /agents/status       → GET  /agents/status
 */

import * as http from "http";

export interface HealthResponse {
  status: string;
  project?: Record<string, unknown> | string;
  llm_provider?: string;
  version?: string;
  service?: string;
}

export interface Proposal {
  trace_id: string;
  action_type: string;
  risk_class: string;
  status: string;
  created_at: string;
  summary?: string;
  payload?: Record<string, unknown>;
  proposal_type?: string; // alias for action_type
}

export interface QueueItem {
  task_id: string;
  task_type: string;
  status: string;
  created_at: string;
  priority?: number;
}

export interface AgentInfo {
  role: string;
  status: string;
  last_task?: string | null;
  task_count_today?: number;
}

export interface ProjectInfo {
  id: string;
  name: string;
  domain?: string;
  description?: string;
}

export class SageApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  /**
   * Low-level GET/POST using Node's built-in http module (no dependencies).
   * This avoids any fetch/node-fetch compatibility issues across VS Code versions.
   */
  private request(
    method: string,
    path: string,
    body?: unknown
  ): Promise<unknown> {
    return new Promise((resolve, reject) => {
      const url = new URL(path, this.baseUrl);
      const options: http.RequestOptions = {
        method,
        hostname: url.hostname,
        port: url.port,
        path: url.pathname + url.search,
        headers: { "Content-Type": "application/json" },
        timeout: 10000,
      };

      const req = http.request(options, (res) => {
        let data = "";
        res.on("data", (chunk) => (data += chunk));
        res.on("end", () => {
          try {
            resolve(JSON.parse(data));
          } catch {
            resolve(data);
          }
        });
      });

      req.on("error", reject);
      req.on("timeout", () => {
        req.destroy();
        reject(new Error("Request timeout"));
      });

      if (body) {
        req.write(JSON.stringify(body));
      }
      req.end();
    });
  }

  private async get<T>(path: string): Promise<T> {
    return (await this.request("GET", path)) as T;
  }

  private async post<T>(path: string, body?: unknown): Promise<T> {
    return (await this.request("POST", path, body)) as T;
  }

  // --- Health & Status ---

  async health(): Promise<boolean> {
    try {
      const res = await this.get<HealthResponse>("/health");
      return res.status === "ok" || res.status === "healthy";
    } catch {
      return false;
    }
  }

  async getStatus(): Promise<HealthResponse> {
    return this.get<HealthResponse>("/health");
  }

  /**
   * Extract the project name from the health response.
   * /health returns project as either a metadata dict or a string.
   */
  getProjectName(health: HealthResponse): string {
    if (!health.project) {
      return "";
    }
    if (typeof health.project === "string") {
      return health.project;
    }
    // project is a metadata dict — extract the project name
    return (
      (health.project as Record<string, unknown>).project as string ||
      (health.project as Record<string, unknown>).name as string ||
      ""
    );
  }

  /**
   * Extract the LLM provider name from the health response.
   * /health returns llm_provider (not provider).
   */
  getProviderName(health: HealthResponse): string {
    return health.llm_provider || "";
  }

  async getLLMStatus(): Promise<Record<string, unknown>> {
    return this.get<Record<string, unknown>>("/llm/status");
  }

  // --- Approvals ---
  // Backend: GET /proposals/pending → { proposals: [...], count: N }

  async getPendingApprovals(): Promise<Proposal[]> {
    try {
      const res = await this.get<{ proposals: Proposal[] }>(
        "/proposals/pending"
      );
      return res.proposals || [];
    } catch {
      return [];
    }
  }

  async approveProposal(
    traceId: string,
    feedback?: string
  ): Promise<Record<string, unknown>> {
    return this.post<Record<string, unknown>>(`/approve/${traceId}`, {
      decided_by: "human",
      feedback: feedback || "",
    });
  }

  async rejectProposal(
    traceId: string,
    feedback: string
  ): Promise<Record<string, unknown>> {
    // Backend uses POST /reject/{trace_id} with RejectRequest (feedback only)
    return this.post<Record<string, unknown>>(`/reject/${traceId}`, {
      feedback,
    });
  }

  // --- Queue ---
  // Backend: GET /queue/tasks → bare array of task objects

  async getQueue(): Promise<QueueItem[]> {
    try {
      const res = await this.get<QueueItem[]>("/queue/tasks");
      // Backend returns a bare array (not wrapped in { tasks: [...] })
      return Array.isArray(res) ? res : [];
    } catch {
      return [];
    }
  }

  // --- Solutions ---
  // Backend: GET /config/projects → { projects: [{id, name, domain, ...}], active: "..." }

  async getSolutions(): Promise<string[]> {
    try {
      const res = await this.get<{
        projects: ProjectInfo[];
        active: string;
      }>("/config/projects");
      return (res.projects || []).map((p) => p.id || p.name);
    } catch {
      return [];
    }
  }

  async getActiveSolution(): Promise<string> {
    try {
      const res = await this.get<{
        projects: ProjectInfo[];
        active: string;
      }>("/config/projects");
      return res.active || "";
    } catch {
      return "";
    }
  }

  async switchSolution(name: string): Promise<Record<string, unknown>> {
    return this.post<Record<string, unknown>>("/config/switch", {
      project: name,
    });
  }

  // --- LLM ---

  async switchLLM(
    provider: string,
    model?: string
  ): Promise<Record<string, unknown>> {
    return this.post<Record<string, unknown>>("/llm/switch", {
      provider,
      ...(model ? { model } : {}),
    });
  }

  // --- Agents ---
  // Backend: GET /agents/status → bare array of agent objects

  async getAgents(): Promise<AgentInfo[]> {
    try {
      const res = await this.get<AgentInfo[]>("/agents/status");
      // Backend returns a bare array (not wrapped in { agents: [...] })
      return Array.isArray(res) ? res : [];
    } catch {
      return [];
    }
  }
}
