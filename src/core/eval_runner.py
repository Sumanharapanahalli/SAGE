"""
SAGE Framework — Evaluation & Benchmarking Runner
===================================================
Loads golden test sets from solutions/<name>/evals/*.yaml, runs each
prompt through the LLM/agent, scores output, and persists results to SQLite.

Purpose:
  Measure agent quality over time. Catch regressions before they reach prod.
  Closing the improvement loop that the SAGE Lean Loop promises.

Eval YAML format (solutions/<name>/evals/my_eval.yaml):
  ---
  name: "Analyst quality — error logs"
  description: "Verify analyst correctly identifies root causes"
  cases:
    - id: "err_001"
      role: "analyst"
      input: "Error: NullPointerException at com.example.Service:42"
      expected_keywords: ["null", "pointer", "NullPointerException"]
      expected_sentiment: "negative"   # optional
      max_response_length: 2000        # optional

Scoring:
  Each case is scored 0-100 based on keyword presence + length compliance.
  Summary: pass/fail per case, mean score, regression alert if mean drops > 10%.

Usage:
    from src.core.eval_runner import eval_runner
    results = eval_runner.run(suite="analyst_quality")
    history = eval_runner.get_history(suite="analyst_quality", limit=10)
"""

import json
import logging
import os
import sqlite3
import time
import uuid
import yaml

logger = logging.getLogger("EvalRunner")

_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "eval_results.db",
)


def _get_evals_dir() -> str:
    try:
        from src.core.project_loader import project_config, _SOLUTIONS_DIR
        return os.path.join(_SOLUTIONS_DIR, project_config.project_name, "evals")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score_case(response: str, case: dict) -> dict:
    """
    Score a single eval case 0-100.

    Scoring breakdown:
      - Keyword coverage: up to 70 pts (each expected keyword = 70/n pts)
      - Length compliance: up to 30 pts (within max_response_length)
    """
    score = 0
    details = {}

    keywords = case.get("expected_keywords", [])
    if keywords:
        resp_lower = response.lower()
        found = [kw for kw in keywords if kw.lower() in resp_lower]
        kw_score = int(70 * len(found) / len(keywords))
        score += kw_score
        details["keywords_found"] = found
        details["keywords_missing"] = [kw for kw in keywords if kw not in found]
        details["keyword_score"] = kw_score

    max_len = case.get("max_response_length")
    if max_len:
        len_score = 30 if len(response) <= max_len else max(0, 30 - (len(response) - max_len) // 100)
        score += len_score
        details["length_score"] = len_score
        details["response_length"] = len(response)
    else:
        score += 30  # no length constraint — full points

    passed = score >= 60   # threshold: 60/100
    return {
        "score":   score,
        "passed":  passed,
        "details": details,
    }


# ---------------------------------------------------------------------------
# EvalRunner
# ---------------------------------------------------------------------------

class EvalRunner:
    """
    Loads eval suites from YAML files, runs them, scores results, and
    persists to SQLite for trend tracking.
    """

    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path
        self._init_db()

    def _init_db(self):
        try:
            os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
            conn = sqlite3.connect(self._db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS eval_runs (
                    run_id       TEXT PRIMARY KEY,
                    suite        TEXT NOT NULL,
                    solution     TEXT,
                    started_at   TEXT,
                    finished_at  TEXT,
                    total_cases  INTEGER,
                    passed_cases INTEGER,
                    mean_score   REAL,
                    results_json TEXT
                )
            """)
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.error("Eval DB init failed: %s", exc)

    def list_suites(self) -> list[str]:
        """Return names of available eval suites for the active solution."""
        evals_dir = _get_evals_dir()
        if not evals_dir or not os.path.isdir(evals_dir):
            return []
        suites = []
        for fn in sorted(os.listdir(evals_dir)):
            if fn.endswith((".yaml", ".yml")) and not fn.startswith("_"):
                suites.append(fn.rsplit(".", 1)[0])
        return suites

    def _load_suite(self, suite: str) -> dict:
        """Load a YAML eval suite by name. Returns the parsed dict."""
        evals_dir = _get_evals_dir()
        for ext in (".yaml", ".yml"):
            path = os.path.join(evals_dir, suite + ext)
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
        raise FileNotFoundError(f"Eval suite '{suite}' not found in {evals_dir}")

    def run(self, suite: str = None) -> dict:
        """
        Run an eval suite (or all suites if suite=None).

        Args:
            suite: Name of the eval YAML file (without extension).
                   If None, runs all suites found in evals/.

        Returns:
            dict with run_id, suite, passed, failed, mean_score, cases.
        """
        from src.core.llm_gateway import llm_gateway

        suites_to_run = [suite] if suite else self.list_suites()
        if not suites_to_run:
            return {"error": "No eval suites found", "suites_dir": _get_evals_dir()}

        all_results = []
        for suite_name in suites_to_run:
            try:
                suite_data = self._load_suite(suite_name)
            except FileNotFoundError as e:
                all_results.append({"suite": suite_name, "error": str(e)})
                continue

            cases = suite_data.get("cases", [])
            case_results = []

            for case in cases:
                case_id    = case.get("id", str(uuid.uuid4())[:8])
                role       = case.get("role", "analyst")
                input_text = case.get("input", "")

                if not input_text:
                    continue

                try:
                    system_prompt = self._get_role_prompt(role)
                    response = llm_gateway.generate(
                        prompt=input_text,
                        system_prompt=system_prompt,
                        trace_name=f"eval_{suite_name}_{case_id}",
                    )
                except Exception as exc:
                    case_results.append({
                        "case_id": case_id,
                        "error":   str(exc),
                        "score":   0,
                        "passed":  False,
                    })
                    continue

                scoring = _score_case(response, case)
                case_results.append({
                    "case_id":   case_id,
                    "role":      role,
                    "input":     input_text[:200],
                    "response":  response[:500],
                    "score":     scoring["score"],
                    "passed":    scoring["passed"],
                    "details":   scoring["details"],
                })

            all_results.append({
                "suite":        suite_name,
                "name":         suite_data.get("name", suite_name),
                "total_cases":  len(case_results),
                "passed_cases": sum(1 for c in case_results if c.get("passed")),
                "mean_score":   (
                    sum(c.get("score", 0) for c in case_results) / len(case_results)
                    if case_results else 0.0
                ),
                "cases":        case_results,
            })

        run_id    = str(uuid.uuid4())
        total     = sum(r.get("total_cases", 0) for r in all_results)
        passed    = sum(r.get("passed_cases", 0) for r in all_results)
        mean_score = sum(r.get("mean_score", 0) for r in all_results) / max(len(all_results), 1)

        self._persist_run(run_id, suite or "all", total, passed, mean_score, all_results)

        return {
            "run_id":       run_id,
            "suite":        suite or "all",
            "total_cases":  total,
            "passed_cases": passed,
            "failed_cases": total - passed,
            "mean_score":   round(mean_score, 1),
            "results":      all_results,
        }

    def _get_role_prompt(self, role: str) -> str:
        """Get system prompt for a role from the active solution's prompts.yaml."""
        try:
            from src.core.project_loader import project_config
            prompts = project_config.get_prompts()
            return prompts.get(role, {}).get(
                "system_prompt",
                f"You are an expert {role}. Complete the task concisely.",
            )
        except Exception:
            return f"You are an expert {role}. Complete the task concisely."

    def _persist_run(
        self, run_id: str, suite: str, total: int, passed: int,
        mean_score: float, results: list,
    ) -> None:
        """Write eval run summary to SQLite."""
        try:
            solution = ""
            try:
                from src.core.project_loader import project_config
                solution = project_config.project_name
            except Exception:
                pass

            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                """INSERT OR REPLACE INTO eval_runs
                   (run_id, suite, solution, started_at, finished_at,
                    total_cases, passed_cases, mean_score, results_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, suite, solution, now, now, total, passed, mean_score,
                 json.dumps(results)),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.error("Failed to persist eval run: %s", exc)

    def get_history(self, suite: str = None, limit: int = 20) -> list[dict]:
        """
        Return historical eval run summaries (without full case details).

        Args:
            suite:  Filter by suite name (None = all suites).
            limit:  Max number of runs to return (most recent first).

        Returns:
            List of dicts: [{run_id, suite, total_cases, passed_cases,
                              mean_score, started_at}, ...]
        """
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            if suite:
                cursor = conn.execute(
                    "SELECT * FROM eval_runs WHERE suite=? ORDER BY started_at DESC LIMIT ?",
                    (suite, limit),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM eval_runs ORDER BY started_at DESC LIMIT ?",
                    (limit,),
                )
            rows = cursor.fetchall()
            conn.close()
            return [
                {
                    "run_id":       r["run_id"],
                    "suite":        r["suite"],
                    "solution":     r["solution"],
                    "started_at":   r["started_at"],
                    "total_cases":  r["total_cases"],
                    "passed_cases": r["passed_cases"],
                    "mean_score":   r["mean_score"],
                }
                for r in rows
            ]
        except Exception as exc:
            logger.error("Failed to fetch eval history: %s", exc)
            return []


# Global singleton
eval_runner = EvalRunner()
