import {
  useSetTelemetryEnabled,
  useTelemetryStatus,
} from "@/hooks/useTelemetry";

export function TelemetryPanel() {
  const status = useTelemetryStatus();
  const toggle = useSetTelemetryEnabled();

  if (status.isLoading) return <p className="text-sm text-gray-600">Loading…</p>;
  if (status.isError)
    return (
      <p className="text-sm text-red-700">
        Telemetry status unavailable: {status.error.kind}
      </p>
    );

  const data = status.data!;

  return (
    <div className="space-y-3">
      <label className="flex items-start gap-3">
        <input
          type="checkbox"
          className="mt-1 h-4 w-4"
          checked={data.enabled}
          disabled={toggle.isPending}
          onChange={(e) => toggle.mutate(e.target.checked)}
        />
        <span className="text-sm">
          <span className="font-medium">Send anonymous usage data</span>
          <br />
          <span className="text-gray-600">
            Only event names and non-identifying fields from the allowlist
            below are recorded. Disabled by default.
          </span>
        </span>
      </label>

      {data.enabled && data.anon_id && (
        <p className="text-xs text-gray-500">
          Anonymous ID:{" "}
          <span className="font-mono">{data.anon_id}</span>
        </p>
      )}

      <details className="text-xs text-gray-600">
        <summary className="cursor-pointer select-none">
          What gets sent?
        </summary>
        <div className="mt-2 space-y-1">
          <p>
            <strong>Events:</strong>{" "}
            <span className="font-mono">{data.allowed_events.join(", ")}</span>
          </p>
          <p>
            <strong>Fields:</strong>{" "}
            <span className="font-mono">{data.allowed_fields.join(", ")}</span>
          </p>
          <p className="mt-1">
            Anything not listed above is dropped before the event is written.
          </p>
        </div>
      </details>

      {toggle.isError && (
        <p className="text-sm text-red-700">
          Could not update telemetry setting: {toggle.error.kind}
        </p>
      )}
    </div>
  );
}
