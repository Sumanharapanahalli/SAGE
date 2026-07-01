"""
SAGE[ai] - LLM Gateway (Singleton with Pluggable Backends)
===========================================================

Supports three providers:
  1. "gemini"  - Gemini CLI (no API keys, uses browser OAuth)
  2. "local"   - llama-cpp-python (offline, GPU-direct)
  3. "claude"  - Anthropic API (requires ANTHROPIC_API_KEY env var)

Thread-locked: only ONE inference at a time (GPU safety + QMS compliance).
"""

from __future__ import annotations

import threading
import subprocess
import logging
import random
import time
import os
import yaml
from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any

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

def _init_langfuse(cfg: dict[str, Any]) -> None:
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
            "not set — observability disabled."
        )
        return
    try:
        from langfuse import Langfuse
        _langfuse_client = Langfuse(public_key=pub_key, secret_key=sec_key, host=host)
        logging.getLogger("LLMGateway").info("Langfuse observability active (host: %s)", host)
    except ImportError:
        logging.getLogger("LLMGateway").warning(
            "langfuse package not installed — observability disabled. "
            "Install with: pip install langfuse"
        )

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config", "config.yaml"
)


def _load_config() -> dict[str, Any]:
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
_MODEL_LIMITS: dict[str, dict[str, int]] = {
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
    def generate(self, prompt: str, system_prompt: str) -> str:
        pass

    @abstractmethod
    def provider_name(self) -> str:
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

    def __init__(self, config: dict[str, Any]) -> None:
        self.logger = logging.getLogger("GeminiCLI")
        self.model = config.get("gemini_model", "gemini-3.5-flash")
        self.timeout = config.get("gemini_timeout", config.get("timeout", 120))
        self.gemini_path = self._find_gemini()
        self.logger.info("Gemini CLI provider ready (model: %s, path: %s)", self.model, self.gemini_path)

    def _find_gemini(self) -> str | None:
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

        self.logger.warning("Gemini CLI not found. Install with: npm install -g @google/gemini-cli")
        return None

    def provider_name(self) -> str:
        return "GeminiCLI (" + self.model + ")"

    def generate(self, prompt: str, system_prompt: str) -> str:
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

            self.logger.debug("Calling Gemini CLI (prompt via stdin)...")
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
                self.logger.error("Gemini CLI error (rc=%d): %s", result.returncode, err)
                return "Error from Gemini CLI: " + err

            output = result.stdout.strip()
            # Filter out non-content lines (hook registry messages, etc.)
            lines = output.split('\n')
            filtered = [l for l in lines if not l.startswith("Loaded cached") and not l.startswith("Hook registry")]
            output = '\n'.join(filtered).strip()

            return output if output else "Error: Gemini CLI returned empty output."

        except subprocess.TimeoutExpired:
            self.logger.error("Gemini CLI timed out after %ds", self.timeout)
            return "Error: Gemini CLI timed out."
        except FileNotFoundError:
            self.logger.critical("Gemini CLI not found at: %s", self.gemini_path)
            return "Error: Gemini CLI not installed or not on PATH."
        except Exception as e:
            self.logger.error("Gemini CLI call failed: %s", e)
            return "Error: " + str(e)


# ---------------------------------------------------------------------------
# Provider 2: Local Llama (GGUF, GPU-direct)
# ---------------------------------------------------------------------------
class LocalLlamaProvider(LLMProvider):
    """
    Loads GGUF model directly into Python process memory via llama-cpp-python.
    Zero network calls. Maximum VRAM efficiency.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.logger = logging.getLogger("LocalLlama")
        self._model = None

        try:
            from llama_cpp import Llama
        except ImportError:
            self.logger.critical("llama-cpp-python not installed.")
            return

        model_path = config.get("model_path", "")
        if not model_path or not os.path.exists(model_path):
            self.logger.error("Model file not found: %s", model_path)
            return

        self.logger.info("Loading GGUF model: %s", model_path)
        try:
            self._model = Llama(
                model_path=model_path,
                n_gpu_layers=-1,
                n_ctx=config.get("max_tokens", 2048),
                verbose=False,
            )
            self.logger.info("Local model loaded.")
        except Exception as e:
            self.logger.critical("Failed to load model: %s", e)

    def provider_name(self) -> str:
        return "LocalLlama (GGUF)"

    def generate(self, prompt: str, system_prompt: str) -> str:
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

    def __init__(self, config: dict[str, Any]) -> None:
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
        self.logger.info("Claude Code CLI provider ready (model: %s, path: %s)", self.model, self.claude_path)

    def _find_claude(self) -> str | None:
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
        self.logger.warning("Claude Code CLI not found at known paths.")
        return None

    def provider_name(self) -> str:
        return f"ClaudeCodeCLI ({self.model})"

    def generate(self, prompt: str, system_prompt: str) -> str:
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
            self.logger.debug("Calling Claude Code CLI via stdin...")
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
                self.logger.error("Claude Code CLI error (rc=%d): %s", result.returncode, err)
                return "Error from Claude Code CLI: " + err
            output = result.stdout.strip()
            return output if output else "Error: Claude Code CLI returned empty output."
        except subprocess.TimeoutExpired:
            return "Error: Claude Code CLI timed out."
        except FileNotFoundError:
            return "Error: Claude Code CLI not installed or not on PATH."
        except Exception as e:
            self.logger.error("Claude Code CLI call failed: %s", e)
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

    def __init__(self, config: dict[str, Any]) -> None:
        self.logger = logging.getLogger("ClaudeAPI")
        self.model = config.get("claude_model", "claude-sonnet-4-5")
        self.timeout = config.get("timeout", 120)
        self._client = None

        api_key = os.environ.get("ANTHROPIC_API_KEY", config.get("anthropic_api_key", ""))
        if not api_key:
            self.logger.error("ANTHROPIC_API_KEY not set. Claude provider unavailable.")
            return

        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key)
            self.logger.info("Claude API provider ready (model: %s)", self.model)
        except ImportError:
            self.logger.critical("anthropic SDK not installed. Run: pip install anthropic")

    def provider_name(self) -> str:
        return f"Claude API ({self.model})"

    def generate(self, prompt: str, system_prompt: str) -> str:
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
            self.logger.error("Claude API call failed: %s", e)
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

    def __init__(self, config: dict[str, Any]) -> None:
        self.logger = logging.getLogger("OllamaProvider")
        self.model   = config.get("ollama_model", "llama3.2")
        self.host    = config.get("ollama_host", "http://localhost:11434")
        self.timeout = config.get("timeout", 120)
        self.logger.info("Ollama provider ready (model: %s, host: %s)", self.model, self.host)

    def provider_name(self) -> str:
        return f"Ollama ({self.model})"

    def generate(self, prompt: str, system_prompt: str) -> str:
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
            self.logger.error("Ollama connection failed (is `ollama serve` running?): %s", e)
            return f"Error: Cannot reach Ollama at {self.host}. Run: ollama serve"
        except Exception as e:
            self.logger.error("Ollama generate failed: %s", e)
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

    def __init__(self, config: dict[str, Any]) -> None:
        self.logger  = logging.getLogger("GenericCLI")
        self.path    = config.get("generic_cli_path", "")
        self.args    = config.get("generic_cli_args", ["-p", "{prompt}"])
        self.model   = config.get("generic_cli_model", "generic")
        self.timeout = config.get("timeout", 120)

        if not self.path:
            self.logger.error("generic_cli_path not set in config.yaml")
        else:
            self.logger.info("Generic CLI provider: %s (model: %s)", self.path, self.model)

    def provider_name(self) -> str:
        return f"GenericCLI ({self.model})"

    def generate(self, prompt: str, system_prompt: str) -> str:
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
                self.logger.error("Generic CLI error (rc=%d): %s", result.returncode, err)
                return f"Error from {self.model}: {err}"
            output = result.stdout.strip()
            return output if output else f"Error: {self.model} returned empty output."
        except subprocess.TimeoutExpired:
            return f"Error: {self.model} CLI timed out."
        except FileNotFoundError:
            return f"Error: CLI not found at {self.path}"
        except Exception as e:
            self.logger.error("Generic CLI failed: %s", e)
            return f"Error: {e}"


# ===========================================================================
# Circuit Breaker (per-provider, lightweight, thread-safe)
# ===========================================================================
class CircuitBreaker:
    """Lightweight per-provider circuit breaker.

    Protects the gateway from hammering a provider that is failing. State
    machine (transitions are logged at WARNING):

        CLOSED    -> normal operation. Each consecutive failure increments a
                     counter; reaching ``failure_threshold`` trips to OPEN.
        OPEN      -> calls are rejected immediately (fail-fast) WITHOUT touching
                     the provider. After ``reset_timeout`` seconds the next
                     attempt is admitted as a SINGLE probe (transition to
                     HALF_OPEN).
        HALF_OPEN -> exactly ONE probe call is allowed through at a time.
                     Success closes the circuit (CLOSED); failure re-opens it
                     (OPEN) for another ``reset_timeout`` cooldown window.

    Defaults match the spec: 3 consecutive failures -> open for 60 seconds.
    The provider interface is untouched — this wraps the gateway's *call*, not
    the provider.

    Time is read through the injectable ``clock`` callable (default
    ``time.time``) so tests can advance the cooldown window deterministically
    without sleeping. All state is guarded by an internal ``threading.Lock``.
    """

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

    def __init__(self, name: str, failure_threshold: int = 3, reset_timeout: float = 60.0,
                 logger: logging.Logger | None = None, clock: Any = None) -> None:
        self.name = name
        self.failure_threshold = max(1, int(failure_threshold))
        self.reset_timeout = float(reset_timeout)
        self.logger = logger or logging.getLogger("CircuitBreaker")
        self._clock = clock or time.time
        self._state = self.CLOSED
        self._consecutive_failures = 0
        self._opened_at = 0.0
        # One-shot guard: True while a single HALF_OPEN probe is outstanding.
        self._half_open_in_flight = False
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def _set_state(self, new_state: str) -> None:
        """Set state and log the transition. Caller must hold ``self._lock``."""
        old = self._state
        if old != new_state:
            self._state = new_state
            self.logger.warning(
                "Circuit breaker '%s': %s -> %s", self.name, old, new_state
            )

    def allow_request(self) -> bool:
        """Atomically decide admission and reserve the HALF_OPEN probe slot."""
        with self._lock:
            if self._state == self.OPEN:
                if (self._clock() - self._opened_at) >= self.reset_timeout:
                    self._set_state(self.HALF_OPEN)
                    self._half_open_in_flight = True  # reserve the one probe slot
                    return True
                return False
            if self._state == self.HALF_OPEN:
                if self._half_open_in_flight:
                    return False
                self._half_open_in_flight = True
                return True
            # CLOSED — allow through.
            return True

    def record_success(self) -> None:
        """Register a successful call: reset failures and close the circuit."""
        with self._lock:
            self._consecutive_failures = 0
            self._half_open_in_flight = False
            if self._state != self.CLOSED:
                self._set_state(self.CLOSED)

    def record_failure(self) -> None:
        """Register a failed call: count it and trip the circuit if needed."""
        with self._lock:
            self._half_open_in_flight = False
            if self._state == self.HALF_OPEN:
                # Probe failed — re-open and restart the cooldown.
                self._opened_at = self._clock()
                self._consecutive_failures = self.failure_threshold
                self._set_state(self.OPEN)
                return
            self._consecutive_failures += 1
            if (
                self._state == self.CLOSED
                and self._consecutive_failures >= self.failure_threshold
            ):
                self._opened_at = self._clock()
                self._set_state(self.OPEN)

    def status(self) -> dict[str, Any]:
        with self._lock:
            remaining = 0.0
            if self._state == self.OPEN:
                remaining = max(0.0, self.reset_timeout - (self._clock() - self._opened_at))
            return {
                "name": self.name,
                "state": self._state,
                "consecutive_failures": self._consecutive_failures,
                "half_open_in_flight": self._half_open_in_flight,
                "reset_in_s": round(remaining, 1),
            }


# ===========================================================================
# Fallback error
# ===========================================================================
class LLMProviderError(Exception):
    """Raised when every provider in a fallback chain has failed.

    Carries the per-provider failures so callers can inspect them, and renders
    a message that names every failed provider (and its error) for logging.
    """

    def __init__(self, failures: list[tuple[str, str]]) -> None:
        # failures: iterable of (provider_name, error_message) tuples
        self.failures = list(failures)
        providers = ", ".join(name for name, _ in self.failures) or "<none>"
        details = "; ".join(f"{name}: {err}" for name, err in self.failures)
        message = f"All LLM providers failed [{providers}]"
        if details:
            message += f" — {details}"
        super().__init__(message)


# ===========================================================================
# Multi-LLM Provider Pool
# ===========================================================================


class ProviderPool:
    """Registry of multiple LLM providers for parallel generation."""

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}
        self._default: str | None = None
        self._lock = threading.Lock()

    def register(self, name: str, provider: LLMProvider) -> None:
        with self._lock:
            self._providers[name] = provider
            if self._default is None:
                self._default = name

    def get(self, name: str) -> LLMProvider | None:
        return self._providers.get(name)

    def get_default(self) -> LLMProvider | None:
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

    def status(self) -> dict[str, Any]:
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
) -> dict[str, Any]:
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
            logger.warning("Provider '%s' failed: %s", name, exc)
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

# Provider types the runtime can switch to (matches the branches in
# proposal_executor._execute_llm_switch). This is the canonical "what can I
# switch to" list — distinct from ProviderPool.list_providers(), which returns
# the providers currently *registered* for parallel multi-critic generation.
SWITCHABLE_PROVIDERS: list[str] = ["gemini", "claude-code", "ollama", "local", "claude"]


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

    _instance: LLMGateway | None = None
    _lock = threading.Lock()   # singleton creation lock only

    # Provider-aware concurrency limits
    PROVIDER_CONCURRENCY: dict[str, int] = {
        "local": 1,         # Single GPU — must serialise
        "generic-cli": 1,   # Unknown CLI — conservative
        "ollama": 2,        # Ollama HTTP — moderate concurrency
        "gemini": 4,        # Cloud API — server-side concurrency
        "claude": 4,        # Cloud API
        "claude-code": 2,   # CLI tool — moderate
    }

    def __new__(cls) -> LLMGateway:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self.logger = logging.getLogger("LLMGateway")
        self.provider: LLMProvider | None = None
        self.provider_pool = ProviderPool()
        self._usage: dict[str, Any] = {
            "calls": 0,
            "calls_today": 0,
            "estimated_tokens": 0,
            "errors": 0,
            "started_at": time.time(),
            "day_started_at": time.time(),  # resets at UTC midnight
        }
        self._routing_stats: dict[str, int] = {"low": 0, "medium": 0, "high": 0}

        config = _load_config()
        llm_cfg = config.get("llm", {})

        # Initialise optional observability
        _init_langfuse(config)

        backend = llm_cfg.get("provider", "claude-code")
        self.logger.info("Selected LLM provider: %s", backend)

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
            self.logger.error("Unknown provider '%s'. Defaulting to claude-code.", backend)
            self.provider = ClaudeCodeCLIProvider(llm_cfg)

        # ── Provider-aware inference semaphore ──────────────────────────
        # Replaces the old single threading.Lock with a semaphore whose
        # concurrency limit matches the provider's capability.
        _concurrency = self.PROVIDER_CONCURRENCY.get(backend, 1)
        self._inference_semaphore = threading.Semaphore(_concurrency)
        self.logger.info(
            "LLM Gateway active: %s (concurrency=%d)",
            self.provider.provider_name(), _concurrency,
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

        # ── Resilience: per-provider circuit breaker ─────────────────────
        # After N consecutive failures on a provider, "open" the circuit so
        # calls fail fast for a cooldown window instead of repeatedly hitting
        # a dead/over-quota backend. Spec defaults: 3 failures -> open 60s.
        # Configurable via llm.circuit_breaker; set "enabled: false" to disable.
        _cb_cfg = llm_cfg.get("circuit_breaker", {}) if isinstance(llm_cfg, dict) else {}
        self._cb_enabled = bool(_cb_cfg.get("enabled", True))
        self._cb_failure_threshold = int(_cb_cfg.get("failure_threshold", 3))
        self._cb_reset_timeout = float(_cb_cfg.get("reset_timeout", 60.0))
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._cb_registry_lock = threading.Lock()

    # Substrings that mark a *retryable* failure (vs a permanent one like
    # "not configured" / "not installed", which must NOT be retried).
    _TRANSIENT_ERROR_MARKERS: tuple[str, ...] = (
        "timed out", "timeout", "rate limit", "429", "500", "502", "503", "504",
        "temporarily", "unavailable", "connection", "reset by peer", "overloaded",
        "empty output",
    )

    def _is_transient_error(self, result: object) -> bool:
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

    def _generate_with_retry(self, prompt: str, system_prompt: str) -> str:
        """Call the provider, retrying transient failures with backoff.

        Retries on a raised exception OR a returned transient-error string, up to
        self._retry_max extra attempts. A successful or permanently-failed result
        is returned immediately (so non-retryable errors fail fast). The final
        exception is re-raised so the caller's existing handling still applies.
        """
        for attempt in range(self._retry_max + 1):
            try:
                result = self.provider.generate(prompt, system_prompt)  # type: ignore[union-attr]
            except Exception as e:  # noqa: BLE001 — provider may raise anything
                if attempt < self._retry_max:
                    delay = self._retry_delay(attempt)
                    self.logger.warning("provider raised (%s); retry %d/%d in %.2fs",
                                        e, attempt + 1, self._retry_max, delay)
                    time.sleep(delay)
                    continue
                raise
            if self._is_transient_error(result) and attempt < self._retry_max:
                delay = self._retry_delay(attempt)
                self.logger.warning("transient provider error (%r); retry %d/%d in %.2fs",
                                    (result or "")[:80], attempt + 1, self._retry_max, delay)
                time.sleep(delay)
                continue
            return result
        return result  # pragma: no cover — loop always returns or raises first

    def _is_failure_result(self, result: object) -> bool:
        """True if a provider result counts as a circuit-breaker *failure*.

        Any error result (raised exceptions are handled separately) is a
        failure, regardless of whether it is transient or permanent: a
        permanently-misconfigured provider should also trip the breaker so we
        stop calling it. A None / empty / "Error..." string is a failure.
        """
        if result is None:
            return True
        if not isinstance(result, str):
            return False
        s = result.strip()
        return s == "" or s.lower().startswith("error")

    def _get_circuit_breaker(self, provider_name: str) -> CircuitBreaker:
        """Return (creating if needed) the breaker for this provider name."""
        breaker = self._circuit_breakers.get(provider_name)
        if breaker is None:
            with self._cb_registry_lock:
                breaker = self._circuit_breakers.get(provider_name)
                if breaker is None:
                    breaker = CircuitBreaker(
                        name=provider_name,
                        failure_threshold=self._cb_failure_threshold,
                        reset_timeout=self._cb_reset_timeout,
                        logger=self.logger,
                    )
                    self._circuit_breakers[provider_name] = breaker
        return breaker

    def _circuit_open_message(self, provider_name: str) -> str:
        return (
            f"Error: Circuit breaker OPEN for provider '{provider_name}' — "
            f"provider failed {self._cb_failure_threshold} times in a row; "
            f"calls are blocked for up to {int(self._cb_reset_timeout)}s. "
            f"Retry shortly."
        )

    def generate_stream(self, prompt: str, system_prompt: str = "You are a helpful AI assistant.",
                        trace_name: str = "llm_stream", metadata: dict[str, Any] | None = None,
                        request_id: str = "") -> Iterator[str]:
        """
        Streaming variant of generate().  Yields str chunks as they become available.

        For providers that support native streaming (Claude API) tokens are
        yielded as received.  For CLI-based providers the full response is
        fetched, then word-chunked to simulate streaming — callers get
        progressive output either way.

        The thread lock is held for the duration of the stream (same single-
        lane guarantee as generate()).

        Args:
            request_id: Optional per-request correlation id. Defaults to the
                        current request context (set by RequestIDMiddleware).

        Yields:
            str  — incremental text chunks, never empty strings.
        """
        if self.provider is None:
            yield "Error: No LLM provider configured."
            return

        if not request_id:
            try:
                from src.core.request_context import get_request_id
                request_id = get_request_id()
            except Exception:
                request_id = ""

        with self._inference_semaphore:
            self.logger.debug("Streaming generation started. Provider: %s", self.provider.provider_name())
            start = time.time()

            # ── Circuit breaker: fail fast if this provider's circuit is open ──
            provider_name = self.provider.provider_name()
            breaker = self._get_circuit_breaker(provider_name) if self._cb_enabled else None
            if breaker is not None and not breaker.allow_request():
                self.logger.warning(
                    "Circuit OPEN for '%s' — rejecting stream without calling provider.",
                    provider_name,
                    extra={"event": "circuit_breaker", "provider": provider_name, "status": "open_rejected"},
                )
                self._usage["errors"] += 1
                yield self._circuit_open_message(provider_name)
                return

            result = ""
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
                    self.logger.error("Claude API stream failed: %s", e)
                    if breaker is not None:
                        breaker.record_failure()
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

            # ── Circuit breaker: record outcome ──
            if breaker is not None:
                if self._is_failure_result(result):
                    breaker.record_failure()
                else:
                    breaker.record_success()

            elapsed = time.time() - start
            self.logger.info(
                "Streaming generation done in %.2fs", elapsed,
                extra={
                    "event": "generation_stream",
                    "provider": provider_name,
                    "duration_ms": int(elapsed * 1000),
                    "status": "completed",
                    "request_id": request_id,
                },
            )
            self._maybe_reset_daily()
            self._usage["calls"] += 1
            self._usage["calls_today"] += 1
            self._usage["estimated_tokens"] += (len(prompt) + len(system_prompt) + len(result)) // 4

    def generate(self, prompt: str, system_prompt: str = "You are a helpful AI assistant.",
                 trace_name: str = "llm_generate", metadata: dict[str, Any] | None = None,
                 trace_id: str = "", agent_name: str = "", request_id: str = "") -> str:
        """Thread-safe generation. Only ONE call at a time.

        Args:
            prompt:        User/task prompt.
            system_prompt: Role/instruction context.
            trace_name:    Langfuse trace name (e.g. agent class + method).
            metadata:      Extra key-value pairs attached to the Langfuse trace.
            trace_id:      Optional trace ID for cost tracking correlation.
            agent_name:    Agent role name for per-agent budget enforcement.
            request_id:    Optional per-request correlation id. Defaults to the
                           current request context (set by RequestIDMiddleware).
        """
        if self.provider is None:
            return "Error: No LLM provider configured."

        # Resolve request_id from the active request context when not supplied.
        if not request_id:
            try:
                from src.core.request_context import get_request_id
                request_id = get_request_id()
            except Exception:
                request_id = ""

        # Fold request_id into the observability metadata for correlation.
        metadata = dict(metadata or {})
        if request_id:
            metadata.setdefault("request_id", request_id)

        start = time.time()
        self.logger.debug("Acquiring inference lock...")

        with self._inference_semaphore:
            self.logger.debug("Semaphore acquired. Provider: %s", self.provider.provider_name())

            # ----------------------------------------------------------------
            # T1-002: PII detection and data residency check
            # ----------------------------------------------------------------
            config = _load_config()
            try:
                from src.core import pii_filter
                scrubbed_prompt, detected_entities = pii_filter.scrub_text(prompt, config)
                if detected_entities:
                    self.logger.warning(
                        "PII detected and redacted: %s", detected_entities
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
                    self.logger.warning("Agent budget check failed (non-fatal): %s", _bexc)

            # ----------------------------------------------------------------
            # Circuit breaker: if this provider's circuit is OPEN, fail fast
            # WITHOUT calling the provider (and without burning a retry budget).
            # allow_request() atomically admits at most one HALF_OPEN probe.
            # ----------------------------------------------------------------
            provider_name = self.provider.provider_name()
            breaker = self._get_circuit_breaker(provider_name) if self._cb_enabled else None
            if breaker is not None and not breaker.allow_request():
                self.logger.warning(
                    "Circuit OPEN for '%s' — rejecting call without contacting provider.",
                    provider_name,
                    extra={"event": "circuit_breaker", "provider": provider_name, "status": "open_rejected"},
                )
                self._usage["errors"] += 1
                return self._circuit_open_message(provider_name)

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
                    self.logger.debug("Langfuse trace init failed (non-fatal): %s", lf_err)

            # --- OpenTelemetry span (no-op if SDK not installed) ---
            from src.core.tracing import trace_llm_call as _otel_trace

            with _otel_trace(
                provider=self.provider.provider_name(),
                model=getattr(self.provider, "model", "unknown"),
                prompt_length=len(prompt),
                system_prompt_length=len(system_prompt),
                trace_name=trace_name,
                trace_id=trace_id or request_id,
            ) as _otel_span:
                try:
                    if request_id:
                        try:
                            _otel_span.set_attribute("llm.request_id", request_id)
                        except Exception:
                            pass
                    try:
                        result = self._generate_with_retry(prompt, system_prompt)
                    except Exception:
                        # A raised provider failure trips the breaker too.
                        if breaker is not None:
                            breaker.record_failure()
                        raise

                    # --- Circuit breaker: record success / failure outcome ---
                    if breaker is not None:
                        if self._is_failure_result(result):
                            breaker.record_failure()
                        else:
                            breaker.record_success()

                    elapsed = time.time() - start
                    self.logger.info(
                        "Generation done in %.2fs", elapsed,
                        extra={
                            "event": "generation",
                            "provider": self.provider.provider_name(),
                            "duration_ms": int(elapsed * 1000),
                            "status": "completed",
                            "request_id": request_id,
                        },
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
                        _ct.record_usage(_tenant, _solution, _model, input_tokens, output_tokens, trace_id or request_id)
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
                            self.logger.debug("Langfuse generation.end failed (non-fatal): %s", lf_err)

                    return result
                except ValueError:
                    # Re-raise budget/PII errors as-is (not wrapped as "Error: ...")
                    raise
                except Exception as e:
                    self.logger.error(
                        "Generation failed: %s", e,
                        extra={
                            "event": "generation",
                            "provider": self.provider.provider_name(),
                            "status": "error",
                            "request_id": request_id,
                        },
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
                          trace_name: str = "llm_generate", metadata: dict[str, Any] | None = None,
                          trace_id: str = "", request_id: str = "") -> str:
        """
        Route to a task-specific model if task_routing is configured.

        Looks up llm.task_routing.routes[task_type] in config.yaml.
        Falls back to the default provider when routing is disabled or no
        route is defined for this task_type.

        Format: "provider/model" (e.g. "ollama/llama3.2") or just "model"
        (e.g. "claude-sonnet-4-6", reuses current provider type).

        request_id is propagated to the underlying generate() call (defaults
        to the active request context, same as generate()).
        """
        config = _load_config()
        routing_cfg = config.get("llm", {}).get("task_routing", {})

        if not routing_cfg.get("enabled", False):
            return self.generate(prompt, system_prompt, trace_name, metadata, trace_id, request_id=request_id)

        routes: dict[str, str] = routing_cfg.get("routes", {})
        route_value: str = routes.get(task_type, "")

        if not route_value:
            return self.generate(prompt, system_prompt, trace_name, metadata, trace_id, request_id=request_id)

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
            return self.generate(prompt, system_prompt, trace_name, metadata, trace_id, request_id=request_id)

        # Different provider requested — build a temporary provider instance
        self.logger.info(
            "Task routing: task_type=%s → provider=%s model=%s",
            task_type, routed_provider, routed_model,
        )
        llm_cfg = config.get("llm", {}).copy()
        try:
            if routed_provider == "ollama":
                llm_cfg["ollama_model"] = routed_model
                tmp_provider: LLMProvider = OllamaProvider(llm_cfg)
            elif routed_provider in ("claude", "claude-code"):
                llm_cfg["claude_model"] = routed_model
                tmp_provider = ClaudeCodeCLIProvider(llm_cfg)
            elif routed_provider == "gemini":
                llm_cfg["gemini_model"] = routed_model
                tmp_provider = GeminiCLIProvider(llm_cfg)
            else:
                self.logger.warning(
                    "Task routing: unknown provider '%s' — using default", routed_provider
                )
                return self.generate(prompt, system_prompt, trace_name, metadata, trace_id, request_id=request_id)

            # Run with the temporary provider (still under the main lock via generate())
            saved_provider = self.provider
            self.provider = tmp_provider
            try:
                result = self.generate(prompt, system_prompt, trace_name, metadata, trace_id, request_id=request_id)
            finally:
                self.provider = saved_provider
            return result

        except Exception as exc:
            self.logger.warning(
                "Task routing provider init failed (%s) — falling back to default: %s",
                routed_provider, exc,
            )
            return self.generate(prompt, system_prompt, trace_name, metadata, trace_id, request_id=request_id)

    def generate_multi(
        self,
        prompt: str,
        system_prompt: str,
        *,
        strategy: str = "voting",
        provider_names: list[str] | None = None,
    ) -> dict[str, Any]:
        """Delegate to generate_parallel using this gateway's provider_pool."""
        return generate_parallel(
            self.provider_pool, prompt, system_prompt,
            strategy=strategy, provider_names=provider_names,
        )

    def generate_with_fallback(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful AI assistant.",
        *,
        provider_names: list[str] | None = None,
    ) -> str:
        """Try registered providers in order; return the first success.

        Falls back to the next provider whenever one *raises*. Honours the
        single-lane inference guarantee (held across the whole chain). If every
        provider fails, raises LLMProviderError naming all failed providers.

        Args:
            prompt:         User/task prompt.
            system_prompt:  Role/instruction context.
            provider_names: Explicit ordered list of pool provider keys to try.
                            Defaults to every provider registered in the pool.

        Raises:
            LLMProviderError: when no provider yields a successful response.
        """
        names = provider_names or self.provider_pool.list_providers()
        if not names:
            raise LLMProviderError([("<none>", "no providers configured")])

        failures: list[tuple[str, str]] = []
        with self._inference_semaphore:
            for name in names:
                provider = self.provider_pool.get(name)
                if provider is None:
                    failures.append((name, "provider not registered"))
                    continue
                try:
                    self.logger.debug("Fallback attempt via provider '%s'", name)
                    return provider.generate(prompt, system_prompt)
                except Exception as exc:  # noqa: BLE001 — provider may raise anything
                    self.logger.warning("Provider '%s' failed: %s", name, exc)
                    failures.append((name, str(exc)))

        raise LLMProviderError(failures)

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
            self.logger.info("Daily request counter reset (new UTC day).")

    # ── Public accessors ────────────────────────────────────────────────
    def get_provider_name(self) -> str:
        if self.provider:
            return self.provider.provider_name()
        return "None"

    def get_usage(self) -> dict[str, Any]:
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

    def get_model_info(self) -> dict[str, Any]:
        """Return the active model's name and known quota limits."""
        model = "unknown"
        if self.provider is not None:
            if hasattr(self.provider, "model"):
                model = self.provider.model      # type: ignore[attr-defined]  # GeminiCLIProvider / ClaudeAPIProvider
            elif hasattr(self.provider, "_model") and self.provider._model is not None:  # type: ignore[attr-defined]  # LocalLlamaProvider
                model = "local"
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
