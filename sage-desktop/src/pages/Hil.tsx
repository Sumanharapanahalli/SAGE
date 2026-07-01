import { useState } from "react";

import { toDesktopError } from "@/api/client";
import type { HILTransportName } from "@/api/types";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import {
  useHilConnect,
  useHilReport,
  useHilRunSuite,
  useHilStatus,
} from "@/hooks/useHil";

const TRANSPORTS: HILTransportName[] = ["mock", "serial", "jlink", "can", "openocd"];
const STANDARDS = ["IEC62304", "DO178C", "EN50128", "ISO26262", "IEC62443"];

const DEFAULT_TESTS = `[
  {
    "id": "TC-001",
    "name": "Power-on self test",
    "requirement_id": "REQ-001",
    "description": "Device boots cleanly",
    "procedure": ["Power on", "Observe LED"],
    "expected_result": "LED green within 2s"
  }
]`;

/** Transport-specific config fields. Only the fields relevant to the
 * selected transport are shown — mock needs none. */
function TransportConfigFields({
  transport,
  config,
  onChange,
}: {
  transport: HILTransportName;
  config: Record<string, string>;
  onChange: (key: string, value: string) => void;
}) {
  const field = (key: string, label: string, placeholder = "") => (
    <label className="block text-xs">
      <span className="block font-medium">{label}</span>
      <input
        className="mt-1 w-full rounded border border-gray-300 p-1.5 text-sm"
        value={config[key] ?? ""}
        placeholder={placeholder}
        onChange={(e) => onChange(key, e.target.value)}
      />
    </label>
  );

  if (transport === "serial") {
    return (
      <div className="grid grid-cols-2 gap-2">
        {field("port", "Port", "/dev/ttyUSB0")}
        {field("baud_rate", "Baud rate", "115200")}
      </div>
    );
  }
  if (transport === "jlink") {
    return (
      <div className="grid grid-cols-2 gap-2">
        {field("device", "Device")}
        {field("serial_number", "Serial number")}
        {field("speed", "Speed (kHz)", "4000")}
      </div>
    );
  }
  if (transport === "can") {
    return (
      <div className="grid grid-cols-2 gap-2">
        {field("interface", "Interface", "socketcan")}
        {field("channel", "Channel", "can0")}
        {field("bitrate", "Bitrate", "500000")}
      </div>
    );
  }
  if (transport === "openocd") {
    return field("openocd_config", "OpenOCD config", "board/stm32f4discovery.cfg");
  }
  return null;
}

function parseTestCases(input: string) {
  const trimmed = input.trim();
  if (!trimmed) return null;
  try {
    const parsed: unknown = JSON.parse(trimmed);
    if (!Array.isArray(parsed)) return null;
    return parsed;
  } catch {
    return null;
  }
}

/** Connect to a HIL hardware transport, run test suites, and generate
 * regulatory evidence reports — all as explicit operator actions. Never
 * auto-connects: connecting can spawn subprocesses (JLinkExe/openocd) or
 * open a real serial/CAN handle. */
export default function Hil() {
  const status = useHilStatus();
  const connect = useHilConnect();
  const runSuite = useHilRunSuite();

  const [transport, setTransport] = useState<HILTransportName>("mock");
  const [config, setConfig] = useState<Record<string, string>>({});
  const [testsInput, setTestsInput] = useState(DEFAULT_TESTS);
  const [testsError, setTestsError] = useState("");
  const [standard, setStandard] = useState(STANDARDS[0]);
  const [reportRequested, setReportRequested] = useState(false);

  const sessionId = status.data?.session_id ?? "";
  const report = useHilReport(reportRequested ? sessionId : "", standard);

  const statusError = status.error ? toDesktopError(status.error) : null;
  const connectError = connect.error ? toDesktopError(connect.error) : null;
  const runError = runSuite.error ? toDesktopError(runSuite.error) : null;
  const reportError = report.error ? toDesktopError(report.error) : null;

  const handleConnect = () => {
    connect.mutate({ transport, config });
  };

  const handleRunSuite = () => {
    const tests = parseTestCases(testsInput);
    if (tests === null) {
      setTestsError("Test cases must be valid JSON (an array of objects).");
      return;
    }
    setTestsError("");
    runSuite.mutate({ tests: tests as never, transport, config });
  };

  const handleGenerateReport = () => {
    setReportRequested(true);
  };

  return (
    <div className="p-6 space-y-4">
      <h2 className="font-semibold text-lg">HIL</h2>
      <p className="text-sm text-slate-500">
        Hardware-in-the-Loop test runner and regulatory evidence
        generation. Connecting to real hardware transports is always an
        explicit action.
      </p>

      <ErrorBanner error={statusError} />

      <div className="rounded border border-sage-100 bg-white p-4 text-sm space-y-1">
        <div className="font-medium">Status</div>
        {status.data?.connected ? (
          <div>
            Connected — transport <span className="font-mono">{status.data.transport}</span>,
            session <span className="font-mono">{status.data.session_id}</span>,{" "}
            {status.data.tests_run} test(s) run
          </div>
        ) : (
          <div className="text-slate-500">Not connected. {status.data?.message ?? ""}</div>
        )}
      </div>

      <div className="rounded border border-sage-100 bg-white p-4 space-y-3">
        <div className="font-medium text-sm">Connect</div>
        <label className="block text-xs">
          <span className="block font-medium">Transport</span>
          <select
            className="mt-1 rounded border border-gray-300 p-1.5 text-sm"
            value={transport}
            onChange={(e) => {
              setTransport(e.target.value as HILTransportName);
              setConfig({});
            }}
          >
            {TRANSPORTS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <TransportConfigFields
          transport={transport}
          config={config}
          onChange={(key, value) => setConfig((prev) => ({ ...prev, [key]: value }))}
        />
        <button
          type="button"
          onClick={handleConnect}
          disabled={connect.isPending}
          className="rounded bg-sage-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {connect.isPending ? "Connecting…" : "Connect"}
        </button>
        <ErrorBanner error={connectError} />
      </div>

      <div className="rounded border border-sage-100 bg-white p-4 space-y-3">
        <div className="font-medium text-sm">Run suite</div>
        <label className="block text-xs">
          <span className="block font-medium">Test cases (JSON)</span>
          <textarea
            className="mt-1 block w-full rounded border border-gray-300 p-2 font-mono text-xs"
            rows={8}
            value={testsInput}
            onChange={(e) => setTestsInput(e.target.value)}
          />
        </label>
        {testsError && (
          <div role="alert" className="text-xs text-red-700">
            {testsError}
          </div>
        )}
        <button
          type="button"
          onClick={handleRunSuite}
          disabled={runSuite.isPending}
          className="rounded bg-sage-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {runSuite.isPending ? "Running…" : "Run suite"}
        </button>
        <ErrorBanner error={runError} />
        {runSuite.data && (
          <div className="text-sm">
            {runSuite.data.passed} / {runSuite.data.total} passed
            {" "}({runSuite.data.pass_rate}%)
          </div>
        )}
      </div>

      <div className="rounded border border-sage-100 bg-white p-4 space-y-3">
        <div className="font-medium text-sm">Regulatory evidence report</div>
        <label className="block text-xs">
          <span className="block font-medium">Standard</span>
          <select
            className="mt-1 rounded border border-gray-300 p-1.5 text-sm"
            value={standard}
            onChange={(e) => setStandard(e.target.value)}
          >
            {STANDARDS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={handleGenerateReport}
          disabled={!sessionId || report.isFetching}
          className="rounded bg-sage-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {report.isFetching ? "Generating…" : "Generate report"}
        </button>
        {!sessionId && (
          <div className="text-xs text-slate-500">
            Run a suite first to generate a session-scoped report.
          </div>
        )}
        <ErrorBanner error={reportError} />
        {report.data && (
          <div className="text-sm space-y-1">
            <div className="font-medium">{report.data.standard_full_name}</div>
            <div>
              {report.data.summary.passed} / {report.data.summary.total_tests} passed —{" "}
              {report.data.summary.overall_status}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
