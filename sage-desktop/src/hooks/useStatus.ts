import { useQuery } from "@tanstack/react-query";

import { getStatus, handshake } from "@/api/client";
import type {
  DesktopError,
  HandshakeResponse,
  StatusResponse,
} from "@/api/types";

export const statusKey = ["status"] as const;
export const handshakeKey = ["handshake"] as const;

/** Poll sidecar health every 5 seconds. */
export function useStatus() {
  return useQuery<StatusResponse, DesktopError>({
    queryKey: statusKey,
    queryFn: () => getStatus(),
    refetchInterval: 5000,
  });
}

/** One-shot handshake at startup. */
export function useHandshake() {
  return useQuery<HandshakeResponse, DesktopError>({
    queryKey: handshakeKey,
    queryFn: () => handshake(),
    staleTime: Infinity,
  });
}
