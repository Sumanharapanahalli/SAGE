import { useState } from "react";

import type { OrgTemplate } from "@/api/types";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import { useOrgTemplates } from "@/hooks/useOnboarding";

/**
 * Pick a pre-built team structure to start the new solution from.
 *
 * The web app has both the `/onboarding/org-templates` endpoint and a
 * 263-line `OrgStructureChooser.tsx`, but **nothing imports that component** —
 * it was never wired into the web wizard, so there was no reference for how a
 * chosen template should reach generation.
 *
 * Desktop routes it through `generate_solution(org_context=...)`, which the
 * framework already documents as "prepended to description before LLM
 * generation". So the choice actually steers the drafted prompts.yaml, with no
 * framework change: the enabled roles become a brief, and the template's
 * compliance standards are merged into the request.
 */

export interface OrgChoice {
  templateId: string;
  enabledRoles: string[];
  complianceStandards: string[];
  /** The role brief handed to the LLM as org_context. */
  brief: string;
}

interface Props {
  onChange: (choice: OrgChoice | null) => void;
}

function buildBrief(template: OrgTemplate, enabled: string[]): string {
  const roles = template.roles.filter((r) => enabled.includes(r.key));
  if (roles.length === 0) return "";
  const lines = roles.map((r) => `- ${r.key} (${r.name}): ${r.description}`);
  return [
    `Team structure: ${template.name}.`,
    "Create exactly these expert roles in prompts.yaml:",
    ...lines,
  ].join("\n");
}

export function OrgTemplateChooser({ onChange }: Props) {
  const { data, isLoading, error } = useOrgTemplates();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [disabledRoles, setDisabledRoles] = useState<Record<string, string[]>>(
    {},
  );

  const templates = data?.templates ?? [];

  const enabledFor = (t: OrgTemplate) =>
    t.roles.map((r) => r.key).filter((k) => !(disabledRoles[t.id] ?? []).includes(k));

  const emit = (id: string | null, disabled: Record<string, string[]>) => {
    if (!id) return onChange(null);
    const template = templates.find((t) => t.id === id);
    if (!template) return onChange(null);
    const enabled = template.roles
      .map((r) => r.key)
      .filter((k) => !(disabled[id] ?? []).includes(k));
    onChange({
      templateId: id,
      enabledRoles: enabled,
      complianceStandards: template.compliance_standards ?? [],
      brief: buildBrief(template, enabled),
    });
  };

  const select = (id: string) => {
    // Clicking the selected template clears it — starting from no template is
    // a valid choice, and there is no other way back to it.
    const next = selectedId === id ? null : id;
    setSelectedId(next);
    emit(next, disabledRoles);
  };

  const toggleRole = (templateId: string, roleKey: string) => {
    setDisabledRoles((prev) => {
      const current = prev[templateId] ?? [];
      const next = current.includes(roleKey)
        ? current.filter((k) => k !== roleKey)
        : [...current, roleKey];
      const updated = { ...prev, [templateId]: next };
      if (selectedId === templateId) emit(templateId, updated);
      return updated;
    });
  };

  if (error) return <ErrorBanner error={error} />;
  if (isLoading)
    return <p className="text-sm text-slate-500">Loading team templates…</p>;
  if (templates.length === 0) return null;

  return (
    <div className="space-y-2">
      <div className="text-xs uppercase text-sage-700">
        Start from a team structure (optional)
      </div>
      <ul className="space-y-2">
        {templates.map((t) => {
          const selected = selectedId === t.id;
          return (
            <li
              key={t.id}
              className={
                selected
                  ? "rounded border-2 border-sage-500 bg-sage-50 p-3"
                  : "rounded border border-sage-200 p-3"
              }
            >
              <button
                className="flex w-full items-start gap-2 text-left"
                aria-pressed={selected}
                onClick={() => select(t.id)}
              >
                <span aria-hidden="true">{t.icon}</span>
                <span>
                  <span className="block text-sm font-medium text-sage-900">
                    {t.name}
                  </span>
                  <span className="block text-xs text-sage-700">
                    {t.description}
                  </span>
                </span>
              </button>

              {selected && (
                <fieldset className="mt-3 space-y-1 border-t border-sage-200 pt-2">
                  <legend className="text-xs text-slate-400">
                    Roles to create
                  </legend>
                  {t.roles.map((r) => (
                    <label
                      key={r.key}
                      className="flex items-center gap-2 text-xs text-sage-900"
                    >
                      <input
                        type="checkbox"
                        checked={enabledFor(t).includes(r.key)}
                        onChange={() => toggleRole(t.id, r.key)}
                      />
                      {r.name}
                    </label>
                  ))}
                </fieldset>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
