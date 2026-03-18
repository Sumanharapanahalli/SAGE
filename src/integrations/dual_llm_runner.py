"""
SAGE[ai] - Dual LLM Runner (Teacher-Student Architecture)
==========================================================
Configurable teacher-student LLM architecture for solution domains.
A local student model and a cloud teacher both operate on domain tasks.

Strategies:
  teacher_only      -- Teacher handles all; student observes for distillation
  student_first     -- Student first; escalate to teacher if confidence < threshold
  parallel_compare  -- Both run concurrently; judge picks better result
  student_only      -- Student handles all (post-training phase)

Configuration in solutions/<name>/project.yaml:
  llm_strategy:
    mode: "dual"
    student:
      provider: "ollama"
      model: "gemma3:1b"
      confidence_threshold: 0.82
      handles_task_tiers: ["light"]
    teacher:
      provider: "gemini"
      model: "gemini-2.5-flash"
    strategy: "student_first"
    task_overrides:
      ANALYZE_CRASH: "parallel_compare"
    distillation:
      enabled: true
      output_dir: "data/distillation/<solution>/"
      min_samples_before_training: 200
      format: "alpaca"
"""

import json
import logging
import os
import time
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("DualLLMRunner")


def score_confidence(output: dict, task_type: str = "") -> float:
    """
    Rule-based confidence scorer for student model output.
    Returns 0.0-1.0. Used in student_first mode to decide escalation.
    """
    if not isinstance(output, dict):
        return 0.0

    score = 1.0

    # Check for common required fields
    if "severity" in output:
        valid_severities = {"RED", "AMBER", "GREEN", "UNKNOWN", "HIGH", "MEDIUM", "LOW", "CRITICAL", "INFO"}
        if str(output["severity"]).upper() not in valid_severities:
            score -= 0.4

    # Generic filler root cause reduces confidence
    generic_phrases = [
        "unknown error", "something went wrong", "error occurred",
        "an error", "not sure", "cannot determine",
    ]
    root_cause = str(output.get("root_cause_hypothesis", output.get("root_cause", ""))).lower()
    if any(p in root_cause for p in generic_phrases):
        score -= 0.25

    # Very short response is suspect
    total_chars = sum(len(str(v)) for v in output.values())
    if total_chars < 50:
        score -= 0.3

    return max(0.0, min(1.0, score))


class DualLLMRunner:
    """
    Manages teacher-student LLM routing for a solution.
    Instantiated per-solution by LLMGateway when llm_strategy.mode == "dual".
    """

    def __init__(self, strategy_config: dict, solution_name: str = ""):
        self.logger = logging.getLogger("DualLLMRunner")
        self.solution_name = solution_name
        self._lock = threading.Lock()

        student_cfg = strategy_config.get("student", {})
        teacher_cfg = strategy_config.get("teacher", {})
        self.default_strategy = strategy_config.get("strategy", "teacher_only")
        self.task_overrides = strategy_config.get("task_overrides", {})
        self.confidence_threshold = float(student_cfg.get("confidence_threshold", 0.82))

        distill_cfg = strategy_config.get("distillation", {})
        self.distillation_enabled = distill_cfg.get("enabled", True)
        _base = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data", "distillation",
        )
        self.distillation_dir = distill_cfg.get(
            "output_dir",
            os.path.join(_base, solution_name or "default"),
        )
        self.min_samples = int(distill_cfg.get("min_samples_before_training", 200))
        self.distill_format = distill_cfg.get("format", "alpaca")

        # Build student and teacher providers
        self._student_provider = self._build_provider(student_cfg)
        self._teacher_provider = self._build_provider(teacher_cfg)

        self.logger.info(
            "DualLLMRunner ready: strategy=%s student=%s teacher=%s",
            self.default_strategy,
            student_cfg.get("model", "?"),
            teacher_cfg.get("model", "?"),
        )

    def _build_provider(self, cfg: dict):
        """Build an LLM provider from a config dict."""
        if not cfg:
            return None
        provider_name = cfg.get("provider", "ollama")
        model = cfg.get("model", "")
        try:
            if provider_name == "ollama":
                from src.core.llm_gateway import OllamaProvider
                merged = {"ollama_model": model, "ollama_host": cfg.get("ollama_host", "http://localhost:11434"), "timeout": 60}
                return OllamaProvider(merged)
            elif provider_name == "gemini":
                from src.core.llm_gateway import GeminiCLIProvider
                return GeminiCLIProvider({"gemini_model": model or "gemini-2.5-flash", "timeout": 120})
            elif provider_name == "claude-code":
                from src.core.llm_gateway import ClaudeCodeCLIProvider
                return ClaudeCodeCLIProvider({"claude_model": model or "claude-sonnet-4-6", "timeout": 120})
            elif provider_name == "claude":
                from src.core.llm_gateway import ClaudeAPIProvider
                return ClaudeAPIProvider({"claude_model": model or "claude-sonnet-4-6", "timeout": 120})
        except Exception as e:
            self.logger.warning("Could not build provider %s: %s", provider_name, e)
        return None

    def generate(self, prompt: str, system_prompt: str, task_type: str = "") -> str:
        """
        Main entry point. Routes based on strategy, returns best response.
        Falls back to teacher if student unavailable.
        """
        strategy = self.task_overrides.get(task_type.upper(), self.default_strategy)

        if strategy == "teacher_only":
            return self._teacher_generate(prompt, system_prompt, observe=True, task_type=task_type)

        elif strategy == "student_only":
            if self._student_provider:
                return self._student_provider.generate(prompt, system_prompt)
            return self._teacher_generate(prompt, system_prompt, observe=False, task_type=task_type)

        elif strategy == "student_first":
            return self._student_first(prompt, system_prompt, task_type)

        elif strategy == "parallel_compare":
            return self._parallel_compare(prompt, system_prompt, task_type)

        else:
            return self._teacher_generate(prompt, system_prompt, observe=False, task_type=task_type)

    def _teacher_generate(self, prompt: str, system_prompt: str, observe: bool = True, task_type: str = "") -> str:
        """Generate with teacher. If observe=True, log to distillation."""
        if self._teacher_provider is None:
            return "Error: Teacher provider not configured."
        result = self._teacher_provider.generate(prompt, system_prompt)
        if observe and self.distillation_enabled:
            self._log_distillation("shadow_observations", {
                "task_type": task_type,
                "input": prompt[:500],
                "teacher_output": result[:1000],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        return result

    def _student_first(self, prompt: str, system_prompt: str, task_type: str) -> str:
        """Student generates first; escalate to teacher if confidence low."""
        if self._student_provider is None:
            return self._teacher_generate(prompt, system_prompt, observe=True, task_type=task_type)

        student_result = self._student_provider.generate(prompt, system_prompt)

        # Score the student output
        try:
            import json as _json
            start = student_result.find("{")
            end = student_result.rfind("}") + 1
            if start >= 0 and end > start:
                parsed = _json.loads(student_result[start:end])
                confidence = score_confidence(parsed, task_type)
            else:
                confidence = 0.5  # non-JSON -- uncertain
        except Exception:
            confidence = 0.5

        if confidence >= self.confidence_threshold:
            return student_result

        # Escalate to teacher
        self.logger.info("Escalating %s to teacher (confidence=%.2f < %.2f)", task_type, confidence, self.confidence_threshold)
        teacher_result = self._teacher_generate(prompt, system_prompt, observe=False, task_type=task_type)
        if self.distillation_enabled:
            self._log_distillation("escalations", {
                "task_type": task_type,
                "input": prompt[:500],
                "student_output": student_result[:500],
                "teacher_output": teacher_result[:500],
                "student_confidence": confidence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        return teacher_result

    def _parallel_compare(self, prompt: str, system_prompt: str, task_type: str) -> str:
        """Run student + teacher concurrently; return the better result."""
        if self._student_provider is None:
            return self._teacher_generate(prompt, system_prompt, observe=True, task_type=task_type)

        results = {}

        def run_student():
            try:
                results["student"] = self._student_provider.generate(prompt, system_prompt)
            except Exception as e:
                results["student_error"] = str(e)

        def run_teacher():
            try:
                results["teacher"] = self._teacher_generate(prompt, system_prompt, observe=False, task_type=task_type)
            except Exception as e:
                results["teacher_error"] = str(e)

        t1 = threading.Thread(target=run_student)
        t2 = threading.Thread(target=run_teacher)
        t1.start()
        t2.start()
        t1.join(timeout=90)
        t2.join(timeout=120)

        student_out = results.get("student", "")
        teacher_out = results.get("teacher", "")

        if not student_out:
            return teacher_out or "Error: Both providers failed."
        if not teacher_out:
            return student_out

        # Simple judge: parse JSON, score both, return winner
        student_score = 0.5
        teacher_score = 0.7  # teacher gets slight default advantage
        try:
            import json as _json
            for out, key in ((student_out, "student"), (teacher_out, "teacher")):
                s = out.find("{")
                e = out.rfind("}") + 1
                if s >= 0 and e > s:
                    parsed = _json.loads(out[s:e])
                    sc = score_confidence(parsed, task_type)
                    if key == "student":
                        student_score = sc
                    else:
                        teacher_score = sc
        except Exception:
            pass

        winner = "student" if student_score > teacher_score else "teacher"

        if self.distillation_enabled:
            self._log_distillation("comparisons", {
                "task_type": task_type,
                "input": prompt[:500],
                "student": student_out[:500],
                "teacher": teacher_out[:500],
                "winner": winner,
                "scores": {"student": student_score, "teacher": teacher_score},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        return student_out if winner == "student" else teacher_out

    def _log_distillation(self, log_type: str, entry: dict):
        """Append a distillation entry to the appropriate JSONL file."""
        try:
            os.makedirs(self.distillation_dir, exist_ok=True)
            path = os.path.join(self.distillation_dir, f"{log_type}.jsonl")
            with self._lock:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry) + "\n")
        except Exception as e:
            self.logger.debug("Distillation log failed (non-fatal): %s", e)

    def get_stats(self) -> dict:
        """Return distillation stats for this solution."""
        stats = {
            "solution": self.solution_name,
            "strategy": self.default_strategy,
            "distillation_dir": self.distillation_dir,
            "counts": {},
        }
        for log_type in ("comparisons", "escalations", "shadow_observations"):
            path = os.path.join(self.distillation_dir, f"{log_type}.jsonl")
            if os.path.isfile(path):
                try:
                    with open(path) as f:
                        count = sum(1 for _ in f)
                    stats["counts"][log_type] = count
                except Exception:
                    stats["counts"][log_type] = 0
            else:
                stats["counts"][log_type] = 0
        return stats

    def export_training_data(self, fmt: str = "alpaca") -> list:
        """Export distillation data in Alpaca or ShareGPT format."""
        data = []
        for log_type in ("escalations", "comparisons"):
            path = os.path.join(self.distillation_dir, f"{log_type}.jsonl")
            if not os.path.isfile(path):
                continue
            try:
                with open(path) as f:
                    for line in f:
                        entry = json.loads(line.strip())
                        teacher_out = entry.get("teacher_output") or entry.get("teacher", "")
                        if not teacher_out:
                            continue
                        if fmt == "alpaca":
                            data.append({
                                "instruction": entry.get("input", ""),
                                "input": "",
                                "output": teacher_out,
                                "task_type": entry.get("task_type", ""),
                            })
                        else:  # sharegpt
                            data.append({
                                "conversations": [
                                    {"from": "human", "value": entry.get("input", "")},
                                    {"from": "gpt", "value": teacher_out},
                                ]
                            })
            except Exception as e:
                self.logger.warning("Export failed for %s: %s", log_type, e)
        return data
