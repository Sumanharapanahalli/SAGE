import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import * as client from "@/api/client";
import type {
  DesktopError,
  ReflectRecentList,
  ReflectResult,
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
