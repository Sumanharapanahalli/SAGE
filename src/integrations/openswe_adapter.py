"""
SAGE Framework — OpenSWE BaseRunner Adapter
=============================================
Wraps the existing OpenSWERunner to conform to the BaseRunner interface.
Registers for all SWE_ROLES (developer, qa_engineer, system_tester, etc.).

Does NOT replace openswe_runner.py — delegates to it.
"""

import logging

from src.integrations.base_runner import (
    BaseRunner, RunResult, VerificationReport, VerificationFinding,
    VerificationSeverity, Exercise, ExerciseScore,
    register_runner, SWE_ROLES,
)

logger = logging.getLogger("Runner.openswe")


class OpenSWEAdapter(BaseRunner):
    """BaseRunner adapter for the existing OpenSWERunner."""

    def __init__(self):
        super().__init__(
            name="openswe",
            roles=list(SWE_ROLES),
            docker_image="",
        )

    def _get_inner(self):
        from src.integrations.openswe_runner import get_openswe_runner
        return get_openswe_runner()

    # ── Execute ─────────────────────────────────────────────────────────

    def execute(self, task, workspace, sandbox_handle=None):
        run_id = self._new_run_id()
        try:
            inner = self._get_inner()
            raw = inner.build(
                task=task,
                repo_path=workspace,
                sandbox_handle=sandbox_handle,
            )
            return self._make_result(
                run_id=raw.get("run_id", run_id),
                status=raw.get("status", "completed"),
                tier=raw.get("tier", "direct"),
                output=raw.get("code", "") or raw.get("output", ""),
                files_changed=raw.get("files_changed", []),
                metrics={"raw_tier": raw.get("tier", "unknown")},
            )
        except Exception as exc:
            self.logger.error("OpenSWE execute failed: %s", exc)
            return self._make_error(run_id, str(exc))

    # ── Verify ──────────────────────────────────────────────────────────

    def verify(self, result, task):
        findings = []
        score = 50.0

        if result.status == "error":
            findings.append(VerificationFinding(
                check="execution", severity=VerificationSeverity.ERROR,
                message="Execution failed", details={"errors": result.errors},
            ))
            return VerificationReport(passed=False, score=0.0, findings=findings)

        # Check files produced
        if result.files_changed:
            score += 20.0
            findings.append(VerificationFinding(
                check="files_produced", severity=VerificationSeverity.PASS,
                message=f"Produced {len(result.files_changed)} files",
            ))
        else:
            findings.append(VerificationFinding(
                check="files_produced", severity=VerificationSeverity.WARNING,
                message="No files produced",
            ))

        # Check output exists
        if result.output and len(result.output.strip()) > 10:
            score += 15.0
            findings.append(VerificationFinding(
                check="output_content", severity=VerificationSeverity.PASS,
                message="Output contains content",
            ))

        # Check acceptance criteria mentioned in output
        criteria = task.get("acceptance_criteria", [])
        if criteria and result.output:
            matched = sum(1 for c in criteria if c.lower() in result.output.lower())
            ratio = matched / len(criteria) if criteria else 0
            score += ratio * 15.0

        score = min(score, 100.0)
        return VerificationReport(
            passed=score >= 50.0,
            score=score,
            findings=findings,
            metrics={"files_count": len(result.files_changed)},
        )

    # ── Toolchain ───────────────────────────────────────────────────────

    def get_toolchain(self):
        return {
            "runner": self.name,
            "docker_image": self.docker_image,
            "roles": self.roles,
            "tools": ["python", "node", "go", "rust", "java", "git", "pytest", "npm"],
            "packages": ["linters", "formatters", "test-frameworks", "package-managers"],
        }

    def get_workflow(self):
        return [
            {"step": 1, "name": "explore", "description": "Explore repo structure and understand context"},
            {"step": 2, "name": "code", "description": "Generate code using ReAct pattern"},
            {"step": 3, "name": "test", "description": "Run tests and lint checks"},
            {"step": 4, "name": "review", "description": "Self-review against acceptance criteria"},
            {"step": 5, "name": "pr", "description": "Create PR with changes"},
        ]

    def get_experience_keys(self):
        return ["task_type", "language", "framework", "domain"]

    # ── Exercises ───────────────────────────────────────────────────────

    def get_exercises(self, difficulty="intermediate"):
        exercises = {
            "beginner": [
                Exercise(
                    id="swe-b01", role="developer", task_type="BACKEND",
                    difficulty="beginner",
                    description="Create a REST API endpoint that returns a greeting with the user's name",
                    acceptance_criteria=["Endpoint returns 200", "Response includes name", "Input validation present"],
                    expected_artifacts=["app.py", "test_app.py"],
                    tags=["api", "python"],
                ),
                Exercise(
                    id="swe-b02", role="developer", task_type="FRONTEND",
                    difficulty="beginner",
                    description="Build a React component that displays a list of items with a search filter",
                    acceptance_criteria=["Component renders", "Filter works", "Tests pass"],
                    expected_artifacts=["ItemList.tsx", "ItemList.test.tsx"],
                    tags=["react", "typescript"],
                ),
            ],
            "intermediate": [
                Exercise(
                    id="swe-i01", role="developer", task_type="BACKEND",
                    difficulty="intermediate",
                    description="Implement a rate limiter middleware with sliding window algorithm",
                    acceptance_criteria=["Rate limits enforced", "Sliding window accurate", "Thread-safe", "Tests pass"],
                    expected_artifacts=["rate_limiter.py", "test_rate_limiter.py"],
                    tags=["middleware", "python"],
                ),
            ],
            "advanced": [
                Exercise(
                    id="swe-a01", role="developer", task_type="BACKEND",
                    difficulty="advanced",
                    description="Build a distributed task queue with priority scheduling and dead letter handling",
                    acceptance_criteria=["Priority ordering correct", "Dead letter after 3 retries", "Concurrent safe", "Integration tests pass"],
                    expected_artifacts=["task_queue.py", "worker.py", "test_task_queue.py"],
                    tags=["distributed", "python"],
                ),
            ],
        }
        return exercises.get(difficulty, exercises["intermediate"])

    def grade_exercise(self, exercise, result):
        score = 0.0
        criteria_results = {}

        # Check artifacts produced
        expected = set(exercise.expected_artifacts)
        produced = set(result.files_changed)
        artifact_match = len(expected & produced) / max(len(expected), 1)
        score += artifact_match * 40
        criteria_results["artifacts_produced"] = artifact_match >= 0.5

        # Check status
        if result.status == "completed":
            score += 30
            criteria_results["execution_success"] = True
        else:
            criteria_results["execution_success"] = False

        # Check output quality
        if result.output and len(result.output) > 50:
            score += 15
            criteria_results["has_output"] = True
        else:
            criteria_results["has_output"] = False

        # Check verification passed
        if result.verification and result.verification.passed:
            score += 15
            criteria_results["verification_passed"] = True

        score = min(score, 100.0)
        hints = []
        if not criteria_results.get("artifacts_produced"):
            hints.append(f"Expected artifacts: {exercise.expected_artifacts}")
        if not criteria_results.get("has_output"):
            hints.append("Generate more substantial code output")

        return ExerciseScore(
            exercise_id=exercise.id,
            passed=score >= 60,
            score=score,
            criteria_results=criteria_results,
            feedback="Good" if score >= 60 else "Needs improvement",
            improvement_hints=hints,
        )


# ---------------------------------------------------------------------------
# Auto-register on import
# ---------------------------------------------------------------------------

_adapter = OpenSWEAdapter()
register_runner(_adapter)
