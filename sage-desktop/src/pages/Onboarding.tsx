import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ImportFlow } from "@/components/domain/ImportFlow";
import { OnboardingWizard } from "@/components/domain/OnboardingWizard";
import type { OrgChoice } from "@/components/domain/OrgTemplateChooser";
import { OrgTemplateChooser } from "@/components/domain/OrgTemplateChooser";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import { useOnboardingGenerate } from "@/hooks/useOnboarding";
import { useSwitchSolution } from "@/hooks/useSolutions";

type Mode = "describe" | "import";

export default function Onboarding() {
  const nav = useNavigate();
  const gen = useOnboardingGenerate();
  const swap = useSwitchSolution();
  // "describe" stays the default: it is the documented path in CLAUDE.md, and
  // importing only makes sense when there is already a codebase to point at.
  const [mode, setMode] = useState<Mode>("describe");
  const [org, setOrg] = useState<OrgChoice | null>(null);

  if (mode === "import") {
    return (
      <div className="mx-auto max-w-2xl space-y-4 p-6">
        <h2 className="text-lg font-semibold">New solution</h2>
        <ModeToggle mode={mode} onChange={setMode} />
        <ErrorBanner error={swap.error} />
        <ImportFlow
          onSaved={(name, path) =>
            swap.mutate({ name, path }, { onSuccess: () => nav("/status") })
          }
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <h2 className="text-lg font-semibold">New solution</h2>
      <ModeToggle mode={mode} onChange={setMode} />
      <p className="text-sm text-gray-600">
        Describe what you're building. The wizard asks the LLM to draft
        project.yaml, prompts.yaml, and tasks.yaml for you. You can switch
        to the new solution immediately after it's created.
      </p>
      {/* A failed solution switch (sidecar respawn) is otherwise silent — the
          wizard keeps showing the created-result view. Surface it here. */}
      <ErrorBanner error={swap.error} />
      <OrgTemplateChooser onChange={setOrg} />
      <OnboardingWizard
        isPending={gen.isPending}
        error={gen.error ?? null}
        result={gen.data ?? null}
        onGenerate={(p) =>
          gen.mutate({
            ...p,
            // The template's role brief steers the drafted prompts.yaml;
            // generate_solution prepends org_context to the description.
            org_context: org?.brief || undefined,
            // Union, not override — the operator's own entries are theirs to
            // keep, and a template must not silently drop them.
            compliance_standards: Array.from(
              new Set([
                ...(p.compliance_standards ?? []),
                ...(org?.complianceStandards ?? []),
              ]),
            ),
          })
        }
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

function ModeToggle({
  mode,
  onChange,
}: {
  mode: Mode;
  onChange: (m: Mode) => void;
}) {
  return (
    <div role="tablist" className="flex gap-1 border-b border-sage-100">
      {(
        [
          ["describe", "Describe it"],
          ["import", "Import a folder"],
        ] as const
      ).map(([id, label]) => (
        <button
          key={id}
          role="tab"
          aria-selected={mode === id}
          onClick={() => onChange(id)}
          className={
            mode === id
              ? "border-b-2 border-sage-500 px-4 py-2 text-sm font-medium text-sage-900"
              : "px-4 py-2 text-sm text-sage-700 hover:text-sage-900"
          }
        >
          {label}
        </button>
      ))}
    </div>
  );
}
