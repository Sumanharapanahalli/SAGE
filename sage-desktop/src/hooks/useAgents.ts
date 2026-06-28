import { useQuery } from "@tanstack/react-query";

import { getAgent, listAgents } from "@/api/client";
import type { Agent, DesktopError } from "@/api/types";

export const agentsKey = ["agents"] as const;
export const agentKey = (name: string) => ["agent", name] as const;

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
