import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as client from "@/api/client";
import type { DesktopError, LlmInfo, LlmSwitchResult } from "@/api/types";

export const useLlmInfo = () =>
  useQuery<LlmInfo, DesktopError>({
    queryKey: ["llm", "info"],
    queryFn: client.getLlmInfo,
  });

interface SwitchVars {
  provider: string;
  model?: string;
  save_as_default?: boolean;
}

export const useSwitchLlm = () => {
  const qc = useQueryClient();
  return useMutation<LlmSwitchResult, DesktopError, SwitchVars>({
    mutationFn: (req) => client.switchLlm(req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["llm"] });
      qc.invalidateQueries({ queryKey: ["status"] });
    },
  });
};
