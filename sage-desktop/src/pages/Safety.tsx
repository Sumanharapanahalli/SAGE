import { useState } from "react";

import { toDesktopError } from "@/api/client";
import type { SafetyFmeaEntryInput, SafetyFtaNode } from "@/api/types";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import {
  useAsil,
  useFmea,
  useFta,
  useIec62304,
  useSil,
} from "@/hooks/useSafety";

/**
 * Functional safety derivation — the inverse of the Compliance page.
 *
 * /compliance takes the safety class as an INPUT ("which checklist do I owe
 * for CLASS_C?"). This DERIVES it ("what class/ASIL/SIL does this hazard
 * imply?"), over the stateless engine in src/core/functional_safety.py.
 *
 * Two deliberate divergences from the web UI's safety page, both of which are
 * bugs there and are pinned by tests here:
 *
 *   1. FTA posts the NESTED tree the engine can walk ({top_event, gate,
 *      children:[...]}), not a flat `gates` list. A flat list makes the engine
 *      silently return probability 0.0 and no cut sets.
 *   2. Results are read from the engine's REAL field names — `asil`, `sil`,
 *      `safety_class`, `required_processes`. The web page reads `asil_level`
 *      and `sil_level`, which the engine never emits, so its ASIL and SIL tabs
 *      render blank.
 *
 * Nothing auto-fires: every analysis is a mutation behind an explicit button,
 * since each is a pure function of operator-entered input.
 */

const TABS = [
  { id: "fmea", label: "FMEA" },
  { id: "fta", label: "FTA" },
  { id: "asil", label: "ASIL" },
  { id: "sil", label: "SIL" },
  { id: "iec62304", label: "IEC 62304" },
] as const;

type TabId = (typeof TABS)[number]["id"];

const SEVERITIES = ["S0", "S1", "S2", "S3"];
const EXPOSURES = ["E0", "E1", "E2", "E3", "E4"];
const CONTROLLABILITIES = ["C0", "C1", "C2", "C3"];
const RISK_LEVELS = [
  "death_possible",
  "serious_injury_possible",
  "injury_possible",
  "no_injury",
];

const EMPTY_ROW: SafetyFmeaEntryInput = {
  component: "",
  failure_mode: "",
  effect: "",
  severity: 5,
  occurrence: 5,
  detection: 5,
};

const inputCls =
  "mt-1 w-full rounded border border-sage-200 px-2 py-1 text-sm focus:border-sage-400 focus:outline-none";
const btnCls =
  "rounded bg-sage-500 px-4 py-2 text-sm font-medium text-white hover:bg-sage-600 disabled:opacity-50";

export default function Safety() {
  const [tab, setTab] = useState<TabId>("fmea");

  const fmea = useFmea();
  const fta = useFta();
  const asil = useAsil();
  const sil = useSil();
  const iec = useIec62304();

  // ── FMEA state ──────────────────────────────────────────────────────────
  const [rows, setRows] = useState<SafetyFmeaEntryInput[]>([{ ...EMPTY_ROW }]);
  const setRow = (i: number, patch: Partial<SafetyFmeaEntryInput>) =>
    setRows((prev) => prev.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  // ── FTA state ───────────────────────────────────────────────────────────
  const [topEvent, setTopEvent] = useState("");
  const [gate, setGate] = useState<"AND" | "OR">("OR");
  const [leaves, setLeaves] = useState([{ event: "", probability: 0.001 }]);
  const setLeaf = (i: number, patch: Partial<(typeof leaves)[number]>) =>
    setLeaves((prev) => prev.map((l, j) => (j === i ? { ...l, ...patch } : l)));

  // ── ASIL / SIL / IEC state ──────────────────────────────────────────────
  const [severity, setSeverity] = useState("S3");
  const [exposure, setExposure] = useState("E4");
  const [controllability, setControllability] = useState("C3");
  const [pfh, setPfh] = useState(1e-8);
  const [riskLevel, setRiskLevel] = useState(RISK_LEVELS[0]);

  const rawError =
    fmea.error ?? fta.error ?? asil.error ?? sil.error ?? iec.error ?? null;
  const error = rawError ? toDesktopError(rawError) : null;

  const runFtaAnalysis = () => {
    const tree: SafetyFtaNode = {
      top_event: topEvent,
      gate,
      // Every leaf carries BOTH `event` and `probability`: the engine keys the
      // probability roll-up off one and the minimal cut sets off the other, so
      // dropping either silently degrades one of the two results.
      children: leaves
        .filter((l) => l.event.trim())
        .map((l) => ({ event: l.event, probability: l.probability })),
    };
    fta.mutate(tree);
  };

  return (
    <div className="space-y-4 p-6">
      <p className="text-sm text-sage-700">
        Derive a safety classification from a hazard. Compliance asks which
        checklist a given class owes; this asks which class the hazard implies.
      </p>

      <div role="tablist" className="flex gap-1 border-b border-sage-100">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={
              tab === t.id
                ? "border-b-2 border-sage-500 px-4 py-2 text-sm font-medium text-sage-900"
                : "px-4 py-2 text-sm text-sage-700 hover:text-sage-900"
            }
          >
            {t.label}
          </button>
        ))}
      </div>

      <ErrorBanner error={error} />

      {/* ── FMEA ─────────────────────────────────────────────────────────── */}
      {tab === "fmea" && (
        <section className="space-y-4">
          {rows.map((row, i) => (
            <div
              key={i}
              className="grid grid-cols-2 gap-3 rounded border border-sage-100 p-3 md:grid-cols-3"
            >
              <label className="block text-xs text-sage-700">
                {i === 0 ? "Component" : `Component ${i + 1}`}
                <input
                  className={inputCls}
                  value={row.component}
                  onChange={(e) => setRow(i, { component: e.target.value })}
                />
              </label>
              <label className="block text-xs text-sage-700">
                {i === 0 ? "Failure mode" : `Failure mode ${i + 1}`}
                <input
                  className={inputCls}
                  value={row.failure_mode}
                  onChange={(e) => setRow(i, { failure_mode: e.target.value })}
                />
              </label>
              <label className="block text-xs text-sage-700">
                {i === 0 ? "Effect" : `Effect ${i + 1}`}
                <input
                  className={inputCls}
                  value={row.effect}
                  onChange={(e) => setRow(i, { effect: e.target.value })}
                />
              </label>
              {(["severity", "occurrence", "detection"] as const).map((f) => (
                <label key={f} className="block text-xs capitalize text-sage-700">
                  {i === 0 ? f : `${f} ${i + 1}`}
                  <input
                    type="number"
                    min={1}
                    max={10}
                    className={inputCls}
                    value={row[f]}
                    onChange={(e) =>
                      setRow(i, { [f]: Number(e.target.value) })
                    }
                  />
                </label>
              ))}
            </div>
          ))}

          <div className="flex gap-2">
            <button
              className="rounded border border-sage-200 px-3 py-2 text-sm text-sage-700 hover:bg-sage-50"
              onClick={() => setRows((p) => [...p, { ...EMPTY_ROW }])}
            >
              Add row
            </button>
            <button
              className={btnCls}
              disabled={fmea.isPending || !rows.some((r) => r.component.trim())}
              onClick={() =>
                fmea.mutate(rows.filter((r) => r.component.trim()))
              }
            >
              {fmea.isPending ? "Running…" : "Run FMEA"}
            </button>
          </div>

          {fmea.data && (
            <div className="space-y-2">
              {/* Max RPN is deliberately not repeated here — the table is
                  RPN-descending, so its top row already is the max. */}
              <div className="text-sm text-sage-700">
                Total entries: {fmea.data.summary.total_entries} · Action items:{" "}
                {fmea.data.summary.action_items}
              </div>
              <table className="w-full text-left text-sm">
                <thead className="text-xs uppercase text-sage-700">
                  <tr>
                    <th className="py-1">Component</th>
                    <th className="py-1">Failure mode</th>
                    <th className="py-1">RPN</th>
                    <th className="py-1">Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {fmea.data.entries.map((e) => (
                    <tr key={e.id} className="border-t border-sage-100">
                      <td className="py-1">{e.component}</td>
                      <td className="py-1">{e.failure_mode}</td>
                      <td className="py-1 font-medium">{e.rpn}</td>
                      <td className="py-1">{e.risk_level}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {/* ── FTA ──────────────────────────────────────────────────────────── */}
      {tab === "fta" && (
        <section className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-xs text-sage-700">
              Top event
              <input
                className={inputCls}
                value={topEvent}
                onChange={(e) => setTopEvent(e.target.value)}
              />
            </label>
            <label className="block text-xs text-sage-700">
              Gate
              <select
                className={inputCls}
                value={gate}
                onChange={(e) => setGate(e.target.value as "AND" | "OR")}
              >
                <option value="OR">OR</option>
                <option value="AND">AND</option>
              </select>
            </label>
          </div>

          {leaves.map((leaf, i) => (
            <div key={i} className="grid grid-cols-2 gap-3">
              <label className="block text-xs text-sage-700">
                {i === 0 ? "Event" : `Event ${i + 1}`}
                <input
                  className={inputCls}
                  value={leaf.event}
                  onChange={(e) => setLeaf(i, { event: e.target.value })}
                />
              </label>
              <label className="block text-xs text-sage-700">
                {i === 0 ? "Probability" : `Probability ${i + 1}`}
                <input
                  type="number"
                  step="any"
                  min={0}
                  className={inputCls}
                  value={leaf.probability}
                  onChange={(e) =>
                    setLeaf(i, { probability: Number(e.target.value) })
                  }
                />
              </label>
            </div>
          ))}

          <div className="flex gap-2">
            <button
              className="rounded border border-sage-200 px-3 py-2 text-sm text-sage-700 hover:bg-sage-50"
              onClick={() =>
                setLeaves((p) => [...p, { event: "", probability: 0.001 }])
              }
            >
              Add event
            </button>
            <button
              className={btnCls}
              disabled={fta.isPending || !topEvent.trim()}
              onClick={runFtaAnalysis}
            >
              {fta.isPending ? "Running…" : "Run FTA"}
            </button>
          </div>

          {fta.data && (
            <div className="space-y-2 text-sm">
              <div>
                Top-event probability:{" "}
                <span className="font-medium">{fta.data.probability}</span>
              </div>
              <div>
                <div className="text-xs uppercase text-sage-700">
                  Minimal cut sets
                </div>
                <ul className="list-inside list-disc">
                  {fta.data.minimal_cut_sets.map((cs, i) => (
                    <li key={i}>{cs.join(" AND ")}</li>
                  ))}
                </ul>
              </div>
              <div>
                <div className="text-xs uppercase text-sage-700">
                  Single-point failures
                </div>
                {fta.data.single_point_failures.length === 0 ? (
                  <div className="text-sage-700">None</div>
                ) : (
                  <ul className="list-inside list-disc">
                    {fta.data.single_point_failures.map((cs, i) => (
                      <li key={i}>{cs.join(", ")}</li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}
        </section>
      )}

      {/* ── ASIL ─────────────────────────────────────────────────────────── */}
      {tab === "asil" && (
        <section className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <label className="block text-xs text-sage-700">
              Severity
              <select
                className={inputCls}
                value={severity}
                onChange={(e) => setSeverity(e.target.value)}
              >
                {SEVERITIES.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </label>
            <label className="block text-xs text-sage-700">
              Exposure
              <select
                className={inputCls}
                value={exposure}
                onChange={(e) => setExposure(e.target.value)}
              >
                {EXPOSURES.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </label>
            <label className="block text-xs text-sage-700">
              Controllability
              <select
                className={inputCls}
                value={controllability}
                onChange={(e) => setControllability(e.target.value)}
              >
                {CONTROLLABILITIES.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </label>
          </div>
          <button
            className={btnCls}
            disabled={asil.isPending}
            onClick={() =>
              asil.mutate({ severity, exposure, controllability })
            }
          >
            {asil.isPending ? "Classifying…" : "Classify ASIL"}
          </button>

          {asil.data && (
            <div className="rounded border border-sage-100 p-4">
              <div className="text-xs uppercase text-sage-700">
                {asil.data.standard}
              </div>
              <div
                data-testid="asil-result"
                className="text-2xl font-bold text-sage-900"
              >
                ASIL {asil.data.asil}
              </div>
              <div className="mt-1 text-sm text-sage-700">
                {asil.data.description}
              </div>
            </div>
          )}
        </section>
      )}

      {/* ── SIL ──────────────────────────────────────────────────────────── */}
      {tab === "sil" && (
        <section className="space-y-4">
          <label className="block max-w-sm text-xs text-sage-700">
            Probability of dangerous failure per hour
            <input
              type="number"
              step="any"
              min={0}
              className={inputCls}
              value={pfh}
              onChange={(e) => setPfh(Number(e.target.value))}
            />
          </label>
          <button
            className={btnCls}
            disabled={sil.isPending}
            onClick={() => sil.mutate(pfh)}
          >
            {sil.isPending ? "Classifying…" : "Classify SIL"}
          </button>

          {sil.data && (
            <div className="rounded border border-sage-100 p-4">
              <div className="text-xs uppercase text-sage-700">
                {sil.data.standard}
              </div>
              <div
                data-testid="sil-result"
                className="text-2xl font-bold text-sage-900"
              >
                SIL {sil.data.sil}
              </div>
              <div className="mt-1 text-sm text-sage-700">
                {sil.data.description}
              </div>
            </div>
          )}
        </section>
      )}

      {/* ── IEC 62304 ────────────────────────────────────────────────────── */}
      {tab === "iec62304" && (
        <section className="space-y-4">
          <label className="block max-w-sm text-xs text-sage-700">
            Risk level
            <select
              className={inputCls}
              value={riskLevel}
              onChange={(e) => setRiskLevel(e.target.value)}
            >
              {RISK_LEVELS.map((r) => (
                <option key={r}>{r}</option>
              ))}
            </select>
          </label>
          <button
            className={btnCls}
            disabled={iec.isPending}
            onClick={() => iec.mutate(riskLevel)}
          >
            {iec.isPending ? "Classifying…" : "Classify safety class"}
          </button>

          {iec.data && (
            <div className="rounded border border-sage-100 p-4">
              <div className="text-xs uppercase text-sage-700">
                {iec.data.standard}
              </div>
              <div
                data-testid="iec62304-result"
                className="text-2xl font-bold text-sage-900"
              >
                Class {iec.data.safety_class}
              </div>
              <div className="mt-1 text-sm text-sage-700">
                {iec.data.description}
              </div>
              <div className="mt-3 text-xs uppercase text-sage-700">
                Required processes
              </div>
              <ul className="list-inside list-disc text-sm">
                {iec.data.required_processes.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
