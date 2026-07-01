import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as client from "@/api/client";
import type {
  DesktopError,
  EvalHistoryResult,
  EvalRunResult,
  EvalSuiteList,
} from "@/api/types";

export const evalSuitesKey = ["evalSuites"];
export const evalHistoryKey = ["evalHistory"];

export const useEvalSuites = () =>
  useQuery<EvalSuiteList, DesktopError>({
    queryKey: evalSuitesKey,
    queryFn: () => client.listEvalSuites(),
  });

export const useRunEval = () => {
  const qc = useQueryClient();
  return useMutation<EvalRunResult, DesktopError, string | undefined>({
    mutationFn: (suite) => client.runEval(suite),
    onSuccess: () => qc.invalidateQueries({ queryKey: evalHistoryKey }),
  });
};

export const useEvalHistory = (suite?: string, limit = 20) =>
  useQuery<EvalHistoryResult, DesktopError>({
    queryKey: [...evalHistoryKey, suite, limit],
    queryFn: () => client.getEvalHistory(suite, limit),
  });
