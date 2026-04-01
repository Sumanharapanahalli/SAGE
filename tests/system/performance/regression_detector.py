"""
Performance regression detector.

Loads stored baselines, runs fresh measurements, and fails if any
critical path has regressed by more than REGRESSION_THRESHOLD_PCT.

Usage:
  python -m tests.system.performance.regression_detector
  python -m tests.system.performance.regression_detector --threshold 15

Exit codes: 0 = pass, 1 = regression detected, 2 = no baselines found.
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tests.system.performance.baseline_collector import (
    BASELINE_DIR,
    CRITICAL_PATHS,
    collect_all,
)

REGRESSION_THRESHOLD_PCT = 20.0  # Flag if p99 degrades by more than 20%


def load_baseline(name: str) -> Optional[Dict[str, Any]]:
    path = BASELINE_DIR / f"{name}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def compare(baseline: Dict, current: Dict, threshold_pct: float) -> Dict[str, Any]:
    b_p99 = baseline.get("p99_ms", 0.0)
    c_p99 = current.get("p99_ms", 0.0)

    if b_p99 == 0:
        regression_pct = 0.0
    else:
        regression_pct = ((c_p99 - b_p99) / b_p99) * 100.0

    regressed = regression_pct > threshold_pct
    improved = regression_pct < -5.0  # >5% improvement worth noting

    return {
        "name": baseline["name"],
        "baseline_p99_ms": b_p99,
        "current_p99_ms": c_p99,
        "delta_ms": round(c_p99 - b_p99, 2),
        "regression_pct": round(regression_pct, 2),
        "threshold_pct": threshold_pct,
        "regressed": regressed,
        "improved": improved,
        "sla_p99_ms": baseline.get("sla_p99_ms", 500),
        "sla_breach": c_p99 > baseline.get("sla_p99_ms", 500),
    }


def print_report(comparisons: List[Dict]) -> None:
    print("\n" + "=" * 70)
    print("PERFORMANCE REGRESSION REPORT")
    print(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    regressions = [c for c in comparisons if c["regressed"]]
    sla_breaches = [c for c in comparisons if c["sla_breach"]]
    improvements = [c for c in comparisons if c["improved"]]

    for c in comparisons:
        status = "REGRESSED" if c["regressed"] else ("IMPROVED " if c["improved"] else "OK       ")
        sla_flag = " [SLA BREACH]" if c["sla_breach"] else ""
        print(
            f"  {status}  {c['name']:<25} "
            f"baseline={c['baseline_p99_ms']:>7.1f}ms  "
            f"current={c['current_p99_ms']:>7.1f}ms  "
            f"delta={c['delta_ms']:>+7.1f}ms  "
            f"({c['regression_pct']:>+6.1f}%){sla_flag}"
        )

    print("\nSUMMARY:")
    print(f"  Endpoints tested:  {len(comparisons)}")
    print(f"  Regressions:       {len(regressions)}")
    print(f"  SLA breaches:      {len(sla_breaches)}")
    print(f"  Improvements:      {len(improvements)}")
    print("=" * 70)

    if regressions:
        print("\nREGRESSIONS DETECTED:")
        for r in regressions:
            print(
                f"  {r['name']}: {r['baseline_p99_ms']:.1f}ms -> {r['current_p99_ms']:.1f}ms "
                f"(+{r['regression_pct']:.1f}% vs {r['threshold_pct']}% threshold)"
            )

    if sla_breaches:
        print("\nSLA BREACHES:")
        for r in sla_breaches:
            print(
                f"  {r['name']}: {r['current_p99_ms']:.1f}ms > SLA {r['sla_p99_ms']}ms"
            )


def save_comparison_report(comparisons: List[Dict]) -> None:
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": not any(c["regressed"] or c["sla_breach"] for c in comparisons),
        "regressions": [c for c in comparisons if c["regressed"]],
        "sla_breaches": [c for c in comparisons if c["sla_breach"]],
        "all_comparisons": comparisons,
    }
    report_file = BASELINE_DIR / "_regression_report.json"
    report_file.write_text(json.dumps(report, indent=2))
    print(f"\nReport saved to: {report_file}")


async def detect(threshold_pct: float = REGRESSION_THRESHOLD_PCT) -> Tuple[bool, List[Dict]]:
    # Check baselines exist
    existing = [p for p in CRITICAL_PATHS if (BASELINE_DIR / f"{p['name']}.json").exists()]
    if not existing:
        print("ERROR: No baselines found. Run baseline_collector.py first.", file=sys.stderr)
        sys.exit(2)

    print(f"Running fresh measurements for {len(existing)} endpoints (threshold: {threshold_pct}%)...")
    current_results = await collect_all()
    current_map = {r["name"]: r for r in current_results if not r.get("skipped")}

    comparisons = []
    for path_def in existing:
        name = path_def["name"]
        baseline = load_baseline(name)
        current = current_map.get(name)
        if baseline and current:
            comparisons.append(compare(baseline, current, threshold_pct))

    print_report(comparisons)
    save_comparison_report(comparisons)

    passed = not any(c["regressed"] or c["sla_breach"] for c in comparisons)
    return passed, comparisons


def main():
    parser = argparse.ArgumentParser(description="Detect performance regressions vs baseline")
    parser.add_argument(
        "--threshold",
        type=float,
        default=REGRESSION_THRESHOLD_PCT,
        help=f"Regression threshold %% (default: {REGRESSION_THRESHOLD_PCT})",
    )
    args = parser.parse_args()

    passed, comparisons = asyncio.run(detect(threshold_pct=args.threshold))
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
