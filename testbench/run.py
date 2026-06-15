"""SAGE Test Bench — a generic, config-driven test runner for ANY solution.

One bench, many project types. A solution declares what to test in a
`testbench.yaml` (or solutions/<name>/testbench.yaml); this runner dispatches the
declared suites to pluggable DRIVERS and aggregates one report.

Drivers (testbench/drivers/):
  api       — functional/integration/system checks against a running REST/HTTP backend
  load      — N concurrent user journeys + a read-throughput burst
  browser   — headless-Chromium UI smoke (every view renders, no console errors)
  mobile    — mobile app tests (flutter test / appium) — for mobile solutions
  embedded  — hardware-in-the-loop / firmware unit tests (serial, J-Link) — for embedded

Each Python driver exposes `run(cfg: dict) -> dict` returning
  {driver, passed, failed, skipped, checks: [{name, status, detail}], note}.
The browser driver is Node; a thin wrapper shells out to it.

Usage:
  python testbench/run.py --config testbench/configs/poseengine.yaml [--suite api,load]
  python testbench/run.py --solution poseengine            # uses solutions/poseengine/testbench.yaml
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent

try:
    import yaml
except ImportError:
    print("PyYAML required: pip install pyyaml", file=sys.stderr)
    sys.exit(2)

# Driver registry — name -> module under testbench.drivers.
DRIVERS = {
    "api": "drivers.api",
    "load": "drivers.load",
    "browser": "drivers.browser",
    "mobile": "drivers.mobile",
    "embedded": "drivers.embedded",
}


def _load_config(args) -> dict:
    if args.config:
        path = Path(args.config)
    elif args.solution:
        path = REPO / "solutions" / args.solution / "testbench.yaml"
        if not path.exists():
            path = ROOT / "configs" / f"{args.solution}.yaml"
    else:
        raise SystemExit("provide --config <file> or --solution <name>")
    if not path.exists():
        raise SystemExit(f"config not found: {path}")
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg["_config_path"] = str(path)
    return cfg


def main():
    ap = argparse.ArgumentParser(description="SAGE generic test bench")
    ap.add_argument("--config", help="path to a testbench.yaml")
    ap.add_argument("--solution", help="solution name (uses its testbench.yaml)")
    ap.add_argument("--suite", help="comma-list to run a subset (default: all declared)")
    ap.add_argument("--report", help="write a markdown report to this path")
    args = ap.parse_args()

    cfg = _load_config(args)
    project = cfg.get("project", "unknown")
    suites = cfg.get("suites", {})
    only = set(s.strip() for s in args.suite.split(",")) if args.suite else None

    sys.path.insert(0, str(ROOT))  # so `import drivers.*` resolves

    print(f"\n=== SAGE Test Bench :: {project} ({cfg['_config_path']}) ===")
    results = []
    for name, scfg in suites.items():
        if only and name not in only:
            continue
        if not scfg or scfg.get("enabled") is False:
            print(f"\n--- suite '{name}': skipped (disabled) ---")
            continue
        if name not in DRIVERS:
            print(f"\n--- suite '{name}': no driver, skipped ---")
            continue
        print(f"\n--- suite '{name}' ---")
        t0 = time.perf_counter()
        try:
            driver = importlib.import_module(DRIVERS[name])
            res = driver.run(scfg) or {}
        except Exception as e:  # noqa: BLE001 - a driver failure shouldn't abort the bench
            res = {"driver": name, "passed": 0, "failed": 1, "skipped": 0,
                   "checks": [{"name": f"{name} driver", "status": "FAIL", "detail": f"{type(e).__name__}: {e}"}],
                   "note": "driver raised"}
        res["driver"] = name
        res["duration_s"] = round(time.perf_counter() - t0, 1)
        results.append(res)
        for c in res.get("checks", []):
            print(f"  [{c['status']}] {c['name']}" + (f"  - {c['detail']}" if c.get('detail') else ""))
        print(f"  => {res.get('passed',0)} pass / {res.get('failed',0)} fail / "
              f"{res.get('skipped',0)} skip  ({res['duration_s']}s)")

    total_p = sum(r.get("passed", 0) for r in results)
    total_f = sum(r.get("failed", 0) for r in results)
    print(f"\n=== BENCH SUMMARY :: {project} :: {total_p} pass / {total_f} fail "
          f"across {len(results)} suite(s) ===")

    if args.report:
        _write_report(Path(args.report), project, cfg, results, total_p, total_f)
        print(f"report: {args.report}")

    sys.exit(1 if total_f else 0)


def _write_report(path, project, cfg, results, total_p, total_f):
    lines = [f"# Test Bench Report — {project}\n",
             f"Config: `{cfg['_config_path']}` · **{total_p} pass / {total_f} fail**\n"]
    for r in results:
        lines.append(f"## {r['driver']} — {r.get('passed',0)} pass / {r.get('failed',0)} fail "
                     f"({r.get('duration_s','?')}s)")
        if r.get("note"):
            lines.append(f"_{r['note']}_\n")
        for c in r.get("checks", []):
            lines.append(f"- **[{c['status']}]** {c['name']}" + (f" — {c['detail']}" if c.get('detail') else ""))
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
