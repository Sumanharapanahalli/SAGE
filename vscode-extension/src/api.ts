/**
 * SAGE API Client
 * ================
 * Typed HTTP client for the SAGE FastAPI backend.
 * All communication goes through localhost — no external network needed.
 */

import * as http from "http";

export interface HealthResponse {
  status: string;
  project?: string;
  provider?: string;
  endpoints?: number;
}

export interface Proposal {
  trace_id: string;
  proposal_type: string;
  risk_class: string;
  status: string;
  created_at: string;
  summary?: string;
  payload?: Record<string, unknown>;
}

export interface QueueItem {
  task_id: string;
  task_type: string;
  status: string;
  created_at: string;
}

export interface AgentInfo {
  role: string;
  status: string;
  tasks_completed?: number;
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

  async getLLMStatus(): Promise<Record<string, unknown>> {
    return this.get<Record<string, unknown>>("/llm/status");
  }

  // --- Approvals ---

  async getPendingApprovals(): Promise<Proposal[]> {
    try {
      const res = await this.get<{ proposals: Proposal[] }>("/approvals");
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
      approved: true,
      feedback: feedback || "",
    });
  }

  async rejectProposal(
    traceId: string,
    feedback: string
  ): Promise<Record<string, unknown>> {
    return this.post<Record<string, unknown>>(`/approve/${traceId}`, {
      approved: false,
      feedback,
    });
  }

  // --- Queue ---

  async getQueue(): Promise<QueueItem[]> {
    try {
      const res = await this.get<{ tasks: QueueItem[] }>("/queue");
      return res.tasks || [];
    } catch {
      return [];
    }
  }

  // --- Solutions ---

  async getSolutions(): Promise<string[]> {
    try {
      const res = await this.get<{ solutions: string[] }>("/config/solutions");
      return res.solutions || [];
    } catch {
      return [];
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

  async getAgents(): Promise<AgentInfo[]> {
    try {
      const res = await this.get<{ agents: AgentInfo[] }>("/agents");
      return res.agents || [];
    } catch {
      return [];
    }
  }

  // --- Stats (for dashboard) ---

  async getStats(): Promise<Record<string, unknown>> {
    try {
      return await this.get<Record<string, unknown>>("/stats");
    } catch {
      return {};
    }
  }
}
