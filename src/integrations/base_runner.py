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
    ├── OpenSWERunner   — Software engineering (explore → code → test → PR)
    ├── OpenFWRunner    — Firmware (HAL code → cross-compile → static analysis → binary metrics)
    ├── OpenEDARunner   — Electronics (schematic → layout → DRC → Gerber)
    ├── OpenSimRunner   — Simulation (model → simulate → waveform → timing)
    ├── OpenMLRunner    — Machine learning (data → train → evaluate → track)
    ├── OpenDocRunner   — Documentation (research → draft → cross-ref → validate)
    ├── OpenDesignRunner— UX/Design (wireframe → prototype → accessibility → tokens)
    └── OpenStrategyRunner — Strategy (analyze → framework → plan → action)

The 3-tier isolation cascade (OpenShell → SandboxRunner → Direct) is orthogonal
to the domain runner: any runner can execute in any isolation tier.

Thread-safe. Audit every action. Return error dicts, never raise.
"""

import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
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
            "output": self.output[:2000] if self.output else "",
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
        """Return required tools, packages, and docker image for this runner."""
        return {
            "runner": self.name,
            "docker_image": self.docker_image,
            "roles": self.roles,
            "tools": [],
            "packages": [],
        }

    def get_workflow(self) -> list[dict]:
        """Return the step sequence for this domain's execution."""
        return [{"step": 1, "name": "execute", "description": "Run task"}]

    def get_experience_keys(self) -> list[str]:
        """Return the vector store key dimensions for experience retrieval."""
        return ["task_type", "domain"]

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
    "localization_engineer",
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
    "data_scientist",
]

DOC_ROLES = [
    "technical_writer", "regulatory_specialist", "legal_advisor",
    "safety_engineer", "business_analyst", "financial_analyst",
    "analyst",
]

DESIGN_ROLES = [
    "ux_designer",
]

STRATEGY_ROLES = [
    "product_manager", "marketing_strategist", "operations_manager",
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
    "orchestration": ORCHESTRATION_ROLES,
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
        "src.integrations.openstrategy_runner",
    ]
    for mod in runner_modules:
        try:
            importlib.import_module(mod)
        except Exception as exc:
            logger.debug("Could not import runner %s: %s", mod, exc)


_auto_register_runners()
