import { useMutation, useQueryClient } from "@tanstack/react-query";

import { knowledgeSync } from "@/api/client";
import type { DesktopError, KnowledgeSyncResult } from "@/api/types";

import { knowledgeKeys } from "./useKnowledge";

interface SyncArgs {
  /** Omit to sync the active solution's own directory (the common case). */
  directory?: string;
}

export function useKnowledgeSync() {
  const qc = useQueryClient();
  return useMutation<KnowledgeSyncResult, DesktopError, SyncArgs>({
    mutationFn: ({ directory }) => knowledgeSync(directory),
    onSuccess: () => {
      // A sync can add thousands of chunks — the browse list and stats tile
      // are both stale immediately.
      qc.invalidateQueries({ queryKey: knowledgeKeys.all });
    },
  });
}
