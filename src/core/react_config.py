"""
SAGE Framework -- ReAct Pattern Configuration Loader
====================================================
Loads config/react_pattern.yaml, performs environment-variable substitution,
and validates the result against config/react_pattern_schema.json.

Usage:
    from src.core.react_config import react_config

    provider = react_config.llm["provider"]
    max_iter = react_config.react_loop["max_iterations"]
    cfg_dict = react_config.as_dict()

Validation runs once at import time. ConfigurationError is raised with a
human-readable message listing every violation -- no silent bad defaults.
"""

import json
import logging
import os
import re
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_CONFIG_DIR = os.path.join(_PROJECT_ROOT, "config")
_PATTERN_YAML = os.path.join(_CONFIG_DIR, "react_pattern.yaml")
_SCHEMA_JSON = os.path.join(_CONFIG_DIR, "react_pattern_schema.json")

# Regex matching ${VAR_NAME:-default_value} or ${VAR_NAME}
_ENV_RE = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?}")


class ConfigurationError(RuntimeError):
    """Raised when react_pattern.yaml fails schema validation."""


def _substitute_env(text: str) -> str:
    """Replace ${VAR:-default} placeholders with environment values."""

    def _replace(m: re.Match) -> str:
        var, default = m.group(1), m.group(2) or ""
        return os.environ.get(var, default)

    return _ENV_RE.sub(_replace, text)


def _load_yaml_with_env(path: str) -> dict:
    """Read a YAML file, substitute env vars, and parse."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"ReAct config not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        raw = fh.read()
    substituted = _substitute_env(raw)
    return yaml.safe_load(substituted)


def _load_schema(path: str) -> dict:
    """Load the JSON Schema used for validation."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"ReAct config schema not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _coerce_hitl_enabled(cfg: dict) -> None:
    """Convert hitl.enabled string 'true'/'false' to bool after env substitution."""
    try:
        val = cfg["react_loop"]["hitl"]["enabled"]
        if isinstance(val, str):
            cfg["react_loop"]["hitl"]["enabled"] = val.lower() == "true"
    except (KeyError, TypeError):
        pass


def _validate(cfg: dict, schema: dict) -> None:
    """
    Validate *cfg* against *schema*.

    Uses jsonschema when available; falls back to a lightweight structural
    check so the framework still starts even without the optional dependency.
    """
    try:
        import jsonschema  # optional dependency

        validator = jsonschema.Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(cfg), key=lambda e: list(e.path))
        if errors:
            messages = []
            for err in errors:
                path = " -> ".join(str(p) for p in err.absolute_path) or "(root)"
                messages.append(f"  [{path}] {err.message}")
            raise ConfigurationError(
                "react_pattern.yaml failed schema validation:\n" + "\n".join(messages)
            )
    except ImportError:
        # jsonschema not installed -- run lightweight structural checks
        _validate_lightweight(cfg)


def _validate_lightweight(cfg: dict) -> None:
    """Minimal structural validation when jsonschema is unavailable."""
    errors = []

    top_keys = {"llm", "tool_registry", "system_prompt", "react_loop"}
    missing = top_keys - cfg.keys()
    if missing:
        errors.append(f"Missing top-level keys: {sorted(missing)}")

    llm = cfg.get("llm", {})
    valid_providers = {"gemini", "claude-code", "ollama", "local", "generic-cli", "claude"}
    if llm.get("provider") not in valid_providers:
        errors.append(
            f"llm.provider '{llm.get('provider')}' is not in {sorted(valid_providers)}"
        )
    temp = llm.get("temperature")
    if not isinstance(temp, (int, float)) or not (0.0 <= float(temp) <= 1.0):
        errors.append(f"llm.temperature must be a float in [0.0, 1.0], got: {temp!r}")
    max_tok = llm.get("max_tokens")
    if not isinstance(max_tok, int) or not (256 <= max_tok <= 32768):
        errors.append(f"llm.max_tokens must be an int in [256, 32768], got: {max_tok!r}")

    loop = cfg.get("react_loop", {})
    max_iter = loop.get("max_iterations")
    if not isinstance(max_iter, int) or max_iter < 1:
        errors.append(f"react_loop.max_iterations must be a positive int, got: {max_iter!r}")

    prompt = cfg.get("system_prompt", {})
    if prompt.get("mode") not in {"file", "inline"}:
        errors.append(f"system_prompt.mode must be 'file' or 'inline', got: {prompt.get('mode')!r}")

    if errors:
        raise ConfigurationError(
            "react_pattern.yaml failed structural validation:\n"
            + "\n".join(f"  {e}" for e in errors)
        )


class ReactConfig:
    """
    Validated, env-substituted view of react_pattern.yaml.

    Attributes mirror the top-level YAML keys: llm, tool_registry,
    system_prompt, react_loop. All values are plain Python dicts/lists.
    """

    def __init__(self, yaml_path: str = _PATTERN_YAML, schema_path: str = _SCHEMA_JSON) -> None:
        self._yaml_path = yaml_path
        self._schema_path = schema_path
        self._data: dict[str, Any] = {}
        self._load_and_validate()

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    @property
    def llm(self) -> dict:
        return self._data["llm"]

    @property
    def tool_registry(self) -> dict:
        return self._data["tool_registry"]

    @property
    def system_prompt(self) -> dict:
        return self._data["system_prompt"]

    @property
    def react_loop(self) -> dict:
        return self._data["react_loop"]

    def as_dict(self) -> dict:
        """Return a shallow copy of the full config dict."""
        return dict(self._data)

    def reload(self) -> None:
        """Re-read and re-validate the config file (e.g. after a hot-reload)."""
        self._load_and_validate()
        logger.info("react_config: reloaded from %s", self._yaml_path)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_and_validate(self) -> None:
        cfg = _load_yaml_with_env(self._yaml_path)
        _coerce_hitl_enabled(cfg)
        schema = _load_schema(self._schema_path)
        _validate(cfg, schema)
        self._data = cfg
        logger.info(
            "react_config: loaded and validated (provider=%s, max_iterations=%d, hitl=%s)",
            cfg["llm"]["provider"],
            cfg["react_loop"]["max_iterations"],
            cfg["react_loop"]["hitl"]["enabled"],
        )


# Module-level singleton -- validated at import time.
# Any misconfiguration raises ConfigurationError immediately,
# preventing the server from starting with a broken ReAct config.
try:
    react_config = ReactConfig()
except (FileNotFoundError, ConfigurationError) as _exc:
    logger.error("react_config: FATAL -- %s", _exc)
    raise
