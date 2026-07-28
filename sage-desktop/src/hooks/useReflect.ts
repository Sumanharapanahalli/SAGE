import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import * as client from "@/api/client";
import type {
  DesktopError,
  ReflectProgress,
  ReflectRecentList,
  ReflectResult,
  ReflectStarted,
  ReflectStats,
} from "@/api/types";

export const reflectStatsKey = ["reflectStats"];
export const reflectRecentKey = ["reflectRecent"];

export interface RunReflectionArgs {
  task: string;
  context?: string;
  maxIterations?: number;
  acceptanceThreshold?: number;
}

export const useReflectStats = () =>
  useQuery<ReflectStats, DesktopError>({
    queryKey: reflectStatsKey,
    queryFn: () => client.reflectStats(),
  });

export const useReflectRecent = (limit = 20) =>
  useQuery<ReflectRecentList, DesktopError>({
    queryKey: [...reflectRecentKey, limit],
    queryFn: () => client.reflectRecent(limit),
  });

export const useRunReflection = () => {
  const qc = useQueryClient();
  return useMutation<ReflectResult, DesktopError, RunReflectionArgs>({
    mutationFn: (args) =>
      client.reflectRun(
        args.task,
        args.context,
        args.maxIterations,
        args.acceptanceThreshold,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: reflectStatsKey });
      qc.invalidateQueries({ queryKey: reflectRecentKey });
    },
  });
};

/** Start a reflection as a background job, returning a run_id to poll. */
export const useStartReflection = () =>
  useMutation<ReflectStarted, DesktopError, RunReflectionArgs>({
    mutationFn: (args) =>
      client.reflectStart(
        args.task,
        args.context,
        args.maxIterations,
        args.acceptanceThreshold,
      ),
  });

/** Poll a running reflection's live progress (iterations stream in as they
 * complete). Stops polling once the job is no longer running. */
export const useReflectProgress = (runId: string | null) =>
  useQuery<ReflectProgress, DesktopError>({
    queryKey: ["reflectProgress", runId],
    enabled: !!runId,
    queryFn: () => client.reflectProgress(runId as string),
    refetchInterval: (query) =>
      query.state.data?.state === "running" ? 800 : false,
  });
