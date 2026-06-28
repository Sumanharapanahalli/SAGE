import { useNavigate } from "react-router-dom";

import { OnboardingWizard } from "@/components/domain/OnboardingWizard";
import { useOnboardingGenerate } from "@/hooks/useOnboarding";
import { useSwitchSolution } from "@/hooks/useSolutions";

export default function Onboarding() {
  const nav = useNavigate();
  const gen = useOnboardingGenerate();
  const swap = useSwitchSolution();

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <h2 className="text-lg font-semibold">New solution</h2>
      <p className="text-sm text-gray-600">
        Describe what you're building. The wizard asks the LLM to draft
        project.yaml, prompts.yaml, and tasks.yaml for you. You can switch
        to the new solution immediately after it's created.
      </p>
      <OnboardingWizard
        isPending={gen.isPending}
        error={gen.error ?? null}
        result={gen.data ?? null}
        onGenerate={(p) => gen.mutate(p)}
        onSwitch={(name, path) => {
          swap.mutate(
            { name, path },
            {
              onSuccess: () => nav("/status"),
            },
          );
        }}
        onClose={() => nav(-1)}
      />
    </div>
  );
}
