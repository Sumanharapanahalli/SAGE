import { ErrorBanner } from "@/components/layout/ErrorBanner";
import { useMonitorStatus, useSchedulerStatus } from "@/hooks/useMonitor";

/** MonitorAgent's polling threads (Teams / Metabase / GitLab) — a
 * legitimately-often-off subsystem outside of a fully-configured
 * deployment, so "not running" renders as a clean status line, not an
 * error banner. A real transport failure (sidecar down, RpcError) still
 * surfaces via ErrorBanner. */
function MonitorAgentCard() {
  const { data, error, isLoading } = useMonitorStatus();

  return (
    <div className="rounded border border-sage-100 bg-white p-4">
      <h3 className="mb-2 text-sm font-medium text-slate-500">Monitor Agent</h3>
      <ErrorBanner error={error ?? null} />
      {isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {data && !data.running && (
        <p className="text-sm text-slate-500">Not active — no pollers running.</p>
      )}
      {data && data.running && (
        <dl className="space-y-1 text-sm">
          <div className="flex justify-between">
            <dt className="text-slate-500">Active threads</dt>
            <dd className="font-medium">{data.thread_count ?? 0}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">Threads</dt>
            <dd className="font-medium">
              {(data.active_threads ?? []).join(", ") || "—"}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">Messages seen</dt>
            <dd className="font-medium">{data.seen_messages ?? 0}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">Issues seen</dt>
            <dd className="font-medium">{data.seen_issues ?? 0}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">Teams configured</dt>
            <dd className="font-medium">{data.teams_configured ? "yes" : "no"}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">Metabase configured</dt>
            <dd className="font-medium">{data.metabase_configured ? "yes" : "no"}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">GitLab configured</dt>
            <dd className="font-medium">{data.gitlab_configured ? "yes" : "no"}</dd>
          </div>
        </dl>
      )}
    </div>
  );
}

/** TaskScheduler's running state + schedule count — same graceful
 * degradation as MonitorAgentCard: "not running" is a clean status line. */
function SchedulerCard() {
  const { data, error, isLoading } = useSchedulerStatus();

  return (
    <div className="rounded border border-sage-100 bg-white p-4">
      <h3 className="mb-2 text-sm font-medium text-slate-500">Task Scheduler</h3>
      <ErrorBanner error={error ?? null} />
      {isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {data && !data.running && (
        <p className="text-sm text-slate-500">Not active — scheduler is not running.</p>
      )}
      {data && data.running && (
        <dl className="space-y-1 text-sm">
          <div className="flex justify-between">
            <dt className="text-slate-500">Scheduled tasks</dt>
            <dd className="font-medium">{data.scheduled_count ?? 0}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">Next check in</dt>
            <dd className="font-medium">{data.next_check_in_seconds ?? 0}s</dd>
          </div>
        </dl>
      )}
    </div>
  );
}

/** Read-only visibility into the two background subsystems the desktop
 * sidecar can host: the MonitorAgent's event pollers and the cron-like
 * TaskScheduler. Both are read via the sidecar's monitor.* RPC methods,
 * which degrade gracefully on any construction/call failure — so a
 * "not active" subsystem always renders as a calm status line, never an
 * error banner. */
export default function Monitor() {
  return (
    <div className="p-6 space-y-4">
      <h2 className="font-semibold text-lg">Monitor</h2>
      <div className="grid gap-4 md:grid-cols-2">
        <MonitorAgentCard />
        <SchedulerCard />
      </div>
    </div>
  );
}
