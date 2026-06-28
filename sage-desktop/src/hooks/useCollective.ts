import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  collectiveClaimHelpRequest,
  collectiveCloseHelpRequest,
  collectiveCreateHelpRequest,
  collectiveListHelpRequests,
  collectiveListLearnings,
  collectivePublishLearning,
  collectiveRespondToHelpRequest,
  collectiveSearchLearnings,
  collectiveStats,
  collectiveSync,
  collectiveValidateLearning,
} from "@/api/client";
import type {
  CollectiveHelpCreateResult,
  CollectiveHelpListResult,
  CollectiveHelpMutationResult,
  CollectiveListResult,
  CollectivePublishResult,
  CollectiveSearchResult,
  CollectiveStats,
  CollectiveSyncResult,
  CollectiveValidateResult,
  DesktopError,
} from "@/api/types";

export const collectiveKeys = {
  all: ["collective"] as const,
  learnings: (args: {
    solution?: string;
    topic?: string;
    limit?: number;
    offset?: number;
  }) => ["collective", "learnings", args] as const,
  search: (args: {
    query: string;
    tags?: string[];
    solution?: string;
    limit?: number;
  }) => ["collective", "search", args] as const,
  help: (args: { status?: "open" | "closed"; expertise?: string[] }) =>
    ["collective", "help", args] as const,
  stats: ["collective", "stats"] as const,
};

export function useCollectiveList(
  args: {
    solution?: string;
    topic?: string;
    limit?: number;
    offset?: number;
  } = {},
) {
  return useQuery<CollectiveListResult, DesktopError>({
    queryKey: collectiveKeys.learnings(args),
    queryFn: () => collectiveListLearnings(args),
    staleTime: 0,
  });
}

export function useCollectiveSearch(args: {
  query: string;
  tags?: string[];
  solution?: string;
  limit?: number;
}) {
  const enabled = args.query.trim().length > 0;
  return useQuery<CollectiveSearchResult, DesktopError>({
    queryKey: collectiveKeys.search(args),
    queryFn: () => collectiveSearchLearnings(args),
    enabled,
    staleTime: 0,
  });
}

export function useCollectiveHelpList(
  args: { status?: "open" | "closed"; expertise?: string[] } = {},
) {
  return useQuery<CollectiveHelpListResult, DesktopError>({
    queryKey: collectiveKeys.help(args),
    queryFn: () => collectiveListHelpRequests(args),
    staleTime: 0,
  });
}

export function useCollectiveStats() {
  return useQuery<CollectiveStats, DesktopError>({
    queryKey: collectiveKeys.stats,
    queryFn: () => collectiveStats(),
    staleTime: 0,
  });
}

interface PublishArgs {
  author_agent: string;
  author_solution: string;
  topic: string;
  title: string;
  content: string;
  tags?: string[];
  confidence?: number;
  source_task_id?: string;
  proposed_by?: string;
}

export function usePublishLearning() {
  const qc = useQueryClient();
  return useMutation<CollectivePublishResult, DesktopError, PublishArgs>({
    mutationFn: (payload) => collectivePublishLearning(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: collectiveKeys.all });
    },
  });
}

export function useValidateLearning() {
  const qc = useQueryClient();
  return useMutation<
    CollectiveValidateResult,
    DesktopError,
    { id: string; validated_by: string }
  >({
    mutationFn: ({ id, validated_by }) =>
      collectiveValidateLearning(id, validated_by),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: collectiveKeys.all });
    },
  });
}

interface CreateHelpArgs {
  title: string;
  requester_agent: string;
  requester_solution: string;
  urgency?: "low" | "medium" | "high" | "critical";
  required_expertise?: string[];
  context?: string;
}

export function useCreateHelpRequest() {
  const qc = useQueryClient();
  return useMutation<CollectiveHelpCreateResult, DesktopError, CreateHelpArgs>({
    mutationFn: (payload) => collectiveCreateHelpRequest(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: collectiveKeys.all });
    },
  });
}

export function useClaimHelpRequest() {
  const qc = useQueryClient();
  return useMutation<
    CollectiveHelpMutationResult,
    DesktopError,
    { id: string; agent: string; solution: string }
  >({
    mutationFn: ({ id, agent, solution }) =>
      collectiveClaimHelpRequest(id, agent, solution),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: collectiveKeys.all });
    },
  });
}

export function useRespondToHelpRequest() {
  const qc = useQueryClient();
  return useMutation<
    CollectiveHelpMutationResult,
    DesktopError,
    {
      id: string;
      responder_agent: string;
      responder_solution: string;
      content: string;
    }
  >({
    mutationFn: (payload) => collectiveRespondToHelpRequest(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: collectiveKeys.all });
    },
  });
}

export function useCloseHelpRequest() {
  const qc = useQueryClient();
  return useMutation<CollectiveHelpMutationResult, DesktopError, string>({
    mutationFn: (id) => collectiveCloseHelpRequest(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: collectiveKeys.all });
    },
  });
}

export function useCollectiveSync() {
  const qc = useQueryClient();
  return useMutation<CollectiveSyncResult, DesktopError, void>({
    mutationFn: () => collectiveSync(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: collectiveKeys.all });
    },
  });
}
