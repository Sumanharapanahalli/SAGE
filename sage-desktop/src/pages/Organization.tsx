import { useEffect, useState } from "react";

import { toDesktopError } from "@/api/client";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import { useOrg, useReloadOrg, useUpdateOrg } from "@/hooks/useOrg";

/** Operator-owned org identity (name/mission/vision/core_values) that
 * shapes every solution's onboarding and agent context, plus a read-only
 * view of the cross-team routes declared across all solutions.
 *
 * Channel/solution/route CRUD (org.yaml's producers/consumers graph) is
 * out of scope for this pass — see src/interface/api.py's
 * /org/channels, /org/solutions, /org/routes for the follow-up surface. */
export default function Organization() {
  const query = useOrg();
  const update = useUpdateOrg();
  const reload = useReloadOrg();

  const [name, setName] = useState("");
  const [mission, setMission] = useState("");
  const [vision, setVision] = useState("");
  const [coreValues, setCoreValues] = useState("");
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    if (!initialized && query.data) {
      const org = query.data.org ?? {};
      setName(org.name ?? "");
      setMission(org.mission ?? "");
      setVision(org.vision ?? "");
      setCoreValues((org.core_values ?? []).join("\n"));
      setInitialized(true);
    }
  }, [initialized, query.data]);

  const handleSave = () => {
    update.mutate({
      name: name.trim() || undefined,
      mission: mission.trim() || undefined,
      vision: vision.trim() || undefined,
      core_values: coreValues.trim()
        ? coreValues
            .split("\n")
            .map((v) => v.trim())
            .filter(Boolean)
        : undefined,
    });
  };

  const loadError = query.error ? toDesktopError(query.error) : null;
  const saveError = update.error ? toDesktopError(update.error) : null;
  const reloadError = reload.error ? toDesktopError(reload.error) : null;
  const routes = query.data?.routes ?? [];

  if (query.isLoading) {
    return (
      <div className="p-6 text-sm text-slate-600">Loading organization…</div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-6">
      <div>
        <h2 className="font-semibold text-lg">Organization</h2>
        <p className="text-sm text-slate-600">
          Identity fields shape every solution&apos;s onboarding and agent
          context.
        </p>
      </div>

      <ErrorBanner error={loadError} />

      <div className="rounded border border-sage-100 bg-white p-4 space-y-4">
        <label className="block">
          <span className="block text-sm font-medium">Name</span>
          <input
            className="mt-1 w-full rounded border border-gray-300 p-2 text-sm"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Acme Corp"
          />
        </label>

        <label className="block">
          <span className="block text-sm font-medium">Mission</span>
          <textarea
            className="mt-1 w-full rounded border border-gray-300 p-2 text-sm"
            rows={3}
            value={mission}
            onChange={(e) => setMission(e.target.value)}
          />
        </label>

        <label className="block">
          <span className="block text-sm font-medium">Vision</span>
          <textarea
            className="mt-1 w-full rounded border border-gray-300 p-2 text-sm"
            rows={3}
            value={vision}
            onChange={(e) => setVision(e.target.value)}
          />
        </label>

        <label className="block">
          <span className="block text-sm font-medium">Core values</span>
          <p className="text-xs text-slate-500">One per line.</p>
          <textarea
            className="mt-1 w-full rounded border border-gray-300 p-2 text-sm"
            rows={4}
            value={coreValues}
            onChange={(e) => setCoreValues(e.target.value)}
          />
        </label>

        <div className="flex gap-3">
          <button
            type="button"
            onClick={handleSave}
            disabled={update.isPending}
            className="rounded bg-sage-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
          >
            {update.isPending ? "Saving…" : "Save"}
          </button>
          <button
            type="button"
            onClick={() => reload.mutate()}
            disabled={reload.isPending}
            className="rounded border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-50"
          >
            {reload.isPending ? "Reloading…" : "Reload"}
          </button>
        </div>
      </div>

      <ErrorBanner error={saveError} />
      <ErrorBanner error={reloadError} />

      <div className="rounded border border-sage-100 bg-white p-4">
        <div className="text-sm font-medium mb-2">Cross-team routes</div>
        {routes.length === 0 ? (
          <div className="text-sm text-slate-500">
            No cross-team routes declared.
          </div>
        ) : (
          <ul className="space-y-1 text-sm">
            {routes.map((r, i) => (
              <li key={i}>
                {r.source} → {r.target}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
