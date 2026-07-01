import { useEffect, useState } from "react";

import {
  useAssessComplianceGap,
  useComplianceChecklist,
  useComplianceDomains,
} from "@/hooks/useCompliance";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import { toDesktopError } from "@/api/client";

/** Turn a required_task checklist item's id ("TASK-RISK_ANALYSIS") back
 * into the raw task type string the sidecar's gap_assessment expects
 * ("RISK_ANALYSIS") — see compliance_flags.generate_compliance_checklist,
 * which builds the id as f"TASK-{task}". */
function taskIdToTaskType(id: string): string {
  return id.startsWith("TASK-") ? id.slice("TASK-".length) : id;
}

/** Assessment tooling on top of the audit RECORD already on desktop: pick a
 * domain + risk level, see the full checklist, check off completed task
 * types, and assess conformance. */
export default function Compliance() {
  const domains = useComplianceDomains();
  const [domain, setDomain] = useState("");
  const [riskLevel, setRiskLevel] = useState("");
  const [checked, setChecked] = useState<Set<string>>(new Set());

  // Default to the first domain/risk-level once domains load.
  useEffect(() => {
    if (!domain && domains.data && domains.data.domains.length > 0) {
      const first = domains.data.domains[0];
      setDomain(first.domain);
      setRiskLevel(first.risk_levels[0] ?? "");
    }
  }, [domain, domains.data]);

  const checklist = useComplianceChecklist(domain, riskLevel);
  const assess = useAssessComplianceGap();

  const selectedDomain = domains.data?.domains.find((d) => d.domain === domain);

  const toggle = (id: string) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleAssess = () => {
    const completed_tasks = [...checked].map(taskIdToTaskType);
    assess.mutate({ domain, risk_level: riskLevel, completed_tasks });
  };

  const error = assess.error ? toDesktopError(assess.error) : null;
  const requiredTaskItems =
    checklist.data?.items.filter((i) => i.type === "required_task") ?? [];

  return (
    <div className="p-6 space-y-4">
      <h2 className="font-semibold text-lg">Compliance</h2>

      {domains.isLoading && (
        <div className="text-sm text-slate-500">Loading domains…</div>
      )}

      <ErrorBanner error={domains.error ?? checklist.error ?? null} />

      <div className="flex gap-3">
        <label className="block">
          <span className="block text-sm font-medium">Domain</span>
          <select
            className="mt-1 rounded border border-gray-300 p-2"
            value={domain}
            onChange={(e) => {
              setDomain(e.target.value);
              setChecked(new Set());
              const d = domains.data?.domains.find((x) => x.domain === e.target.value);
              setRiskLevel(d?.risk_levels[0] ?? "");
            }}
          >
            {(domains.data?.domains ?? []).map((d) => (
              <option key={d.domain} value={d.domain}>
                {d.domain}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="block text-sm font-medium">Risk level</span>
          <select
            className="mt-1 rounded border border-gray-300 p-2"
            value={riskLevel}
            onChange={(e) => {
              setRiskLevel(e.target.value);
              setChecked(new Set());
            }}
          >
            {(selectedDomain?.risk_levels ?? []).map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </label>
      </div>

      {checklist.data && (
        <div className="rounded border border-sage-100 bg-white p-4">
          <div className="text-sm text-slate-500 mb-2">
            {checklist.data.standard} — {checklist.data.total_items} items
            {checklist.data.hil_testing_required && " · HIL testing required"}
          </div>
          <ul className="space-y-1">
            {requiredTaskItems.map((item) => (
              <li key={item.id} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={checked.has(item.id)}
                  onChange={() => toggle(item.id)}
                />
                <span>{item.description}</span>
              </li>
            ))}
          </ul>

          <button
            type="button"
            onClick={handleAssess}
            disabled={assess.isPending}
            className="mt-3 rounded bg-sage-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
          >
            {assess.isPending ? "Assessing…" : "Assess conformance"}
          </button>
        </div>
      )}

      <ErrorBanner error={error} />

      {assess.data && (
        <div className="rounded border border-sage-100 bg-white p-4 text-sm">
          <div className="font-medium">
            {assess.data.compliance_pct}% compliant
            {assess.data.compliant ? " — no gaps" : ""}
          </div>
          {assess.data.missing_tasks.length > 0 && (
            <div className="mt-1 text-slate-600">
              Missing: {assess.data.missing_tasks.join(", ")}
            </div>
          )}
          {assess.data.blocking_gaps.length > 0 && (
            <div className="mt-1 text-red-700">
              Blocking (HIL required): {assess.data.blocking_gaps.join(", ")}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
