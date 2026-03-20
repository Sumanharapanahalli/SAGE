/**
 * Polls GET /health/llm every 60 seconds to verify the LLM connection is alive.
 * Returns { connected, provider, latency_ms, detail, isChecking }.
 * Also checks immediately on mount.
 */
import { useQuery } from '@tanstack/react-query'
import { fetchLLMHealth } from '../api/client'

export function useLLMHealth() {
  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['llm-health'],
    queryFn: fetchLLMHealth,
    refetchInterval: 60_000,      // check every 60 s
    refetchOnWindowFocus: true,   // recheck when user returns to tab
    retry: 1,                     // one retry before marking disconnected
    retryDelay: 3000,
  })

  return {
    connected:  data?.connected ?? null,   // null = not yet checked
    provider:   data?.provider ?? '',
    latency_ms: data?.latency_ms ?? 0,
    detail:     data?.detail ?? '',
    isChecking: isLoading || isFetching,
  }
}
