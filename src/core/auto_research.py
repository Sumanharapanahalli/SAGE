"""
SAGE Framework — AutoResearch Engine
=======================================
Autonomous experiment engine inspired by Karpathy's autoresearch.

Source: https://github.com/karpathy/autoresearch

Core principle: hill-climbing experiment loop.
  1. Propose a code change (LLM generates hypothesis + diff)
  2. Run the experiment (fixed wall-clock budget)
  3. Extract the metric from output
  4. Keep if improved, discard if not (git commit / git reset)
  5. Loop forever — the "never stop" principle

Git is the experiment tracker:
  - Each experiment runs on a branch
  - Successful experiments are committed (checkpoint)
  - Failed experiments are reset (discard)
  - The commit log IS the experiment log

Thread-safe. SQLite-backed. Non-blocking.
"""

import json
import logging
import os
import re
import sqlite3
import subprocess
import threading
import time
import uuid
from typing import Any, Optional

logger = logging.getLogger("AutoResearch")


class AutoResearchEngine:
    """
    Autonomous experiment engine with hill-climbing optimization.

    Runs experiments in a loop: LLM proposes code changes, experiments run
    with fixed budget, metrics are extracted, and changes are kept/discarded.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.path.join(os.getcwd(), ".sage", "auto_research.db")
        self._db_path = db_path
        self._lock = threading.Lock()
        self._baseline_metric: Optional[float] = None
        self._default_budget_s = 300
        self._program: str = ""
        self._init_db()

    # ------------------------------------------------------------------
    # SQLite persistence
    # ------------------------------------------------------------------

    def _init_db(self):
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS experiments (
                    id TEXT PRIMARY KEY,
                    experiment_id TEXT,
                    description TEXT,
                    hypothesis TEXT,
                    metric_name TEXT,
                    metric_value REAL,
                    baseline REAL,
                    decision TEXT,
                    commit_hash TEXT,
                    duration_s REAL,
                    status TEXT,
                    error TEXT,
                    files_changed TEXT,
                    created_at REAL
                )
            """)
            conn.commit()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Core experiment loop
    # ------------------------------------------------------------------

    def run_experiment(
        self,
        workspace: str,
        metric_name: str,
        run_command: str,
        budget_s: Optional[int] = None,
        direction: str = "lower",
    ) -> dict:
        """
        Run a single experiment: propose → apply → execute → measure → keep/discard.
        """
        if budget_s is None:
            budget_s = self._default_budget_s

        experiment_id = f"exp-{uuid.uuid4().hex[:8]}"

        # 1. LLM proposes a code change
        history = self.get_results(limit=10)
        prompt = self._build_experiment_prompt(workspace, self._baseline_metric, history)
        try:
            from src.core.llm_gateway import llm_gateway
            llm_response = llm_gateway.generate(prompt)
            proposal = json.loads(llm_response)
        except Exception as e:
            logger.warning("LLM proposal failed: %s", e)
            proposal = {"description": "No proposal", "changes": [], "hypothesis": "N/A"}

        # 2. Apply changes
        changes = proposal.get("changes", [])
        if changes:
            self._apply_changes(changes, workspace)

        # 3. Commit changes before running
        commit_hash = self._git_commit(workspace, proposal.get("description", experiment_id))

        # 4. Execute experiment
        result = self._execute_experiment(workspace, run_command, budget_s)

        # 5. Extract metric
        metric_value = None
        if result["status"] == "completed":
            metric_value = self._extract_metric(result.get("output", ""), metric_name)
            if metric_value is not None:
                result["metric_value"] = metric_value

        # 6. Decide: keep or discard
        if result["status"] == "crashed" or metric_value is None:
            decision = "discard"
            self._git_reset(workspace)
        elif self._baseline_metric is not None and self._is_improvement(
            metric_value, self._baseline_metric, direction
        ):
            decision = "keep"
            self._baseline_metric = metric_value
        else:
            decision = "discard"
            self._git_reset(workspace)

        result["decision"] = decision
        result["experiment_id"] = experiment_id
        result["description"] = proposal.get("description", "")
        result["hypothesis"] = proposal.get("hypothesis", "")
        result["commit_hash"] = commit_hash
        result["baseline"] = self._baseline_metric
        result["metric_name"] = metric_name

        # 7. Log result
        self.log_result(result)

        return result

    def run_session(
        self,
        workspace: str,
        metric_name: str,
        run_command: str,
        max_experiments: int = 10,
        budget_s: Optional[int] = None,
        direction: str = "lower",
    ) -> dict:
        """
        Run a session of N experiments — the "never stop" loop.
        """
        # Set up branch
        self._create_branch(workspace, f"session-{uuid.uuid4().hex[:6]}")

        # Run baseline first
        baseline = self._run_baseline(workspace, run_command, metric_name, budget_s)
        if baseline is not None:
            self._baseline_metric = baseline

        kept = 0
        discarded = 0
        crashed = 0
        results = []

        for i in range(max_experiments):
            try:
                result = self.run_experiment(
                    workspace=workspace,
                    metric_name=metric_name,
                    run_command=run_command,
                    budget_s=budget_s,
                    direction=direction,
                )
                results.append(result)

                if result.get("status") == "crashed":
                    crashed += 1
                elif result.get("decision") == "keep":
                    kept += 1
                else:
                    discarded += 1

            except Exception as e:
                logger.error("Experiment %d crashed: %s", i, e)
                crashed += 1

        return {
            "total_experiments": max_experiments,
            "kept": kept,
            "discarded": discarded,
            "crashed": crashed,
            "final_baseline": self._baseline_metric,
            "results": results,
        }

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _execute_experiment(
        self,
        workspace: str,
        run_command: str,
        budget_s: int = 300,
    ) -> dict:
        """Run the experiment command with a wall-clock timeout."""
        try:
            result = subprocess.run(
                run_command,
                shell=True,
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=budget_s,
            )
            return {
                "status": "completed" if result.returncode == 0 else "failed",
                "output": result.stdout,
                "error": result.stderr,
                "duration_s": budget_s,  # approximate
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "crashed",
                "error": f"Timeout: experiment exceeded {budget_s}s budget",
                "output": "",
                "duration_s": budget_s,
            }
        except Exception as e:
            return {
                "status": "crashed",
                "error": str(e),
                "output": "",
                "duration_s": 0,
            }

    # ------------------------------------------------------------------
    # Metric extraction
    # ------------------------------------------------------------------

    def _extract_metric(self, output: str, metric_name: str) -> Optional[float]:
        """
        Extract the last occurrence of a named metric from output text.

        Supports patterns like:
          - val_bpb: 2.847
          - accuracy: 0.952
          - loss 3.45
        """
        pattern = rf"{re.escape(metric_name)}[:\s]+([0-9]+\.?[0-9]*)"
        matches = re.findall(pattern, output)
        if not matches:
            return None
        return float(matches[-1])

    def _is_improvement(self, new: float, old: float, direction: str) -> bool:
        """Check if new metric is better than old, given direction."""
        if direction == "lower":
            return new < old
        elif direction == "higher":
            return new > old
        return False

    # ------------------------------------------------------------------
    # Git operations
    # ------------------------------------------------------------------

    def _create_branch(self, workspace: str, tag: str) -> str:
        """Create a new git branch for the experiment."""
        branch_name = f"autoresearch/{tag}"
        try:
            subprocess.run(
                ["git", "checkout", "-b", branch_name],
                cwd=workspace,
                capture_output=True,
                text=True,
            )
        except Exception as e:
            logger.warning("Branch creation failed: %s", e)
        return branch_name

    def _git_commit(self, workspace: str, message: str) -> str:
        """Commit current changes and return the commit hash."""
        try:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=workspace,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "commit", "-m", f"[autoresearch] {message}"],
                cwd=workspace,
                capture_output=True,
                text=True,
            )
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=workspace,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip()
        except Exception as e:
            logger.warning("Git commit failed: %s", e)
            return ""

    def _git_reset(self, workspace: str):
        """Discard the last commit (failed experiment)."""
        try:
            subprocess.run(
                ["git", "reset", "--hard", "HEAD~1"],
                cwd=workspace,
                capture_output=True,
                text=True,
            )
        except Exception as e:
            logger.warning("Git reset failed: %s", e)

    def _apply_changes(self, changes: list, workspace: str) -> bool:
        """Apply search-and-replace changes proposed by the LLM."""
        try:
            for change in changes:
                filepath = change["file"]
                if not os.path.isabs(filepath):
                    filepath = os.path.join(workspace, filepath)

                with open(filepath, "r") as f:
                    content = f.read()

                content = content.replace(change["search"], change["replace"])

                with open(filepath, "w") as f:
                    f.write(content)

            return True
        except Exception as e:
            logger.warning("Apply changes failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Baseline
    # ------------------------------------------------------------------

    def _run_baseline(
        self,
        workspace: str,
        run_command: str,
        metric_name: str,
        budget_s: Optional[int] = None,
    ) -> Optional[float]:
        """Run the baseline experiment to establish starting metric."""
        if budget_s is None:
            budget_s = self._default_budget_s
        result = self._execute_experiment(workspace, run_command, budget_s)
        if result["status"] == "completed":
            return self._extract_metric(result.get("output", ""), metric_name)
        return None

    # ------------------------------------------------------------------
    # Research program (Markdown-as-skill)
    # ------------------------------------------------------------------

    def load_program(self, path: str) -> str:
        """Load a research program from a Markdown file."""
        try:
            with open(path, "r") as f:
                self._program = f.read()
            return self._program
        except FileNotFoundError:
            logger.info("No program.md at %s, using default instructions", path)
            self._program = (
                "You are an autonomous research agent. Propose modifications to the "
                "codebase that will improve the target metric. Each proposal should "
                "include a hypothesis, the specific changes, and expected effect."
            )
            return self._program

    def _build_experiment_prompt(
        self,
        workspace: str,
        baseline: Optional[float],
        history: list,
    ) -> str:
        """Build the LLM prompt for proposing an experiment."""
        parts = []

        if self._program:
            parts.append(f"## Research Program\n{self._program}")

        parts.append(f"## Workspace\n{workspace}")

        if baseline is not None:
            parts.append(f"## Current Baseline\nMetric value: {baseline}")

        if history:
            parts.append("## Recent Experiments")
            for h in history[-5:]:
                desc = h.get("description", "N/A")
                val = h.get("metric_value", "N/A")
                dec = h.get("decision", "N/A")
                parts.append(f"- {desc}: metric={val}, decision={dec}")

        parts.append(
            "## Instructions\n"
            "Propose a single code change that will improve the metric. "
            "Respond with JSON containing: description, hypothesis, changes "
            "(list of {file, search, replace}), expected_effect."
        )

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Results logging
    # ------------------------------------------------------------------

    def log_result(self, result: dict):
        """Log an experiment result to SQLite."""
        with self._lock:
            with self._conn() as conn:
                conn.execute(
                    """INSERT INTO experiments
                       (id, experiment_id, description, hypothesis, metric_name,
                        metric_value, baseline, decision, commit_hash,
                        duration_s, status, error, files_changed, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        str(uuid.uuid4()),
                        result.get("experiment_id", ""),
                        result.get("description", ""),
                        result.get("hypothesis", ""),
                        result.get("metric_name", ""),
                        result.get("metric_value"),
                        result.get("baseline"),
                        result.get("decision", ""),
                        result.get("commit_hash", ""),
                        result.get("duration_s"),
                        result.get("status", ""),
                        result.get("error", ""),
                        json.dumps(result.get("files_changed", [])),
                        time.time(),
                    ),
                )
                conn.commit()

    def get_results(self, limit: int = 100) -> list:
        """Get experiment results ordered by time."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM experiments ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_best_result(self, direction: str = "lower") -> Optional[dict]:
        """Get the experiment with the best metric value."""
        order = "ASC" if direction == "lower" else "DESC"
        with self._conn() as conn:
            row = conn.execute(
                f"SELECT * FROM experiments WHERE metric_value IS NOT NULL "
                f"ORDER BY metric_value {order} LIMIT 1",
            ).fetchone()
            return dict(row) if row else None

    def stats(self) -> dict:
        """Get experiment analytics summary."""
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
            kept = conn.execute(
                "SELECT COUNT(*) FROM experiments WHERE decision='keep'"
            ).fetchone()[0]
            discarded = conn.execute(
                "SELECT COUNT(*) FROM experiments WHERE decision='discard'"
            ).fetchone()[0]
            crashed = conn.execute(
                "SELECT COUNT(*) FROM experiments WHERE status='crashed'"
            ).fetchone()[0]

            best_row = conn.execute(
                "SELECT MIN(metric_value) FROM experiments WHERE metric_value IS NOT NULL"
            ).fetchone()
            best_metric = best_row[0] if best_row else None

            return {
                "total_experiments": total,
                "kept": kept,
                "discarded": discarded,
                "crashed": crashed,
                "best_metric": best_metric,
            }
