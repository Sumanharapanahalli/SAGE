import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  knowledgeAdd,
  knowledgeDelete,
  knowledgeList,
  knowledgeSearch,
  knowledgeStats,
} from "@/api/client";
import type {
  DesktopError,
  KnowledgeAddResult,
  KnowledgeDeleteResult,
  KnowledgeListResult,
  KnowledgeSearchResult,
  KnowledgeStats,
} from "@/api/types";

export const knowledgeKeys = {
  all: ["knowledge"] as const,
  list: (limit: number, offset: number) =>
    ["knowledge", "list", { limit, offset }] as const,
  search: (query: string, topK: number) =>
    ["knowledge", "search", { query, topK }] as const,
  stats: ["knowledge", "stats"] as const,
};

export function useKnowledgeList(limit = 50, offset = 0) {
  return useQuery<KnowledgeListResult, DesktopError>({
    queryKey: knowledgeKeys.list(limit, offset),
    queryFn: () => knowledgeList({ limit, offset }),
    staleTime: 0,
  });
}

export function useKnowledgeSearch(query: string, topK = 10) {
  const enabled = query.trim().length > 0;
  return useQuery<KnowledgeSearchResult, DesktopError>({
    queryKey: knowledgeKeys.search(query, topK),
    queryFn: () => knowledgeSearch(query, topK),
    enabled,
    staleTime: 0,
  });
}

export function useKnowledgeStats() {
  return useQuery<KnowledgeStats, DesktopError>({
    queryKey: knowledgeKeys.stats,
    queryFn: () => knowledgeStats(),
    staleTime: 0,
  });
}

interface AddArgs {
  text: string;
  metadata?: Record<string, unknown>;
}

export function useAddKnowledge() {
  const qc = useQueryClient();
  return useMutation<KnowledgeAddResult, DesktopError, AddArgs>({
    mutationFn: ({ text, metadata }) => knowledgeAdd(text, metadata),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: knowledgeKeys.all });
    },
  });
}

export function useDeleteKnowledge() {
  const qc = useQueryClient();
  return useMutation<KnowledgeDeleteResult, DesktopError, string>({
    mutationFn: (id) => knowledgeDelete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: knowledgeKeys.all });
    },
  });
}
