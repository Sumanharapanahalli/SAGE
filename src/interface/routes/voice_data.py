"""POST /voice_data — request models, response models, and route handler.

Accepts a JSON body containing a structured audio_data object, validates it,
and returns a structured processing result.  Actual transcription/ML inference
is out-of-scope for this layer; the handler delegates to a thin processing
function that can be swapped for a real provider (Whisper, Google STT, etc.).
"""
from __future__ import annotations

import base64
import binascii
import logging
import time
import uuid
from enum import Enum
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Voice Data"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SUPPORTED_FORMATS = {"wav", "mp3", "flac", "ogg", "webm", "m4a"}
_MIN_SAMPLE_RATE = 8_000   # 8 kHz — telephony minimum
_MAX_SAMPLE_RATE = 96_000  # 96 kHz — hi-fi maximum
_MAX_DURATION_SECONDS = 300.0  # 5-minute clip limit
_MAX_CONTENT_BYTES = 50 * 1024 * 1024  # 50 MB decoded limit
_MAX_METADATA_KEYS = 32


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AudioEncoding(str, Enum):
    base64 = "base64"
    raw_bytes = "raw_bytes"  # future-proofing; not decoded in this handler


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------

class AudioDataPayload(BaseModel):
    """Structured audio payload embedded inside VoiceDataRequest."""

    format: str = Field(
        ...,
        description=f"Audio container format. Supported: {sorted(_SUPPORTED_FORMATS)}",
        min_length=2,
        max_length=8,
    )
    sample_rate: int = Field(
        ...,
        ge=_MIN_SAMPLE_RATE,
        le=_MAX_SAMPLE_RATE,
        description="Sample rate in Hz (8000–96000).",
    )
    channels: int = Field(
        ...,
        ge=1,
        le=8,
        description="Number of audio channels (1–8).",
    )
    duration_seconds: float = Field(
        ...,
        gt=0.0,
        le=_MAX_DURATION_SECONDS,
        description="Clip duration in seconds (>0, <=300).",
    )
    encoding: AudioEncoding = Field(
        default=AudioEncoding.base64,
        description="How the content field is encoded.",
    )
    content: str = Field(
        ...,
        min_length=4,
        description="Encoded audio bytes (base64 by default).",
    )
    language: Optional[str] = Field(
        default=None,
        max_length=16,
        description="BCP-47 language tag, e.g. 'en-US'. Optional hint for transcription.",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Arbitrary caller metadata attached to the clip.",
    )

    @field_validator("format")
    @classmethod
    def format_must_be_supported(cls, v: str) -> str:
        normalised = v.lower().lstrip(".")
        if normalised not in _SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported audio format '{v}'. "
                f"Supported: {sorted(_SUPPORTED_FORMATS)}"
            )
        return normalised

    @field_validator("content")
    @classmethod
    def content_must_be_valid_base64(cls, v: str) -> str:
        try:
            decoded = base64.b64decode(v, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(f"'content' is not valid base64: {exc}") from exc
        if len(decoded) > _MAX_CONTENT_BYTES:
            raise ValueError(
                f"Decoded audio content exceeds the {_MAX_CONTENT_BYTES // (1024 * 1024)} MB limit."
            )
        return v

    @field_validator("metadata")
    @classmethod
    def metadata_size_limit(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if v is not None and len(v) > _MAX_METADATA_KEYS:
            raise ValueError(
                f"'metadata' exceeds the maximum of {_MAX_METADATA_KEYS} keys."
            )
        return v

    @model_validator(mode="after")
    def duration_consistent_with_sample_rate(self) -> "AudioDataPayload":
        """Rough sanity check: decoded content size should be plausible for the
        stated duration and sample rate (16-bit mono baseline)."""
        decoded_len = len(base64.b64decode(self.content))
        # Minimum expected bytes: 1 channel, 8-bit, at the claimed sample rate
        min_expected = int(self.sample_rate * self.duration_seconds * 1)
        # Allow a generous 50x slack to accommodate compression and multi-channel
        if decoded_len > 0 and decoded_len < min_expected // 50:
            raise ValueError(
                "Decoded content size is implausibly small for the stated "
                f"duration ({self.duration_seconds}s) and sample_rate "
                f"({self.sample_rate} Hz). Got {decoded_len} bytes, "
                f"expected at least {min_expected // 50}."
            )
        return self


class VoiceDataRequest(BaseModel):
    """Top-level request envelope."""

    audio_data: AudioDataPayload = Field(
        ...,
        description="Structured audio payload to process.",
    )
    request_id: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Optional caller-supplied correlation ID.",
    )


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class ProcessingResult(BaseModel):
    decoded_size_bytes: int
    format: str
    sample_rate: int
    channels: int
    duration_seconds: float
    language: Optional[str]
    # Placeholder fields — replace with real STT output
    transcript: Optional[str]
    confidence: Optional[float]
    processing_note: str


class VoiceDataResponse(BaseModel):
    request_id: str
    status: str
    result: ProcessingResult
    duration_ms: float


class ErrorDetail(BaseModel):
    request_id: str
    status: str
    error: str
    detail: Optional[str] = None


# ---------------------------------------------------------------------------
# Processing logic (stub — swap for a real STT provider)
# ---------------------------------------------------------------------------

def _process_audio(payload: AudioDataPayload) -> ProcessingResult:
    """Decode and inspect the audio clip.

    In production, replace the stub transcript with a call to Whisper, Google
    Speech-to-Text, AWS Transcribe, or any compatible provider.
    """
    decoded = base64.b64decode(payload.content)
    decoded_size = len(decoded)

    # --- stub transcription -------------------------------------------
    # Real implementation would pass `decoded` to an STT engine.
    transcript: Optional[str] = None
    confidence: Optional[float] = None
    processing_note = (
        "Audio received and validated. "
        "Connect a Speech-to-Text provider to enable transcription."
    )
    # ------------------------------------------------------------------

    return ProcessingResult(
        decoded_size_bytes=decoded_size,
        format=payload.format,
        sample_rate=payload.sample_rate,
        channels=payload.channels,
        duration_seconds=payload.duration_seconds,
        language=payload.language,
        transcript=transcript,
        confidence=confidence,
        processing_note=processing_note,
    )


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post(
    "/voice_data",
    response_model=VoiceDataResponse,
    status_code=status.HTTP_200_OK,
    summary="Receive and process a structured audio clip.",
    responses={
        400: {"model": ErrorDetail, "description": "Validation or processing error"},
        422: {"description": "Request body schema violation"},
        500: {"model": ErrorDetail, "description": "Unexpected server error"},
    },
)
async def voice_data(
    body: VoiceDataRequest,
    request: Request,
) -> JSONResponse:
    """Receive a base64-encoded audio clip, validate it, and process it.

    **Request body**::

        {
          "audio_data": {
            "format": "wav",
            "sample_rate": 16000,
            "channels": 1,
            "duration_seconds": 3.5,
            "encoding": "base64",
            "content": "<base64-encoded audio bytes>",
            "language": "en-US",
            "metadata": {}
          },
          "request_id": "optional-caller-id"
        }

    Validation rules:
    - ``format`` must be one of: wav, mp3, flac, ogg, webm, m4a
    - ``sample_rate`` must be 8000–96000 Hz
    - ``channels`` must be 1–8
    - ``duration_seconds`` must be > 0 and <= 300
    - ``content`` must be valid base64 and decode to <= 50 MB
    - ``metadata`` must have <= 32 top-level keys
    """
    request_id = (body.request_id or "").strip() or str(uuid.uuid4())
    client_ip = getattr(request.client, "host", "unknown") if request.client else "unknown"
    logger.info(
        "voice_data received",
        extra={
            "request_id": request_id,
            "client_ip": client_ip,
            "format": body.audio_data.format,
            "duration_s": body.audio_data.duration_seconds,
        },
    )

    t0 = time.perf_counter()

    try:
        result = _process_audio(body.audio_data)
    except ValueError as exc:
        duration_ms = round((time.perf_counter() - t0) * 1000, 3)
        logger.warning(
            "voice_data processing error: %s",
            exc,
            extra={"request_id": request_id, "duration_ms": duration_ms},
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorDetail(
                request_id=request_id,
                status="error",
                error="ProcessingError",
                detail=str(exc),
            ).model_dump(),
        )
    except Exception:  # noqa: BLE001
        duration_ms = round((time.perf_counter() - t0) * 1000, 3)
        logger.exception(
            "voice_data unexpected error",
            extra={"request_id": request_id, "duration_ms": duration_ms},
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorDetail(
                request_id=request_id,
                status="error",
                error="InternalServerError",
                detail="An unexpected error occurred. Check server logs.",
            ).model_dump(),
        )

    duration_ms = round((time.perf_counter() - t0) * 1000, 3)
    logger.info(
        "voice_data processed",
        extra={"request_id": request_id, "duration_ms": duration_ms},
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=VoiceDataResponse(
            request_id=request_id,
            status="success",
            result=result,
            duration_ms=duration_ms,
        ).model_dump(),
    )
