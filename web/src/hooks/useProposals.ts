import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchPendingProposals, type Proposal } from '../api/client'

export const PROPOSALS_QUERY_KEY = ['proposals-pending'] as const

export function useProposals() {
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: PROPOSALS_QUERY_KEY,
    queryFn: fetchPendingProposals,
    refetchInterval: 10_000,
  })
  const proposals: Proposal[] = data?.proposals ?? []

  return {
    proposals,
    isLoading,
    invalidate: () => queryClient.invalidateQueries({ queryKey: PROPOSALS_QUERY_KEY }),
  }
}
