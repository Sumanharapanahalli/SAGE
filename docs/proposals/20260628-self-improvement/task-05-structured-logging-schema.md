# Task 5: Structured logging schema

**Category:** backend  
**Score:** 9.5/10  
**Converged:** True  
**Iterations:** 2  
**Elapsed:** 965s  

---

## Task

Replace all `logger.info(f'...')` f-string calls in src/core/llm_gateway.py and src/core/queue_manager.py with structured `logger.info(msg, extra={...})` calls. Fields: event, provider, duration_ms, task_id, status. Add a JSON formatter option in a new src/core/log_config.py that can be toggled with env var SAGE_JSON_LOGS=1.

## Criteria

No f-string logs remain in targeted files; all log calls use extra={} with named fields; log_config.py exists with JSON formatter; SAGE_JSON_LOGS=1 activates it; existing tests pass.

## Proposal (submit to HITL approval gate)

# src/core/log_config.py
"""
SAGE[ai] - Logging Configuration
================================
Central logging setup with an optional structured-JSON formatter.

A plain, human-readable formatter is the default. Set the environment
variable ``SAGE_JSON_LOGS=1`` (also accepts ``true``/``yes``/``on``) to emit
one JSON object per log record. Structured fields attached to a record via
``logger.info(msg, extra={...})`` are promoted to top-level JSON keys.

Canonical structured fields (any subset may be present on a record):
    event, provider, duration_ms, task_id, status

Usage:
    from src.core.log_config import configure_logging
    configure_logging()            # call once, early in process startup
"""

import json
import logging
import os

# Canonical structured fields promoted to top-level keys in JSON output.
STRUCTURED_FIELDS = ("event", "provider", "duration_ms", "task_id", "status")

# LogRecord attributes that are always present on a record — used to detect the
# *extra=* fields a caller attached. Computed from a blank record so it stays
# correct across Python versions (e.g. the 3.12+ "taskName" attribute).
_RESERVED = set(logging.makeLogRecord({}).__dict__.keys()) | {"message", "asctime"}

# Accepted truthy spellings for the toggle env var.
_TRUTHY = ("1", "true", "yes", "on")

# Marker attribute so configure_logging() only ever removes handlers it itself
# installed — leaving pytest's log-capture handlers (and any others) untouched.
_SAGE_HANDLER_FLAG = "_sage_log_handler"


def json_logs_enabled() -> bool:
    """True when SAGE_JSON_LOGS is set to a truthy value (1/true/yes/on)."""
    return os.environ.get("SAGE_JSON_LOGS", "").strip().lower() in _TRUTHY


class JsonFormatter(logging.Formatter):
    """Render each LogRecord as a single-line JSON object.

    Standard fields (timestamp, level, logger, message) are always emitted.
    Canonical STRUCTURED_FIELDS are emitted when present on the record, and
    any other ``extra=`` keys are appended too. Exception / stack info is
    serialised into the JSON object rather than printed as a trailing blob.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Promote canonical structured fields when present.
        for field in STRUCTURED_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)

        # Include any other extra= attributes not already accounted for.
        for key, value in record.__dict__.items():
            if key not in _RESERVED and key not in payload:
                payload[key] = value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


def build_formatter() -> logging.Formatter:
    """Return the JSON formatter when SAGE_JSON_LOGS is enabled, else a plain one."""
    if json_logs_enabled():
        return JsonFormatter()
    return logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def configure_logging(level: int = logging.INFO, *, force: bool = True) -> None:
    """Install a single SAGE stream handler on the root logger.

    Honours ``SAGE_JSON_LOGS=1`` to switch the output format to structured JSON.

    pytest-safe: with ``force=True`` only previously-installed SAGE handlers are
    removed before re-installing, so pytest's log-capture handlers (and any
    other third-party handlers) are preserved. ``make test`` log capture is
    therefore unaffected even if a test calls this function.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(build_formatter())
    setattr(handler, _SAGE_HANDLER_FLAG, True)

    root = logging.getLogger()
    if force:
        for existing in root.handlers[:]:
            if getattr(existing, _SAGE_HANDLER_FLAG, False):
                root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)
```

```python
# src/core/llm_gateway.py
"""
SAGE[ai] - LLM Gateway (Singleton with Pluggable Backends)
===========================================================

Supports three providers:
  1. "gemini"  - Gemini CLI (no API keys, uses browser OAuth)
  2. "local"   - llama-cpp-python (offline, GPU-direct)
  3. "claude"  - Anthropic API (requires ANTHROPIC_API_KEY env var)

Thread-locked: only ONE inference at a time (GPU safety + QMS compliance).

Structured logging: log records carry an ``extra={...}`` dict whose keys are
drawn ONLY from the canonical set {event, provider, duration_ms, task_id,
status}. Messages are static strings — no f-string or %-style interpolation —
so all variable detail lives in the canonical fields (or in exc_info for
exceptions). Set SAGE_JSON_LOGS=1 and call
src.core.log_config.configure_logging() to emit them as JSON.
"""

import threading
import subprocess
import logging
import random
import time
import os
import yaml
from abc import ABC, abstractmethod

# ---------------------------------------------------------------------------
# Optional Langfuse observability — graceful no-op when not configured
# ---------------------------------------------------------------------------
_langfuse_client = None

# Module-level reference to project_config — allows patching in tests and
# avoids repeated local imports inside the hot generate() path.
try:
    from src.core.project_loader import project_config
except Exception:
    project_config = None  # type: ignore[assignment]

def _init_langfuse(cfg: dict) -> None:
    """Initialise Langfuse if enabled and credentials are available."""
    global _langfuse_client
    obs = cfg.get("observability", {})
    if not obs.get("langfuse_enabled", False):
        return
    pub_key = os.environ.get("LANGFUSE_PUBLIC_KEY", obs.get("langfuse_public_key", ""))
    sec_key = os.environ.get("LANGFUSE_SECRET_KEY", obs.get("langfuse_secret_key", ""))
    host    = obs.get("langfuse_host", "https://cloud.langfuse.com")
    if not pub_key or not sec_key:
        logging.getLogger("LLMGateway").warning(
            "Langfuse enabled in config but LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY "
            "not set — observability disabled.",
            extra={"event": "langfuse_init", "provider": "langfuse", "status": "disabled"},
        )
        return
    try:
        from langfuse import Langfuse
        _langfuse_client = Langfuse(public_key=pub_key, secret_key=sec_key, host=host)
        logging.getLogger("LLMGateway").info(
            "Langfuse observability active",
            extra={"event": "langfuse_init", "provider": "langfuse", "status": "active"},
        )
    except ImportError:
        logging.getLogger("LLMGateway").warning(
            "langfuse package not installed — observability disabled. "
            "Install with: pip install langfuse",
            extra={"event": "langfuse_init", "provider": "langfuse", "status": "disabled"},
        )

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config", "config.yaml"
)


def _load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return yaml.safe_load(f)
    # Fallback defaults when config not found (e.g. imported from another project)
    return {
        "llm": {
            "provider": "claude-code",
            "timeout": 120,
        }
    }


# ---------------------------------------------------------------------------
# Known model limits (free tier defaults — override via config if on paid plan)
# daily_requests = 0  means unlimited (local / self-hosted)
# ---------------------------------------------------------------------------
_MODEL_LIMITS: dict = {
    # Gemini (Google free tier)
    "gemini-3.5-flash":         {"daily_requests": 500,  "context_tokens": 1_048_576},
    "gemini-3.1-flash-lite":  {"daily_requests": 1500, "context_tokens": 1_048_576},
    "gemini-2.5-flash":       {"daily_requests": 500,  "context_tokens": 1_048_576},
    "gemini-2.5-pro":         {"daily_requests": 25,   "context_tokens": 1_048_576},
    "gemini-2.0-flash":       {"daily_requests": 1500, "context_tokens": 1_048_576},
    # Claude (via Claude Code CLI or Anthropic API — no hard daily limit, track calls)
    "claude-sonnet-4-5":          {"daily_requests": 0, "context_tokens": 200_000},
    "claude-sonnet-4-6":          {"daily_requests": 0, "context_tokens": 200_000},
    "claude-opus-4-5":            {"daily_requests": 0, "context_tokens": 200_000},
    "claude-haiku-4-5":           {"daily_requests": 0, "context_tokens": 200_000},
    "claude-3-5-sonnet-20241022": {"daily_requests": 0, "context_tokens": 200_000},
    "claude-3-haiku-20240307":    {"daily_requests": 0, "context_tokens": 200_000},
    # Local (unlimited)
    "local":                  {"daily_requests": 0,    "context_tokens": 2048},
    # Ollama local models (unlimited — runs on your hardware)
    "llama3.2":               {"daily_requests": 0,    "context_tokens": 128_000},
    "llama3.1":               {"daily_requests": 0,    "context_tokens": 128_000},
    "llama3":                 {"daily_requests": 0,    "context_tokens": 8_192},
    "mistral":                {"daily_requests": 0,    "context_tokens": 32_768},
    "phi3":                   {"daily_requests": 0,    "context_tokens": 128_000},
    "qwen2.5":                {"daily_requests": 0,    "context_tokens": 128_000},
    "deepseek-r1":            {"daily_requests": 0,    "context_tokens": 64_000},
    "codellama":              {"daily_requests": 0,    "context_tokens": 16_384},
    # Generic CLI (unlimited — provider-defined)
    "generic":                {"daily_requests": 0,    "context_tokens": 8_192},
}


# ---------------------------------------------------------------------------
# Abstract Provider
# ---------------------------------------------------------------------------
class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt, system_prompt):
        pass

    @abstractmethod
    def provider_name(self):
        pass


# ---------------------------------------------------------------------------
# Provider 1: Gemini CLI
# ---------------------------------------------------------------------------
class GeminiCLIProvider(LLMProvider):
    """
    Calls the locally installed Gemini CLI via subprocess using the -p flag.
    No API keys needed - the CLI handles OAuth via browser.
    Requires GOOGLE_CLOUD_PROJECT env var for Workspace accounts.
    """

    def __init__(self, config):
        self.logger = logging.getLogger("GeminiCLI")
        self.model = config.get("gemini_model", "gemini-3.5-flash")
        self.timeout = config.get("gemini_timeout", config.get("timeout", 120))
        self.gemini_path = self._find_gemini()
        self.logger.info(
            "Gemini CLI provider ready",
            extra={"event": "provider_ready", "provider": "gemini", "status": "ready"},
        )

    def _find_gemini(self):
        """Locate the gemini CLI executable."""
        import shutil

        # 1. Check if 'gemini' is directly on PATH
        found = shutil.which("gemini")
        if found:
            return found

        # 2. Check npm global bin directory (Windows)
        npm_bin = os.path.join(os.environ.get("APPDATA", ""), "npm")
        for candidate in ["gemini.cmd", "gemini.ps1", "gemini"]:
            full = os.path.join(npm_bin, candidate)
            if os.path.exists(full):
                return full

        # 3. Try npx as last resort
        npx = shutil.which("npx")
        if npx:
            return "__npx__"  # Sentinel: use npx invocation

        self.logger.warning(
            "Gemini CLI not found. Install with: npm install -g @google/gemini-cli",
            extra={"event": "provider_ready", "provider": "gemini", "status": "not_found"},
        )
        return None

    def provider_name(self):
        return "GeminiCLI (" + self.model + ")"

    def generate(self, prompt, system_prompt):
        if not self.gemini_path:
            return "Error: Gemini CLI not found. Install with: npm install -g @google/gemini-cli"

        # Keep this MINIMAL. A heavy "you are a pure text-generation API" preamble
        # makes gemini-2.5-flash respond TO the preamble ("I am ready to act as an
        # API, please provide a prompt") instead of doing the task. System + request,
        # with a short tool-suppression note at the END, answers reliably.
        combined = (
            (system_prompt + "\n\n" if system_prompt else "")
            + prompt
            + "\n\n(Answer directly with the requested output only — do not use tools or run commands.)"
        )

        # Build environment with required project settings.
        # GOOGLE_CLOUD_PROJECT must be set in the environment — no hardcoded fallback (T-I-05).
        env = os.environ.copy()
        if "GOOGLE_CLOUD_PROJECT_ID" not in env and "GOOGLE_CLOUD_PROJECT" in env:
            env["GOOGLE_CLOUD_PROJECT_ID"] = env["GOOGLE_CLOUD_PROJECT"]
        # Ensure npm global bin is on PATH
        npm_bin = os.path.join(env.get("APPDATA", ""), "npm")
        if npm_bin not in env.get("PATH", ""):
            env["PATH"] = env.get("PATH", "") + os.pathsep + npm_bin

        try:
            # -m selects the model (e.g. gemini-2.5-flash). The prompt goes via
            # STDIN, NOT a -p argument: gemini's Windows launcher is a .CMD that
            # re-parses args through cmd.exe, which mangles long prompts with
            # quotes/newlines (a short prompt works, an evaluator prompt exits
            # rc=1). gemini reads the prompt from stdin in headless mode.
            if self.gemini_path == "__npx__":
                cmd = ["npx", "-y", "@google/gemini-cli", "-m", self.model]
            else:
                cmd = [self.gemini_path, "-m", self.model]

            self.logger.debug(
                "Calling Gemini CLI (prompt via stdin)",
                extra={"event": "generation", "provider": "gemini", "status": "calling"},
            )
            result = subprocess.run(
                cmd,
                input=combined,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                encoding="utf-8",
                errors="replace",
                env=env,
                cwd=os.path.expanduser("~"),  # avoid picking up CLAUDE.md/GEMINI.md from project dir
            )

            if result.returncode != 0:
                err = result.stderr.strip() if result.stderr else "Unknown error"
                self.logger.error(
                    "Gemini CLI returned a non-zero exit code",
                    extra={"event": "generation", "provider": "gemini", "status": "error"},
                )
                return "Error from Gemini CLI: " + err

            output = result.stdout.strip()
            # Filter out non-content lines (hook registry messages, etc.)
            lines = output.split('\n')
            filtered = [l for l in lines if not l.startswith("Loaded cached") and not l.startswith("Hook registry")]
            output = '\n'.join(filtered).strip()

            return output if output else "Error: Gemini CLI returned empty output."

        except subprocess.TimeoutExpired:
            self.logger.error(
                "Gemini CLI timed out",
                extra={"event": "generation", "provider": "gemini", "status": "timeout"},
            )
            return "Error: Gemini CLI timed out."
        except FileNotFoundError:
            self.logger.critical(
                "Gemini CLI not installed or not on PATH",
                extra={"event": "generation", "provider": "gemini", "status": "not_found"},
            )
            return "Error: Gemini CLI not installed or not on PATH."
        except Exception as e:
            self.logger.error(
                "Gemini CLI call failed",
                exc_info=True,
                extra={"event": "generation", "provider": "gemini", "status": "error"},
            )
            return "Error: " + str(e)


# ---------------------------------------------------------------------------
# Provider 2: Local Llama (GGUF, GPU-direct)
# ---------------------------------------------------------------------------
class LocalLlamaProvider(LLMProvider):
    """
    Loads GGUF model directly into Python process memory via llama-cpp-python.
    Zero network calls. Maximum VRAM efficiency.
    """

    def __init__(self, config):
        self.logger = logging.getLogger("LocalLlama")
        self._model = None

        try:
            from llama_cpp import Llama
        except ImportError:
            self.logger.critical(
                "llama-cpp-python not installed.",
                extra={"event": "model_load", "provider": "local", "status": "error"},
            )
            return

        model_path = config.get("model_path", "")
        if not model_path or not os.path.exists(model_path):
            self.logger.error(
                "Model file not found",
                extra={"event": "model_load", "provider": "local", "status": "error"},
            )
            return

        self.logger.info(
            "Loading GGUF model",
            extra={"event": "model_load", "provider": "local", "status": "loading"},
        )
        try:
            self._model = Llama(
                model_path=model_path,
                n_gpu_layers=-1,
                n_ctx=config.get("max_tokens", 2048),
                verbose=False,
            )
            self.logger.info(
                "Local model loaded.",
                extra={"event": "model_load", "provider": "local", "status": "loaded"},
            )
        except Exception as e:
            self.logger.critical(
                "Failed to load model",
                exc_info=True,
                extra={"event": "model_load", "provider": "local", "status": "error"},
            )

    def provider_name(self):
        return "LocalLlama (GGUF)"

    def generate(self, prompt, system_prompt):
        if self._model is None:
            return "Error: Local model not loaded."

        # Phi-3 / Llama-3 chat template
        SYS_OPEN = "<" + "|system|" + ">"
        SYS_CLOSE = "<" + "|end|" + ">"
        USR_OPEN = "<" + "|user|" + ">"
        USR_CLOSE = "<" + "|end|" + ">"
        AST_OPEN = "<" + "|assistant|" + ">"

        full_prompt = (
            SYS_OPEN + "\n" + system_prompt + SYS_CLOSE + "\n"
            + USR_OPEN + "\n" + prompt + USR_CLOSE + "\n"
            + AST_OPEN + "\n"
        )

        output = self._model(
            full_prompt,
            max_tokens=512,
            stop=[SYS_CLOSE, "User:", "System:"],
            echo=False,
        )

        return output["choices"][0]["text"].strip()


# ---------------------------------------------------------------------------
# Provider 3: Claude Code CLI (uses installed Claude Code — no API key needed)
# ---------------------------------------------------------------------------
class ClaudeCodeCLIProvider(LLMProvider):
    """
    Calls the Claude Code CLI via subprocess using the -p / --print flag.
    No API key needed — uses Claude Code's own auth (run 'claude' once to authenticate).
    Install: npm install -g @anthropic-ai/claude-code
    """

    def __init__(self, config):
        self.logger = logging.getLogger("ClaudeCodeCLI")
        self.model = config.get("claude_model", "claude-sonnet-4-5")
        self.timeout = config.get("timeout", 120)
        # Hardening hooks (opt-in; default preserves prior agentic behaviour):
        #   disallowed_tools -> passed to --disallowedTools so the CLI can't touch
        #     files (use for the Evaluator-Optimizer optimizer: pure text proposal,
        #     no writes to the real repo => HITL integrity).
        #   cwd -> run the subprocess here (e.g. a throwaway sandbox).
        self.disallowed_tools = config.get("disallowed_tools", "")
        self.cwd = config.get("cwd")
        # Accept explicit path from config or UI, otherwise auto-detect
        explicit_path = config.get("claude_path", "")
        if explicit_path and os.path.exists(explicit_path):
            self.claude_path = explicit_path
        else:
            self.claude_path = self._find_claude()
        self.logger.info(
            "Claude Code CLI provider ready",
            extra={"event": "provider_ready", "provider": "claude-code", "status": "ready"},
        )

    def _find_claude(self):
        import shutil
        # 1. Well-known install location (Windows Claude Code default)
        known = os.path.join(
            os.environ.get("USERPROFILE", ""),
            ".local", "bin", "claude.exe"
        )
        if os.path.exists(known):
            return known
        # 2. PATH lookup
        found = shutil.which("claude")
        if found:
            return found
        # 3. npm global bin (Windows)
        npm_bin = os.path.join(os.environ.get("APPDATA", ""), "npm")
        for candidate in ["claude.cmd", "claude.ps1", "claude"]:
            full = os.path.join(npm_bin, candidate)
            if os.path.exists(full):
                return full
        self.logger.warning(
            "Claude Code CLI not found at known paths.",
            extra={"event": "provider_ready", "provider": "claude-code", "status": "not_found"},
        )
        return None

    def provider_name(self):
        return f"ClaudeCodeCLI ({self.model})"

    def generate(self, prompt, system_prompt):
        if not self.claude_path:
            return "Error: Claude Code CLI not found. Install with: npm install -g @anthropic-ai/claude-code"

        combined = (
            "SYSTEM INSTRUCTION (follow strictly):\n"
            + system_prompt + "\n\n"
            + "USER REQUEST:\n"
            + prompt + "\n"
        )

        env = os.environ.copy()
        npm_bin = os.path.join(env.get("APPDATA", ""), "npm")
        if npm_bin not in env.get("PATH", ""):
            env["PATH"] = env.get("PATH", "") + os.pathsep + npm_bin

        try:
            # IMPORTANT: pass the prompt via STDIN, not as a `-p <prompt>` argv.
            # Windows CreateProcess caps a command line at ~32K chars; a large
            # context (e.g. a whole source file) as an argument silently fails and
            # claude returns empty. `claude -p` with no prompt arg reads stdin
            # (input-format text), which has no such limit. (Same fix we applied to
            # the Gemini CLI provider.)
            cmd = [self.claude_path, "--model", self.model, "-p"]
            if self.disallowed_tools:
                cmd += ["--disallowedTools", self.disallowed_tools]
            self.logger.debug(
                "Calling Claude Code CLI via stdin",
                extra={"event": "generation", "provider": "claude-code", "status": "calling"},
            )
            result = subprocess.run(
                cmd,
                input=combined,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                encoding="utf-8",
                errors="replace",
                env=env,
                cwd=self.cwd,
            )
            if result.returncode != 0:
                err = result.stderr.strip() if result.stderr else "Unknown error"
                self.logger.error(
                    "Claude Code CLI returned a non-zero exit code",
                    extra={"event": "generation", "provider": "claude-code", "status": "error"},
                )
                return "Error from Claude Code CLI: " + err
            output = result.stdout.strip()
            return output if output else "Error: Claude Code CLI returned empty output."
        except subprocess.TimeoutExpired:
            return "Error: Claude Code CLI timed out."
        except FileNotFoundError:
            return "Error: Claude Code CLI not installed or not on PATH."
        except Exception as e:
            self.logger.error(
                "Claude Code CLI call failed",
                exc_info=True,
                extra={"event": "generation", "provider": "claude-code", "status": "error"},
            )
            return "Error: " + str(e)


# ---------------------------------------------------------------------------
# Provider 4: Claude API (Anthropic)
# ---------------------------------------------------------------------------
class ClaudeAPIProvider(LLMProvider):
    """
    Calls the Anthropic Claude API using the anthropic Python SDK.
    Requires ANTHROPIC_API_KEY environment variable.
    Install: pip install anthropic
    """

    def __init__(self, config):
        self.logger = logging.getLogger("ClaudeAPI")
        self.model = config.get("claude_model", "claude-sonnet-4-5")
        self.timeout = config.get("timeout", 120)
        self._client = None

        api_key = os.environ.get("ANTHROPIC_API_KEY", config.get("anthropic_api_key", ""))
        if not api_key:
            self.logger.error(
                "ANTHROPIC_API_KEY not set. Claude provider unavailable.",
                extra={"event": "provider_ready", "provider": "claude", "status": "unavailable"},
            )
            return

        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key)
            self.logger.info(
                "Claude API provider ready",
                extra={"event": "provider_ready", "provider": "claude", "status": "ready"},
            )
        except ImportError:
            self.logger.critical(
                "anthropic SDK not installed. Run: pip install anthropic",
                extra={"event": "provider_ready", "provider": "claude", "status": "error"},
            )

    def provider_name(self):
        return f"Claude API ({self.model})"

    def generate(self, prompt, system_prompt):
        if self._client is None:
            return "Error: Claude API client not initialised. Check ANTHROPIC_API_KEY and 'pip install anthropic'."

        try:
            message = self._client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        except Exception as e:
            self.logger.error(
                "Claude API call failed",
                exc_info=True,
                extra={"event": "generation", "provider": "claude", "status": "error"},
            )
            return f"Error: {e}"


# ---------------------------------------------------------------------------
# Provider 5: Ollama (local, no API key, no login — just `ollama serve`)
# ---------------------------------------------------------------------------
class OllamaProvider(LLMProvider):
    """
    Calls a locally running Ollama server via its REST API.
    No API keys, no browser login — just install Ollama and run `ollama serve`.
    Install: https://ollama.com   |   Models: ollama pull llama3.2

    Supports any model pulled via `ollama pull <model>`.
    Default model: llama3.2 (fast, 3B params, runs on CPU).
    """

    def __init__(self, config):
        self.logger = logging.getLogger("OllamaProvider")
        self.model   = config.get("ollama_model", "llama3.2")
        self.host    = config.get("ollama_host", "http://localhost:11434")
        self.timeout = config.get("timeout", 120)
        self.logger.info(
            "Ollama provider ready",
            extra={"event": "provider_ready", "provider": "ollama", "status": "ready"},
        )

    def provider_name(self):
        return f"Ollama ({self.model})"

    def generate(self, prompt, system_prompt):
        import json as _json
        import urllib.request as _req
        import urllib.error

        payload = _json.dumps({
            "model":  self.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {"temperature": 0.1},
        }).encode()

        try:
            request = _req.Request(
                f"{self.host}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with _req.urlopen(request, timeout=self.timeout) as resp:
                data = _json.loads(resp.read().decode())
                return data.get("response", "").strip()
        except urllib.error.URLError as e:
            self.logger.error(
                "Ollama connection failed (is `ollama serve` running?)",
                exc_info=True,
                extra={"event": "generation", "provider": "ollama", "status": "error"},
            )
            return f"Error: Cannot reach Ollama at {self.host}. Run: ollama serve"
        except Exception as e:
            self.logger.error(
                "Ollama generate failed",
                exc_info=True,
                extra={"event": "generation", "provider": "ollama", "status": "error"},
            )
            return f"Error: {e}"


# ---------------------------------------------------------------------------
# Provider 6: Generic CLI (any tool that reads prompt from stdin or -p flag)
# ---------------------------------------------------------------------------
class GenericCLIProvider(LLMProvider):
    """
    Wraps any AI CLI tool that accepts a prompt via -p / --prompt flag or stdin.
    Configure in config.yaml:

      llm:
        provider: "generic-cli"
        generic_cli_path: "/usr/local/bin/my-ai-tool"
        generic_cli_args: ["-p", "{prompt}"]   # {prompt} replaced at runtime
        generic_cli_model: "my-model"           # used in provider_name only

    This makes SAGE compatible with any future CLI-based model without code changes.
    Examples: aider, continue, lm-studio-cli, any custom wrapper.
    """

    def __init__(self, config):
        self.logger  = logging.getLogger("GenericCLI")
        self.path    = config.get("generic_cli_path", "")
        self.args    = config.get("generic_cli_args", ["-p", "{prompt}"])
        self.model   = config.get("generic_cli_model", "generic")
        self.timeout = config.get("timeout", 120)

        if not self.path:
            self.logger.error(
                "generic_cli_path not set in config.yaml",
                extra={"event": "provider_ready", "provider": "generic-cli", "status": "error"},
            )
        else:
            self.logger.info(
                "Generic CLI provider ready",
                extra={"event": "provider_ready", "provider": "generic-cli", "status": "ready"},
            )

    def provider_name(self):
        return f"GenericCLI ({self.model})"

    def generate(self, prompt, system_prompt):
        if not self.path:
            return "Error: generic_cli_path not configured."

        combined = f"SYSTEM: {system_prompt}\n\nUSER: {prompt}"
        cmd = [
            token.replace("{prompt}", combined).replace("{system}", system_prompt)
            for token in [self.path] + self.args
        ]

        env = os.environ.copy()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            if result.returncode != 0:
                err = result.stderr.strip() or "non-zero exit"
                self.logger.error(
                    "Generic CLI returned a non-zero exit code",
                    extra={"event": "generation", "provider": "generic-cli", "status": "error"},
                )
                return f"Error from {self.model}: {err}"
            output = result.stdout.strip()
            return output if output else f"Error: {self.model} returned empty output."
        except subprocess.TimeoutExpired:
            return f"Error: {self.model} CLI timed out."
        except FileNotFoundError:
            return f"Error: CLI not found at {self.path}"
        except Exception as e:
            self.logger.error(
                "Generic CLI failed",
                exc_info=True,
                extra={"event": "generation", "provider": "generic-cli", "status": "error"},
            )
            return f"Error: {e}"


# ===========================================================================
# Multi-LLM Provider Pool
# ===========================================================================


class ProviderPool:
    """Registry of multiple LLM providers for parallel generation."""

    def __init__(self):
        self._providers: dict = {}
        self._default: str | None = None
        self._lock = threading.Lock()

    def register(self, name: str, provider) -> None:
        with self._lock:
            self._providers[name] = provider
            if self._default is None:
                self._default = name

    def get(self, name: str):
        return self._providers.get(name)

    def get_default(self):
        if self._default:
            return self._providers.get(self._default)
        return None

    @property
    def default_name(self) -> str | None:
        return self._default

    def set_default(self, name: str) -> None:
        if name in self._providers:
            self._default = name

    def list_providers(self) -> list[str]:
        return list(self._providers.keys())

    def remove(self, name: str) -> None:
        with self._lock:
            self._providers.pop(name, None)
            if self._default == name:
                self._default = next(iter(self._providers), None)

    def status(self) -> dict:
        return {
            "default": self._default,
            "providers": self.list_providers(),
        }


def generate_parallel(
    pool: ProviderPool,
    prompt: str,
    system_prompt: str,
    *,
    strategy: str = "voting",
    provider_names: list[str] | None = None,
) -> dict:
    """Run prompt across multiple providers in parallel, aggregate by strategy.

    Strategies:
      - voting:   majority consensus wins
      - fastest:  first response wins
      - fallback: try in order, use first success
      - quality:  pick longest (richest) response
    """
    import concurrent.futures
    logger = logging.getLogger("ProviderPool")
    names = provider_names or pool.list_providers()
    start = time.time()

    # -- Collect responses in parallel --
    def _call(name: str) -> tuple[str, str | None, str | None]:
        """Returns (name, response_or_None, error_or_None)."""
        provider = pool.get(name)
        if provider is None:
            return name, None, f"provider '{name}' not registered"
        try:
            resp = provider.generate(prompt, system_prompt)
            return name, resp, None
        except Exception as exc:
            logger.warning(
                "Provider failed during parallel generation",
                exc_info=True,
                extra={"event": "generate_parallel", "provider": name, "status": "error"},
            )
            return name, None, str(exc)

    if strategy == "fallback":
        # Sequential: try each in order, return first success
        for name in names:
            n, resp, err = _call(name)
            if resp is not None:
                elapsed = int((time.time() - start) * 1000)
                return {
                    "response": resp,
                    "provider": n,
                    "strategy": "fallback",
                    "elapsed_ms": elapsed,
                }
        return {"error": "all providers failed", "strategy": "fallback"}

    # Parallel execution for voting / fastest / quality
    results: list[tuple[str, str | None, str | None]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(names)) as executor:
        futures = {executor.submit(_call, n): n for n in names}

        if strategy == "fastest":
            # Return as soon as the first success comes back
            for future in concurrent.futures.as_completed(futures):
                name, resp, err = future.result()
                if resp is not None:
                    elapsed = int((time.time() - start) * 1000)
                    # Cancel remaining futures (best-effort)
                    for f in futures:
                        f.cancel()
                    return {
                        "response": resp,
                        "provider": name,
                        "strategy": "fastest",
                        "elapsed_ms": elapsed,
                    }
            # All failed
            return {"error": "all providers failed", "strategy": "fastest"}

        # Wait for all (voting / quality)
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    elapsed = int((time.time() - start) * 1000)
    successes = [(n, r) for n, r, e in results if r is not None]

    if not successes:
        return {"error": "all providers failed", "strategy": strategy}

    if strategy == "voting":
        from collections import Counter
        votes = Counter(r for _, r in successes)
        winner = votes.most_common(1)[0][0]
        winning_provider = next(n for n, r in successes if r == winner)
        return {
            "response": winner,
            "provider": winning_provider,
            "strategy": "voting",
            "votes": dict(votes),
            "elapsed_ms": elapsed,
        }

    if strategy == "quality":
        # Simple heuristic: longest response is richest
        best_name, best_resp = max(successes, key=lambda x: len(x[1]))
        return {
            "response": best_resp,
            "provider": best_name,
            "strategy": "quality",
            "elapsed_ms": elapsed,
        }

    # Default: return first success
    name, resp = successes[0]
    return {
        "response": resp,
        "provider": name,
        "strategy": strategy,
        "elapsed_ms": elapsed,
    }


# ===========================================================================
# LLM Gateway (Singleton + Thread Lock)
# ===========================================================================
class LLMGateway:
    """
    Thread-safe singleton that routes LLM calls through a provider-aware
    semaphore.

    Cloud API providers (gemini, claude, claude-code, ollama HTTP) support
    server-side concurrency, so we allow multiple parallel inferences.
    Local/GPU providers (local, generic-cli) are single-lane.

    Usage:
        from src.core.llm_gateway import llm_gateway
        response = llm_gateway.generate("Analyze this log...")
    """

    _instance = None
    _lock = threading.Lock()   # singleton creation lock only

    # Provider-aware concurrency limits
    PROVIDER_CONCURRENCY = {
        "local": 1,         # Single GPU — must serialise
        "generic-cli": 1,   # Unknown CLI — conservative
        "ollama": 2,        # Ollama HTTP — moderate concurrency
        "gemini": 4,        # Cloud API — server-side concurrency
        "claude": 4,        # Cloud API
        "claude-code": 2,   # CLI tool — moderate
    }

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.logger = logging.getLogger("LLMGateway")
        self.provider = None
        self.provider_pool = ProviderPool()
        self._usage = {
            "calls": 0,
            "calls_today": 0,
            "estimated_tokens": 0,
            "errors": 0,
            "started_at": time.time(),
            "day_started_at": time.time(),  # resets at UTC midnight
        }
        self._routing_stats = {"low": 0, "medium": 0, "high": 0}

        config = _load_config()
        llm_cfg = config.get("llm", {})

        # Initialise optional observability
        _init_langfuse(config)

        backend = llm_cfg.get("provider", "claude-code")
        self.logger.info(
            "Selected LLM provider",
            extra={"event": "provider_select", "provider": backend, "status": "selected"},
        )

        if backend == "gemini":
            self.provider = GeminiCLIProvider(llm_cfg)
        elif backend == "local":
            self.provider = LocalLlamaProvider(llm_cfg)
        elif backend == "claude-code":
            self.provider = ClaudeCodeCLIProvider(llm_cfg)
        elif backend == "claude":
            self.provider = ClaudeAPIProvider(llm_cfg)
        elif backend == "ollama":
            self.provider = OllamaProvider(llm_cfg)
        elif backend == "generic-cli":
            self.provider = GenericCLIProvider(llm_cfg)
        else:
            self.logger.error(
                "Unknown provider — defaulting to claude-code.",
                extra={"event": "provider_select", "provider": backend, "status": "unknown"},
            )
            self.provider = ClaudeCodeCLIProvider(llm_cfg)

        # ── Provider-aware inference semaphore ──────────────────────────
        # Replaces the old single threading.Lock with a semaphore whose
        # concurrency limit matches the provider's capability.
        _concurrency = self.PROVIDER_CONCURRENCY.get(backend, 1)
        self._inference_semaphore = threading.Semaphore(_concurrency)
        self.logger.info(
            "LLM Gateway active",
            extra={"event": "gateway_active", "provider": self.provider.provider_name(),
                   "status": "active"},
        )

        # ── Resilience: retry transient LLM failures (backoff + jitter) ──
        # API/CLI providers hit transient failures (rate limits, 5xx, timeouts,
        # the odd empty response). Without a retry, one blip fails a whole agent
        # workflow. Configurable via llm.retry; defaults are conservative and
        # only ever fire on a *transient* error, so success paths are unchanged.
        _retry_cfg = llm_cfg.get("retry", {}) if isinstance(llm_cfg, dict) else {}
        self._retry_max = int(_retry_cfg.get("max_retries", 2))
        self._retry_base_delay = float(_retry_cfg.get("base_delay", 0.5))
        self._retry_max_delay = float(_retry_cfg.get("max_delay", 8.0))

    # Substrings that mark a *retryable* failure (vs a permanent one like
    # "not configured" / "not installed", which must NOT be retried).
    _TRANSIENT_ERROR_MARKERS = (
        "timed out", "timeout", "rate limit", "429", "500", "502", "503", "504",
        "temporarily", "unavailable", "connection", "reset by peer", "overloaded",
        "empty output",
    )

    def _is_transient_error(self, result) -> bool:
        """True if a provider result represents a transient (retryable) failure."""
        if result is None:
            return True
        if not isinstance(result, str):
            return False
        low = result.strip().lower()
        if low == "":
            return True  # an empty response is treated as a transient blip
        if not low.startswith("error"):
            return False
        return any(m in low for m in self._TRANSIENT_ERROR_MARKERS)

    def _retry_delay(self, attempt: int) -> float:
        """Exponential backoff with full jitter, capped at max_delay."""
        capped = min(self._retry_max_delay, self._retry_base_delay * (2 ** attempt))
        return capped * (0.5 + random.random() * 0.5)  # 50–100% jitter

    def _generate_with_retry(self, prompt, system_prompt) -> str:
        """Call the provider, retrying transient failures with backoff.

        Retries on a raised exception OR a returned transient-error string, up to
        self._retry_max extra attempts. A successful or permanently-failed result
        is returned immediately (so non-retryable errors fail fast). The final
        exception is re-raised so the caller's existing handling still applies.
        """
        for attempt in range(self._retry_max + 1):
            try:
                result = self.provider.generate(prompt, system_prompt)
            except Exception as e:  # noqa: BLE001 — provider may raise anything
                if attempt < self._retry_max:
                    delay = self._retry_delay(attempt)
                    self.logger.warning(
                        "Provider raised an exception; retrying after backoff",
                        exc_info=True,
                        extra={"event": "generate_retry",
                               "provider": self.provider.provider_name(),
                               "status": "retrying"},
                    )
                    time.sleep(delay)
                    continue
                raise
            if self._is_transient_error(result) and attempt < self._retry_max:
                delay = self._retry_delay(attempt)
                self.logger.warning(
                    "Transient provider error; retrying after backoff",
                    extra={"event": "generate_retry",
                           "provider": self.provider.provider_name(),
                           "status": "retrying"},
                )
                time.sleep(delay)
                continue
            return result
        return result  # pragma: no cover — loop always returns or raises first

    def generate_stream(self, prompt, system_prompt="You are a helpful AI assistant.",
                        trace_name: str = "llm_stream", metadata: dict = None):
        """
        Streaming variant of generate().  Yields str chunks as they become available.

        For providers that support native streaming (Claude API) tokens are
        yielded as received.  For CLI-based providers the full response is
        fetched, then word-chunked to simulate streaming — callers get
        progressive output either way.

        The thread lock is held for the duration of the stream (same single-
        lane guarantee as generate()).

        Yields:
            str  — incremental text chunks, never empty strings.
        """
        if self.provider is None:
            yield "Error: No LLM provider configured."
            return

        with self._inference_semaphore:
            self.logger.debug(
                "Streaming generation started",
                extra={"event": "generation_stream",
                       "provider": self.provider.provider_name(), "status": "started"},
            )
            start = time.time()

            # Claude API supports real streaming
            if isinstance(self.provider, ClaudeAPIProvider) and self.provider._client is not None:
                try:
                    import anthropic
                    with self.provider._client.messages.stream(
                        model=self.provider.model,
                        max_tokens=1024,
                        system=system_prompt,
                        messages=[{"role": "user", "content": prompt}],
                    ) as stream:
                        full = []
                        for text in stream.text_stream:
                            full.append(text)
                            yield text
                    result = "".join(full)
                except Exception as e:
                    self.logger.error(
                        "Claude API stream failed",
                        exc_info=True,
                        extra={"event": "generation_stream",
                               "provider": self.provider.provider_name(), "status": "error"},
                    )
                    yield f"Error: {e}"
                    return
            else:
                # CLI / local providers: run full generation, then chunk output
                result = self.provider.generate(prompt, system_prompt)
                # Yield in ~4-word chunks to simulate progressive streaming
                words = result.split(" ")
                chunk_size = 4
                for i in range(0, len(words), chunk_size):
                    chunk = " ".join(words[i:i + chunk_size])
                    if i + chunk_size < len(words):
                        chunk += " "
                    yield chunk

            elapsed = time.time() - start
            self.logger.info(
                "Streaming generation done",
                extra={"event": "generation_stream", "provider": self.provider.provider_name(),
                       "duration_ms": int(elapsed * 1000), "status": "completed"},
            )
            self._maybe_reset_daily()
            self._usage["calls"] += 1
            self._usage["calls_today"] += 1
            self._usage["estimated_tokens"] += (len(prompt) + len(system_prompt) + len(result)) // 4

    def generate(self, prompt, system_prompt="You are a helpful AI assistant.",
                 trace_name: str = "llm_generate", metadata: dict = None,
                 trace_id: str = "", agent_name: str = "") -> str:
        """Thread-safe generation. Only ONE call at a time.

        Args:
            prompt:        User/task prompt.
            system_prompt: Role/instruction context.
            trace_name:    Langfuse trace name (e.g. agent class + method).
            metadata:      Extra key-value pairs attached to the Langfuse trace.
            trace_id:      Optional trace ID for cost tracking correlation.
            agent_name:    Agent role name for per-agent budget enforcement.
        """
        if self.provider is None:
            return "Error: No LLM provider configured."

        start = time.time()
        self.logger.debug(
            "Acquiring inference lock",
            extra={"event": "generation", "provider": self.provider.provider_name(),
                   "status": "acquiring"},
        )

        with self._inference_semaphore:
            self.logger.debug(
                "Semaphore acquired",
                extra={"event": "generation", "provider": self.provider.provider_name(),
                       "status": "acquired"},
            )

            # ----------------------------------------------------------------
            # T1-002: PII detection and data residency check
            # ----------------------------------------------------------------
            config = _load_config()
            try:
                from src.core import pii_filter
                scrubbed_prompt, detected_entities = pii_filter.scrub_text(prompt, config)
                if detected_entities:
                    self.logger.warning(
                        "PII detected and redacted",
                        extra={"event": "pii_redaction",
                               "provider": self.provider.provider_name(), "status": "redacted"},
                    )
                    pii_cfg = config.get("pii", {})
                    if pii_cfg.get("fail_on_detection", False):
                        raise ValueError(
                            f"Prompt rejected: PII detected — {detected_entities}"
                        )
                prompt = scrubbed_prompt

                if not pii_filter.check_data_residency(self.provider.provider_name(), config):
                    raise ValueError(
                        "Provider not allowed for configured data residency region"
                    )
            except ImportError:
                pass  # pii_filter not available — proceed without PII check

            # ----------------------------------------------------------------
            # Complexity classification for routing stats
            # ----------------------------------------------------------------
            try:
                from src.core.complexity_classifier import complexity_classifier
                _complexity = complexity_classifier.classify(prompt, system_prompt)
                self._routing_stats[_complexity.value] = self._routing_stats.get(_complexity.value, 0) + 1
            except Exception:
                pass  # classifier failure is non-fatal

            # ----------------------------------------------------------------
            # T1-004: Budget check before LLM call
            # ----------------------------------------------------------------
            try:
                from src.core import cost_tracker as _ct
                from src.core.tenant import get_current_tenant
                _tenant = get_current_tenant()
                _solution = ""
                try:
                    from src.core.project_loader import project_config as _pc
                    _solution = _pc.project_name or ""
                except Exception:
                    pass
                _ct.check_budget(_tenant, _solution)
            except ValueError:
                raise
            except Exception:
                pass  # cost_tracker import failure is non-fatal

            # --- Per-agent budget ceiling check ---
            if agent_name:
                try:
                    _agent_pc = project_config
                    if _agent_pc is not None:
                        _agent_budget = _agent_pc.get_agent_budget(agent_name)
                        if _agent_budget is not None:
                            _limit = _agent_budget.get("monthly_calls", 0)
                            if _limit > 0:
                                _agent_calls = self._usage.get(f"agent_{agent_name}_calls", 0)
                                if _agent_calls >= _limit:
                                    raise RuntimeError(
                                        f"Agent '{agent_name}' monthly call budget ({_limit}) exceeded."
                                    )
                                self._usage[f"agent_{agent_name}_calls"] = _agent_calls + 1
                except RuntimeError:
                    raise
                except Exception as _bexc:
                    self.logger.warning(
                        "Agent budget check failed (non-fatal)",
                        exc_info=True,
                        extra={"event": "agent_budget_check",
                               "provider": self.provider.provider_name(), "status": "error"},
                    )

            # --- Langfuse trace (no-op if client not initialised) ---
            _lf_generation = None
            if _langfuse_client is not None:
                try:
                    _lf_trace = _langfuse_client.trace(
                        name=trace_name,
                        metadata={**(metadata or {}), "provider": self.provider.provider_name()},
                    )
                    _lf_generation = _lf_trace.generation(
                        name="generate",
                        model=getattr(self.provider, "model", "unknown"),
                        input={"system": system_prompt, "prompt": prompt},
                    )
                except Exception as lf_err:
                    self.logger.debug(
                        "Langfuse trace init failed (non-fatal)",
                        exc_info=True,
                        extra={"event": "langfuse_trace",
                               "provider": self.provider.provider_name(), "status": "error"},
                    )

            # --- OpenTelemetry span (no-op if SDK not installed) ---
            from src.core.tracing import trace_llm_call as _otel_trace

            with _otel_trace(
                provider=self.provider.provider_name(),
                model=getattr(self.provider, "model", "unknown"),
                prompt_length=len(prompt),
                system_prompt_length=len(system_prompt),
                trace_name=trace_name,
                trace_id=trace_id,
            ) as _otel_span:
                try:
                    result = self._generate_with_retry(prompt, system_prompt)
                    elapsed = time.time() - start
                    self.logger.info(
                        "Generation done",
                        extra={"event": "generation", "provider": self.provider.provider_name(),
                               "duration_ms": int(elapsed * 1000), "status": "completed"},
                    )
                    # Roll daily counter over at UTC midnight
                    self._maybe_reset_daily()
                    # Estimate tokens as (input + output chars) / 4
                    input_tokens  = (len(prompt) + len(system_prompt)) // 4
                    output_tokens = len(result) // 4
                    self._usage["calls"] += 1
                    self._usage["calls_today"] += 1
                    self._usage["estimated_tokens"] += input_tokens + output_tokens

                    # OTel: record output metrics on span
                    _otel_span.set_attribute("llm.output_tokens", output_tokens)
                    _otel_span.set_attribute("llm.input_tokens", input_tokens)
                    _otel_span.set_attribute("llm.duration_s", elapsed)

                    # ----------------------------------------------------------------
                    # T1-004: Record cost after successful generation
                    # ----------------------------------------------------------------
                    try:
                        from src.core import cost_tracker as _ct
                        from src.core.tenant import get_current_tenant
                        _tenant = get_current_tenant()
                        _solution = ""
                        try:
                            from src.core.project_loader import project_config as _pc
                            _solution = _pc.project_name or ""
                        except Exception:
                            pass
                        _model = getattr(self.provider, "model", "unknown")
                        _ct.record_usage(_tenant, _solution, _model, input_tokens, output_tokens, trace_id)
                    except Exception:
                        pass  # cost tracking is non-fatal

                    # Close Langfuse generation span with output
                    if _lf_generation is not None:
                        try:
                            _lf_generation.end(
                                output=result,
                                usage={"total_tokens": input_tokens + output_tokens},
                            )
                        except Exception as lf_err:
                            self.logger.debug(
                                "Langfuse generation.end failed (non-fatal)",
                                exc_info=True,
                                extra={"event": "langfuse_generation_end",
                                       "provider": self.provider.provider_name(),
                                       "status": "error"},
                            )

                    return result
                except ValueError:
                    # Re-raise budget/PII errors as-is (not wrapped as "Error: ...")
                    raise
                except Exception as e:
                    self.logger.error(
                        "Generation failed",
                        exc_info=True,
                        extra={"event": "generation", "provider": self.provider.provider_name(),
                               "status": "error"},
                    )
                    self._usage["errors"] += 1
                    if _lf_generation is not None:
                        try:
                            _lf_generation.end(output=f"ERROR: {e}", level="ERROR")
                        except Exception:
                            pass
                    return "Error: " + str(e)

    def generate_for_task(self, task_type: str, prompt: str,
                          system_prompt: str = "You are a helpful AI assistant.",
                          trace_name: str = "llm_generate", metadata: dict = None,
                          trace_id: str = "") -> str:
        """
        Route to a task-specific model if task_routing is configured.

        Looks up llm.task_routing.routes[task_type] in config.yaml.
        Falls back to the default provider when routing is disabled or no
        route is defined for this task_type.

        Format: "provider/model" (e.g. "ollama/llama3.2") or just "model"
        (e.g. "claude-sonnet-4-6", reuses current provider type).
        """
        config = _load_config()
        routing_cfg = config.get("llm", {}).get("task_routing", {})

        if not routing_cfg.get("enabled", False):
            return self.generate(prompt, system_prompt, trace_name, metadata, trace_id)

        routes: dict = routing_cfg.get("routes", {})
        route_value: str = routes.get(task_type, "")

        if not route_value:
            return self.generate(prompt, system_prompt, trace_name, metadata, trace_id)

        # Parse "provider/model" or just "model"
        if "/" in route_value:
            routed_provider, routed_model = route_value.split("/", 1)
        else:
            routed_provider = ""
            routed_model = route_value

        # If current provider matches routed provider (or no provider given),
        # temporarily override the model if it differs
        current_provider_name = self.provider.provider_name().lower() if self.provider else ""
        if not routed_provider or routed_provider.lower() in current_provider_name:
            return self.generate(prompt, system_prompt, trace_name, metadata, trace_id)

        # Different provider requested — build a temporary provider instance
        self.logger.info(
            "Task routing",
            extra={"event": "task_routing", "provider": routed_provider, "status": "routed"},
        )
        llm_cfg = config.get("llm", {}).copy()
        try:
            if routed_provider == "ollama":
                llm_cfg["ollama_model"] = routed_model
                tmp_provider = OllamaProvider(llm_cfg)
            elif routed_provider in ("claude", "claude-code"):
                llm_cfg["claude_model"] = routed_model
                tmp_provider = ClaudeCodeCLIProvider(llm_cfg)
            elif routed_provider == "gemini":
                llm_cfg["gemini_model"] = routed_model
                tmp_provider = GeminiCLIProvider(llm_cfg)
            else:
                self.logger.warning(
                    "Task routing: unknown provider — using default",
                    extra={"event": "task_routing", "provider": routed_provider,
                           "status": "unknown"},
                )
                return self.generate(prompt, system_prompt, trace_name, metadata, trace_id)

            # Run with the temporary provider (still under the main lock via generate())
            saved_provider = self.provider
            self.provider = tmp_provider
            try:
                result = self.generate(prompt, system_prompt, trace_name, metadata, trace_id)
            finally:
                self.provider = saved_provider
            return result

        except Exception as exc:
            self.logger.warning(
                "Task routing provider init failed — falling back to default",
                exc_info=True,
                extra={"event": "task_routing", "provider": routed_provider, "status": "error"},
            )
            return self.generate(prompt, system_prompt, trace_name, metadata, trace_id)

    def generate_multi(
        self,
        prompt: str,
        system_prompt: str,
        *,
        strategy: str = "voting",
        provider_names: list[str] | None = None,
    ) -> dict:
        """Delegate to generate_parallel using this gateway's provider_pool."""
        return generate_parallel(
            self.provider_pool, prompt, system_prompt,
            strategy=strategy, provider_names=provider_names,
        )

    def _maybe_reset_daily(self) -> None:
        """Reset calls_today when we cross a UTC midnight boundary."""
        import datetime as _dt
        day_start = _dt.datetime.fromtimestamp(
            self._usage["day_started_at"], tz=_dt.timezone.utc
        ).date()
        today = _dt.datetime.now(_dt.timezone.utc).date()
        if today > day_start:
            self._usage["calls_today"] = 0
            self._usage["day_started_at"] = time.time()
            self.logger.info(
                "Daily request counter reset (new UTC day).",
                extra={"event": "daily_reset", "status": "reset"},
            )

    def get_provider_name(self):
        if self.provider:
            return self.provider.provider_name()
        return "None"

    def get_usage(self) -> dict:
        """Return current session + daily usage stats."""
        import datetime as _dt
        started = _dt.datetime.fromtimestamp(
            self._usage["started_at"], tz=_dt.timezone.utc
        ).isoformat()
        day_started = _dt.datetime.fromtimestamp(
            self._usage["day_started_at"], tz=_dt.timezone.utc
        ).isoformat()
        return {
            "calls": self._usage["calls"],
            "calls_today": self._usage["calls_today"],
            "estimated_tokens": self._usage["estimated_tokens"],
            "errors": self._usage["errors"],
            "started_at": started,
            "day_started_at": day_started,
        }

    def get_model_info(self) -> dict:
        """Return the active model's name and known quota limits."""
        model = "unknown"
        if self.provider is not None:
            if hasattr(self.provider, "model"):
                model = self.provider.model      # GeminiCLIProvider / ClaudeAPIProvider
            elif hasattr(self.provider, "_model") and self.provider._model is not None:
                model = "local"                  # LocalLlamaProvider
        limits = _MODEL_LIMITS.get(model, {"daily_requests": 0, "context_tokens": 4096})
        return {
            "model": model,
            "daily_request_limit": limits["daily_requests"],
            "context_tokens": limits["context_tokens"],
            "unlimited": limits["daily_requests"] == 0,
        }

    def reset_usage(self) -> None:
        """Reset session usage counters (called on provider switch)."""
        self._usage["calls"] = 0
        self._usage["calls_today"] = 0
        self._usage["estimated_tokens"] = 0
        self._usage["errors"] = 0
        self._usage["started_at"] = time.time()
        self._usage["day_started_at"] = time.time()


# ---------------------------------------------------------------------------
# Global Access Point
# ---------------------------------------------------------------------------
llm_gateway = LLMGateway()
```

```python
# src/core/queue_manager.py
"""
SAGE[ai] - Queue Manager
=========================
Thread-safe FIFO task queue with SQLite persistence. Ensures single-lane
execution for compliance and survives process restarts.

Task types:
  ANALYZE_LOG    - Run analyst agent on a log entry
  CREATE_MR      - Create a merge request from an issue
  REVIEW_MR      - Review a merge request
  FLASH_FIRMWARE - Flash firmware via J-Link
  MONITOR_CHECK  - On-demand monitor poll

ISO 13485 Note: Single-lane serialized execution ensures a deterministic,
auditable sequence of AI actions. No parallel AI decisions.

Wave Execution Note: When compliance_mode is False, ParallelTaskRunner groups
independent tasks (no depends_on) into wave 0 and runs them concurrently via
ThreadPoolExecutor. Tasks with depends_on are deferred to subsequent waves.
LLM calls inside each task still route through the single-lane LLMGateway lock.

Persistence Note: Tasks are written to SQLite on submit and updated on
completion/failure. Pending tasks are restored on process restart.

Structured logging: log records carry an ``extra={...}`` dict whose keys are
drawn ONLY from the canonical set {event, provider, duration_ms, task_id,
status}. Messages are static strings — no f-string or %-style interpolation —
so all variable detail lives in the canonical fields (or in exc_info for
exceptions). Set SAGE_JSON_LOGS=1 and call
src.core.log_config.configure_logging() to emit them as JSON.
"""

import json
import logging
import os
import queue
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Path to the shared audit/task SQLite database
_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "audit_log.db",
)


def _run_hooks(commands: list, cwd: str = None) -> None:
    """Run a list of shell commands sequentially. Logs failures but does not raise."""
    import subprocess as _sp
    for cmd in commands:
        try:
            result = _sp.run(cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=cwd)
            if result.returncode != 0:
                logger.warning(
                    "Hook command failed",
                    extra={"event": "hook_run", "status": "error"},
                )
            else:
                logger.debug(
                    "Hook ran ok",
                    extra={"event": "hook_run", "status": "ok"},
                )
        except Exception as exc:
            logger.warning(
                "Hook command raised an exception",
                exc_info=True,
                extra={"event": "hook_run", "status": "error"},
            )


def _fanout_subtasks(queue_manager, parent_task_id: str, subtasks: list) -> list:
    """
    Submit a list of subtask dicts to the queue, grouping by wave.
    Each dict: {task_type, payload, wave (int, default 0), priority (optional)}.

    Wave 0 tasks have no dependencies.
    Wave N tasks depend on all task_ids from wave N-1.

    Returns list of submitted task_ids in order.
    """
    from collections import defaultdict
    waves: dict = defaultdict(list)
    for st in subtasks:
        waves[st.get("wave", 0)].append(st)

    all_ids: list = []
    prev_wave_ids: list = []

    for wave_num in sorted(waves.keys()):
        wave_ids = []
        for st in waves[wave_num]:
            task_id = queue_manager.submit(
                st["task_type"],
                st.get("payload", {}),
                priority=st.get("priority", 5),
                source="subagent",
                depends_on=list(prev_wave_ids),
                metadata={"parent_task_id": parent_task_id, "wave": wave_num},
            )
            wave_ids.append(task_id)
        all_ids.extend(wave_ids)
        prev_wave_ids = wave_ids

    logger.info(
        "Fanout: subtasks spawned",
        extra={"event": "fanout", "task_id": parent_task_id, "status": "spawned"},
    )
    return all_ids


class TaskStatus:
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"  # dependency failed — cannot execute


# ---------------------------------------------------------------------------
# Transient error classification — retry these, not permanent errors
# ---------------------------------------------------------------------------

_TRANSIENT_PATTERNS = [
    "timeout", "timed out", "connection refused", "connection reset",
    "rate limit", "429", "503", "502", "504", "temporary", "unavailable",
    "retry", "EAGAIN", "broken pipe", "connection aborted",
]


def _is_transient_error(error_msg: str) -> bool:
    """Classify an error as transient (retryable) vs permanent."""
    lower = error_msg.lower()
    return any(p in lower for p in _TRANSIENT_PATTERNS)


# ---------------------------------------------------------------------------
# Loop Detection — prevents stuck agents from spinning forever
# Inspired by DeerFlow's LoopDetectionMiddleware
# ---------------------------------------------------------------------------

class LoopDetector:
    """Detects repeated identical task dispatches within a sliding window.

    Hashes (task_type, payload_keys_sorted) for each dispatch. If the same
    hash appears WARN_THRESHOLD times, logs a warning. At STOP_THRESHOLD,
    raises a LoopDetectedError to force-stop the loop.

    Thread-safe: uses a Lock to guard the sliding window.
    """

    WARN_THRESHOLD = 3
    STOP_THRESHOLD = 5
    WINDOW_SIZE = 20  # sliding window of recent dispatches

    def __init__(self):
        self._window: list[str] = []
        self._lock = threading.Lock()
        self.logger = logging.getLogger("LoopDetector")

    def _hash_task(self, task_type: str, payload: dict) -> str:
        """Create a deterministic hash of a task dispatch."""
        import hashlib
        key = json.dumps(
            {"type": task_type, "keys": sorted(payload.keys()),
             "vals": str(sorted(str(v)[:100] for v in payload.values()))},
            sort_keys=True,
        )
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def check(self, task_type: str, payload: dict) -> None:
        """Check for loops. Raises LoopDetectedError at STOP_THRESHOLD."""
        h = self._hash_task(task_type, payload)

        with self._lock:
            self._window.append(h)
            if len(self._window) > self.WINDOW_SIZE:
                self._window = self._window[-self.WINDOW_SIZE:]

            count = self._window.count(h)

        if count >= self.STOP_THRESHOLD:
            msg = (
                f"Loop detected: task_type={task_type} dispatched "
                f"{count} times in last {self.WINDOW_SIZE} calls. Force-stopping."
            )
            self.logger.error(
                "Loop detected — force-stopping dispatch",
                extra={"event": "loop_detected", "status": "stopped"},
            )
            raise LoopDetectedError(msg)

        if count >= self.WARN_THRESHOLD:
            self.logger.warning(
                "Possible dispatch loop detected",
                extra={"event": "loop_detected", "status": "warning"},
            )

    def reset(self):
        """Clear the sliding window."""
        with self._lock:
            self._window.clear()


class LoopDetectedError(Exception):
    """Raised when the LoopDetector identifies a stuck dispatch loop."""


# ---------------------------------------------------------------------------
# Task Timeout defaults per task type (seconds)
# ---------------------------------------------------------------------------

TASK_TIMEOUT_DEFAULTS: dict[str, int] = {
    "ANALYZE_LOG": 120,
    "CREATE_MR": 300,
    "REVIEW_MR": 180,
    "FLASH_FIRMWARE": 600,
    "MONITOR_CHECK": 60,
    "PLAN_TASK": 300,
    "WORKFLOW": 600,
    "CODE_TASK": 600,
}

DEFAULT_TASK_TIMEOUT = 300  # 5 minutes fallback


class Task:
    """Represents a single unit of work in the task queue."""

    def __init__(self, task_type: str, payload: dict, priority: int = 5,
                 plan_trace_id: str = "", source: str = "",
                 depends_on: Optional[List[str]] = None,
                 max_retries: int = 3, timeout: Optional[int] = None):
        self.task_id = str(uuid.uuid4())
        self.task_type = task_type
        self.payload = payload
        self.priority = priority  # Lower number = higher priority (1=highest, 10=lowest)
        self.status = TaskStatus.PENDING
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None
        self.result: Any = None
        self.error: Optional[str] = None
        self.plan_trace_id: str = plan_trace_id
        self.source: str = source
        # List of task_ids this task depends on (empty = no dependencies = wave 0)
        self.depends_on: List[str] = depends_on or []
        # Wave metadata populated by ParallelTaskRunner at dispatch time
        self.metadata: dict = {}
        # Retry tracking
        self.retry_count: int = 0
        self.max_retries: int = max_retries
        self.last_error: Optional[str] = None
        self.error_history: List[str] = []
        # Per-task timeout in seconds (None = use default for task_type)
        self.timeout: int = timeout or TASK_TIMEOUT_DEFAULTS.get(
            task_type.upper(), DEFAULT_TASK_TIMEOUT
        )

    def __lt__(self, other: "Task") -> bool:
        """Priority queue comparison: lower priority number = higher priority."""
        return self.priority < other.priority

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "priority": self.priority,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "payload_keys": list(self.payload.keys()),
            "depends_on": self.depends_on,
            "metadata": self.metadata,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "timeout": self.timeout,
        }


class TaskQueue:
    """
    Thread-safe FIFO priority task queue backed by SQLite for persistence.

    On startup, any tasks left in 'pending' or 'in_progress' state (from a
    previous run) are automatically restored to the in-memory queue.

    Usage:
        from src.core.queue_manager import task_queue
        task_id = task_queue.submit("ANALYZE_LOG", {"log_entry": "Error: ..."})
    """

    def __init__(self, db_path: str = _DB_PATH):
        self._queue: queue.PriorityQueue = queue.PriorityQueue()
        self._tasks: Dict[str, Task] = {}
        self._lock = threading.Lock()
        self.logger = logging.getLogger("TaskQueue")
        self._db_path = db_path
        self._init_db()
        self._restore_pending_tasks()

    # -----------------------------------------------------------------------
    # SQLite helpers
    # -----------------------------------------------------------------------

    def _init_db(self):
        """Create the task_queue table if it does not exist."""
        try:
            os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
            conn = sqlite3.connect(self._db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_queue (
                    task_id        TEXT PRIMARY KEY,
                    task_type      TEXT NOT NULL,
                    payload        TEXT NOT NULL,
                    priority       INTEGER DEFAULT 5,
                    status         TEXT DEFAULT 'pending',
                    created_at     TEXT,
                    started_at     TEXT,
                    completed_at   TEXT,
                    result         TEXT,
                    error          TEXT,
                    plan_trace_id  TEXT,
                    source         TEXT
                )
            """)
            conn.commit()
            # Migration: add columns to pre-existing databases
            for col, col_type in [
                ("plan_trace_id", "TEXT"),
                ("source", "TEXT"),
                ("depends_on", "TEXT"),
                ("metadata", "TEXT"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE task_queue ADD COLUMN {col} {col_type}")
                    conn.commit()
                    self.logger.info(
                        "Migrated task_queue: added column",
                        extra={"event": "db_migrate", "status": "migrated"},
                    )
                except Exception:
                    pass  # Column already exists
            conn.close()
            self.logger.info(
                "Task queue SQLite storage initialised",
                extra={"event": "db_init", "status": "initialised"},
            )
        except Exception as exc:
            self.logger.error(
                "Failed to initialise task queue DB",
                exc_info=True,
                extra={"event": "db_init", "status": "error"},
            )

    def _restore_pending_tasks(self):
        """Load pending/in-progress tasks from a previous run on startup."""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM task_queue "
                "WHERE status IN ('pending', 'in_progress') "
                "ORDER BY priority ASC, created_at ASC"
            )
            rows = cursor.fetchall()
            conn.close()

            restored = 0
            for row in rows:
                task = Task.__new__(Task)
                task.task_id = row["task_id"]
                task.task_type = row["task_type"]
                task.payload = json.loads(row["payload"])
                task.priority = row["priority"]
                # Reset in_progress → pending; the worker that held the task is gone
                task.status = TaskStatus.PENDING
                task.created_at = row["created_at"]
                task.started_at = None
                task.completed_at = None
                task.result = None
                task.error = None
                raw_depends = row["depends_on"] if "depends_on" in row.keys() else None
                task.depends_on = json.loads(raw_depends) if raw_depends else []
                raw_meta = row["metadata"] if "metadata" in row.keys() else None
                task.metadata = json.loads(raw_meta) if raw_meta else {}
                # New fields for retry/timeout — safe defaults for pre-existing tasks
                task.retry_count = 0
                task.max_retries = 3
                task.last_error = None
                task.error_history = []
                task.timeout = TASK_TIMEOUT_DEFAULTS.get(
                    task.task_type.upper(), DEFAULT_TASK_TIMEOUT
                )

                with self._lock:
                    self._tasks[task.task_id] = task
                self._queue.put((task.priority, task.created_at, task))
                restored += 1

            if restored:
                self.logger.info(
                    "Restored pending task(s) from SQLite on startup.",
                    extra={"event": "tasks_restored", "status": "restored"},
                )
        except Exception as exc:
            self.logger.error(
                "Failed to restore pending tasks",
                exc_info=True,
                extra={"event": "tasks_restored", "status": "error"},
            )

    def _db_insert(self, task: Task):
        """Persist a newly submitted task to SQLite."""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "INSERT OR REPLACE INTO task_queue "
                "(task_id, task_type, payload, priority, status, created_at, "
                "plan_trace_id, source, depends_on, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    task.task_id,
                    task.task_type,
                    json.dumps(task.payload),
                    task.priority,
                    task.status,
                    task.created_at,
                    task.plan_trace_id,
                    task.source,
                    json.dumps(task.depends_on),
                    json.dumps(task.metadata),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            self.logger.error(
                "DB insert failed for task",
                exc_info=True,
                extra={"event": "db_insert", "task_id": task.task_id, "status": "error"},
            )

    def _db_update(self, task: Task):
        """Update status, timestamps, result/error, and metadata for an existing task."""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "UPDATE task_queue "
                "SET status=?, started_at=?, completed_at=?, result=?, error=?, metadata=? "
                "WHERE task_id=?",
                (
                    task.status,
                    task.started_at,
                    task.completed_at,
                    json.dumps(task.result) if task.result is not None else None,
                    task.error,
                    json.dumps(task.metadata),
                    task.task_id,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            self.logger.error(
                "DB update failed for task",
                exc_info=True,
                extra={"event": "db_update", "task_id": task.task_id, "status": "error"},
            )

    # -----------------------------------------------------------------------
    # Public Queue Operations
    # -----------------------------------------------------------------------

    def submit(self, task_type: str, payload: dict, priority: int = 5,
               plan_trace_id: str = "", source: str = "",
               depends_on: Optional[List[str]] = None,
               metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Adds a new task to the queue and persists it to SQLite.

        Args:
            task_type:      Task category (e.g. 'ANALYZE_LOG', 'CREATE_MR')
            payload:        Task-specific data dict
            priority:       Integer priority 1-10 (1=highest, default=5)
            plan_trace_id:  Optional trace_id of the implementation plan proposal
            source:         'sage' for framework tasks, 'solution' for solution tasks
            depends_on:     Optional list of task_ids this task depends on.
                            Tasks with no depends_on are placed in wave 0.
            metadata:       Optional extra key-value pairs persisted with the task
                            and returned by get_all_tasks() for filtering.

        Returns:
            task_id string for tracking.
        """
        task = Task(task_type, payload, priority, plan_trace_id=plan_trace_id,
                    source=source, depends_on=depends_on)
        if metadata:
            task.metadata.update(metadata)
        with self._lock:
            self._tasks[task.task_id] = task
        self._db_insert(task)
        self._queue.put((priority, task.created_at, task))
        self.logger.info(
            "Task submitted",
            extra={"event": "task_submitted", "task_id": task.task_id,
                   "status": TaskStatus.PENDING},
        )
        return task.task_id

    def get_next(self, timeout: float = 1.0) -> Optional[Task]:
        """
        Blocking get of the next highest-priority task.

        Args:
            timeout: Max seconds to wait (default 1.0)

        Returns:
            Task object or None if queue is empty after timeout.
        """
        try:
            _, _, task = self._queue.get(timeout=timeout)
            with self._lock:
                task.status = TaskStatus.IN_PROGRESS
                task.started_at = datetime.now(timezone.utc).isoformat()
                self._db_update(task)
            self.logger.debug(
                "Dequeued task",
                extra={"event": "task_dequeued", "task_id": task.task_id,
                       "status": TaskStatus.IN_PROGRESS},
            )
            return task
        except queue.Empty:
            return None

    def mark_done(self, task_id: str, result: Any = None):
        """
        Marks a task as completed with an optional result.

        Args:
            task_id: The task's ID
            result:  Optional result data
        """
        with self._lock:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now(timezone.utc).isoformat()
                task.result = result
                self._db_update(task)
                self.logger.info(
                    "Task completed",
                    extra={"event": "task_completed", "task_id": task_id,
                           "status": TaskStatus.COMPLETED},
                )
            else:
                self.logger.warning(
                    "mark_done called for unknown task_id",
                    extra={"event": "task_completed", "task_id": task_id, "status": "unknown"},
                )
        try:
            self._queue.task_done()
        except ValueError:
            pass  # task was not dequeued via get_next() (e.g. parallel runner path)

    def mark_failed(self, task_id: str, error: str):
        """Marks a task as failed and persists the error message."""
        with self._lock:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now(timezone.utc).isoformat()
                task.error = error
                task.error_history.append(error)
                self._db_update(task)
                self.logger.error(
                    "Task failed",
                    extra={"event": "task_failed", "task_id": task_id,
                           "status": TaskStatus.FAILED},
                )
        try:
            self._queue.task_done()
        except ValueError:
            pass

    def mark_blocked(self, task_id: str, reason: str):
        """Mark a task as blocked due to failed dependency."""
        with self._lock:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                task.status = TaskStatus.BLOCKED
                task.error = reason
                self._db_update(task)
                self.logger.warning(
                    "Task blocked due to failed dependency",
                    extra={"event": "task_blocked", "task_id": task_id,
                           "status": TaskStatus.BLOCKED},
                )

    def retry_task(self, task_id: str) -> bool:
        """Re-queue a failed task if it has retries remaining and the error is transient.

        Returns True if the task was re-queued, False otherwise.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            if task.status != TaskStatus.FAILED:
                return False
            if task.retry_count >= task.max_retries:
                self.logger.info(
                    "Task exhausted retries",
                    extra={"event": "task_retry_exhausted", "task_id": task_id,
                           "status": "exhausted"},
                )
                return False
            if not _is_transient_error(task.error or ""):
                self.logger.info(
                    "Task has permanent error, not retrying",
                    extra={"event": "task_retry_skipped", "task_id": task_id,
                           "status": "permanent_error"},
                )
                return False

            task.retry_count += 1
            task.status = TaskStatus.PENDING
            task.started_at = None
            task.completed_at = None
            task.last_error = task.error
            task.error = None
            self._db_update(task)

        # Backoff: 2^retry_count seconds (2, 4, 8...)
        backoff = min(2 ** task.retry_count, 60)
        self.logger.info(
            "Retrying task after backoff",
            extra={"event": "task_retry", "task_id": task_id, "status": "retrying"},
        )
        time.sleep(backoff)
        self._queue.put((task.priority, task.created_at, task))
        return True

    def get_blocked_dependents(self, failed_task_id: str) -> List[str]:
        """Find all tasks that depend on the failed task and block them."""
        blocked_ids = []
        with self._lock:
            for tid, task in self._tasks.items():
                if failed_task_id in task.depends_on and task.status == TaskStatus.PENDING:
                    blocked_ids.append(tid)
        return blocked_ids

    def propagate_failure(self, failed_task_id: str) -> List[str]:
        """Block all tasks depending on a failed task. Returns list of blocked task IDs."""
        blocked = self.get_blocked_dependents(failed_task_id)
        for tid in blocked:
            self.mark_blocked(tid, f"Dependency {failed_task_id} failed")
            # Recursively block downstream
            blocked.extend(self.propagate_failure(tid))
        return blocked

    def get_status(self, task_id: str) -> Optional[dict]:
        """
        Returns the current status of a task.

        Args:
            task_id: Task ID to look up

        Returns:
            Task status dict or None if not found.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            return task.to_dict() if task else None

    def get_pending_count(self) -> int:
        """Returns the number of tasks currently in the queue (not started)."""
        return self._queue.qsize()

    def get_all_tasks(self) -> list:
        """Returns status of all tracked tasks (for dashboard)."""
        with self._lock:
            return [t.to_dict() for t in self._tasks.values()]


class TaskWorker(threading.Thread):
    """
    Background worker thread that processes tasks from the TaskQueue.
    Dispatches to the appropriate agent based on task_type.
    Single-lane: processes one task at a time (by design).

    Enhanced with:
    - Loop detection (DeerFlow-inspired)
    - Retry with exponential backoff for transient errors
    - Per-task timeout enforcement
    - Error-to-context feedback for LLM self-correction
    - Dependency failure propagation
    """

    def __init__(self, task_queue: TaskQueue, name: str = "TaskWorker"):
        super().__init__(name=name, daemon=True)
        self._queue = task_queue
        self._running = False
        self._loop_detector = LoopDetector()
        self.logger = logging.getLogger("TaskWorker")

    def run(self):
        """Main task processing loop."""
        self._running = True
        self.logger.info(
            "TaskWorker started (single-lane compliance mode).",
            extra={"event": "worker_started", "status": "started"},
        )

        while self._running:
            task = self._queue.get_next(timeout=1.0)
            if task is None:
                continue  # Queue empty, keep polling

            self.logger.info(
                "Processing task",
                extra={"event": "task_processing", "task_id": task.task_id,
                       "status": "in_progress"},
            )
            try:
                # Loop detection
                self._loop_detector.check(task.task_type, task.payload)

                # Execute with timeout
                result = self._dispatch_with_timeout(task)
                self._queue.mark_done(task.task_id, result)
            except LoopDetectedError as e:
                self.logger.error(
                    "Loop detected for task",
                    exc_info=True,
                    extra={"event": "loop_detected", "task_id": task.task_id,
                           "status": "failed"},
                )
                self._queue.mark_failed(task.task_id, f"LOOP_DETECTED: {e}")
                self._queue.propagate_failure(task.task_id)
            except _TaskTimeoutError as e:
                self.logger.error(
                    "Task timed out",
                    extra={"event": "task_timeout", "task_id": task.task_id,
                           "status": "timeout"},
                )
                self._queue.mark_failed(task.task_id, f"TIMEOUT: {e}")
                # Retry on timeout (transient)
                if not self._queue.retry_task(task.task_id):
                    self._queue.propagate_failure(task.task_id)
            except Exception as e:
                error_msg = str(e)
                self.logger.error(
                    "Task failed",
                    exc_info=True,
                    extra={"event": "task_failed", "task_id": task.task_id,
                           "status": "failed"},
                )
                self._queue.mark_failed(task.task_id, error_msg)

                # Auto-retry transient errors
                if _is_transient_error(error_msg):
                    if not self._queue.retry_task(task.task_id):
                        self._queue.propagate_failure(task.task_id)
                else:
                    self._queue.propagate_failure(task.task_id)

        self.logger.info(
            "TaskWorker stopped.",
            extra={"event": "worker_stopped", "status": "stopped"},
        )

    def _dispatch_with_timeout(self, task: Task) -> Any:
        """Execute dispatch with a per-task timeout.

        Uses a daemon thread + Event to enforce the timeout. If the task
        exceeds its timeout, raises _TaskTimeoutError.
        """
        result_holder: dict = {}
        error_holder: dict = {}
        done_event = threading.Event()

        def _run():
            try:
                result_holder["result"] = self._dispatch(task)
            except Exception as exc:
                error_holder["error"] = exc
            finally:
                done_event.set()

        worker_thread = threading.Thread(target=_run, daemon=True)
        worker_thread.start()

        if not done_event.wait(timeout=task.timeout):
            raise _TaskTimeoutError(
                f"Task {task.task_type} (id={task.task_id}) exceeded "
                f"timeout of {task.timeout}s"
            )

        if "error" in error_holder:
            raise error_holder["error"]

        return result_holder.get("result")

    def stop(self):
        """Signals the worker to stop after completing the current task."""
        self._running = False

    def build_error_context(self, task: Task) -> str:
        """Build error context from previous failures for LLM self-correction.

        When a task is being retried, include the error history so the LLM
        can reason about what went wrong and try a different approach.
        """
        error_history = getattr(task, "error_history", [])
        if not error_history:
            return ""
        retry_count = getattr(task, "retry_count", 0)
        max_retries = getattr(task, "max_retries", 3)
        lines = [
            f"\n[RETRY CONTEXT — Attempt {retry_count + 1}/{max_retries}]",
            "Previous attempts failed with these errors:",
        ]
        for i, err in enumerate(error_history[-3:], 1):  # last 3 errors
            lines.append(f"  Attempt {i}: {err[:200]}")
        lines.append("Adjust your approach to avoid these errors.")
        return "\n".join(lines)

    def _dispatch(self, task: Task) -> Any:
        """
        Routes a task to the appropriate agent method.

        Args:
            task: The Task to dispatch

        Returns:
            Result from the agent (dict, str, etc.)
        """
        task_type = task.task_type.upper()
        payload = task.payload

        # Inject error context for retried tasks (error-to-context feedback)
        error_ctx = self.build_error_context(task)
        if error_ctx:
            payload = {**payload}  # shallow copy to avoid mutating original
            existing = payload.get("log_entry", payload.get("task", payload.get("description", "")))
            if isinstance(existing, str) and existing:
                # Append error context to the primary text field
                for key in ("log_entry", "task", "description"):
                    if key in payload:
                        payload[key] = payload[key] + error_ctx
                        break

        from src.core.project_loader import project_config
        hooks = project_config.get_task_hooks(task_type)
        _run_hooks(hooks["pre"])

        if task_type == "ANALYZE_LOG":
            from src.agents.analyst import analyst_agent
            log_entry = payload.get("log_entry", "")
            if not log_entry:
                raise ValueError("ANALYZE_LOG task missing 'log_entry' in payload.")
            result = analyst_agent.analyze_log(log_entry)

        elif task_type == "CREATE_MR":
            from src.agents.developer import developer_agent
            project_id = payload.get("project_id")
            issue_iid = payload.get("issue_iid")
            if not project_id or not issue_iid:
                raise ValueError("CREATE_MR task missing 'project_id' or 'issue_iid'.")
            result = developer_agent.create_mr_from_issue(
                project_id=int(project_id),
                issue_iid=int(issue_iid),
                source_branch=payload.get("source_branch"),
            )

        elif task_type == "REVIEW_MR":
            from src.agents.developer import developer_agent
            project_id = payload.get("project_id")
            mr_iid = payload.get("mr_iid")
            if not project_id or not mr_iid:
                raise ValueError("REVIEW_MR task missing 'project_id' or 'mr_iid'.")
            result = developer_agent.review_merge_request(
                project_id=int(project_id),
                mr_iid=int(mr_iid),
            )

        elif task_type == "FLASH_FIRMWARE":
            # Delegates to J-Link MCP server tool
            from mcp_servers.jlink_server import flash_firmware, connect_jlink
            device = payload.get("device", "")
            bin_path = payload.get("bin_path", "")
            interface = payload.get("interface", "SWD")
            speed = payload.get("speed", 4000)
            if not device or not bin_path:
                raise ValueError("FLASH_FIRMWARE task missing 'device' or 'bin_path'.")
            connect_result = connect_jlink(device=device, interface=interface, speed=speed)
            if "error" in connect_result:
                raise RuntimeError(f"J-Link connect failed: {connect_result['error']}")
            result = flash_firmware(bin_path=bin_path)

        elif task_type == "MONITOR_CHECK":
            from src.agents.monitor import monitor_agent
            source = payload.get("source", "all")
            if source in ("teams", "all") and monitor_agent._teams_team_id:
                monitor_agent._poll_teams.__func__  # Check it exists
            result = {"status": "monitor_check_triggered", "source": source}

        elif task_type == "PLAN_TASK":
            from src.agents.planner import planner_agent
            description = payload.get("description", "")
            if not description:
                raise ValueError("PLAN_TASK missing 'description' in payload.")
            result = planner_agent.plan_and_execute(description)

        elif task_type == "WORKFLOW":
            from src.integrations.langgraph_runner import langgraph_runner
            workflow_name = payload.get("workflow_name", "")
            if not workflow_name:
                raise ValueError("WORKFLOW task missing 'workflow_name' in payload.")
            state = payload.get("state", {})
            result = langgraph_runner.run(workflow_name, state)

        elif task_type == "CODE_TASK":
            from src.integrations.autogen_runner import autogen_runner
            task_description = payload.get("task", "")
            if not task_description:
                raise ValueError("CODE_TASK missing 'task' in payload.")
            trace_id = payload.get("trace_id")
            result = autogen_runner.plan(task_description, trace_id=trace_id)

        else:
            raise ValueError(
                f"Unknown task_type: '{task_type}'. "
                "Supported: ANALYZE_LOG, CREATE_MR, REVIEW_MR, FLASH_FIRMWARE, "
                "MONITOR_CHECK, PLAN_TASK, WORKFLOW, CODE_TASK"
            )

        _run_hooks(hooks["post"])

        # After hook execution, check for subtask fanout
        subtasks = task.payload.get("subtasks", [])
        if subtasks:
            try:
                _fanout_subtasks(self._queue, task.task_id, subtasks)
            except Exception as exc:
                self.logger.warning(
                    "Subtask fanout failed",
                    exc_info=True,
                    extra={"event": "fanout", "task_id": task.task_id, "status": "error"},
                )

        return result


class _TaskTimeoutError(Exception):
    """Raised when a task exceeds its configured timeout."""


# ---------------------------------------------------------------------------
# Parallel Task Runner
# ---------------------------------------------------------------------------

class ParallelConfig:
    """
    Runtime-adjustable configuration for ParallelTaskRunner.

    Attributes:
        max_workers:       Maximum threads in the pool (default 4).
        parallel_enabled:  When False the runner falls back to sequential,
                           identical to the legacy single-lane behaviour.
    """

    def __init__(self, max_workers: int = 4, parallel_enabled: bool = True):
        self._lock = threading.Lock()
        self._max_workers = max_workers
        self._parallel_enabled = parallel_enabled

    @property
    def max_workers(self) -> int:
        with self._lock:
            return self._max_workers

    @max_workers.setter
    def max_workers(self, value: int):
        with self._lock:
            self._max_workers = max(1, int(value))

    @property
    def parallel_enabled(self) -> bool:
        with self._lock:
            return self._parallel_enabled

    @parallel_enabled.setter
    def parallel_enabled(self, value: bool):
        with self._lock:
            self._parallel_enabled = bool(value)

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "max_workers": self._max_workers,
                "parallel_enabled": self._parallel_enabled,
            }


class ParallelTaskRunner:
    """
    Wave-based parallel task executor.

    A *wave* is a set of tasks that share no data dependencies and can
    therefore run concurrently.  The scheduler:

      1. Inspects all PENDING tasks passed to execute_parallel().
      2. Assigns tasks with an empty depends_on list to wave 0.
      3. Assigns tasks whose entire depends_on set is satisfied by wave N
         to wave N+1.
      4. Submits each wave to a ThreadPoolExecutor, waiting for every task
         in the wave to complete before advancing.

    Compliance override:
      If compliance_mode=True (project has compliance_standards set) the runner
      falls back to strict sequential single-lane execution regardless of the
      parallel_enabled flag.  This matches the ISO 13485 guarantee.

    LLM single-lane guarantee:
      Task parallelism is at the *dispatch* level only.  LLM calls inside each
      task still route through the LLMGateway's threading.Lock, so inference
      remains single-lane.
    """

    def __init__(self, queue_manager: "TaskQueue", config: "ParallelConfig" = None):
        self._queue = queue_manager
        self.config = config or ParallelConfig()
        self.logger = logging.getLogger("ParallelTaskRunner")
        # Live state — updated during execute_parallel(); read by /queue/status
        self._state_lock = threading.Lock()
        self._active_wave: int = 0
        self._wave_size: int = 0
        self._parallel_active: bool = False

    # ------------------------------------------------------------------
    # Public state accessors (for /queue/status)
    # ------------------------------------------------------------------

    @property
    def active_wave(self) -> int:
        with self._state_lock:
            return self._active_wave

    @property
    def wave_size(self) -> int:
        with self._state_lock:
            return self._wave_size

    @property
    def parallel_active(self) -> bool:
        with self._state_lock:
            return self._parallel_active

    # ------------------------------------------------------------------
    # Core execution helpers
    # ------------------------------------------------------------------

    def _run_one(self, worker: TaskWorker, task: Task) -> dict:
        """
        Execute a single task via the worker's _dispatch_with_timeout() method.
        Updates task status on the queue and returns a result summary.
        Handles retry for transient errors and dependency propagation.
        This method is called from a thread-pool thread.
        """
        task.started_at = datetime.now(timezone.utc).isoformat()
        with self._queue._lock:
            task.status = TaskStatus.IN_PROGRESS
            self._queue._db_update(task)

        try:
            result = worker._dispatch_with_timeout(task)
            self._queue.mark_done(task.task_id, result)
            return {"task_id": task.task_id, "status": TaskStatus.COMPLETED, "result": result}
        except (_TaskTimeoutError, Exception) as exc:
            error_msg = str(exc)
            self.logger.error(
                "Parallel task failed",
                exc_info=True,
                extra={"event": "parallel_task", "task_id": task.task_id, "status": "failed"},
            )
            self._queue.mark_failed(task.task_id, error_msg)

            # Attempt retry for transient errors
            if _is_transient_error(error_msg):
                retried = self._queue.retry_task(task.task_id)
                if retried:
                    return {"task_id": task.task_id, "status": "retrying", "error": error_msg}

            # Propagate failure to dependents
            blocked = self._queue.propagate_failure(task.task_id)
            return {
                "task_id": task.task_id,
                "status": TaskStatus.FAILED,
                "error": error_msg,
                "blocked_dependents": blocked,
            }

    def run_wave(self, tasks: List[Task], wave_id: int, worker: TaskWorker) -> List[dict]:
        """
        Run a list of independent tasks concurrently.

        Tags each task's metadata with wave_id and parallel_group (sibling
        task IDs in the same wave) before dispatch.

        Returns:
            List of result dicts, one per task.
        """
        if not tasks:
            return []

        sibling_ids = [t.task_id for t in tasks]
        for task in tasks:
            task.metadata["wave_id"] = wave_id
            task.metadata["parallel_group"] = [tid for tid in sibling_ids if tid != task.task_id]
            self._queue._db_update(task)

        max_workers = min(self.config.max_workers, len(tasks))
        self.logger.info(
            "Wave dispatching task(s)",
            extra={"event": "wave_dispatch", "status": "dispatching"},
        )

        results: List[dict] = []
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="sage-wave") as pool:
            futures = {pool.submit(self._run_one, worker, task): task for task in tasks}
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as exc:
                    task = futures[future]
                    self.logger.error(
                        "Wave future raised an error",
                        exc_info=True,
                        extra={"event": "wave_dispatch", "task_id": task.task_id,
                               "status": "failed"},
                    )
                    results.append({"task_id": task.task_id, "status": TaskStatus.FAILED,
                                    "error": str(exc)})
        return results

    def execute_parallel(self, pending_tasks: List[Task], worker: TaskWorker,
                         compliance_mode: bool = False) -> None:
        """
        Group tasks into waves and execute them.

        Wave assignment algorithm:
          - Wave 0: tasks whose depends_on list is empty.
          - Wave N+1: tasks whose entire depends_on set is a subset of
            task IDs that completed in wave 0..N.

        Falls back to strict sequential execution when:
          - compliance_mode is True, OR
          - self.config.parallel_enabled is False

        Args:
            pending_tasks:   List of Task objects to execute (all PENDING).
            worker:          TaskWorker instance used for _dispatch().
            compliance_mode: If True, force sequential single-lane execution.
        """
        if not pending_tasks:
            return

        sequential = compliance_mode or not self.config.parallel_enabled
        self.logger.info(
            "execute_parallel: dispatching tasks",
            extra={"event": "execute_parallel", "status": "starting"},
        )

        if sequential:
            with self._state_lock:
                self._parallel_active = False
                self._active_wave = 0
                self._wave_size = 1
            for task in pending_tasks:
                task.started_at = datetime.now(timezone.utc).isoformat()
                with self._queue._lock:
                    task.status = TaskStatus.IN_PROGRESS
                    self._queue._db_update(task)
                try:
                    result = worker._dispatch(task)
                    self._queue.mark_done(task.task_id, result)
                except Exception as exc:
                    self.logger.error(
                        "Sequential task failed",
                        exc_info=True,
                        extra={"event": "execute_parallel", "task_id": task.task_id,
                               "status": "failed"},
                    )
                    self._queue.mark_failed(task.task_id, str(exc))
            with self._state_lock:
                self._parallel_active = False
                self._active_wave = 0
                self._wave_size = 0
            return

        # Build wave assignment
        completed_ids: set = set()
        remaining = list(pending_tasks)
        wave_id = 0

        with self._state_lock:
            self._parallel_active = True

        failed_ids: set = set()

        try:
            while remaining:
                # Collect tasks whose dependencies are all satisfied
                wave_tasks = []
                blocked_tasks = []
                still_waiting = []

                for t in remaining:
                    dep_set = set(t.depends_on)
                    # Check if any dependency failed — block this task
                    if dep_set & failed_ids:
                        blocked_tasks.append(t)
                    elif dep_set.issubset(completed_ids):
                        wave_tasks.append(t)
                    else:
                        still_waiting.append(t)

                # Block tasks whose dependencies failed
                for t in blocked_tasks:
                    failed_deps = list(set(t.depends_on) & failed_ids)
                    self._queue.mark_blocked(
                        t.task_id,
                        f"Dependencies failed: {failed_deps}",
                    )
                    failed_ids.add(t.task_id)

                if not wave_tasks and not still_waiting:
                    break  # all remaining are blocked

                if not wave_tasks:
                    # Dependency cycle or unresolvable — fall back to sequential remainder
                    self.logger.warning(
                        "Wave scheduler: tasks have unresolvable dependencies, "
                        "running sequentially.",
                        extra={"event": "execute_parallel", "status": "unresolvable"},
                    )
                    wave_tasks = still_waiting
                    still_waiting = []

                with self._state_lock:
                    self._active_wave = wave_id
                    self._wave_size = len(wave_tasks)

                results = self.run_wave(wave_tasks, wave_id, worker)

                # Mark all completed tasks so subsequent waves can use them
                for res in results:
                    if res["status"] == TaskStatus.COMPLETED:
                        completed_ids.add(res["task_id"])
                    elif res["status"] == TaskStatus.FAILED:
                        failed_ids.add(res["task_id"])

                # Remove dispatched tasks from remaining
                dispatched_ids = {t.task_id for t in wave_tasks}
                remaining = [t for t in still_waiting if t.task_id not in dispatched_ids]
                wave_id += 1
        finally:
            with self._state_lock:
                self._parallel_active = False
                self._active_wave = 0
                self._wave_size = 0


# ---------------------------------------------------------------------------
# Global instances
# ---------------------------------------------------------------------------
loop_detector = LoopDetector()
parallel_config = ParallelConfig()
task_queue = TaskQueue()
task_worker = TaskWorker(task_queue)
parallel_runner = ParallelTaskRunner(task_queue, parallel_config)

# ---------------------------------------------------------------------------
# Per-solution queue factory — for cross-team task routing
# ---------------------------------------------------------------------------
_queue_registry: dict = {}
_queue_registry_lock = threading.Lock()


def get_task_queue(solution_name: str) -> TaskQueue:
    """
    Return (or lazily create) a TaskQueue scoped to a specific solution.
    The active solution continues to use the module-level `task_queue` singleton.
    Other solutions get their own instances, lazily created and cached.
    Thread-safe: uses a Lock to guard the registry.
    """
    with _queue_registry_lock:
        if solution_name not in _queue_registry:
            _queue_registry[solution_name] = TaskQueue()
        return _queue_registry[solution_name]

---

## Iteration History

**Iter 1** — score 7.0 pass=False  
Feedback: Strong work on log_config.py — JsonFormatter, SAGE_JSON_LOGS toggle, configure_logging(), and top-level promotion of named fields all satisfy criteria 7-13, and there are no f-string logging calls (cr  

**Iter 2** — score 9.5 pass=True  
Feedback:   

