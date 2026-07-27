"""Tests for src.interface.routes.voice_data audio validation + processing.

Previously untested (SAGE self-improvement loop, issue #23).
"""

import base64

import pytest
from pydantic import ValidationError

from src.interface.routes.voice_data import AudioDataPayload, _process_audio


def _payload(content: bytes = b"x" * 4096, fmt: str = "wav"):
    # Content must be plausibly sized for duration*sample_rate (model validator).
    return AudioDataPayload(
        format=fmt,
        sample_rate=16_000,
        channels=1,
        duration_seconds=0.1,
        encoding="base64",
        content=base64.b64encode(content).decode(),
    )


def test_process_audio_reports_decoded_size():
    raw = b"x" * 4096
    result = _process_audio(_payload(raw))
    assert result.decoded_size_bytes == len(raw)
    assert result.format == "wav"
    assert result.sample_rate == 16_000
    # Stub transcription — no transcript yet, but a processing note is present.
    assert result.transcript is None
    assert result.processing_note


def test_unsupported_format_is_rejected():
    with pytest.raises(ValidationError):
        _payload(fmt="xyz")


def test_sample_rate_out_of_range_rejected():
    with pytest.raises(ValidationError):
        AudioDataPayload(
            format="wav",
            sample_rate=1,  # below 8 kHz minimum
            channels=1,
            duration_seconds=1.0,
            encoding="base64",
            content=base64.b64encode(b"x").decode(),
        )
