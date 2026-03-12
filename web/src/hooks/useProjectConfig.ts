import { useQuery } from '@tanstack/react-query'
import { fetchProjectConfig } from '../api/client'

export function useProjectConfig() {
  return useQuery({
    queryKey: ['project-config'],
    queryFn: fetchProjectConfig,
    staleTime: 5 * 60 * 1000, // 5 min — project rarely changes
    retry: false,
  })
}
