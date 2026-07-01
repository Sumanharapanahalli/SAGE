import { useQuery } from "@tanstack/react-query";

import { getAgent, getAgentPerformance, listAgents } from "@/api/client";
import type { Agent, AgentPerformance, DesktopError } from "@/api/types";

export const agentsKey = ["agents"] as const;
export const agentKey = (name: string) => ["agent", name] as const;
export const agentPerformanceKey = (role_key: string) =>
  ["agent-performance", role_key] as const;

export function useAgents() {
  return useQuery<Agent[], DesktopError>({
    queryKey: agentsKey,
    queryFn: () => listAgents(),
  });
}

export function useAgent(name: string) {
  return useQuery<Agent, DesktopError>({
    queryKey: agentKey(name),
    queryFn: () => getAgent(name),
    enabled: name.length > 0,
  });
}

export function useAgentPerformance(role_key: string, enabled = true) {
  return useQuery<AgentPerformance, DesktopError>({
    queryKey: agentPerformanceKey(role_key),
    queryFn: () => getAgentPerformance(role_key),
    enabled: role_key.length > 0 && enabled,
  });
}
