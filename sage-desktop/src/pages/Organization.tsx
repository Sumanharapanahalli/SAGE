import { useEffect, useState } from "react";

import { toDesktopError } from "@/api/client";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import {
  useAddOrgRoute,
  useCreateOrgChannel,
  useDeleteOrgChannel,
  useDeleteOrgRoute,
  useOrg,
  useReloadOrg,
  useUpdateOrg,
} from "@/hooks/useOrg";

/** Operator-owned org identity (name/mission/vision/core_values) that
 * shapes every solution's onboarding and agent context, plus a read-only
 * view of the cross-team routes declared across all solutions.
 *
 * Channel/solution/route CRUD (org.yaml's producers/consumers graph) is
 * out of scope for this pass — see src/interface/api.py's
 * Routes and channels are editable here. Routes live in each solution's own
 * project.yaml (not org.yaml), so adding one names the SOURCE solution. */
const inputCls =
  "mt-1 block rounded border border-sage-200 px-2 py-1 text-sm focus:border-sage-400 focus:outline-none";

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
  // knowledge_channels is a read-only passthrough on OrgIdentity, so it is not
  // in the typed shape — read it defensively.
  const channelNames = Object.keys(
    ((query.data?.org ?? {}) as { knowledge_channels?: Record<string, unknown> })
      .knowledge_channels ?? {},
  );

  const addRoute = useAddOrgRoute();
  const deleteRoute = useDeleteOrgRoute();
  const createChannel = useCreateOrgChannel();
  const deleteChannel = useDeleteOrgChannel();

  const [routeSource, setRouteSource] = useState("");
  const [routeTarget, setRouteTarget] = useState("");
  const [channelName, setChannelName] = useState("");

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
        <div className="mb-2 text-sm font-medium">Cross-team routes</div>
        {routes.length === 0 ? (
          <div className="text-sm text-slate-500">
            No cross-team routes declared.
          </div>
        ) : (
          <ul className="space-y-1 text-sm">
            {routes.map((r, i) => (
              <li key={i} className="flex items-center gap-2">
                <span>
                  {r.source} → {r.target}
                </span>
                <button
                  className="text-xs text-red-700 hover:underline"
                  onClick={() =>
                    deleteRoute.mutate({ solution: r.source, target: r.target })
                  }
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="mt-3 flex flex-wrap items-end gap-2">
          <label className="text-xs text-sage-700">
            From solution
            <input
              className={inputCls}
              value={routeSource}
              onChange={(e) => setRouteSource(e.target.value)}
            />
          </label>
          <label className="text-xs text-sage-700">
            To solution
            <input
              className={inputCls}
              value={routeTarget}
              onChange={(e) => setRouteTarget(e.target.value)}
            />
          </label>
          <button
            className="rounded bg-sage-500 px-3 py-2 text-sm font-medium text-white hover:bg-sage-600 disabled:opacity-50"
            disabled={
              addRoute.isPending || !routeSource.trim() || !routeTarget.trim()
            }
            onClick={() =>
              addRoute.mutate(
                { solution: routeSource, target: routeTarget },
                {
                  onSuccess: () => {
                    setRouteSource("");
                    setRouteTarget("");
                  },
                },
              )
            }
          >
            Add route
          </button>
        </div>
      </div>

      <div className="rounded border border-sage-100 bg-white p-4">
        <div className="mb-2 text-sm font-medium">Knowledge channels</div>
        {channelNames.length === 0 ? (
          <div className="text-sm text-slate-500">
            No knowledge channels defined.
          </div>
        ) : (
          <ul className="space-y-1 text-sm">
            {channelNames.map((name) => (
              <li key={name} className="flex items-center gap-2">
                <span>{name}</span>
                <button
                  className="text-xs text-red-700 hover:underline"
                  onClick={() => deleteChannel.mutate(name)}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="mt-3 flex flex-wrap items-end gap-2">
          <label className="text-xs text-sage-700">
            Channel name
            <input
              className={inputCls}
              value={channelName}
              onChange={(e) => setChannelName(e.target.value)}
            />
          </label>
          <button
            className="rounded bg-sage-500 px-3 py-2 text-sm font-medium text-white hover:bg-sage-600 disabled:opacity-50"
            disabled={createChannel.isPending || !channelName.trim()}
            onClick={() =>
              createChannel.mutate(
                { name: channelName },
                { onSuccess: () => setChannelName("") },
              )
            }
          >
            Add channel
          </button>
        </div>
      </div>
    </div>
  );
}
