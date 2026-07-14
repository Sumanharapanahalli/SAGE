import { useEffect, useState } from "react";

import { ErrorBanner } from "@/components/layout/ErrorBanner";
import {
  useRegulatoryAssess,
  useRegulatoryChecklist,
  useRegulatoryGapAnalysis,
  useRegulatoryRoadmap,
  useRegulatoryStandards,
} from "@/hooks/useRegulatory";
import type { ProductProfile } from "@/api/types";

/** Split a comma/newline separated operator input into a clean list. */
function toList(raw: string): string[] {
  return raw
    .split(/[,\n]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

/**
 * Multi-standard REGULATORY assessment — the traceability half that
 * `compliance.*` (5 bundled engineering domains) does not cover: a global
 * standards registry, per-standard requirement checklists, artifact gap
 * analysis against a real product profile, and a phased submission roadmap.
 */
export default function Regulatory() {
  const standards = useRegulatoryStandards();
  const [standardId, setStandardId] = useState("");

  const [productName, setProductName] = useState("");
  const [regions, setRegions] = useState("us, eu");
  const [artifacts, setArtifacts] = useState("");
  const [usesAiMl, setUsesAiMl] = useState(false);

  // Default to the first standard once the registry loads.
  useEffect(() => {
    if (!standardId && standards.data && standards.data.standards.length > 0) {
      setStandardId(standards.data.standards[0].id);
    }
  }, [standardId, standards.data]);

  const checklist = useRegulatoryChecklist(standardId);
  const assess = useRegulatoryAssess();
  const gap = useRegulatoryGapAnalysis();
  const roadmap = useRegulatoryRoadmap();

  const product: ProductProfile = {
    product_name: productName,
    target_regions: toList(regions),
    existing_artifacts: toList(artifacts),
    uses_ai_ml: usesAiMl,
  };

  const assessments = assess.data
    ? Object.values(assess.data.assessments)
    : [];

  return (
    <div className="p-6 space-y-4">
      <h2 className="font-semibold text-lg">Regulatory</h2>

      {standards.isLoading && (
        <div className="text-sm text-slate-500">Loading standards…</div>
      )}

      <ErrorBanner error={standards.error ?? checklist.error ?? null} />

      {/* --- Product profile --------------------------------------------- */}
      <div className="rounded border border-sage-100 bg-white p-4 space-y-3">
        <div className="text-sm font-medium">Product profile</div>
        <div className="flex flex-wrap gap-3">
          <label className="block">
            <span className="block text-sm font-medium">Product name</span>
            <input
              className="mt-1 rounded border border-gray-300 p-2 text-sm"
              value={productName}
              onChange={(e) => setProductName(e.target.value)}
            />
          </label>
          <label className="block">
            <span className="block text-sm font-medium">
              Target regions (comma separated)
            </span>
            <input
              className="mt-1 rounded border border-gray-300 p-2 text-sm"
              value={regions}
              onChange={(e) => setRegions(e.target.value)}
            />
          </label>
          <label className="block">
            <span className="block text-sm font-medium">
              Existing artifacts (comma separated)
            </span>
            <input
              className="mt-1 w-80 rounded border border-gray-300 p-2 text-sm"
              value={artifacts}
              onChange={(e) => setArtifacts(e.target.value)}
            />
          </label>
          <label className="flex items-center gap-2 self-end pb-2 text-sm">
            <input
              type="checkbox"
              checked={usesAiMl}
              onChange={(e) => setUsesAiMl(e.target.checked)}
            />
            <span>Uses AI/ML</span>
          </label>
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => assess.mutate({ product })}
            disabled={assess.isPending}
            className="rounded bg-sage-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
          >
            {assess.isPending ? "Assessing…" : "Assess compliance"}
          </button>
          <button
            type="button"
            onClick={() => roadmap.mutate(product)}
            disabled={roadmap.isPending}
            className="rounded border border-sage-300 px-3 py-1.5 text-sm text-sage-900 disabled:opacity-50"
          >
            {roadmap.isPending ? "Generating…" : "Submission roadmap"}
          </button>
        </div>
      </div>

      {/* --- Standard picker + checklist ---------------------------------- */}
      <div className="rounded border border-sage-100 bg-white p-4 space-y-3">
        <label className="block">
          <span className="block text-sm font-medium">Standard</span>
          <select
            className="mt-1 rounded border border-gray-300 p-2 text-sm"
            value={standardId}
            onChange={(e) => setStandardId(e.target.value)}
          >
            {(standards.data?.standards ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>

        {checklist.isLoading && standardId && (
          <div className="text-sm text-slate-500">Loading checklist…</div>
        )}

        {checklist.data && (
          <div>
            <div className="mb-2 text-sm text-slate-500">
              {checklist.data.standard_name} — {checklist.data.items.length}{" "}
              requirements
            </div>
            <ul className="space-y-1">
              {checklist.data.items.map((item) => (
                <li key={item.id} className="text-sm">
                  <span className="font-mono text-xs text-slate-400">
                    {item.id}
                  </span>{" "}
                  {item.requirement}
                  <span className="ml-1 text-xs text-slate-500">
                    (evidence: {item.evidence_needed.join(", ")})
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <button
          type="button"
          onClick={() => gap.mutate({ product, standard_id: standardId })}
          disabled={gap.isPending || !standardId}
          className="rounded border border-sage-300 px-3 py-1.5 text-sm text-sage-900 disabled:opacity-50"
        >
          {gap.isPending ? "Analyzing…" : "Gap analysis"}
        </button>
      </div>

      <ErrorBanner
        error={assess.error ?? gap.error ?? roadmap.error ?? null}
      />

      {/* --- Assessment ---------------------------------------------------- */}
      {assess.data && (
        <div className="rounded border border-sage-100 bg-white p-4 text-sm">
          <div className="font-medium">
            Overall score: {assess.data.overall_score}% across{" "}
            {assess.data.standards_assessed} standards
          </div>
          <ul className="mt-2 space-y-1">
            {assessments.map((a) => (
              <li key={a.standard_id} className="flex flex-wrap gap-2">
                <span className="font-medium">{a.standard_name}</span>
                <span className="text-slate-600">{a.compliance_score}%</span>
                {a.missing_artifacts.length > 0 && (
                  <span className="text-red-700">
                    missing: {a.missing_artifacts.join(", ")}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* --- Gap analysis --------------------------------------------------- */}
      {gap.data && (
        <div className="rounded border border-sage-100 bg-white p-4 text-sm">
          <div className="font-medium">
            Gap analysis — {gap.data.standard_name}
          </div>
          <ul className="mt-2 space-y-1">
            {gap.data.gaps.map((g) => (
              <li key={g.requirement} className="flex flex-wrap gap-2">
                <span
                  className={
                    g.status === "met"
                      ? "text-green-700"
                      : g.status === "partial"
                        ? "text-amber-700"
                        : "text-red-700"
                  }
                >
                  {g.status}
                </span>
                <span>{g.requirement}</span>
                <span className="text-xs text-slate-500">
                  {g.priority} · {g.remediation}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* --- Roadmap -------------------------------------------------------- */}
      {roadmap.data && (
        <div className="rounded border border-sage-100 bg-white p-4 text-sm">
          <div className="font-medium">
            Submission roadmap — {roadmap.data.total_estimated_weeks} weeks
          </div>
          <ul className="mt-2 space-y-2">
            {roadmap.data.phases.map((p) => (
              <li key={p.phase_name}>
                <div className="font-medium">
                  {p.phase_name} ({p.estimated_weeks} weeks)
                </div>
                <div className="text-slate-600">{p.description}</div>
                <div className="text-xs text-slate-500">
                  Standards: {p.standards.join(", ")}
                </div>
                <div className="text-xs text-slate-500">
                  Deliverables: {p.deliverables.join(", ")}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
