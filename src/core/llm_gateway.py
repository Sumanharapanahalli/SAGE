"""
SAGE[ai] - LLM Gateway (Singleton with Pluggable Backends)
===========================================================

Supports three providers:
  1. "gemini"  - Gemini CLI (no API keys, uses browser OAuth)
  2. "local"   - llama-cpp-python (offline, GPU-direct)
  3. "claude"  - Anthropic API (requires ANTHROPIC_API_KEY env var)

Thread-locked: only ONE inference at a time (GPU safety + QMS compliance).
"""

import threading
import subprocess
import logging
import time
import os
import yaml
from abc import ABC, abstractmethod

# ---------------------------------------------------------------------------
# Optional Langfuse observability — graceful no-op when not configured
# ---------------------------------------------------------------------------
_langfuse_client = None

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


def _load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return yaml.safe_load(f)
    # Fallback defaults when config not found (e.g. imported from another project)
    return {
        "llm": {
            "provider": "gemini",
            "gemini_model": "gemini-2.5-flash",
            "timeout": 120,
        }
    }


# ---------------------------------------------------------------------------
# Known model limits (free tier defaults — override via config if on paid plan)
# daily_requests = 0  means unlimited (local / self-hosted)
# ---------------------------------------------------------------------------
_MODEL_LIMITS: dict = {
    # Gemini (Google free tier)
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
        self.model = config.get("gemini_model", "gemini-2.5-flash")
        self.timeout = config.get("timeout", 120)
        self.gemini_path = self._find_gemini()
        self.logger.info("Gemini CLI provider ready (model: %s, path: %s)", self.model, self.gemini_path)

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

        self.logger.warning("Gemini CLI not found. Install with: npm install -g @google/gemini-cli")
        return None

    def provider_name(self):
        return "GeminiCLI (" + self.model + ")"

    def generate(self, prompt, system_prompt):
        if not self.gemini_path:
            return "Error: Gemini CLI not found. Install with: npm install -g @google/gemini-cli"

        combined = (
            "SYSTEM INSTRUCTION (follow strictly):\n"
            + system_prompt + "\n\n"
            + "USER REQUEST:\n"
            + prompt + "\n"
        )

        # Build environment with required project settings
        env = os.environ.copy()
        if "GOOGLE_CLOUD_PROJECT" not in env:
            env["GOOGLE_CLOUD_PROJECT"] = "db-dev-bms-apps"
        if "GOOGLE_CLOUD_PROJECT_ID" not in env:
            env["GOOGLE_CLOUD_PROJECT_ID"] = env["GOOGLE_CLOUD_PROJECT"]
        # Ensure npm global bin is on PATH
        npm_bin = os.path.join(env.get("APPDATA", ""), "npm")
        if npm_bin not in env.get("PATH", ""):
            env["PATH"] = env.get("PATH", "") + os.pathsep + npm_bin

        try:
            # Build command: use -p flag for non-interactive/headless mode
            if self.gemini_path == "__npx__":
                cmd = ["npx", "-y", "@google/gemini-cli", "-p", combined]
            else:
                cmd = [self.gemini_path, "-p", combined]

            self.logger.debug("Calling Gemini CLI with -p flag...")
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

    def __init__(self, config):
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
        # Accept explicit path from config or UI, otherwise auto-detect
        explicit_path = config.get("claude_path", "")
        if explicit_path and os.path.exists(explicit_path):
            self.claude_path = explicit_path
        else:
            self.claude_path = self._find_claude()
        self.logger.info("Claude Code CLI provider ready (model: %s, path: %s)", self.model, self.claude_path)

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
        self.logger.warning("Claude Code CLI not found at known paths.")
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
            cmd = [self.claude_path, "--model", self.model, "-p", combined]
            self.logger.debug("Calling Claude Code CLI with -p flag...")
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

    def __init__(self, config):
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
            self.logger.error("Claude API call failed: %s", e)
            return f"Error: {e}"


# ===========================================================================
# LLM Gateway (Singleton + Thread Lock)
# ===========================================================================
class LLMGateway:
    """
    Thread-safe singleton that routes all LLM calls through a single lock.

    Usage:
        from src.core.llm_gateway import llm_gateway
        response = llm_gateway.generate("Analyze this log...")
    """

    _instance = None
    _lock = threading.Lock()

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
        self._usage = {
            "calls": 0,
            "calls_today": 0,
            "estimated_tokens": 0,
            "errors": 0,
            "started_at": time.time(),
            "day_started_at": time.time(),  # resets at UTC midnight
        }

        config = _load_config()
        llm_cfg = config.get("llm", {})

        # Initialise optional observability
        _init_langfuse(config)

        backend = llm_cfg.get("provider", "gemini")
        self.logger.info("Selected LLM provider: %s", backend)

        if backend == "gemini":
            self.provider = GeminiCLIProvider(llm_cfg)
        elif backend == "local":
            self.provider = LocalLlamaProvider(llm_cfg)
        elif backend == "claude-code":
            self.provider = ClaudeCodeCLIProvider(llm_cfg)
        elif backend == "claude":
            self.provider = ClaudeAPIProvider(llm_cfg)
        else:
            self.logger.error("Unknown provider '%s'. Defaulting to gemini.", backend)
            self.provider = GeminiCLIProvider(llm_cfg)

        self.logger.info("LLM Gateway active: %s", self.provider.provider_name())

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

        with self._lock:
            self.logger.debug("Streaming generation started. Provider: %s", self.provider.provider_name())
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
                    self.logger.error("Claude API stream failed: %s", e)
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
            self.logger.info("Streaming generation done in %.2fs", elapsed)
            self._maybe_reset_daily()
            self._usage["calls"] += 1
            self._usage["calls_today"] += 1
            self._usage["estimated_tokens"] += (len(prompt) + len(system_prompt) + len(result)) // 4

    def generate(self, prompt, system_prompt="You are a helpful AI assistant.",
                 trace_name: str = "llm_generate", metadata: dict = None):
        """Thread-safe generation. Only ONE call at a time.

        Args:
            prompt:       User/task prompt.
            system_prompt: Role/instruction context.
            trace_name:   Langfuse trace name (e.g. agent class + method).
            metadata:     Extra key-value pairs attached to the Langfuse trace.
        """
        if self.provider is None:
            return "Error: No LLM provider configured."

        start = time.time()
        self.logger.debug("Acquiring inference lock...")

        with self._lock:
            self.logger.debug("Lock acquired. Provider: %s", self.provider.provider_name())

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

            try:
                result = self.provider.generate(prompt, system_prompt)
                elapsed = time.time() - start
                self.logger.info("Generation done in %.2fs", elapsed)
                # Roll daily counter over at UTC midnight
                self._maybe_reset_daily()
                # Track usage — estimate tokens as (input + output chars) / 4
                self._usage["calls"] += 1
                self._usage["calls_today"] += 1
                self._usage["estimated_tokens"] += (len(prompt) + len(system_prompt) + len(result)) // 4

                # Close Langfuse generation span with output
                if _lf_generation is not None:
                    try:
                        _lf_generation.end(
                            output=result,
                            usage={"total_tokens": (len(prompt) + len(system_prompt) + len(result)) // 4},
                        )
                    except Exception as lf_err:
                        self.logger.debug("Langfuse generation.end failed (non-fatal): %s", lf_err)

                return result
            except Exception as e:
                self.logger.error("Generation failed: %s", e)
                self._usage["errors"] += 1
                if _lf_generation is not None:
                    try:
                        _lf_generation.end(output=f"ERROR: {e}", level="ERROR")
                    except Exception:
                        pass
                return "Error: " + str(e)

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
