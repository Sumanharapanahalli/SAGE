"""Pydantic Settings — single source of truth for all environment variables.

Fail-fast design: the application raises a descriptive ValidationError at
import time if any required variable is absent or malformed.  Import this
module early in your entrypoint so misconfiguration is caught before any
service connection is attempted.

Usage::

    from config.settings import settings
    print(settings.DATABASE_URL)
"""
from __future__ import annotations

import re
import sys
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageBackend(str, Enum):
    s3 = "s3"
    local = "local"
    gcs = "gcs"


class OcrEngine(str, Enum):
    tesseract = "tesseract"
    easyocr = "easyocr"
    paddleocr = "paddleocr"


class LogLevel(str, Enum):
    debug = "DEBUG"
    info = "INFO"
    warning = "WARNING"
    error = "ERROR"
    critical = "CRITICAL"


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Database
    # ------------------------------------------------------------------ #
    DATABASE_URL: str = Field(
        ...,  # required — no default
        description="PostgreSQL async DSN: postgresql+asyncpg://user:pw@host/db",
    )

    # ------------------------------------------------------------------ #
    # Cache / Queue
    # ------------------------------------------------------------------ #
    REDIS_URL: str = Field(
        ...,
        description="Redis DSN: redis://[:password@]host[:port][/db]",
    )

    # ------------------------------------------------------------------ #
    # Storage
    # ------------------------------------------------------------------ #
    STORAGE_BACKEND: StorageBackend = Field(
        StorageBackend.local,
        description="Storage driver: s3 | local | gcs",
    )
    S3_BUCKET: Optional[str] = Field(
        None,
        description="S3 bucket name — required when STORAGE_BACKEND=s3",
    )
    STORAGE_LOCAL_ROOT: Path = Field(
        Path("/tmp/docproc"),
        description="Root directory for local storage driver",
    )

    # ------------------------------------------------------------------ #
    # Workers
    # ------------------------------------------------------------------ #
    WORKER_CONCURRENCY: int = Field(
        4,
        ge=1,
        le=32,
        description="Concurrent processing workers (1–32)",
    )

    # ------------------------------------------------------------------ #
    # OCR
    # ------------------------------------------------------------------ #
    OCR_ENGINE: OcrEngine = Field(
        OcrEngine.tesseract,
        description="OCR engine: tesseract | easyocr | paddleocr",
    )

    # ------------------------------------------------------------------ #
    # ML Model Paths
    # ------------------------------------------------------------------ #
    NER_MODEL_PATH: Path = Field(
        ...,
        description="Path to NER model directory or file",
    )
    TABLE_MODEL_PATH: Path = Field(
        ...,
        description="Path to table detection model weights (.pt)",
    )
    CLASSIFIER_MODEL_PATH: Path = Field(
        ...,
        description="Path to document classifier model weights (.pt)",
    )

    # ------------------------------------------------------------------ #
    # Logging
    # ------------------------------------------------------------------ #
    LOG_LEVEL: LogLevel = Field(
        LogLevel.info,
        description="Logging verbosity: DEBUG | INFO | WARNING | ERROR | CRITICAL",
    )

    # ------------------------------------------------------------------ #
    # Security
    # ------------------------------------------------------------------ #
    API_KEY_HASH: str = Field(
        ...,
        description="SHA-256 hex digest of the API master key",
    )

    # ------------------------------------------------------------------ #
    # Cross-field validators
    # ------------------------------------------------------------------ #

    @field_validator("API_KEY_HASH")
    @classmethod
    def _validate_api_key_hash(cls, v: str) -> str:
        if not re.fullmatch(r"[0-9a-f]{64}", v):
            raise ValueError(
                "API_KEY_HASH must be a 64-character lowercase hex string "
                "(SHA-256 digest). "
                "Generate one with: "
                "python -c \"import hashlib; print(hashlib.sha256(b'KEY').hexdigest())\""
            )
        return v

    @model_validator(mode="after")
    def _validate_s3_bucket_when_s3(self) -> "Settings":
        if self.STORAGE_BACKEND == StorageBackend.s3 and not self.S3_BUCKET:
            raise ValueError(
                "S3_BUCKET is required when STORAGE_BACKEND=s3. "
                "Set S3_BUCKET in your .env file."
            )
        return self

    @model_validator(mode="after")
    def _validate_database_url_scheme(self) -> "Settings":
        url = self.DATABASE_URL
        if not url.startswith(("postgresql", "sqlite")):
            raise ValueError(
                f"DATABASE_URL must use a postgresql or sqlite scheme, got: {url!r}"
            )
        return self


def _load_settings() -> Settings:
    """Load and return validated settings, printing a human-friendly error on failure."""
    try:
        return Settings()  # type: ignore[call-arg]
    except Exception as exc:  # pydantic ValidationError or missing file
        print(
            "\n[FATAL] Application cannot start — configuration error:\n",
            file=sys.stderr,
        )
        print(str(exc), file=sys.stderr)
        print(
            "\nFix the above issues in your .env file (see .env.example).\n",
            file=sys.stderr,
        )
        sys.exit(1)


# Module-level singleton — validated at import time.
settings: Settings = _load_settings()
