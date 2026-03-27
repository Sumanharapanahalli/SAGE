"""
SAGE Framework — 100-Solution Pipeline Runner
================================================
Systematically runs all 100 solutions through the Build Orchestrator's
3-tier cascade pipeline (OpenShell → SandboxRunner → OpenSWE).

PMP-aligned execution:
  Phase 1: Initiation — validate descriptions, detect domains
  Phase 2: Planning — decompose, critic review, HITL approval
  Phase 3: Execution — wave-based build with cascade isolation
  Phase 4: Monitor — collect metrics, drift checks, tier usage
  Phase 5: Close — aggregate findings, update framework

Usage:
  # Run all 100 (real LLM, slow)
  .venv/bin/python test-solutions/run_pipeline.py

  # Run single domain
  .venv/bin/python test-solutions/run_pipeline.py --domain medtech

  # Run single solution
  .venv/bin/python test-solutions/run_pipeline.py --id 001

  # Dry run (mock LLM, fast validation)
  .venv/bin/python test-solutions/run_pipeline.py --dry-run

  # Resume from last failure
  .venv/bin/python test-solutions/run_pipeline.py --resume
"""

import argparse
import csv
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("pipeline_runner")

SOLUTIONS_DIR = os.path.join(os.path.dirname(__file__), "solutions")
REGISTRY_CSV = os.path.join(os.path.dirname(__file__), "solutions_registry.csv")
REPORT_PATH = os.path.join(os.path.dirname(__file__), "pipeline_report.json")


# ---------------------------------------------------------------------------
# Agent Gym Integration — pre-flight readiness + post-build feedback
# ---------------------------------------------------------------------------

def _get_gym():
    """Lazy-load AgentGym singleton."""
    try:
        from src.core.agent_gym import AgentGym
        return AgentGym()
    except Exception:
        return None


def gym_preflight(description: str, detected_domains: list) -> dict:
    """
    Pre-flight readiness check using Agent Gym analytics.

    Returns:
        {
            "ready": bool,
            "overall_confidence": float (0-100),
            "agent_readiness": {role: {rating, rd, confidence, sessions, ready}},
            "warnings": [str],
        }
    """
    gym = _get_gym()
    if not gym:
        return {"ready": True, "overall_confidence": 0, "agent_readiness": {}, "warnings": ["Gym unavailable"]}

    # Determine which agents the build will need based on detected domains
    from src.integrations.base_runner import get_runner_for_role
    from src.integrations.build_orchestrator import WORKFORCE_REGISTRY

    needed_roles = set()
    for team_name, team in WORKFORCE_REGISTRY.items():
        needed_roles.add(team.get("lead", ""))
        for member in team.get("members", []):
            needed_roles.add(member if isinstance(member, str) else member.get("role", ""))
    needed_roles.discard("")

    # If specific domains detected, narrow to relevant roles
    domain_role_map = {
        "medical_device": ["firmware_engineer", "embedded_tester", "regulatory_specialist", "safety_engineer"],
        "healthcare_software": ["developer", "qa_engineer", "regulatory_specialist", "technical_writer"],
        "fintech": ["developer", "qa_engineer", "security_engineer", "devops_engineer"],
        "automotive": ["firmware_engineer", "embedded_tester", "safety_engineer"],
        "saas": ["developer", "qa_engineer", "devops_engineer", "ux_designer"],
        "mobile_app": ["developer", "qa_engineer", "ux_designer", "product_manager"],
        "iot": ["firmware_engineer", "embedded_tester", "developer", "data_scientist"],
        "ml_ai": ["data_scientist", "developer", "qa_engineer", "devops_engineer"],
    }
    if detected_domains:
        domain_roles = set()
        for d in detected_domains:
            domain_roles.update(domain_role_map.get(d, []))
        if domain_roles:
            needed_roles = needed_roles & domain_roles | domain_roles  # union with domain-specific

    # Check each role's gym rating
    readiness = {}
    warnings = []
    confidence_scores = []

    for role in sorted(needed_roles):
        rating_data = gym.get_ratings_for_role(role)
        if not rating_data:
            readiness[role] = {"rating": 1000, "rd": 350, "confidence": 0, "sessions": 0, "ready": False}
            warnings.append(f"{role}: no training data — confidence 0%")
            confidence_scores.append(0)
            continue

        # Use first skill rating
        r = rating_data[0] if rating_data else None
        if r is None:
            readiness[role] = {"rating": 1000, "rd": 350, "confidence": 0, "sessions": 0, "ready": False}
            confidence_scores.append(0)
            continue

        rating = r.rating if hasattr(r, 'rating') else r.get('rating', 1000)
        rd = r.rating_deviation if hasattr(r, 'rating_deviation') else r.get('rating_deviation', 350)
        sessions = r.sessions if hasattr(r, 'sessions') else r.get('sessions', 0)

        # Confidence: 100% when RD <= 100, 0% when RD >= 350
        confidence = max(0, min(100, (350 - rd) / 2.5))
        ready = rd < 200 and sessions >= 3

        readiness[role] = {
            "rating": round(rating),
            "rd": round(rd),
            "confidence": round(confidence, 1),
            "sessions": sessions,
            "ready": ready,
        }
        confidence_scores.append(confidence)

        if not ready:
            warnings.append(f"{role}: RD={rd:.0f}, sessions={sessions} — needs more training")

    overall = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
    all_ready = all(r["ready"] for r in readiness.values()) if readiness else False

    return {
        "ready": all_ready,
        "overall_confidence": round(overall, 1),
        "agent_readiness": readiness,
        "warnings": warnings,
    }


def gym_post_build(sol_id: str, sol_name: str, domain: str, result: dict):
    """
    Log build outcome back to gym analytics for tracking.

    Stores build performance as a gym analytics event so we can correlate
    agent ratings with actual build success rates.
    """
    gym = _get_gym()
    if not gym:
        return

    try:
        # Store as analytics metadata in the gym DB
        import sqlite3
        db_path = os.path.join(os.path.dirname(__file__), "..", ".gym_data.db")
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS build_outcomes (
                sol_id TEXT,
                sol_name TEXT,
                domain TEXT,
                status TEXT,
                critic_avg REAL,
                task_count INTEGER,
                duration_s REAL,
                tiers_used TEXT,
                preflight_confidence REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Extract metrics
        phases = result.get("phases", {})
        exec_phase = phases.get("execution", {})
        critic_scores = []
        for p in phases.values():
            for cs in (p.get("critic_scores") or []):
                critic_scores.append(cs.get("score", 0) if isinstance(cs, dict) else cs)
        critic_avg = sum(critic_scores) / len(critic_scores) if critic_scores else 0

        conn.execute(
            "INSERT INTO build_outcomes (sol_id, sol_name, domain, status, critic_avg, "
            "task_count, duration_s, tiers_used, preflight_confidence) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                sol_id, sol_name, domain, result.get("status", "unknown"),
                round(critic_avg, 1),
                phases.get("initiation", {}).get("task_count", 0),
                exec_phase.get("duration_s", 0),
                json.dumps(exec_phase.get("tiers_used", [])),
                result.get("preflight", {}).get("overall_confidence", 0),
            ),
        )
        conn.commit()
        conn.close()
        logger.info("[Gym] Build outcome logged for %s (%s)", sol_id, result.get("status"))
    except Exception as exc:
        logger.warning("[Gym] Failed to log build outcome: %s", exc)


def load_registry():
    """Load solutions registry CSV."""
    with open(REGISTRY_CSV) as f:
        return list(csv.DictReader(f))


def find_solution_dir(sol_id, name):
    """Find the solution subfolder by ID prefix."""
    prefix = f"{sol_id}_{name}"
    path = os.path.join(SOLUTIONS_DIR, prefix)
    if os.path.isdir(path):
        return path
    # Fallback: search by ID
    for entry in os.listdir(SOLUTIONS_DIR):
        if entry.startswith(sol_id):
            return os.path.join(SOLUTIONS_DIR, entry)
    return None


def run_solution(sol, dry_run=False, auto_approve=True):
    """
    Run a single solution through the full pipeline.

    Returns a results dict with metrics for the pipeline report.
    """
    sol_id = sol["id"]
    name = sol["name"]
    domain = sol["domain"]
    description = sol["description"]
    sol_dir = find_solution_dir(sol_id, name)

    logger.info("=" * 60)
    logger.info("Solution %s: %s [%s]", sol_id, name, domain)
    logger.info("=" * 60)

    result = {
        "id": sol_id,
        "name": name,
        "domain": domain,
        "status": "pending",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "phases": {},
        "errors": [],
        "framework_issues": [],
    }

    try:
        from src.integrations.build_orchestrator import BuildOrchestrator
        import tempfile

        # ── Phase 0: Pre-flight — Agent Gym readiness check ───────
        logger.info("[Phase 0] Pre-flight — Agent Gym readiness check")
        preflight = gym_preflight(description, [domain])
        result["preflight"] = preflight
        if preflight["warnings"]:
            for w in preflight["warnings"][:5]:
                logger.warning("  ⚠ %s", w)
        logger.info(
            "[Phase 0] Confidence: %.0f%% | Ready: %s | Agents checked: %d",
            preflight["overall_confidence"],
            preflight["ready"],
            len(preflight["agent_readiness"]),
        )

        # Fresh orchestrator per solution
        tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp_db.close()
        orch = BuildOrchestrator(checkpoint_db=tmp_db.name)

        # ── Phase 1: Initiation ──────────────────────────────────
        logger.info("[Phase 1] Initiation — domain detection")
        start_time = time.time()

        if dry_run:
            # Mock LLM for fast validation
            from unittest.mock import MagicMock, patch
            mock_plan = [
                {"step": i+1, "task_type": "BACKEND", "description": f"Task {i+1}",
                 "payload": {}, "depends_on": [], "agent_role": "developer"}
                for i in range(int(sol.get("min_tasks", 8)))
            ]
            mock_critic = {
                "passed": False, "final_score": 55, "iterations": 1,
                "history": [{"score": 55, "iteration": 1}],
                "final_review": {"score": 55, "summary": "Mock review"},
                "threshold": 70,
            }

            with patch.object(orch, "_decompose", return_value=mock_plan), \
                 patch.object(orch, "_critic_review_plan", return_value=mock_critic), \
                 patch.object(orch, "_audit"):
                build_result = orch.start(description)
        else:
            build_result = orch.start(description)

        phase1_time = time.time() - start_time
        result["phases"]["initiation"] = {
            "duration_s": round(phase1_time, 2),
            "run_id": build_result.get("run_id"),
            "state": build_result.get("state"),
            "task_count": build_result.get("task_count", 0),
            "detected_domains": build_result.get("detected_domains", []),
        }

        if build_result.get("state") == "failed":
            result["status"] = "failed_initiation"
            result["errors"].append(build_result.get("error", "Unknown"))
            _save_result(sol_dir, result)
            return result

        run_id = build_result["run_id"]

        # ── Phase 2: Planning — critic review ────────────────────
        logger.info("[Phase 2] Planning — critic scores: %s", build_result.get("critic_scores"))
        result["phases"]["planning"] = {
            "critic_scores": build_result.get("critic_scores", []),
            "hitl_level": build_result.get("hitl_level"),
            "task_count": build_result.get("task_count", 0),
        }

        # Save plan to solution dir
        if sol_dir:
            plan_path = os.path.join(sol_dir, "plan", "build_plan.json")
            with open(plan_path, "w") as f:
                json.dump(build_result, f, indent=2, default=str)

        # ── Phase 3: Execution — approve plan and build ──────────
        if auto_approve and build_result.get("state") == "awaiting_plan":
            logger.info("[Phase 3] Execution — approving plan")
            start_time = time.time()

            if dry_run:
                with patch.object(orch, "_execute_agents"), \
                     patch.object(orch, "_integrate", return_value={
                         "status": "completed", "files_changed": [],
                         "total_tasks": int(sol.get("min_tasks", 8)),
                     }), \
                     patch.object(orch, "_critic_review_code", return_value=mock_critic), \
                     patch.object(orch, "_critic_review_integration", return_value=mock_critic), \
                     patch.object(orch, "_checkpoint"), \
                     patch.object(orch, "_audit"):
                    approve_result = orch.approve_plan(run_id)
            else:
                approve_result = orch.approve_plan(run_id)

            phase3_time = time.time() - start_time
            result["phases"]["execution"] = {
                "duration_s": round(phase3_time, 2),
                "state": approve_result.get("state"),
                "agent_results_count": len(approve_result.get("agent_results", [])),
            }

            # Check execution tiers used
            agent_results = approve_result.get("agent_results", [])
            tiers_used = set()
            for ar in agent_results:
                tier = ar.get("result", {}).get("execution_tier", "openswe_direct")
                tiers_used.add(tier)
            result["phases"]["execution"]["tiers_used"] = list(tiers_used)

        # ── Phase 4: Monitoring — collect metrics ────────────────
        status = orch.get_status(run_id)
        result["phases"]["monitoring"] = {
            "final_state": status.get("state"),
            "critic_scores": status.get("critic_scores", []),
        }

        # ── Phase 5: Closing ─────────────────────────────────────
        result["status"] = "completed" if status.get("state") in ("completed", "awaiting_final") else "incomplete"
        result["completed_at"] = datetime.now(timezone.utc).isoformat()

        # Save final status
        if sol_dir:
            status_path = os.path.join(sol_dir, "plan", "build_status.json")
            with open(status_path, "w") as f:
                json.dump(status, f, indent=2, default=str)

        logger.info("[Phase 5] Closing — status: %s", result["status"])

        # ── Post-build — log outcome to Gym analytics ──────────────
        gym_post_build(sol_id, name, domain, result)

    except Exception as exc:
        result["status"] = "error"
        result["errors"].append(str(exc))
        logger.error("Solution %s failed: %s", sol_id, exc)
        gym_post_build(sol_id, name, domain, result)

    _save_result(sol_dir, result)
    return result


def _save_result(sol_dir, result):
    """Save individual solution result."""
    if sol_dir:
        result_path = os.path.join(sol_dir, "logs", "pipeline_result.json")
        with open(result_path, "w") as f:
            json.dump(result, f, indent=2, default=str)


def generate_report(results):
    """Aggregate results into a pipeline report."""
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_solutions": len(results),
        "summary": {
            "completed": sum(1 for r in results if r["status"] == "completed"),
            "failed": sum(1 for r in results if "fail" in r["status"]),
            "errors": sum(1 for r in results if r["status"] == "error"),
            "incomplete": sum(1 for r in results if r["status"] == "incomplete"),
        },
        "by_domain": {},
        "framework_issues": [],
        "execution_tiers": {"openshell": 0, "sandbox_runner": 0, "openswe_direct": 0},
        "critic_scores": [],
    }

    for r in results:
        domain = r["domain"]
        if domain not in report["by_domain"]:
            report["by_domain"][domain] = {"total": 0, "completed": 0, "failed": 0}
        report["by_domain"][domain]["total"] += 1
        if r["status"] == "completed":
            report["by_domain"][domain]["completed"] += 1
        else:
            report["by_domain"][domain]["failed"] += 1

        # Collect execution tiers
        exec_phase = r.get("phases", {}).get("execution", {})
        for tier in exec_phase.get("tiers_used", []):
            if tier in report["execution_tiers"]:
                report["execution_tiers"][tier] += 1

        # Collect critic scores
        for phase_name, phase_data in r.get("phases", {}).items():
            for cs in phase_data.get("critic_scores", []):
                report["critic_scores"].append({
                    "solution": r["id"],
                    "phase": cs.get("phase", phase_name),
                    "score": cs.get("score", 0),
                })

        # Collect framework issues
        report["framework_issues"].extend(r.get("framework_issues", []))
        if r.get("errors"):
            report["framework_issues"].append({
                "solution": r["id"],
                "errors": r["errors"],
            })

    # Score statistics
    scores = [cs["score"] for cs in report["critic_scores"]] or [0]
    report["critic_stats"] = {
        "avg": round(sum(scores) / len(scores), 1),
        "min": min(scores),
        "max": max(scores),
        "above_70": sum(1 for s in scores if s >= 70),
        "below_50": sum(1 for s in scores if s < 50),
    }

    # ── Gym Analytics Summary ──────────────────────────────────────
    preflight_confidences = [
        r.get("preflight", {}).get("overall_confidence", 0) for r in results
    ]
    preflight_ready = sum(1 for r in results if r.get("preflight", {}).get("ready", False))

    report["gym_analytics"] = {
        "preflight_avg_confidence": round(
            sum(preflight_confidences) / len(preflight_confidences), 1
        ) if preflight_confidences else 0,
        "preflight_ready_count": preflight_ready,
        "preflight_not_ready_count": len(results) - preflight_ready,
        "correlation_note": (
            "Compare preflight confidence with build success rate to validate "
            "that gym ratings predict build quality."
        ),
    }

    # Correlate: do higher-confidence builds succeed more?
    ready_builds = [r for r in results if r.get("preflight", {}).get("ready")]
    not_ready_builds = [r for r in results if not r.get("preflight", {}).get("ready")]
    if ready_builds:
        report["gym_analytics"]["ready_success_rate"] = round(
            sum(1 for r in ready_builds if r["status"] == "completed") / len(ready_builds) * 100, 1
        )
    if not_ready_builds:
        report["gym_analytics"]["not_ready_success_rate"] = round(
            sum(1 for r in not_ready_builds if r["status"] == "completed") / len(not_ready_builds) * 100, 1
        )

    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)

    return report


def update_csv_status(results):
    """Update the registry CSV with execution results."""
    status_map = {r["id"]: r["status"] for r in results}
    rows = load_registry()
    for row in rows:
        if row["id"] in status_map:
            row["status"] = status_map[row["id"]]

    with open(REGISTRY_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="SAGE 100-Solution Pipeline Runner")
    parser.add_argument("--domain", help="Run only solutions from this domain")
    parser.add_argument("--id", help="Run only this solution ID (e.g. 001)")
    parser.add_argument("--dry-run", action="store_true", help="Mock LLM, fast validation")
    parser.add_argument("--resume", action="store_true", help="Skip already-completed solutions")
    parser.add_argument("--no-approve", action="store_true", help="Stop after planning (no execution)")
    parser.add_argument("--gym-check", action="store_true",
                        help="Run gym pre-flight check only (no build)")
    args = parser.parse_args()

    registry = load_registry()

    # Filter
    if args.domain:
        registry = [r for r in registry if r["domain"] == args.domain]
    if args.id:
        registry = [r for r in registry if r["id"] == args.id]

    # Resume: skip completed
    if args.resume:
        completed = set()
        for entry in os.listdir(SOLUTIONS_DIR):
            result_path = os.path.join(SOLUTIONS_DIR, entry, "logs", "pipeline_result.json")
            if os.path.isfile(result_path):
                with open(result_path) as f:
                    data = json.load(f)
                if data.get("status") == "completed":
                    completed.add(data["id"])
        before = len(registry)
        registry = [r for r in registry if r["id"] not in completed]
        logger.info("Resume: skipping %d completed, running %d remaining", before - len(registry), len(registry))

    logger.info("Running %d solutions (dry_run=%s)", len(registry), args.dry_run)

    # Gym-check-only mode: just run pre-flight for all solutions
    if args.gym_check:
        logger.info("=" * 60)
        logger.info("GYM PRE-FLIGHT CHECK (no builds)")
        logger.info("=" * 60)
        ready_count = 0
        for sol in registry:
            pf = gym_preflight(sol["description"], [sol["domain"]])
            status_icon = "✓" if pf["ready"] else "✗"
            logger.info(
                "  %s %s %-30s  confidence=%5.1f%%  warnings=%d",
                status_icon, sol["id"], sol["name"][:30],
                pf["overall_confidence"], len(pf["warnings"]),
            )
            if pf["ready"]:
                ready_count += 1
        logger.info(
            "Ready: %d/%d (%.0f%%)",
            ready_count, len(registry),
            ready_count / max(len(registry), 1) * 100,
        )
        return

    results = []
    for sol in registry:
        result = run_solution(sol, dry_run=args.dry_run, auto_approve=not args.no_approve)
        results.append(result)

        # Log progress
        done = len(results)
        total = len(registry)
        ok = sum(1 for r in results if r["status"] == "completed")
        logger.info("Progress: %d/%d (%.0f%% success)", done, total, ok / max(done, 1) * 100)

    # Generate report
    report = generate_report(results)
    update_csv_status(results)

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 60)
    logger.info("Total: %d | Completed: %d | Failed: %d | Errors: %d",
                report["total_solutions"],
                report["summary"]["completed"],
                report["summary"]["failed"],
                report["summary"]["errors"])
    logger.info("Critic avg: %.1f | Tiers: %s",
                report["critic_stats"]["avg"],
                report["execution_tiers"])
    logger.info("Report: %s", REPORT_PATH)


if __name__ == "__main__":
    main()
