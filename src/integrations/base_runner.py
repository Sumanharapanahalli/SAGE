"""
SAGE Framework — Base Domain Runner Interface
===============================================
Abstract base for all domain-specific execution runners.

Each runner encapsulates a complete execution environment for a role family:
  - Toolchain: what software/hardware the role needs
  - Workflow: the sequence of domain-specific actions
  - Verification: how to validate output quality
  - Experience: how the agent accumulates domain knowledge

Runner hierarchy:
  BaseRunner (abstract)
    ├── OpenSWERunner     — Software engineering (explore → code → test → PR)
    ├── OpenFWRunner      — Firmware (HAL code → cross-compile → static analysis → binary metrics)
    ├── OpenEDARunner     — Electronics (schematic → layout → DRC → Gerber)
    ├── OpenSimRunner     — Simulation (model → simulate → waveform → timing)
    ├── OpenMLRunner      — Machine learning (data → train → evaluate → track)
    ├── OpenDocRunner     — Documentation (research → draft → cross-ref → validate)
    ├── OpenDesignRunner  — UX/Design (wireframe → prototype → accessibility → tokens)
    ├── OpenBrowserRunner — Browser testing/QA (navigate → interact → verify → screenshot)
    └── OpenStrategyRunner — Strategy (analyze → framework → plan → action)

The 3-tier isolation cascade (OpenShell → SandboxRunner → Direct) is orthogonal
to the domain runner: any runner can execute in any isolation tier.

Thread-safe. Audit every action. Return error dicts, never raise.
"""

import logging
import os
import re
import subprocess
import tempfile
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


logger = logging.getLogger("BaseRunner")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

class VerificationSeverity(Enum):
    """Severity levels for verification findings."""
    PASS = "pass"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class VerificationFinding:
    """A single verification check result."""
    check: str
    severity: VerificationSeverity
    message: str
    details: dict = field(default_factory=dict)


@dataclass
class VerificationReport:
    """Aggregate verification result from a domain runner."""
    passed: bool
    score: float  # 0-100
    findings: list[VerificationFinding] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    duration_s: float = 0.0

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "score": self.score,
            "findings": [
                {
                    "check": f.check,
                    "severity": f.severity.value,
                    "message": f.message,
                    "details": f.details,
                }
                for f in self.findings
            ],
            "metrics": self.metrics,
            "duration_s": round(self.duration_s, 3),
        }


@dataclass
class RunResult:
    """Standardized result from any domain runner execution."""
    run_id: str
    status: str  # "completed", "failed", "error", "partial"
    runner: str  # e.g. "openswe", "openfw", "openeda"
    tier: str  # "openshell", "sandbox_runner", "direct"
    artifacts: list[dict] = field(default_factory=list)  # [{path, type, size}]
    output: str = ""
    files_changed: list[str] = field(default_factory=list)
    verification: Optional[VerificationReport] = None
    experience: list[dict] = field(default_factory=list)  # learnings to store
    metrics: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    duration_s: float = 0.0

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "runner": self.runner,
            "tier": self.tier,
            "artifacts": self.artifacts,
            "output": (str(self.output)[:2000] if not isinstance(self.output, str) else self.output[:2000]) if self.output else "",
            "files_changed": self.files_changed,
            "verification": self.verification.to_dict() if self.verification else None,
            "experience": self.experience,
            "metrics": self.metrics,
            "errors": self.errors,
            "duration_s": round(self.duration_s, 3),
        }


@dataclass
class Exercise:
    """A training exercise for the Agent Gym."""
    id: str
    role: str
    task_type: str
    difficulty: str  # "beginner", "intermediate", "advanced", "expert"
    description: str
    acceptance_criteria: list[str]
    expected_artifacts: list[str]  # what the exercise should produce
    grading_rubric: dict = field(default_factory=dict)
    timeout_s: int = 300
    tags: list[str] = field(default_factory=list)


@dataclass
class ExerciseScore:
    """Score from grading an exercise attempt."""
    exercise_id: str
    passed: bool
    score: float  # 0-100
    criteria_results: dict = field(default_factory=dict)  # {criterion: pass/fail}
    feedback: str = ""
    improvement_hints: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Abstract Base Runner
# ---------------------------------------------------------------------------

class BaseRunner(ABC):
    """
    Abstract base for domain-specific execution runners.

    Every runner must implement:
      - execute()        — run a domain task, return RunResult
      - verify()         — validate output with domain-specific checks
      - get_exercises()  — return training exercises for Agent Gym
      - grade_exercise() — score an exercise attempt

    And should implement:
      - get_toolchain()  — return required tools/packages
      - get_workflow()   — return the step sequence for this domain
    """

    def __init__(self, name: str, roles: list[str], docker_image: str = ""):
        self.name = name
        self.roles = roles
        self.docker_image = docker_image
        self.logger = logging.getLogger(f"Runner.{name}")
        self._runs: dict[str, RunResult] = {}

    @abstractmethod
    def execute(
        self,
        task: dict,
        workspace: str,
        sandbox_handle: Any = None,
    ) -> RunResult:
        """
        Execute a domain task.

        Args:
            task: Dict with 'description', 'task_type', 'payload', 'acceptance_criteria'.
            workspace: Working directory for artifacts.
            sandbox_handle: Optional OpenShell SandboxHandle for container isolation.

        Returns:
            RunResult with status, artifacts, verification, and experience.
        """

    @abstractmethod
    def verify(self, result: RunResult, task: dict) -> VerificationReport:
        """
        Run domain-specific verification on execution output.

        Args:
            result: The RunResult from execute().
            task: The original task for context.

        Returns:
            VerificationReport with pass/fail, score, and findings.
        """

    @abstractmethod
    def get_exercises(self, difficulty: str = "intermediate") -> list[Exercise]:
        """
        Return training exercises for Agent Gym.

        Args:
            difficulty: One of "beginner", "intermediate", "advanced", "expert".

        Returns:
            List of exercises appropriate for this runner's domain.
        """

    @abstractmethod
    def grade_exercise(self, exercise: Exercise, result: RunResult) -> ExerciseScore:
        """
        Grade an exercise attempt.

        Args:
            exercise: The exercise definition.
            result: The RunResult from the agent's attempt.

        Returns:
            ExerciseScore with pass/fail, score, and improvement hints.
        """

    def get_toolchain(self) -> dict:
        """Return required tools, packages, and docker image for this runner.

        Merges tools from skill registry with any hardcoded defaults.
        """
        skill_tools = self._get_skill_tools()
        return {
            "runner": self.name,
            "docker_image": self.docker_image,
            "roles": self.roles,
            "tools": skill_tools,
            "packages": [],
        }

    def get_workflow(self) -> list[dict]:
        """Return the step sequence for this domain's execution."""
        return [{"step": 1, "name": "execute", "description": "Run task"}]

    def get_experience_keys(self) -> list[str]:
        """Return the vector store key dimensions for experience retrieval."""
        return ["task_type", "domain"]

    def get_skill_prompt(self, role: str = "") -> str:
        """
        Build a composite system prompt from registered skills for this runner.

        Args:
            role: Optional specific role. If empty, uses all runner skills.

        Returns:
            Prompt fragment from skill YAML files (empty string if no skills loaded).
        """
        try:
            from src.core.skill_loader import skill_registry
            if role:
                return skill_registry.build_prompt_for_role(role)
            # All skills for this runner
            skills = skill_registry.get_for_runner(self.name)
            parts = []
            for skill in skills:
                if skill.prompt:
                    parts.append(f"## Skill: {skill.name} (v{skill.version})\n{skill.prompt}")
            return "\n\n".join(parts)
        except Exception:
            return ""

    def get_acceptance_criteria(self, role: str = "") -> list[str]:
        """Get acceptance criteria from registered skills."""
        try:
            from src.core.skill_loader import skill_registry
            if role:
                return skill_registry.get_acceptance_criteria_for_role(role)
            skills = skill_registry.get_for_runner(self.name)
            criteria = []
            for skill in skills:
                criteria.extend(skill.acceptance_criteria)
            return criteria
        except Exception:
            return []

    def get_skills(self) -> list[dict]:
        """List all active skills registered for this runner."""
        try:
            from src.core.skill_loader import skill_registry
            return [s.to_dict() for s in skill_registry.get_for_runner(self.name)]
        except Exception:
            return []

    def _get_skill_tools(self) -> list[str]:
        """Get the union of tools from all skills for this runner."""
        try:
            from src.core.skill_loader import skill_registry
            skills = skill_registry.get_for_runner(self.name)
            tools = []
            seen = set()
            for skill in skills:
                for tool in skill.tools:
                    if tool not in seen:
                        tools.append(tool)
                        seen.add(tool)
            return tools
        except Exception:
            return []

    # ── Catalog-aware exercise loading ──────────────────────────────────

    def _load_catalog_exercises(self, difficulty: str = "") -> list["Exercise"]:
        """
        Load exercises from the central exercise catalog for this runner's domain.

        Converts catalog Exercise objects (exercise_catalog.py) to runner Exercise
        objects (base_runner.py). Falls back to empty list if catalog unavailable.
        """
        try:
            from src.core.exercise_seeds import get_all_seeds
            seeds = get_all_seeds().get(self.name, [])
            if not seeds:
                return []

            exercises = []
            for i, seed in enumerate(seeds):
                if difficulty and seed.get("difficulty", "") != difficulty:
                    continue
                # Build deterministic ID from domain + index + difficulty
                diff = seed.get("difficulty", "intermediate")
                prefix = self.name[:3]
                ex_id = f"{prefix}-{diff[0]}{i+1:02d}"
                exercises.append(Exercise(
                    id=ex_id,
                    role=self.roles[0] if self.roles else "",
                    task_type=seed.get("task_type", ""),
                    difficulty=diff,
                    description=seed.get("description", seed.get("title", "")),
                    acceptance_criteria=seed.get("acceptance_criteria", []),
                    expected_artifacts=[],
                    tags=seed.get("tags", []),
                ))
            return exercises
        except Exception as exc:
            self.logger.debug("Catalog load failed: %s", exc)
            return []

    # ── LLM-as-judge grading ─────────────────────────────────────────────

    def _llm_grade(
        self,
        exercise: "Exercise",
        result: "RunResult",
        domain_context: str = "",
    ) -> dict:
        """
        Use the LLM as a judge to evaluate an exercise attempt.

        Returns dict with: score (0-100), passed (bool), criteria_results (dict),
        feedback (str), improvement_hints (list[str]).

        Falls back to {"score": 0, "error": ...} if LLM unavailable.
        """
        try:
            from src.core.llm_gateway import llm_gateway

            output_preview = (result.output or "")[:3000]
            criteria_text = "\n".join(f"  - {c}" for c in exercise.acceptance_criteria)

            prompt = (
                f"You are a senior {self.name} domain expert grading a training exercise.\n\n"
                f"## Exercise\n"
                f"**Title:** {exercise.description[:200]}\n"
                f"**Difficulty:** {exercise.difficulty}\n"
                f"**Acceptance Criteria:**\n{criteria_text}\n\n"
                f"## Agent Output\n"
                f"**Status:** {result.status}\n"
                f"**Files produced:** {result.files_changed}\n"
                f"**Output (truncated):**\n```\n{output_preview}\n```\n\n"
                f"{domain_context}\n\n"
                f"## Grading Instructions\n"
                f"Score the attempt 0-100. For each acceptance criterion, mark pass/fail.\n"
                f"Be strict but fair. Partial credit is OK.\n\n"
                f"Return JSON only:\n"
                f'{{"score": N, "passed": true/false, '
                f'"criteria_results": {{"criterion_text": true/false, ...}}, '
                f'"feedback": "one paragraph assessment", '
                f'"improvement_hints": ["hint1", "hint2"]}}'
            )

            response = llm_gateway.generate(
                prompt,
                system_prompt="You are a strict but fair technical grader. Return valid JSON only.",
                trace_name=f"gym.llm_grade.{self.name}",
            )

            # Parse JSON from response
            import json as _json
            import re as _re
            cleaned = response.replace("```json", "").replace("```", "").strip()
            match = _re.search(r'\{[\s\S]*\}', cleaned)
            if match:
                parsed = _json.loads(match.group(0))
                return {
                    "score": max(0, min(100, float(parsed.get("score", 0)))),
                    "passed": bool(parsed.get("passed", False)),
                    "criteria_results": parsed.get("criteria_results", {}),
                    "feedback": str(parsed.get("feedback", "")),
                    "improvement_hints": list(parsed.get("improvement_hints", [])),
                }

            return {"score": 0, "error": "Could not parse LLM grading response"}

        except Exception as exc:
            self.logger.debug("LLM grading failed: %s", exc)
            return {"score": 0, "error": str(exc)}

    # ── Experimental verification (real execution) ────────────────────

    def _extract_code_blocks(self, output: str) -> list[dict]:
        """
        Extract code blocks from LLM output.

        Returns list of {filename, language, code} dicts.
        Detects ```lang blocks, filename hints like '# filename: foo.py', and
        fenced blocks with explicit filenames.
        """
        blocks = []
        # Pattern: ```lang\n...``` optionally preceded by a filename hint
        pattern = re.compile(
            r'(?:(?:#|//|--)\s*(?:file(?:name)?|File)\s*:\s*(\S+)\s*\n)?'
            r'```(\w+)?\s*\n(.*?)```',
            re.DOTALL,
        )
        for match in pattern.finditer(output or ""):
            fname_hint = match.group(1)
            lang = match.group(2) or ""
            code = match.group(3).strip()
            if not code or len(code) < 10:
                continue

            # Infer filename from hint, language, or content
            if fname_hint:
                filename = fname_hint
            elif lang in ("python", "py"):
                filename = "main.py"
            elif lang in ("javascript", "js"):
                filename = "index.js"
            elif lang in ("typescript", "ts"):
                filename = "index.ts"
            elif lang in ("c", "cpp", "c++"):
                filename = "main.c" if lang == "c" else "main.cpp"
            elif lang in ("rust",):
                filename = "main.rs"
            elif lang in ("go",):
                filename = "main.go"
            else:
                filename = f"output.{lang}" if lang else "output.txt"

            # Detect test files by content
            if any(kw in code for kw in ["def test_", "assert ", "pytest", "unittest"]):
                if not fname_hint and filename == "main.py":
                    filename = "test_main.py"

            blocks.append({"filename": filename, "language": lang, "code": code})

        # Deduplicate filenames
        seen = {}
        for block in blocks:
            name = block["filename"]
            if name in seen:
                base, ext = os.path.splitext(name)
                name = f"{base}_{len(seen)}{ext}"
                block["filename"] = name
            seen[name] = True

        return blocks

    def _write_code_to_workspace(
        self, workspace: str, code_blocks: list[dict]
    ) -> list[str]:
        """Write extracted code blocks to workspace directory. Returns list of file paths."""
        written = []
        for block in code_blocks:
            fpath = os.path.join(workspace, block["filename"])
            os.makedirs(os.path.dirname(fpath) or workspace, exist_ok=True)
            with open(fpath, "w") as f:
                f.write(block["code"])
            written.append(fpath)
        return written

    def _run_command(
        self, cmd: list[str], cwd: str, timeout: int = 60
    ) -> dict:
        """
        Run a command in the workspace and capture results.

        Returns {returncode, stdout, stderr, timed_out, duration_s}.
        """
        try:
            start = time.monotonic()
            proc = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            duration = time.monotonic() - start
            return {
                "returncode": proc.returncode,
                "stdout": proc.stdout[:5000],
                "stderr": proc.stderr[:5000],
                "timed_out": False,
                "duration_s": round(duration, 3),
            }
        except subprocess.TimeoutExpired:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
                "timed_out": True,
                "duration_s": timeout,
            }
        except Exception as exc:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": str(exc),
                "timed_out": False,
                "duration_s": 0,
            }

    def get_experimental_commands(self, workspace: str, files: list[str]) -> list[dict]:
        """
        Return domain-specific commands to experimentally verify generated code.

        Override in subclasses for domain-specific verification.
        Returns list of {name, cmd, weight, timeout} dicts.

        Default implementation detects language from file extensions and runs
        appropriate checks (syntax check, lint, test).
        """
        commands = []
        extensions = {os.path.splitext(f)[1] for f in files}

        if ".py" in extensions:
            # Python: syntax check all .py files
            py_files = [f for f in files if f.endswith(".py")]
            commands.append({
                "name": "python_syntax",
                "cmd": ["python3", "-m", "py_compile"] + py_files,
                "weight": 25,
                "timeout": 30,
            })
            # Run tests if test files exist
            test_files = [f for f in py_files if "test" in os.path.basename(f).lower()]
            if test_files:
                commands.append({
                    "name": "python_tests",
                    "cmd": ["python3", "-m", "pytest", "-x", "--tb=short", "-q"] + test_files,
                    "weight": 35,
                    "timeout": 60,
                })
            # Try running main file
            main_files = [f for f in py_files if f not in test_files]
            if main_files:
                commands.append({
                    "name": "python_import",
                    "cmd": ["python3", "-c", f"import importlib.util; "
                            f"spec = importlib.util.spec_from_file_location('m', '{main_files[0]}'); "
                            f"mod = importlib.util.module_from_spec(spec)"],
                    "weight": 15,
                    "timeout": 15,
                })

        if ".js" in extensions or ".ts" in extensions:
            js_files = [f for f in files if f.endswith((".js", ".ts"))]
            commands.append({
                "name": "node_syntax",
                "cmd": ["node", "--check"] + [f for f in js_files if f.endswith(".js")],
                "weight": 25,
                "timeout": 15,
            })

        if ".c" in extensions or ".cpp" in extensions:
            c_files = [f for f in files if f.endswith((".c", ".cpp"))]
            compiler = "gcc" if ".c" in extensions else "g++"
            commands.append({
                "name": "c_compile",
                "cmd": [compiler, "-fsyntax-only", "-Wall", "-Wextra"] + c_files,
                "weight": 35,
                "timeout": 30,
            })

        if ".go" in extensions:
            commands.append({
                "name": "go_build",
                "cmd": ["go", "build", "./..."],
                "weight": 35,
                "timeout": 30,
            })

        if ".rs" in extensions:
            commands.append({
                "name": "rust_check",
                "cmd": ["rustc", "--edition", "2021", "--crate-type", "lib"]
                + [f for f in files if f.endswith(".rs")],
                "weight": 35,
                "timeout": 30,
            })

        return commands

    def _experimental_verify(
        self, result: "RunResult", exercise: "Exercise", workspace: str
    ) -> dict:
        """
        Experimentally verify generated code by actually executing it.

        Steps:
          1. Extract code blocks from agent output
          2. Write them to workspace
          3. Run domain-specific commands (compile, test, lint)
          4. Score based on real results

        Returns {score (0-100), criteria (dict), hints (list), details (dict)}.
        """
        exp_criteria = {}
        exp_hints = []
        details = {}

        # Step 1: Extract code blocks
        code_blocks = self._extract_code_blocks(result.output or "")
        if not code_blocks:
            # No code blocks — check if result has files_changed with real paths
            if result.files_changed:
                existing = [f for f in result.files_changed if os.path.isfile(f)]
                if existing:
                    code_blocks = []  # Use existing files directly
                    files = existing
                else:
                    return {
                        "score": 0,
                        "criteria": {"code_extracted": False},
                        "hints": ["Output must contain code blocks (```lang ... ```) to be experimentally verified"],
                        "details": {"reason": "no_code_blocks"},
                    }
            else:
                return {
                    "score": 0,
                    "criteria": {"code_extracted": False},
                    "hints": ["Output must contain code blocks (```lang ... ```) to be experimentally verified"],
                    "details": {"reason": "no_code_blocks"},
                }

        # Step 2: Write code to workspace (if extracted from output)
        if code_blocks:
            files = self._write_code_to_workspace(workspace, code_blocks)
            exp_criteria["code_extracted"] = True
            exp_criteria["files_written"] = len(files)
            details["files"] = [os.path.basename(f) for f in files]
        else:
            files = result.files_changed

        # Step 3: Get and run experimental commands
        commands = self.get_experimental_commands(workspace, files)
        if not commands:
            # No commands available for this language — partial credit for having code
            return {
                "score": 20,
                "criteria": {**exp_criteria, "has_code": True, "no_verifier": True},
                "hints": ["No experimental verifier available for this language"],
                "details": {**details, "reason": "no_verifier_commands"},
            }

        total_weight = sum(c["weight"] for c in commands)
        earned_weight = 0
        command_results = []

        for cmd_spec in commands:
            cmd_result = self._run_command(
                cmd_spec["cmd"], cwd=workspace, timeout=cmd_spec.get("timeout", 60)
            )
            passed = cmd_result["returncode"] == 0
            command_results.append({
                "name": cmd_spec["name"],
                "passed": passed,
                "returncode": cmd_result["returncode"],
                "duration_s": cmd_result["duration_s"],
                "stdout_preview": cmd_result["stdout"][:200],
                "stderr_preview": cmd_result["stderr"][:200],
            })

            exp_criteria[f"exp:{cmd_spec['name']}"] = passed
            if passed:
                earned_weight += cmd_spec["weight"]
            else:
                stderr = cmd_result["stderr"][:200]
                exp_hints.append(
                    f"{cmd_spec['name']} failed: {stderr}" if stderr
                    else f"{cmd_spec['name']} failed with exit code {cmd_result['returncode']}"
                )

        # Score = proportion of weight earned, scaled to 100
        exp_score = (earned_weight / total_weight * 100) if total_weight > 0 else 0
        details["command_results"] = command_results
        details["earned_weight"] = earned_weight
        details["total_weight"] = total_weight

        return {
            "score": round(exp_score, 1),
            "criteria": exp_criteria,
            "hints": exp_hints,
            "details": details,
        }

    def _combined_grade(
        self,
        exercise: "Exercise",
        result: "RunResult",
        structural_score: float,
        structural_criteria: dict,
        structural_hints: list[str],
        domain_context: str = "",
    ) -> "ExerciseScore":
        """
        Three-way grading: experimental (40%) + LLM-as-judge (30%) + structural (30%).

        Experimental = real code execution (compile, test, run).
        LLM = semantic quality judgment by another LLM.
        Structural = pattern matching on output (fast, deterministic fallback).

        Falls back gracefully: if experimental fails, uses structural + LLM.
        If LLM fails, uses experimental + structural.
        """
        # Try experimental verification first
        workspace = result.metrics.get("workspace") or tempfile.mkdtemp(prefix="sage_exp_")
        exp_result = self._experimental_verify(result, exercise, workspace)
        has_experimental = exp_result["score"] > 0 or exp_result.get("criteria", {}).get("code_extracted")

        # LLM grading
        llm_result = self._llm_grade(exercise, result, domain_context)
        has_llm = "error" not in llm_result

        # Calculate final score based on available signals
        if has_experimental and has_llm:
            # Best case: all three signals — experimental 40%, LLM 30%, structural 30%
            exp_score = exp_result["score"]
            llm_score = llm_result["score"]
            final_score = exp_score * 0.4 + llm_score * 0.3 + structural_score * 0.3
        elif has_experimental and not has_llm:
            # Experimental + structural only — experimental 60%, structural 40%
            exp_score = exp_result["score"]
            final_score = exp_score * 0.6 + structural_score * 0.4
        elif not has_experimental and has_llm:
            # LLM + structural only (old behavior) — LLM 60%, structural 40%
            llm_score = llm_result["score"]
            final_score = llm_score * 0.6 + structural_score * 0.4
        else:
            # Structural only
            final_score = structural_score

        final_score = min(round(final_score, 1), 100.0)

        # Merge all criteria
        merged_criteria = {**structural_criteria}
        for k, v in exp_result.get("criteria", {}).items():
            merged_criteria[k] = v
        if has_llm:
            for k, v in llm_result.get("criteria_results", {}).items():
                merged_criteria[f"llm:{k}"] = v

        # Merge all hints
        merged_hints = list(structural_hints)
        for h in exp_result.get("hints", []):
            if h not in merged_hints:
                merged_hints.append(h)
        if has_llm:
            for h in llm_result.get("improvement_hints", []):
                if h not in merged_hints:
                    merged_hints.append(h)

        # Build feedback summary
        feedback_parts = []
        if has_experimental:
            exp_details = exp_result.get("details", {})
            cmd_results = exp_details.get("command_results", [])
            passed_cmds = sum(1 for c in cmd_results if c["passed"])
            total_cmds = len(cmd_results)
            feedback_parts.append(
                f"Experimental: {passed_cmds}/{total_cmds} checks passed "
                f"(score: {exp_result['score']:.0f}/100)"
            )
        if has_llm:
            feedback_parts.append(
                f"LLM judge: {llm_result['score']:.0f}/100 — "
                f"{llm_result.get('feedback', '')[:200]}"
            )
        feedback_parts.append(f"Structural: {structural_score:.0f}/100")

        return ExerciseScore(
            exercise_id=exercise.id,
            passed=final_score >= 50,
            score=final_score,
            criteria_results=merged_criteria,
            feedback=" | ".join(feedback_parts),
            improvement_hints=merged_hints,
        )

    # ── Shared helpers ──────────────────────────────────────────────────

    def _new_run_id(self) -> str:
        return str(uuid.uuid4())

    def _make_result(
        self,
        run_id: str,
        status: str,
        tier: str = "direct",
        **kwargs,
    ) -> RunResult:
        """Create a RunResult and store it."""
        result = RunResult(
            run_id=run_id,
            status=status,
            runner=self.name,
            tier=tier,
            **kwargs,
        )
        self._runs[run_id] = result
        return result

    def _make_error(self, run_id: str, error: str, tier: str = "direct") -> RunResult:
        """Create an error RunResult."""
        return self._make_result(
            run_id=run_id,
            status="error",
            tier=tier,
            errors=[error],
        )

    def _timed_execute(self, func, *args, **kwargs) -> tuple[Any, float]:
        """Execute a function and return (result, duration_seconds)."""
        start = time.monotonic()
        result = func(*args, **kwargs)
        duration = time.monotonic() - start
        return result, duration

    def get_status(self, run_id: str) -> dict:
        """Return status of a previous run."""
        result = self._runs.get(run_id)
        if result is None:
            return {"error": f"Run '{run_id}' not found", "run_id": run_id}
        return result.to_dict()


# ---------------------------------------------------------------------------
# Runner Registry — maps agent_role → runner name
# ---------------------------------------------------------------------------

# Populated at import time by each runner module calling register_runner()
_RUNNER_REGISTRY: dict[str, str] = {}
_RUNNER_INSTANCES: dict[str, BaseRunner] = {}


def register_runner(runner: BaseRunner) -> None:
    """Register a domain runner for its declared roles."""
    _RUNNER_INSTANCES[runner.name] = runner
    for role in runner.roles:
        _RUNNER_REGISTRY[role] = runner.name
    logger.info("Registered runner '%s' for roles: %s", runner.name, runner.roles)


def register_supplementary_runner(runner: BaseRunner) -> None:
    """
    Register a supplementary runner (does NOT override primary role mappings).

    The runner instance is available via get_runner_by_name() but does NOT
    replace the primary runner for any role. Use for runners that provide
    additional capabilities to roles that already have a primary runner
    (e.g., browser testing for qa_engineer who primarily uses openswe).
    """
    _RUNNER_INSTANCES[runner.name] = runner
    logger.info("Registered supplementary runner '%s' for roles: %s", runner.name, runner.roles)


def get_runner_for_role(role: str) -> Optional[BaseRunner]:
    """Get the appropriate domain runner for an agent role."""
    runner_name = _RUNNER_REGISTRY.get(role)
    if runner_name:
        return _RUNNER_INSTANCES.get(runner_name)
    return None


def get_runner_by_name(name: str) -> Optional[BaseRunner]:
    """Get a runner by its name (e.g., 'openswe', 'openfw')."""
    return _RUNNER_INSTANCES.get(name)


def list_runners() -> list[dict]:
    """List all registered runners and their roles."""
    return [
        {
            "name": runner.name,
            "roles": runner.roles,
            "docker_image": runner.docker_image,
            "toolchain": runner.get_toolchain(),
            "workflow_steps": len(runner.get_workflow()),
        }
        for runner in _RUNNER_INSTANCES.values()
    ]


def get_role_to_runner_map() -> dict[str, str]:
    """Return the full role → runner name mapping."""
    return dict(_RUNNER_REGISTRY)


# ---------------------------------------------------------------------------
# Role family constants — which roles belong to which runner
# ---------------------------------------------------------------------------

SWE_ROLES = [
    "developer", "qa_engineer", "system_tester", "devops_engineer",
    "localization_engineer", "data_engineer", "agentic_engineer",
    "system_engineer",
]

FIRMWARE_ROLES = [
    "firmware_engineer", "embedded_tester",
]

EDA_ROLES = [
    "pcb_designer",
]

SIM_ROLES = [
    "hardware_sim_engineer",
]

ML_ROLES = [
    "data_scientist", "ml_engineer", "gen_ai_engineer",
]

DOC_ROLES = [
    "technical_writer", "regulatory_specialist", "legal_advisor",
    "safety_engineer", "business_analyst", "financial_analyst",
    "analyst",
]

DESIGN_ROLES = [
    "ux_designer",
]

BROWSER_ROLES = [
    "qa_engineer", "system_tester", "ux_designer",
]

STRATEGY_ROLES = [
    "product_manager", "marketing_strategist", "operations_manager",
]

TERMINAL_ROLES = [
    "terminal_operator", "shell_expert",
]

RESEARCH_ROLES = [
    "research_engineer", "ml_researcher",
]

# Orchestration roles don't need a runner — they plan/review, not execute
ORCHESTRATION_ROLES = [
    "planner", "monitor", "critic",
]

# All role families for validation
ALL_ROLE_FAMILIES = {
    "openswe": SWE_ROLES,
    "openfw": FIRMWARE_ROLES,
    "openeda": EDA_ROLES,
    "opensim": SIM_ROLES,
    "openml": ML_ROLES,
    "opendoc": DOC_ROLES,
    "opendesign": DESIGN_ROLES,
    "openstrategy": STRATEGY_ROLES,
    "openterminal": TERMINAL_ROLES,
    "autoresearch": RESEARCH_ROLES,
    "orchestration": ORCHESTRATION_ROLES,
}

# Supplementary runner families — roles that have ADDITIONAL capabilities
# beyond their primary family. Not in ALL_ROLE_FAMILIES to avoid overlap.
SUPPLEMENTARY_FAMILIES = {
    "openbrowser": BROWSER_ROLES,  # qa_engineer, system_tester, ux_designer can also do browser testing
}


# ---------------------------------------------------------------------------
# Auto-import all domain runners to trigger registration
# ---------------------------------------------------------------------------

def _auto_register_runners():
    """Import all runner modules so they self-register via register_runner()."""
    import importlib
    runner_modules = [
        "src.integrations.openswe_adapter",
        "src.integrations.openfw_runner",
        "src.integrations.openeda_runner",
        "src.integrations.opensim_runner",
        "src.integrations.openml_runner",
        "src.integrations.opendoc_runner",
        "src.integrations.opendesign_runner",
        "src.integrations.openbrowser_runner",
        "src.integrations.openstrategy_runner",
        "src.integrations.openterminal_runner",
        "src.integrations.autoresearch_runner",
    ]
    for mod in runner_modules:
        try:
            importlib.import_module(mod)
        except Exception as exc:
            logger.debug("Could not import runner %s: %s", mod, exc)


_auto_register_runners()
