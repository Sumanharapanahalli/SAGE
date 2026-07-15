#!/usr/bin/env python3
"""Measure how good SAGE actually is — with numbers, not opinions.

The Agent Gym is the one instrument in SAGE that produces GROUND TRUTH about agent
quality: an agent plays a real exercise, the output is mechanically graded (did it
execute? did it produce artifacts?), an N-critic panel scores it, the agent reflects,
and a Glicko rating moves. That is a measurement, not a review.

It had never been run. The exercise catalog held 0 rows until it was first instantiated
(it self-seeds 661 exercises across 11 domains), and the Gemini critic was silently
timing out at 30s — so the "panel" was quietly a single judge.

This runs the gym across roles with the full cross-vendor panel
(Claude primary + Gemini + local Qwen) and writes an honest scoreboard: where each role
is strong, where it is weak, and what the agents themselves said they got wrong.

    python scripts/gym_benchmark.py --roles developer,analyst,planner --per-role 2
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


def main() -> int:
    ap = argparse.ArgumentParser(description="Benchmark SAGE agents in the gym")
    ap.add_argument("--roles", default="developer,analyst,planner")
    ap.add_argument("--per-role", type=int, default=2)
    ap.add_argument("--difficulty", default="beginner")
    ap.add_argument("--out", default="docs/GYM_BENCHMARK.md")
    args = ap.parse_args()

    from src.core.agent_gym import AgentGym
    from src.core.exercise_catalog import ExerciseCatalog

    cat = ExerciseCatalog()
    print(f"exercise catalog: {cat.count()}", flush=True)

    gym = AgentGym()
    roles = [r.strip() for r in args.roles.split(",") if r.strip()]
    rows: list[dict] = []

    for role in roles:
        for i in range(args.per_role):
            t0 = time.time()
            print(f"\n=== {role} #{i + 1} ===", flush=True)
            try:
                s = gym.train(role=role, difficulty=args.difficulty)
                d = s.to_dict()
            except Exception as e:  # noqa: BLE001
                print(f"  ERROR: {e}", flush=True)
                rows.append({"role": role, "status": "error", "error": str(e)[:200]})
                continue

            grade = d.get("grade") or {}
            critics = d.get("critic_reviews") or {}
            row = {
                "role": role,
                "status": d.get("status"),
                "exercise_id": d.get("exercise_id"),
                "skill": d.get("skill_name"),
                "difficulty": d.get("difficulty"),
                "passed": grade.get("passed"),
                "grade_score": grade.get("score"),
                "critics": critics,
                "elo_before": d.get("elo_before"),
                "elo_after": d.get("elo_after"),
                "reflection": (d.get("reflection") or "")[:400],
                "improvement_plan": (d.get("improvement_plan") or [])[:3],
                "duration_s": round(time.time() - t0, 1),
            }
            rows.append(row)
            print(
                f"  graded={row['grade_score']} passed={row['passed']} "
                f"critics={critics} elo {row['elo_before']}->{row['elo_after']} "
                f"({row['duration_s']}s)",
                flush=True,
            )

    # ---- report ----------------------------------------------------------
    done = [r for r in rows if r.get("status") == "completed"]
    scores = [
        r["grade_score"] for r in done if isinstance(r.get("grade_score"), (int, float))
    ]
    panels = [set(r["critics"].keys()) for r in done if r.get("critics")]
    all_providers = sorted({p for s in panels for p in s})

    L = [
        "# SAGE Agent Gym — Benchmark",
        "",
        "**What this is:** the gym is SAGE's only source of GROUND TRUTH about agent quality.",
        "An agent plays a real exercise; the output is mechanically graded (did it execute?",
        "did it produce artifacts?); a cross-vendor critic panel scores it; the agent reflects;",
        "a Glicko rating moves. These are measurements, not model opinions.",
        "",
        f"**Sessions:** {len(rows)} ({len(done)} completed, {len(rows) - len(done)} errored)  ",
        f"**Critic panel:** {', '.join(all_providers) if all_providers else 'NONE'}  ",
        f"**Mean graded score:** {sum(scores) / len(scores):.1f}/100"
        if scores
        else "**Mean graded score:** n/a  ",
        "",
        "| Role | Exercise | Skill | Graded | Passed | Critic scores | Elo |",
        "|---|---|---|---|---|---|---|",
    ]

    for r in rows:
        if r.get("status") != "completed":
            L.append(
                f"| {r['role']} | — | — | ERROR | — | — | {str(r.get('error', ''))[:40]} |"
            )
            continue
        cs = ", ".join(f"{k}:{v}" for k, v in (r["critics"] or {}).items()) or "—"
        L.append(
            f"| {r['role']} | `{r['exercise_id']}` | {r['skill']} | "
            f"{r['grade_score']} | {'yes' if r['passed'] else 'no'} | {cs} | "
            f"{r['elo_before']}→{r['elo_after']} |"
        )

    L += [
        "",
        "## What the agents said they got wrong",
        "",
        "These are the agents' own reflections after seeing the critics — the compounding",
        "signal (Law 3). They are the highest-value input to the optimizer.",
        "",
    ]
    for r in done:
        if r.get("reflection"):
            L.append(f"**{r['role']} / `{r['exercise_id']}`**  ")
            L.append(f"{r['reflection']}  ")
            for p in r.get("improvement_plan") or []:
                L.append(f"  - {p}")
            L.append("")

    if len(all_providers) < 2:
        L += [
            "## ⚠️ WARNING — the panel collapsed to a single judge",
            "",
            f"Only `{', '.join(all_providers) or 'none'}` scored. A one-voice 'panel' is",
            "exactly the failure that let a hallucinated critique stand unchallenged.",
            "Check `gemini_timeout` and that the Ollama critic model is served.",
            "",
        ]

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"\nreport -> {args.out}")
    print(f"panel: {all_providers}")
    if scores:
        print(f"mean graded score: {sum(scores) / len(scores):.1f}/100")
    return 0


if __name__ == "__main__":
    sys.exit(main())
