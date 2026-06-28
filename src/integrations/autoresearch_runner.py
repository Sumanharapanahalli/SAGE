"""
SAGE Framework — AutoResearch Runner
=======================================
BaseRunner wrapper for the AutoResearchEngine.

Enables Agent Gym training for research_engineer and ml_researcher roles
by implementing the standard execute/verify/get_exercises/grade_exercise interface.

Workflow: propose hypothesis → apply code change → run experiment → measure metric → keep/discard
"""

import json
import logging
import os
import re
import tempfile

from src.integrations.base_runner import (
    BaseRunner, RunResult, VerificationReport, VerificationFinding,
    VerificationSeverity, Exercise, ExerciseScore,
    register_runner, RESEARCH_ROLES,
)

logger = logging.getLogger("Runner.autoresearch")


class AutoResearchRunner(BaseRunner):
    """Autonomous experiment execution runner."""

    def __init__(self):
        super().__init__(
            name="autoresearch",
            roles=list(RESEARCH_ROLES),
            docker_image="",
        )

    def execute(self, task, workspace, sandbox_handle=None):
        run_id = self._new_run_id()
        try:
            description = task.get("description", "")
            payload = task.get("payload", {})
            metric_name = payload.get("metric_name", "val_loss")
            run_command = payload.get("run_command", "")
            budget_s = payload.get("budget_s")
            direction = payload.get("direction", "lower")
            exp_workspace = payload.get("workspace", workspace)

            from src.core.auto_research import AutoResearchEngine
            engine = AutoResearchEngine()
            result = engine.run_experiment(
                workspace=exp_workspace,
                metric_name=metric_name,
                run_command=run_command,
                budget_s=budget_s,
                direction=direction,
            )

            metrics = {
                "decision": result.get("decision", ""),
                "metric_value": result.get("metric_value"),
                "metric_name": metric_name,
                "baseline": result.get("baseline"),
                "hypothesis": result.get("hypothesis", ""),
                "experiment_id": result.get("experiment_id", ""),
            }

            status = "completed" if result.get("status") != "crashed" else "failed"

            return self._make_result(
                run_id=run_id,
                status=status,
                tier="direct",
                output=json.dumps(result, default=str),
                files_changed=result.get("files_changed", []),
                artifacts=[{"path": "experiment_result.json", "type": "metrics"}],
                metrics=metrics,
            )
        except Exception as exc:
            self.logger.error("AutoResearch execute failed: %s", exc)
            return self._make_error(run_id, str(exc))

    def verify(self, result, task):
        findings = []
        score = 0.0

        if result.status == "error":
            return VerificationReport(
                passed=False, score=0.0,
                findings=[VerificationFinding(
                    "execution", VerificationSeverity.ERROR, "Experiment failed",
                )],
            )

        metrics = result.metrics or {}

        # Experiment completed
        if result.status == "completed":
            score += 20
            findings.append(VerificationFinding(
                "execution", VerificationSeverity.PASS, "Experiment completed",
            ))

        # Metric was extracted
        if metrics.get("metric_value") is not None:
            score += 20
            findings.append(VerificationFinding(
                "metric_extraction", VerificationSeverity.PASS,
                f"Metric extracted: {metrics.get('metric_name')}={metrics['metric_value']}",
            ))
        else:
            findings.append(VerificationFinding(
                "metric_extraction", VerificationSeverity.WARNING,
                "No metric extracted from output",
            ))

        # Decision was made
        decision = metrics.get("decision", "")
        if decision in ("keep", "discard"):
            score += 15
            findings.append(VerificationFinding(
                "decision", VerificationSeverity.PASS,
                f"Decision: {decision}",
            ))

        # Improvement check
        baseline = metrics.get("baseline")
        metric_val = metrics.get("metric_value")
        if decision == "keep" and baseline is not None and metric_val is not None:
            score += 25
            findings.append(VerificationFinding(
                "improvement", VerificationSeverity.PASS,
                f"Improved from {baseline} to {metric_val}",
            ))
        elif decision == "discard":
            score += 10
            findings.append(VerificationFinding(
                "improvement", VerificationSeverity.INFO,
                "No improvement — correctly discarded",
            ))

        # Hypothesis stated
        if metrics.get("hypothesis"):
            score += 10
            findings.append(VerificationFinding(
                "hypothesis", VerificationSeverity.PASS,
                "Hypothesis stated before experiment",
            ))

        score = min(score, 100.0)
        return VerificationReport(
            passed=score >= 30.0, score=score,
            findings=findings, metrics=metrics,
        )

    def get_toolchain(self):
        return {
            "runner": self.name,
            "docker_image": self.docker_image,
            "roles": self.roles,
            "tools": ["python3", "uv", "git", "tensorboard", "optuna", "pytest"],
            "packages": [],
        }

    def get_workflow(self):
        return [
            {"step": 1, "name": "baseline", "description": "Run baseline experiment to establish metric"},
            {"step": 2, "name": "propose", "description": "LLM proposes code change with hypothesis"},
            {"step": 3, "name": "apply", "description": "Apply changes and commit to git"},
            {"step": 4, "name": "execute", "description": "Run experiment with fixed budget"},
            {"step": 5, "name": "measure", "description": "Extract metric from output"},
            {"step": 6, "name": "decide", "description": "Keep (improved) or discard (git reset)"},
        ]

    def get_experience_keys(self):
        return ["task_type", "metric_name", "domain", "hypothesis_type"]

    def get_exercises(self, difficulty="intermediate"):
        """Load from central catalog (64 autoresearch seeds), fall back to hardcoded."""
        catalog = self._load_catalog_exercises(difficulty)
        if catalog:
            return catalog
        # Minimal fallback
        return [
            Exercise(
                id="ar-fallback-01",
                role="research_engineer",
                task_type="hyperparameter_search",
                difficulty=difficulty,
                description="Run a learning rate sweep [1e-5, 1e-4, 1e-3, 1e-2] and select the best",
                acceptance_criteria=["All rates tested", "Best rate selected", "Results logged"],
                expected_artifacts=["results.json"],
                tags=["hyperparameter", "learning-rate"],
            ),
        ]

    def grade_exercise(self, exercise, result):
        """Structural checks (40%) + LLM-as-judge (60%)."""
        score = 0.0
        criteria = {}
        hints = []

        if result.status == "completed":
            score += 20
            criteria["execution_success"] = True

        metrics = result.metrics or {}
        output_lower = (result.output or "").lower()

        # Metric extraction
        if metrics.get("metric_value") is not None:
            score += 15
            criteria["metric_extracted"] = True
        else:
            hints.append("Ensure experiment output contains the target metric in parseable format")

        # Decision made
        if metrics.get("decision") in ("keep", "discard"):
            score += 10
            criteria["decision_made"] = True

        # Hypothesis quality
        if metrics.get("hypothesis") and len(metrics["hypothesis"]) > 10:
            score += 10
            criteria["hypothesis_stated"] = True
        else:
            hints.append("State a clear hypothesis before running the experiment")

        # Research vocabulary
        research_kws = ["hypothesis", "baseline", "metric", "experiment", "result",
                        "improvement", "parameter", "training", "validation", "loss",
                        "accuracy", "ablation", "comparison"]
        kw_hits = sum(1 for k in research_kws if k in output_lower)
        if kw_hits >= 4:
            score += 15
            criteria["research_vocabulary"] = True
        elif kw_hits >= 2:
            score += 8

        # Reproducibility markers
        repro_kws = ["seed", "commit", "git", "checkpoint", "reproducib", "deterministic"]
        if sum(1 for k in repro_kws if k in output_lower) >= 1:
            score += 10
            criteria["reproducibility"] = True
        else:
            hints.append("Include reproducibility markers: random seed, git commit, checkpoints")

        if result.verification and result.verification.passed:
            score += 10
            criteria["verification_passed"] = True

        return self._combined_grade(
            exercise, result, min(score, 100.0), criteria, hints,
            domain_context=(
                "Grade as a senior ML researcher. Check for:\n"
                "- Clear hypothesis stated before experiment\n"
                "- Correct metric extraction and interpretation\n"
                "- Sound keep/discard decision based on metric comparison\n"
                "- Reproducibility (seeds, git tracking, checkpoints)\n"
                "- Scientific rigor in experimental design"
            ),
        )


# Auto-register on import
_runner = AutoResearchRunner()
register_runner(_runner)
