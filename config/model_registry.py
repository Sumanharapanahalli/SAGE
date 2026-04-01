"""Model registry loader.

Reads config/models.yaml, substitutes env-var placeholders, and validates
that every referenced model file/directory exists on disk.  Raises a
clear RuntimeError at startup if any path is missing — fail fast.

Usage::

    from config.model_registry import registry

    # Get config for a specific model:
    ner_cfg = registry.get("ner")
    print(ner_cfg.path)   # Path object, guaranteed to exist

    # Get ordered pipeline for a document type:
    steps = registry.pipeline_for("invoice")
    # -> [ModelConfig(name='document_classifier'), ModelConfig(name='ner'), ...]
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_REGISTRY_PATH = Path(__file__).parent / "models.yaml"
_ENV_VAR_RE = re.compile(r"\$\{([^}]+)\}")


def _expand_env_vars(value: str) -> str:
    """Replace ${VAR_NAME} tokens with their environment variable values."""
    def _replace(match: re.Match) -> str:  # type: ignore[type-arg]
        var = match.group(1)
        resolved = os.environ.get(var, "")
        if not resolved:
            raise EnvironmentError(
                f"Model registry references undefined environment variable: ${{{var}}}. "
                f"Set {var} in your .env file."
            )
        return resolved

    return _ENV_VAR_RE.sub(_replace, value)


@dataclass(frozen=True)
class ModelConfig:
    """Parsed, validated configuration for a single model."""

    name: str
    description: str
    type: str
    path: Path
    version: str
    document_types: list[str] | str
    raw: dict[str, Any] = field(repr=False)

    @property
    def handles_all_types(self) -> bool:
        return self.document_types == "all"

    def handles(self, document_type: str) -> bool:
        if self.handles_all_types:
            return True
        return document_type in self.document_types


class ModelRegistry:
    """In-memory model registry loaded once at startup."""

    def __init__(self, config_path: Path = _REGISTRY_PATH) -> None:
        self._models: dict[str, ModelConfig] = {}
        self._pipelines: dict[str, list[str]] = {}
        self._load(config_path)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def get(self, name: str) -> ModelConfig:
        """Return config for *name*, raising KeyError if not found."""
        try:
            return self._models[name]
        except KeyError:
            available = ", ".join(sorted(self._models))
            raise KeyError(
                f"No model named {name!r} in registry. Available: {available}"
            ) from None

    def all_models(self) -> list[ModelConfig]:
        """Return all registered model configs."""
        return list(self._models.values())

    def pipeline_for(self, document_type: str) -> list[ModelConfig]:
        """Return ordered list of ModelConfigs for *document_type*.

        Falls back to the 'default' pipeline if the type is not explicitly
        configured.  Raises ValueError if neither exists.
        """
        pipeline_keys = self._pipelines.get(
            document_type, self._pipelines.get("default")
        )
        if pipeline_keys is None:
            raise ValueError(
                f"No pipeline defined for document type {document_type!r} and "
                "no 'default' pipeline configured in config/models.yaml."
            )
        return [self._models[k] for k in pipeline_keys]

    # ------------------------------------------------------------------ #
    # Internal loading + validation
    # ------------------------------------------------------------------ #

    def _load(self, config_path: Path) -> None:
        if not config_path.exists():
            raise FileNotFoundError(
                f"Model registry config not found: {config_path}. "
                "Ensure config/models.yaml exists in the project root."
            )

        with config_path.open() as fh:
            data: dict[str, Any] = yaml.safe_load(fh)

        models_raw: dict[str, Any] = data.get("models", {})
        if not models_raw:
            raise ValueError("config/models.yaml has no 'models' section.")

        missing_paths: list[str] = []

        for name, cfg in models_raw.items():
            # Expand ${ENV_VAR} in the path field.
            raw_path: str = cfg.get("path", "")
            try:
                resolved_path_str = _expand_env_vars(raw_path)
            except EnvironmentError as exc:
                raise RuntimeError(
                    f"Model registry startup failure — {name}: {exc}"
                ) from exc

            model_path = Path(resolved_path_str)

            # Resolve relative paths against project root (parent of config/).
            if not model_path.is_absolute():
                project_root = config_path.parent.parent
                model_path = (project_root / model_path).resolve()

            # Collect missing paths instead of raising immediately so we can
            # report ALL missing models in one error.
            if not model_path.exists():
                missing_paths.append(f"  [{name}] {model_path}")

            self._models[name] = ModelConfig(
                name=name,
                description=cfg.get("description", ""),
                type=cfg.get("type", "unknown"),
                path=model_path,
                version=str(cfg.get("version", "unknown")),
                document_types=cfg.get("document_types", []),
                raw=cfg,
            )

        if missing_paths:
            paths_str = "\n".join(missing_paths)
            raise RuntimeError(
                f"Model registry startup failure — the following model paths do not exist:\n"
                f"{paths_str}\n"
                "Download or mount the required model files, then restart the application."
            )

        # Load pipeline routing.
        self._pipelines = {
            doc_type: steps
            for doc_type, steps in data.get("pipelines", {}).items()
        }
        # Validate pipeline references.
        for doc_type, steps in self._pipelines.items():
            for step in steps:
                if step not in self._models:
                    raise ValueError(
                        f"Pipeline for {doc_type!r} references unknown model {step!r}. "
                        "Check config/models.yaml."
                    )


# Module-level singleton — validated at import time.
registry: ModelRegistry = ModelRegistry()
