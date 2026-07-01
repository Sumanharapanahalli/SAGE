import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as client from "@/api/client";
import type {
  DesktopError,
  HILConnectResult,
  HILReportResult,
  HILRunSuiteResult,
  HILStatus,
  HILTestCaseInput,
} from "@/api/types";

export const hilStatusKey = ["hilStatus"];

export const useHilStatus = () =>
  useQuery<HILStatus, DesktopError>({
    queryKey: hilStatusKey,
    queryFn: () => client.getHilStatus(),
  });

interface HilConnectParams {
  transport?: string;
  config?: Record<string, unknown>;
}

export const useHilConnect = () => {
  const qc = useQueryClient();
  return useMutation<HILConnectResult, DesktopError, HilConnectParams>({
    mutationFn: ({ transport, config }) => client.hilConnect(transport, config),
    onSuccess: () => qc.invalidateQueries({ queryKey: hilStatusKey }),
  });
};

interface HilRunSuiteParams {
  tests: HILTestCaseInput[];
  transport?: string;
  config?: Record<string, unknown>;
}

export const useHilRunSuite = () => {
  const qc = useQueryClient();
  return useMutation<HILRunSuiteResult, DesktopError, HilRunSuiteParams>({
    mutationFn: ({ tests, transport, config }) =>
      client.hilRunSuite(tests, transport, config),
    onSuccess: () => qc.invalidateQueries({ queryKey: hilStatusKey }),
  });
};

export const useHilReport = (sessionId: string, standard?: string) =>
  useQuery<HILReportResult, DesktopError>({
    queryKey: ["hilReport", sessionId, standard],
    queryFn: () => client.hilReport(sessionId, standard),
    enabled: !!sessionId,
  });
