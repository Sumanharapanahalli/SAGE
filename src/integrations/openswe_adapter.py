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
                output=raw.get("code", "") or str(raw.get("output", "")),
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
        """Load exercises from central catalog (75 openswe seeds), fall back to hardcoded."""
        catalog = self._load_catalog_exercises(difficulty)
        if catalog:
            return catalog
        fallback = {
            "beginner": [
                Exercise(id="swe-b01", role="developer", task_type="BACKEND",
                         difficulty="beginner",
                         description="Create a REST API endpoint that returns a greeting with the user's name",
                         acceptance_criteria=["Endpoint returns 200", "Response includes name", "Input validation"],
                         expected_artifacts=["app.py", "test_app.py"], tags=["api", "python"]),
            ],
            "intermediate": [
                Exercise(id="swe-i01", role="developer", task_type="BACKEND",
                         difficulty="intermediate",
                         description="Implement a rate limiter middleware with sliding window algorithm",
                         acceptance_criteria=["Rate limits enforced", "Sliding window accurate", "Thread-safe"],
                         expected_artifacts=["rate_limiter.py", "test_rate_limiter.py"], tags=["middleware", "python"]),
            ],
            "advanced": [
                Exercise(id="swe-a01", role="developer", task_type="BACKEND",
                         difficulty="advanced",
                         description="Build a distributed task queue with priority scheduling and dead letter handling",
                         acceptance_criteria=["Priority ordering", "Dead letter after 3 retries", "Concurrent safe"],
                         expected_artifacts=["task_queue.py", "worker.py"], tags=["distributed", "python"]),
            ],
        }
        return fallback.get(difficulty, fallback["intermediate"])

    def grade_exercise(self, exercise, result):
        """Structural checks (40%) + LLM-as-judge (60%)."""
        score = 0.0
        criteria = {}
        hints = []

        # Structural: execution success
        if result.status == "completed":
            score += 30
            criteria["execution_success"] = True
        else:
            criteria["execution_success"] = False
            hints.append("Code must execute without errors")

        # Structural: output quality
        if result.output and len(result.output) > 50:
            score += 20
            criteria["has_output"] = True
        else:
            criteria["has_output"] = False
            hints.append("Generate substantial code output")

        # Structural: code patterns (language-appropriate)
        output_lower = (result.output or "").lower()
        code_patterns = ["def ", "class ", "import ", "function ", "const ", "return ", "async "]
        pattern_hits = sum(1 for p in code_patterns if p in output_lower)
        if pattern_hits >= 2:
            score += 15
            criteria["code_patterns"] = True

        # Structural: testing patterns
        test_patterns = ["test", "assert", "expect", "describe", "it("]
        test_hits = sum(1 for p in test_patterns if p in output_lower)
        if test_hits >= 1:
            score += 15
            criteria["has_tests"] = True
        else:
            hints.append("Include unit tests")

        # Structural: error handling
        error_patterns = ["try", "except", "catch", "error", "raise", "throw"]
        if any(p in output_lower for p in error_patterns):
            score += 10
            criteria["error_handling"] = True

        # Verification bonus
        if result.verification and result.verification.passed:
            score += 10
            criteria["verification_passed"] = True

        return self._combined_grade(
            exercise, result, min(score, 100.0), criteria, hints,
            domain_context=(
                "Grade as a senior software engineer. Check for:\n"
                "- Clean architecture, SOLID principles, separation of concerns\n"
                "- Proper error handling, input validation, edge cases\n"
                "- Test coverage and test quality\n"
                "- Security: no SQL injection, XSS, or OWASP Top 10 vulnerabilities\n"
                "- Code readability and maintainability"
            ),
        )


# ---------------------------------------------------------------------------
# Auto-register on import
# ---------------------------------------------------------------------------

_adapter = OpenSWEAdapter()
register_runner(_adapter)
