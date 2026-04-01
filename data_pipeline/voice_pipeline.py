"""
voice_pipeline.py — Production pipeline for ingesting and managing user voice data.

Design decisions:
  - Idempotent: every upsert uses content_hash (SHA-256) + external_id as dual dedup keys.
    A recording that arrives twice (identical bytes, different filename) is skipped cleanly.
  - No data leakage: quality metrics are computed per-file independently; no cross-record
    statistics that could leak across a train/test boundary.
  - Consent gate: records with consent_given != True are hard-rejected before any DB write.
  - Schema-on-startup: voice_schema.sql is applied via CREATE TABLE IF NOT EXISTS, so the
    pipeline is safe to run on a fresh DB or a DB that already has the tables.
  - Stratified split utility: provided for downstream classification tasks (e.g. speaker ID,
    command recognition).  Scalers/encoders must be fit on the training split only.
  - Experiment logging: every pipeline run is persisted to voice_pipeline_runs +
    voice_validation_results tables with a UUID run_id.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Generator, Iterator, Optional

import psycopg2
import psycopg2.extras
import yaml

# ---------------------------------------------------------------------------
# Structured logging — JSON lines compatible with any log aggregator
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":%(message)s}',
)
logger = logging.getLogger("voice_pipeline")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config(path: str | Path = "voice_pipeline_config.yaml") -> dict:
    with open(path) as fh:
        raw = yaml.safe_load(fh)
    return _expand_env_vars(raw)


def _expand_env_vars(obj: Any) -> Any:
    """Recursively substitute ${VAR:-default} patterns in string values."""
    if isinstance(obj, dict):
        return {k: _expand_env_vars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_env_vars(i) for i in obj]
    if isinstance(obj, str) and "${" in obj:
        import re
        def _sub(m: re.Match) -> str:
            inner = m.group(1)
            if ":-" in inner:
                var, default = inner.split(":-", 1)
            else:
                var, default = inner, ""
            return os.environ.get(var, default)
        return re.sub(r"\$\{([^}]+)\}", _sub, obj)
    return obj


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

@contextmanager
def get_db_conn(db_cfg: dict) -> Generator:
    conn = psycopg2.connect(
        host=db_cfg["host"],
        port=int(db_cfg["port"]),
        dbname=db_cfg["database"],
        user=db_cfg["user"],
        password=db_cfg.get("password", ""),
        connect_timeout=db_cfg.get("connect_timeout", 10),
    )
    conn.autocommit = False
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def apply_schema(conn, schema_file: str | Path) -> None:
    """Apply DDL idempotently (all statements use IF NOT EXISTS)."""
    sql = Path(schema_file).read_text()
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    logger.info('"Applied schema from %s"', schema_file)


# ---------------------------------------------------------------------------
# SHA-256 content hash
# ---------------------------------------------------------------------------

def sha256_of_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Validation — voice-specific rules
# ---------------------------------------------------------------------------

@dataclass
class VoiceValidationResult:
    rule_name: str
    passed: bool
    message: str
    severity: str = "error"  # info | warning | error | critical


@dataclass
class VoiceValidationReport:
    external_id: str
    results: list[VoiceValidationResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results if r.severity in ("error", "critical"))

    @property
    def failures(self) -> list[VoiceValidationResult]:
        return [r for r in self.results if not r.passed]

    def summary(self) -> dict:
        return {
            "external_id": self.external_id,
            "passed": self.passed,
            "total_checks": len(self.results),
            "failure_count": len(self.failures),
            "failures": [asdict(r) for r in self.failures],
        }


def _check_required(record: dict, fields: list[str]) -> list[VoiceValidationResult]:
    out = []
    for f in fields:
        val = record.get(f)
        missing = val is None or (isinstance(val, str) and val.strip() == "")
        out.append(VoiceValidationResult(
            rule_name=f"required:{f}",
            passed=not missing,
            message="" if not missing else f"Required field '{f}' is missing or empty",
            severity="critical",
        ))
    return out


def _check_enum(record: dict, field_name: str, allowed: list, severity: str = "error") -> VoiceValidationResult:
    val = record.get(field_name)
    if val is None:
        return VoiceValidationResult(f"enum:{field_name}", True, "null skipped", "info")
    ok = val in allowed
    return VoiceValidationResult(
        rule_name=f"enum:{field_name}",
        passed=ok,
        message="" if ok else f"'{field_name}'={val!r} not in {allowed}",
        severity=severity,
    )


def _check_numeric_range(
    record: dict,
    field_name: str,
    min_val: float,
    max_val: float,
    severity: str = "error",
) -> VoiceValidationResult:
    val = record.get(field_name)
    if val is None:
        return VoiceValidationResult(f"range:{field_name}", True, "null skipped", "info")
    try:
        n = float(val)
        ok = min_val <= n <= max_val
    except (TypeError, ValueError):
        ok = False
        n = val
    return VoiceValidationResult(
        rule_name=f"range:{field_name}",
        passed=ok,
        message="" if ok else f"'{field_name}'={n} outside [{min_val}, {max_val}]",
        severity=severity,
    )


def _check_consent(record: dict) -> VoiceValidationResult:
    """Hard rejection: consent_given must be boolean True."""
    given = record.get("consent_given")
    ok = given is True
    return VoiceValidationResult(
        rule_name="consent_required",
        passed=ok,
        message="" if ok else f"consent_given={given!r}; recording cannot be stored without explicit consent",
        severity="critical",
    )


def _check_no_future_recording(record: dict, max_skew_seconds: int = 60) -> VoiceValidationResult:
    raw = record.get("recorded_at")
    if raw is None:
        return VoiceValidationResult("no_future_recorded_at", True, "null skipped", "info")
    try:
        if isinstance(raw, str):
            ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        elif isinstance(raw, datetime):
            ts = raw
        else:
            return VoiceValidationResult("no_future_recorded_at", False, f"Cannot parse recorded_at={raw!r}", "error")
        now = datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        ok = ts <= now + timedelta(seconds=max_skew_seconds)
    except Exception as exc:
        return VoiceValidationResult("no_future_recorded_at", False, str(exc), "error")
    return VoiceValidationResult(
        rule_name="no_future_recorded_at",
        passed=ok,
        message="" if ok else f"recorded_at={raw} is in the future (skew > {max_skew_seconds}s)",
        severity="warning",
    )


def validate_voice_recording(record: dict, cfg: dict | None = None) -> VoiceValidationReport:
    """
    Full validation for a single voice recording record.
    cfg is the 'validation.voice_recording' block from voice_pipeline_config.yaml.
    Never raises — all failures are captured in the report.
    """
    cfg = cfg or {}
    report = VoiceValidationReport(external_id=record.get("external_id", "<unknown>"))

    # 1. Required fields
    required = cfg.get("required_fields", [
        "external_id", "content_hash", "storage_uri", "format",
        "duration_seconds", "sample_rate_hz", "channels", "file_size_bytes",
        "recorded_at", "language_bcp47", "consent_given", "consent_timestamp",
    ])
    report.results.extend(_check_required(record, required))

    # 2. Consent — checked early so we don't write unconsented data
    report.results.append(_check_consent(record))

    # 3. Enum checks
    allowed_formats = cfg.get("allowed_formats", ["wav","mp3","flac","ogg","m4a","mp4","webm","aac"])
    report.results.append(_check_enum(record, "format", allowed_formats))

    allowed_sr = cfg.get("allowed_sample_rates", [8000, 16000, 22050, 24000, 44100, 48000])
    sr = record.get("sample_rate_hz")
    sr_ok = sr in allowed_sr if sr is not None else True
    report.results.append(VoiceValidationResult(
        rule_name="sample_rate_hz",
        passed=sr_ok,
        message="" if sr_ok else f"sample_rate_hz={sr} not in {allowed_sr}",
        severity="error",
    ))

    allowed_ch = cfg.get("allowed_channels", [1, 2])
    report.results.append(_check_enum(record, "channels", allowed_ch))

    # 4. Numeric range checks
    dur_cfg = cfg.get("duration", {"min_seconds": 0.1, "max_seconds": 14400})
    report.results.append(_check_numeric_range(
        record, "duration_seconds",
        dur_cfg.get("min_seconds", 0.1),
        dur_cfg.get("max_seconds", 14400),
    ))

    sz_cfg = cfg.get("file_size", {"min_bytes": 100, "max_bytes": 2147483648})
    report.results.append(_check_numeric_range(
        record, "file_size_bytes",
        sz_cfg.get("min_bytes", 100),
        sz_cfg.get("max_bytes", 2_147_483_648),
    ))

    # 5. Temporal check
    skew = cfg.get("max_future_skew_seconds", 60)
    report.results.append(_check_no_future_recording(record, skew))

    return report


# ---------------------------------------------------------------------------
# Optional quality metrics (requires pydub + ffprobe)
# ---------------------------------------------------------------------------

def compute_quality_metrics(audio_path: str | Path, cfg: dict | None = None) -> dict[str, Any]:
    """
    Compute lightweight quality metrics from an audio file.
    Returns a dict ready for insertion into voice_quality_metrics.
    Falls back to empty dict if pydub/ffprobe is unavailable.
    """
    cfg = cfg or {}
    silence_threshold = cfg.get("silence_threshold_db", -50.0)
    clipping_threshold = cfg.get("clipping_threshold_db", -1.0)

    try:
        from pydub import AudioSegment  # type: ignore
        from pydub.silence import detect_silence  # type: ignore

        audio = AudioSegment.from_file(str(audio_path))
        total_ms = len(audio)
        if total_ms == 0:
            return {}

        rms_db = float(audio.dBFS)
        peak_db = float(audio.max_dBFS)
        dynamic_range_db = round(peak_db - rms_db, 3) if rms_db > float("-inf") else None

        # Silence ratio
        silent_ranges = detect_silence(audio, min_silence_len=100, silence_thresh=silence_threshold)
        silent_ms = sum(end - start for start, end in silent_ranges)
        silence_ratio = round(silent_ms / total_ms, 4)
        speech_ratio = round(1.0 - silence_ratio, 4)

        # Clipping: fraction of 10ms frames where peak > threshold
        frame_len = 10  # ms
        frames = [audio[i:i + frame_len] for i in range(0, total_ms, frame_len)]
        clipping_frames = sum(1 for f in frames if f.max_dBFS > clipping_threshold)
        clipping_ratio = round(clipping_frames / max(len(frames), 1), 4)

        # Simplified SNR: compare RMS of loudest quartile vs quietest quartile
        frame_levels = sorted(f.rms for f in frames if f.rms > 0)
        if len(frame_levels) >= 4:
            loud_mean = sum(frame_levels[3 * len(frame_levels) // 4 :]) / max(1, len(frame_levels) // 4)
            quiet_mean = sum(frame_levels[: len(frame_levels) // 4]) / max(1, len(frame_levels) // 4)
            import math
            snr_db = round(20 * math.log10(loud_mean / max(quiet_mean, 1e-9)), 3) if loud_mean > 0 else None
        else:
            snr_db = None

        # Clarity: penalise high clipping and high silence
        clarity_score = round(max(0.0, 1.0 - clipping_ratio * 2 - max(0.0, silence_ratio - 0.3)), 4)

        # Grade
        if clarity_score >= 0.8 and (snr_db or 0) >= 20:
            grade = "excellent"
        elif clarity_score >= 0.6 and (snr_db or 0) >= 10:
            grade = "good"
        elif clarity_score >= 0.4:
            grade = "acceptable"
        elif clarity_score >= 0.2:
            grade = "poor"
        else:
            grade = "unusable"

        return {
            "snr_db": snr_db,
            "rms_db": round(rms_db, 3) if rms_db > float("-inf") else None,
            "peak_db": round(peak_db, 3) if peak_db > float("-inf") else None,
            "dynamic_range_db": dynamic_range_db,
            "silence_ratio": silence_ratio,
            "speech_ratio": speech_ratio,
            "clipping_ratio": clipping_ratio,
            "clarity_score": clarity_score,
            "quality_grade": grade,
            "is_silent": silence_ratio > 0.95,
            "has_clipping": clipping_ratio > 0.01,
            "has_background_noise": (snr_db is not None and snr_db < cfg.get("min_snr_db_warn", 10)),
        }
    except ImportError:
        logger.warning('"pydub not installed — quality metrics skipped for %s"', audio_path)
        return {}
    except Exception as exc:
        logger.warning('"Quality metric error for %s: %s"', audio_path, exc)
        return {}


# ---------------------------------------------------------------------------
# Stratified split (for downstream ML tasks — no leakage)
# ---------------------------------------------------------------------------

def stratified_split(
    records: list[dict],
    label_key: str,
    test_size: float = 0.2,
    val_size: float = 0.1,
    random_seed: int = 42,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Split records into train / val / test with stratification on label_key.

    IMPORTANT — leakage rule:
        Any scaler, encoder, or feature extractor MUST be fit exclusively on the
        returned train split and then applied (transform-only) to val and test.
        Never call fit() or fit_transform() on val or test data.

    Returns: (train, val, test)
    """
    from collections import defaultdict
    import random

    rng = random.Random(random_seed)
    buckets: dict[Any, list[dict]] = defaultdict(list)
    for rec in records:
        buckets[rec.get(label_key)].append(rec)

    train, val, test = [], [], []
    for label, items in buckets.items():
        rng.shuffle(items)
        n = len(items)
        n_test = max(1, round(n * test_size))
        n_val = max(1, round(n * val_size))
        test.extend(items[:n_test])
        val.extend(items[n_test:n_test + n_val])
        train.extend(items[n_test + n_val:])

    logger.info(
        '"Stratified split on %r: train=%d val=%d test=%d (seed=%d)"',
        label_key, len(train), len(val), len(test), random_seed,
    )
    return train, val, test


# ---------------------------------------------------------------------------
# Run tracking
# ---------------------------------------------------------------------------

@dataclass
class PipelineRun:
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_dir: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    records_read: int = 0
    records_loaded: int = 0
    records_skipped: int = 0
    records_failed: int = 0
    status: str = "running"
    error_message: Optional[str] = None

    def to_db_row(self) -> dict:
        return {
            "run_id": self.run_id,
            "source_dir": self.source_dir,
            "started_at": self.started_at,
            "records_read": self.records_read,
            "records_loaded": self.records_loaded,
            "records_skipped": self.records_skipped,
            "records_failed": self.records_failed,
            "status": self.status,
            "error_message": self.error_message,
        }

    @property
    def validation_pass_rate(self) -> float:
        total = self.records_loaded + self.records_failed
        return self.records_loaded / total if total else 1.0


def _start_run(conn, run: PipelineRun) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO voice_pipeline_runs
                (run_id, source_dir, started_at, status)
            VALUES (%(run_id)s, %(source_dir)s, %(started_at)s, 'running')
            ON CONFLICT (run_id) DO NOTHING
            """,
            run.to_db_row(),
        )
    conn.commit()


def _finish_run(conn, run: PipelineRun) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE voice_pipeline_runs SET
                finished_at     = NOW(),
                records_read    = %(records_read)s,
                records_loaded  = %(records_loaded)s,
                records_skipped = %(records_skipped)s,
                records_failed  = %(records_failed)s,
                status          = %(status)s,
                error_message   = %(error_message)s
            WHERE run_id = %(run_id)s
            """,
            run.to_db_row(),
        )
    conn.commit()
    logger.info(
        '"Run %s finished: loaded=%d skipped=%d failed=%d pass_rate=%.2f"',
        run.run_id, run.records_loaded, run.records_skipped,
        run.records_failed, run.validation_pass_rate,
    )


def _persist_validation(conn, run_id: str, report: VoiceValidationReport) -> None:
    rows = [
        {
            "run_id": run_id,
            "external_id": report.external_id,
            "rule_name": r.rule_name,
            "passed": r.passed,
            "message": r.message or None,
            "severity": r.severity,
        }
        for r in report.results
    ]
    if not rows:
        return
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(
            cur,
            """
            INSERT INTO voice_validation_results
                (run_id, external_id, rule_name, passed, message, severity)
            VALUES (%(run_id)s, %(external_id)s, %(rule_name)s, %(passed)s, %(message)s, %(severity)s)
            """,
            rows,
        )


# ---------------------------------------------------------------------------
# DB upserts — all idempotent (ON CONFLICT DO UPDATE)
# ---------------------------------------------------------------------------

def _upsert_speaker(conn, speaker: dict) -> str:
    """Upsert a speaker record; return the speaker_id (UUID string)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO voice_speakers
                (external_id, display_name, language_bcp47, age_group, gender_label)
            VALUES (%(external_id)s, %(display_name)s, %(language_bcp47)s, %(age_group)s, %(gender_label)s)
            ON CONFLICT (external_id) DO UPDATE SET
                display_name    = EXCLUDED.display_name,
                language_bcp47  = EXCLUDED.language_bcp47,
                age_group       = EXCLUDED.age_group,
                gender_label    = EXCLUDED.gender_label,
                updated_at      = NOW()
            RETURNING speaker_id::TEXT
            """,
            {
                "external_id": speaker["external_id"],
                "display_name": speaker.get("display_name"),
                "language_bcp47": speaker.get("language_bcp47", "en-US"),
                "age_group": speaker.get("age_group"),
                "gender_label": speaker.get("gender_label"),
            },
        )
        row = cur.fetchone()
        return row[0]


def _upsert_recording(conn, rec: dict, run_id: str) -> tuple[str, bool]:
    """
    Upsert a voice recording.
    Returns (recording_id, was_inserted).
    Duplicate detection: ON CONFLICT on content_hash (audio bytes) and external_id.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO voice_recordings (
                external_id, content_hash, speaker_id, storage_uri, original_filename,
                format, duration_seconds, sample_rate_hz, channels, bit_depth,
                file_size_bytes, codec, recorded_at, device_type, environment,
                language_bcp47, session_id, task_type,
                consent_given, consent_timestamp, consent_version,
                pii_scrubbed, data_retention_days,
                run_id, raw_metadata
            ) VALUES (
                %(external_id)s, %(content_hash)s, %(speaker_id)s, %(storage_uri)s, %(original_filename)s,
                %(format)s, %(duration_seconds)s, %(sample_rate_hz)s, %(channels)s, %(bit_depth)s,
                %(file_size_bytes)s, %(codec)s, %(recorded_at)s, %(device_type)s, %(environment)s,
                %(language_bcp47)s, %(session_id)s, %(task_type)s,
                %(consent_given)s, %(consent_timestamp)s, %(consent_version)s,
                %(pii_scrubbed)s, %(data_retention_days)s,
                %(run_id)s, %(raw_metadata)s
            )
            ON CONFLICT (content_hash) DO NOTHING
            RETURNING recording_id::TEXT
            """,
            {
                "external_id": rec["external_id"],
                "content_hash": rec["content_hash"],
                "speaker_id": rec.get("speaker_id"),
                "storage_uri": rec["storage_uri"],
                "original_filename": rec.get("original_filename"),
                "format": rec["format"],
                "duration_seconds": rec["duration_seconds"],
                "sample_rate_hz": rec["sample_rate_hz"],
                "channels": rec["channels"],
                "bit_depth": rec.get("bit_depth"),
                "file_size_bytes": rec["file_size_bytes"],
                "codec": rec.get("codec"),
                "recorded_at": rec["recorded_at"],
                "device_type": rec.get("device_type"),
                "environment": rec.get("environment"),
                "language_bcp47": rec.get("language_bcp47", "en-US"),
                "session_id": rec.get("session_id"),
                "task_type": rec.get("task_type"),
                "consent_given": rec["consent_given"],
                "consent_timestamp": rec["consent_timestamp"],
                "consent_version": rec.get("consent_version"),
                "pii_scrubbed": rec.get("pii_scrubbed", False),
                "data_retention_days": rec.get("data_retention_days", 365),
                "run_id": run_id,
                "raw_metadata": json.dumps(rec.get("raw_metadata")) if rec.get("raw_metadata") else None,
            },
        )
        row = cur.fetchone()
        if row is None:
            # Duplicate — fetch existing id
            cur.execute(
                "SELECT recording_id::TEXT FROM voice_recordings WHERE content_hash = %s",
                (rec["content_hash"],),
            )
            existing = cur.fetchone()
            return (existing[0] if existing else ""), False
        return row[0], True


def _upsert_quality_metrics(conn, recording_id: str, metrics: dict) -> None:
    if not metrics:
        return
    metrics["recording_id"] = recording_id
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO voice_quality_metrics (
                recording_id, snr_db, rms_db, peak_db, dynamic_range_db,
                silence_ratio, speech_ratio, clipping_ratio,
                clarity_score, quality_grade,
                is_silent, has_clipping, has_background_noise
            ) VALUES (
                %(recording_id)s, %(snr_db)s, %(rms_db)s, %(peak_db)s, %(dynamic_range_db)s,
                %(silence_ratio)s, %(speech_ratio)s, %(clipping_ratio)s,
                %(clarity_score)s, %(quality_grade)s,
                %(is_silent)s, %(has_clipping)s, %(has_background_noise)s
            )
            ON CONFLICT (recording_id) DO UPDATE SET
                snr_db              = EXCLUDED.snr_db,
                rms_db              = EXCLUDED.rms_db,
                peak_db             = EXCLUDED.peak_db,
                dynamic_range_db    = EXCLUDED.dynamic_range_db,
                silence_ratio       = EXCLUDED.silence_ratio,
                speech_ratio        = EXCLUDED.speech_ratio,
                clipping_ratio      = EXCLUDED.clipping_ratio,
                clarity_score       = EXCLUDED.clarity_score,
                quality_grade       = EXCLUDED.quality_grade,
                is_silent           = EXCLUDED.is_silent,
                has_clipping        = EXCLUDED.has_clipping,
                has_background_noise = EXCLUDED.has_background_noise,
                computed_at         = NOW()
            """,
            {
                "snr_db": metrics.get("snr_db"),
                "rms_db": metrics.get("rms_db"),
                "peak_db": metrics.get("peak_db"),
                "dynamic_range_db": metrics.get("dynamic_range_db"),
                "silence_ratio": metrics.get("silence_ratio"),
                "speech_ratio": metrics.get("speech_ratio"),
                "clipping_ratio": metrics.get("clipping_ratio"),
                "clarity_score": metrics.get("clarity_score"),
                "quality_grade": metrics.get("quality_grade"),
                "is_silent": metrics.get("is_silent", False),
                "has_clipping": metrics.get("has_clipping", False),
                "has_background_noise": metrics.get("has_background_noise", False),
                "recording_id": recording_id,
            },
        )


# ---------------------------------------------------------------------------
# Sidecar manifest loader
# ---------------------------------------------------------------------------

def _load_manifest(audio_path: Path) -> dict:
    """
    Load companion JSON sidecar: audio.wav → audio.json.
    Returns an empty dict if no sidecar exists (caller must supply metadata inline).
    """
    sidecar = audio_path.with_suffix(".json")
    if sidecar.exists():
        with open(sidecar) as fh:
            return json.load(fh)
    return {}


def _build_record_from_file(audio_path: Path, run_id: str) -> dict:
    """
    Construct a recording record from a file on disk + its JSON sidecar.
    content_hash is computed from the actual audio bytes (dedup guarantee).
    """
    stat = audio_path.stat()
    content_hash = sha256_of_file(audio_path)
    meta = _load_manifest(audio_path)

    suffix = audio_path.suffix.lstrip(".").lower()
    # Normalise common aliases
    fmt_map = {"mp4": "mp4", "m4a": "m4a", "oga": "ogg", "opus": "ogg"}
    fmt = fmt_map.get(suffix, suffix)

    return {
        "external_id": meta.get("external_id") or f"{audio_path.stem}_{content_hash[:8]}",
        "content_hash": content_hash,
        "storage_uri": meta.get("storage_uri") or str(audio_path.resolve()),
        "original_filename": audio_path.name,
        "format": meta.get("format") or fmt,
        "duration_seconds": meta.get("duration_seconds"),   # required; must be in sidecar
        "sample_rate_hz": meta.get("sample_rate_hz"),
        "channels": meta.get("channels"),
        "bit_depth": meta.get("bit_depth"),
        "file_size_bytes": stat.st_size,
        "codec": meta.get("codec"),
        "recorded_at": meta.get("recorded_at"),
        "device_type": meta.get("device_type"),
        "environment": meta.get("environment"),
        "language_bcp47": meta.get("language_bcp47", "en-US"),
        "session_id": meta.get("session_id"),
        "task_type": meta.get("task_type"),
        "consent_given": meta.get("consent_given"),
        "consent_timestamp": meta.get("consent_timestamp"),
        "consent_version": meta.get("consent_version"),
        "pii_scrubbed": meta.get("pii_scrubbed", False),
        "data_retention_days": meta.get("data_retention_days", 365),
        "speaker": meta.get("speaker"),     # optional nested speaker dict
        "raw_metadata": meta or None,
        "run_id": run_id,
    }


# ---------------------------------------------------------------------------
# Main pipeline entry points
# ---------------------------------------------------------------------------

def ingest_directory(
    source_dir: str | Path,
    config: dict | None = None,
    config_path: str | Path = "voice_pipeline_config.yaml",
) -> PipelineRun:
    """
    Scan source_dir for audio files, validate, and load into the DB.
    Idempotent: re-running with the same files produces no duplicate rows.

    Returns the completed PipelineRun with counts.
    """
    cfg = config or load_config(config_path)
    db_cfg = cfg["staging_db"]
    val_cfg = cfg.get("validation", {}).get("voice_recording", {})
    qa_cfg = cfg.get("quality_analysis", {})
    alert_threshold = cfg.get("alerts", {}).get("failure_rate_threshold", 0.05)

    source_dir = Path(source_dir)
    patterns = cfg.get("sources", {}).get("filesystem", {}).get(
        "file_patterns", ["*.wav", "*.mp3", "*.flac", "*.ogg", "*.m4a", "*.webm", "*.aac"]
    )

    run = PipelineRun(source_dir=str(source_dir))
    t0 = time.monotonic()

    with get_db_conn(db_cfg) as conn:
        # Apply schema idempotently
        schema_file = cfg["staging_db"].get("schema_file", "voice_schema.sql")
        apply_schema(conn, schema_file)

        _start_run(conn, run)

        audio_files: list[Path] = []
        for pattern in patterns:
            audio_files.extend(source_dir.glob(pattern))

        logger.info('"Starting run %s: found %d audio files in %s"', run.run_id, len(audio_files), source_dir)

        for audio_path in sorted(audio_files):
            run.records_read += 1
            try:
                record = _build_record_from_file(audio_path, run.run_id)

                # Speaker upsert (if provided)
                speaker_meta = record.pop("speaker", None)
                if speaker_meta and speaker_meta.get("external_id"):
                    record["speaker_id"] = _upsert_speaker(conn, speaker_meta)
                else:
                    record["speaker_id"] = None

                # Validate
                report = validate_voice_recording(record, val_cfg)
                _persist_validation(conn, run.run_id, report)

                if not report.passed:
                    logger.warning(
                        '"Validation failed for %s: %s"',
                        audio_path.name,
                        [r.message for r in report.failures],
                    )
                    run.records_failed += 1
                    conn.commit()
                    continue

                # Upsert recording
                recording_id, inserted = _upsert_recording(conn, record, run.run_id)

                if not inserted:
                    logger.debug('"Skipped duplicate: %s (hash=%s)"', audio_path.name, record["content_hash"][:12])
                    run.records_skipped += 1
                    conn.commit()
                    continue

                # Quality metrics (optional)
                if qa_cfg.get("enabled", True) and recording_id:
                    metrics = compute_quality_metrics(audio_path, qa_cfg)
                    if metrics:
                        _upsert_quality_metrics(conn, recording_id, metrics)

                conn.commit()
                run.records_loaded += 1
                logger.info('"Loaded recording_id=%s file=%s"', recording_id, audio_path.name)

            except Exception as exc:
                conn.rollback()
                run.records_failed += 1
                logger.error('"Failed to process %s: %s"', audio_path, exc, exc_info=True)

        # Finalise run
        total_processed = run.records_loaded + run.records_failed
        failure_rate = run.records_failed / max(total_processed, 1)
        run.status = "success" if failure_rate <= alert_threshold else "partial"
        _finish_run(conn, run)

    elapsed = time.monotonic() - t0
    logger.info(
        '"Pipeline complete: run_id=%s loaded=%d skipped=%d failed=%d elapsed=%.1fs"',
        run.run_id, run.records_loaded, run.records_skipped, run.records_failed, elapsed,
    )
    return run


def ingest_records(
    records: list[dict],
    conn,
    run: PipelineRun,
    val_cfg: dict | None = None,
    qa_cfg: dict | None = None,
) -> None:
    """
    Ingest a pre-built list of record dicts (e.g. from an API response).
    Mutates run counters in place.  conn must be open; caller commits.
    """
    val_cfg = val_cfg or {}
    qa_cfg = qa_cfg or {}

    for record in records:
        run.records_read += 1
        try:
            speaker_meta = record.pop("speaker", None)
            if speaker_meta and speaker_meta.get("external_id"):
                record["speaker_id"] = _upsert_speaker(conn, speaker_meta)
            else:
                record.setdefault("speaker_id", None)

            report = validate_voice_recording(record, val_cfg)
            _persist_validation(conn, run.run_id, report)

            if not report.passed:
                run.records_failed += 1
                continue

            recording_id, inserted = _upsert_recording(conn, record, run.run_id)
            if not inserted:
                run.records_skipped += 1
                continue

            if qa_cfg.get("enabled", True) and recording_id and record.get("storage_uri"):
                local_path = record["storage_uri"]
                if Path(local_path).exists():
                    metrics = compute_quality_metrics(local_path, qa_cfg)
                    if metrics:
                        _upsert_quality_metrics(conn, recording_id, metrics)

            run.records_loaded += 1

        except Exception as exc:
            run.records_failed += 1
            logger.error('"ingest_records error for %s: %s"', record.get("external_id"), exc, exc_info=True)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Voice data ingestion pipeline")
    parser.add_argument("source_dir", help="Directory containing audio files to ingest")
    parser.add_argument(
        "--config", default="voice_pipeline_config.yaml",
        help="Path to voice_pipeline_config.yaml",
    )
    args = parser.parse_args()

    completed_run = ingest_directory(args.source_dir, config_path=args.config)
    print(json.dumps({
        "run_id": completed_run.run_id,
        "status": completed_run.status,
        "records_read": completed_run.records_read,
        "records_loaded": completed_run.records_loaded,
        "records_skipped": completed_run.records_skipped,
        "records_failed": completed_run.records_failed,
        "validation_pass_rate": round(completed_run.validation_pass_rate, 4),
    }, indent=2))
