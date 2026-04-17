import { useMutation, useQueryClient } from "@tanstack/react-query";

import { onboardingGenerate } from "@/api/client";
import type {
  DesktopError,
  OnboardingParams,
  OnboardingResult,
} from "@/api/types";
import { solutionsKey } from "@/hooks/useSolutions";

/**
 * Generate a brand-new solution via the onboarding wizard.
 *
 * On a successful `created` response we invalidate the solutions list so
 * the Sidebar picker picks up the new entry. An `exists` status is a
 * soft-fail — we do not invalidate because nothing on disk changed.
 */
export function useOnboardingGenerate() {
  const qc = useQueryClient();
  return useMutation<OnboardingResult, DesktopError, OnboardingParams>({
    mutationFn: (p) => onboardingGenerate(p),
    onSuccess: (data) => {
      if (data.status === "created") {
        qc.invalidateQueries({ queryKey: solutionsKey });
      }
    },
  });
}
