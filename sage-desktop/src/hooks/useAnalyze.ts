import { useMutation, useQueryClient } from "@tanstack/react-query";

import { analyzeLog } from "@/api/client";
import type { DesktopError, Proposal } from "@/api/types";
import { approvalsKey } from "@/hooks/useApprovals";

interface AnalyzeVars {
  log_entry: string;
}

/** The SURFACE -> PROPOSE trigger: submits a log/signal for analysis and
 * creates a real proposal, so on success we invalidate the approvals cache
 * to refresh the inbox. */
export function useAnalyzeLog() {
  const qc = useQueryClient();
  return useMutation<Proposal, DesktopError, AnalyzeVars>({
    mutationFn: (v) => analyzeLog(v.log_entry),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: approvalsKey });
    },
  });
}
