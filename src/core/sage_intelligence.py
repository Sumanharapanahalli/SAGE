"""
SAGE[ai] - Framework Intelligence Layer (SLM)
=============================================
Wraps a locally-running small language model (Gemma 3 1B via Ollama) as the
always-on SAGE framework intelligence layer. Handles framework-level tasks:

  - YAML lint before file write
  - Meta-query conversion (natural language -> API call)
  - Task complexity classification (LIGHT / STANDARD / HEAVY)
  - Framework Q&A via /sage/ask

Falls back gracefully when the SLM is unavailable -- zero breaking changes.
"""

import json
import logging
import os
from enum import Enum
from typing import Optional

logger = logging.getLogger("SAGEIntelligence")

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config", "config.yaml",
)


class TaskTier(str, Enum):
    LIGHT    = "light"     # classification, triage, short summaries -> SLM handles
    STANDARD = "standard"  # analysis, MR review, planning -> full LLM
    HEAVY    = "heavy"     # multi-step ReAct, AutoGen code gen -> full LLM + tools


def _load_sage_intel_config() -> dict:
    try:
        import yaml
        with open(_CONFIG_PATH) as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("sage_intelligence", {})
    except Exception:
        return {}


class SAGEIntelligence:
    """
    Framework-level SLM wrapper. All methods degrade gracefully to
    returning None / defaults when disabled or SLM unavailable.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.logger = logging.getLogger("SAGEIntelligence")
        cfg = _load_sage_intel_config()
        self.enabled = cfg.get("enabled", False)
        self.model = cfg.get("model", "gemma3:1b")
        self.provider = cfg.get("provider", "ollama")
        self.light_task_threshold = float(cfg.get("light_task_threshold", 0.85))
        self.fallback_on_error = cfg.get("fallback_on_error", True)
        self.host = cfg.get("ollama_host", "http://localhost:11434")

        if self.enabled:
            self.logger.info(
                "SAGEIntelligence enabled (model=%s, provider=%s)", self.model, self.provider
            )
        else:
            self.logger.info("SAGEIntelligence disabled (set sage_intelligence.enabled: true to activate)")

    def _ollama_generate(self, prompt: str, system: str = "") -> Optional[str]:
        """Call Ollama with the SLM model. Returns None on any error."""
        if not self.enabled:
            return None
        import json as _json
        import urllib.request as _req
        import urllib.error

        payload = _json.dumps({
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 512},
        }).encode()

        try:
            request = _req.Request(
                f"{self.host}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with _req.urlopen(request, timeout=15) as resp:
                data = _json.loads(resp.read().decode())
                return data.get("response", "").strip()
        except Exception as e:
            self.logger.debug("SLM call failed (non-fatal): %s", e)
            return None

    def classify_task_tier(self, task_description: str) -> TaskTier:
        """
        Classify a task as LIGHT, STANDARD, or HEAVY.
        Used by queue_manager to route cheap tasks to SLM.
        Falls back to STANDARD on error.
        """
        if not self.enabled:
            return TaskTier.STANDARD

        system = (
            "You are a task classifier for the SAGE AI agent framework. "
            "Classify each task into exactly one tier: LIGHT, STANDARD, or HEAVY.\n\n"
            "LIGHT: severity classification, short summaries, field extraction, simple Q&A\n"
            "STANDARD: root cause analysis, code review, planning, MR creation\n"
            "HEAVY: multi-step reasoning, code generation, complex orchestration\n\n"
            "Respond with ONLY one word: LIGHT, STANDARD, or HEAVY."
        )
        response = self._ollama_generate(task_description, system)
        if response is None:
            return TaskTier.STANDARD

        upper = response.strip().upper()
        if upper in ("LIGHT", "STANDARD", "HEAVY"):
            return TaskTier(upper.lower())
        return TaskTier.STANDARD

    def respond_light_task(self, task: str, context: str = "") -> Optional[str]:
        """
        Handle a LIGHT tier task directly with the SLM.
        Returns None if SLM is unavailable or response is below threshold.
        """
        if not self.enabled:
            return None
        prompt = f"{context}\n\n{task}" if context else task
        system = (
            "You are a precise AI assistant embedded in the SAGE framework. "
            "Answer concisely and accurately. For JSON outputs, return only valid JSON."
        )
        return self._ollama_generate(prompt, system)

    def lint_yaml(self, file_name: str, content: str) -> list:
        """
        Check a YAML file for common SAGE configuration mistakes.
        Returns a list of {field, message, suggestion} dicts. Empty list = no issues.
        """
        return self._rule_based_yaml_lint(file_name, content)

    def _rule_based_yaml_lint(self, file_name: str, content: str) -> list:
        """Rule-based YAML lint -- no SLM required. Catches common SAGE mistakes."""
        import yaml
        errors = []

        try:
            parsed = yaml.safe_load(content) or {}
        except yaml.YAMLError as e:
            return [{"field": "root", "message": f"Invalid YAML syntax: {e}", "suggestion": "Fix YAML syntax errors."}]

        if file_name == "project":
            # Required top-level fields
            for field in ("name", "version", "domain"):
                if field not in parsed:
                    errors.append({
                        "field": field,
                        "message": f"Required field '{field}' is missing.",
                        "suggestion": f"Add '{field}: \"your value\"' to project.yaml",
                    })
            # active_modules should be a list
            if "active_modules" in parsed and not isinstance(parsed["active_modules"], list):
                errors.append({
                    "field": "active_modules",
                    "message": "active_modules must be a list.",
                    "suggestion": "Change to:\nactive_modules:\n  - dashboard\n  - analyst",
                })

        elif file_name == "prompts":
            # roles must exist
            if "roles" not in parsed:
                errors.append({
                    "field": "roles",
                    "message": "prompts.yaml must have a 'roles:' top-level key.",
                    "suggestion": "Add:\nroles:\n  analyst:\n    name: Analyst\n    system_prompt: ...",
                })
            else:
                roles = parsed.get("roles", {})
                for role_id, role in roles.items():
                    if not isinstance(role, dict):
                        continue
                    sp = role.get("system_prompt", "")
                    if sp and "json" not in sp.lower() and "JSON" not in sp:
                        errors.append({
                            "field": f"roles.{role_id}.system_prompt",
                            "message": f"Role '{role_id}' system_prompt may produce non-JSON output.",
                            "suggestion": "Add 'Do not output markdown, prose, or any text outside the JSON object.' to the system_prompt.",
                        })

        elif file_name == "tasks":
            if "task_types" not in parsed:
                errors.append({
                    "field": "task_types",
                    "message": "tasks.yaml must have a 'task_types:' key.",
                    "suggestion": "Add:\ntask_types:\n  - ANALYZE_LOG\n  - PLAN_TASK",
                })

        return errors

    def convert_to_api_call(self, user_input: str, solution_context: dict) -> Optional[dict]:
        """
        Convert a natural language user input to a structured SAGE API call.
        Returns {endpoint, method, body, suggested_task_type} or None.
        """
        if not self.enabled:
            return None

        task_types = solution_context.get("task_types", [])
        system = (
            "You are a SAGE framework API router. Convert user intent to a SAGE API call.\n"
            "Available task types: " + ", ".join(task_types) + "\n\n"
            "Respond with ONLY valid JSON in this exact format:\n"
            '{"endpoint": "/analyze", "method": "POST", "body": {"log_entry": "<input>"}, '
            '"suggested_task_type": "ANALYZE_LOG"}\n\n'
            "Common mappings:\n"
            "- analyze/crash/error/log -> POST /analyze with log_entry\n"
            "- review/MR/PR -> POST /mr/review\n"
            "- plan/task/feature -> POST /agent/run with role=planner\n"
            "- ask/help/how -> GET /sage/ask"
        )
        response = self._ollama_generate(user_input, system)
        if response is None:
            return None
        try:
            import json
            # Extract JSON from response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except Exception:
            pass
        return None

    def answer_framework_question(self, question: str) -> str:
        """
        Answer a question about the SAGE framework using the SLM.
        Falls back to a helpful default message if SLM unavailable.
        """
        if not self.enabled:
            return (
                "SAGE Framework Assistant is not enabled. "
                "Set sage_intelligence.enabled: true in config/config.yaml "
                "and install Ollama with: ollama pull gemma3:1b"
            )

        # Load framework docs as context
        docs_context = self._load_framework_docs()
        system = (
            "You are the SAGE Framework Assistant. Answer questions about SAGE accurately and concisely.\n\n"
            "SAGE Framework Documentation:\n" + docs_context + "\n\n"
            "Answer the user's question. If unsure, say so clearly."
        )
        response = self._ollama_generate(question, system)
        if response is None:
            return (
                "SAGE Framework Assistant is temporarily unavailable. "
                "Check that Ollama is running: `ollama serve` and model is available: `ollama pull gemma3:1b`"
            )
        return response

    def _load_framework_docs(self) -> str:
        """Load key framework docs as context for the SLM."""
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        docs = []
        for path in [
            os.path.join(base, "GETTING_STARTED.md"),
            os.path.join(base, "ARCHITECTURE.md"),
        ]:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Truncate each doc to 2000 chars for SLM context
                    docs.append(f"=== {os.path.basename(path)} ===\n{content[:2000]}")
            except Exception:
                pass
        return "\n\n".join(docs) if docs else "SAGE is a modular AI agent framework."


sage_intelligence = SAGEIntelligence()
