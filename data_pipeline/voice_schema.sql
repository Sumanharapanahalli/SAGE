-- =============================================================================
-- Voice Data Pipeline — DDL
-- Idempotent: all statements use IF NOT EXISTS / ON CONFLICT DO NOTHING
-- Supports: user voice recordings, transcriptions, quality metrics
-- Schema version: 1.0.0
--
-- Dedup strategy: voice_recordings.content_hash (SHA-256 of raw audio bytes)
--   ensures the same audio file is never stored twice regardless of filename
--   or source path.  All child tables cascade from recording_id.
--
-- Privacy: consent_given + consent_timestamp are non-nullable on ingest.
--   Recordings without documented consent are rejected at the validation layer.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Pipeline audit (mirrors pipeline_runs in models.sql)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS voice_pipeline_runs (
    run_id          TEXT        PRIMARY KEY,
    source_dir      TEXT,
    started_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at     TIMESTAMP,
    records_read    INTEGER     DEFAULT 0,
    records_loaded  INTEGER     DEFAULT 0,
    records_skipped INTEGER     DEFAULT 0,   -- already-present duplicates
    records_failed  INTEGER     DEFAULT 0,
    status          TEXT        NOT NULL DEFAULT 'running'
                                CHECK (status IN ('running','success','partial','failed')),
    error_message   TEXT
);

-- ---------------------------------------------------------------------------
-- Speaker / user profiles
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS voice_speakers (
    speaker_id      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id     TEXT        UNIQUE NOT NULL,  -- your app's user ID
    display_name    TEXT,
    language_bcp47  TEXT        NOT NULL DEFAULT 'en-US',  -- BCP-47 locale tag
    age_group       TEXT        CHECK (age_group IN ('child','teen','adult','senior')),
    gender_label    TEXT,        -- self-reported; nullable
    created_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vspeakers_ext ON voice_speakers(external_id);

-- ---------------------------------------------------------------------------
-- Voice recordings — one row per audio file
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS voice_recordings (
    recording_id        UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id         TEXT        UNIQUE NOT NULL,  -- caller-supplied dedup key (e.g. session+seq)
    content_hash        TEXT        UNIQUE NOT NULL,  -- SHA-256 of raw audio bytes
    speaker_id          UUID        REFERENCES voice_speakers(speaker_id),

    -- Storage reference (local path or s3://bucket/key or gs://…)
    storage_uri         TEXT        NOT NULL,
    original_filename   TEXT,

    -- Audio technical metadata
    format              TEXT        NOT NULL
                                    CHECK (format IN ('wav','mp3','flac','ogg','m4a','mp4','webm','aac')),
    duration_seconds    NUMERIC(10,3) NOT NULL CHECK (duration_seconds > 0),
    sample_rate_hz      INTEGER     NOT NULL CHECK (sample_rate_hz > 0),
    channels            SMALLINT    NOT NULL CHECK (channels IN (1, 2)),
    bit_depth           SMALLINT,   -- null for lossy formats
    file_size_bytes     BIGINT      NOT NULL CHECK (file_size_bytes > 0),
    codec               TEXT,

    -- Recording context
    recorded_at         TIMESTAMP   NOT NULL,
    device_type         TEXT        CHECK (device_type IN
                                        ('microphone','headset','phone','mobile','smart_speaker','other','unknown')),
    environment         TEXT        CHECK (environment IN
                                        ('quiet','office','outdoor','vehicle','noisy','unknown')),
    language_bcp47      TEXT        NOT NULL DEFAULT 'en-US',
    session_id          TEXT,       -- groups multiple recordings from one session
    task_type           TEXT,       -- 'command','dictation','conversation','read_aloud','free_speech'

    -- Privacy / consent
    consent_given       BOOLEAN     NOT NULL,
    consent_timestamp   TIMESTAMP   NOT NULL,
    consent_version     TEXT,       -- version of the consent document signed
    pii_scrubbed        BOOLEAN     NOT NULL DEFAULT FALSE,
    data_retention_days INTEGER     DEFAULT 365,
    deletion_requested_at TIMESTAMP,

    -- Pipeline metadata
    run_id              TEXT        REFERENCES voice_pipeline_runs(run_id),
    ingested_at         TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    raw_metadata        JSONB       -- original source record verbatim
);

CREATE INDEX IF NOT EXISTS idx_vrec_speaker     ON voice_recordings(speaker_id);
CREATE INDEX IF NOT EXISTS idx_vrec_recorded    ON voice_recordings(recorded_at);
CREATE INDEX IF NOT EXISTS idx_vrec_format      ON voice_recordings(format);
CREATE INDEX IF NOT EXISTS idx_vrec_session     ON voice_recordings(session_id);
CREATE INDEX IF NOT EXISTS idx_vrec_hash        ON voice_recordings(content_hash);
CREATE INDEX IF NOT EXISTS idx_vrec_task        ON voice_recordings(task_type);
-- Partial index: quickly find recordings pending deletion
CREATE INDEX IF NOT EXISTS idx_vrec_deletion
    ON voice_recordings(deletion_requested_at)
    WHERE deletion_requested_at IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Transcriptions — one row per recording; updated when re-processed
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS voice_transcriptions (
    transcription_id    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    recording_id        UUID        NOT NULL UNIQUE REFERENCES voice_recordings(recording_id) ON DELETE CASCADE,
    engine              TEXT        NOT NULL,  -- 'whisper','google_stt','azure_stt','aws_transcribe','manual'
    engine_version      TEXT,
    model_id            TEXT,       -- e.g. 'whisper-large-v3'
    language_detected   TEXT,
    transcript_text     TEXT        NOT NULL,
    word_count          INTEGER,
    confidence_score    NUMERIC(5,4) CHECK (confidence_score BETWEEN 0 AND 1),
    words_json          JSONB,      -- [{word, start_ms, end_ms, confidence}, ...]
    processing_time_ms  INTEGER,
    transcribed_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vtrans_recording ON voice_transcriptions(recording_id);
CREATE INDEX IF NOT EXISTS idx_vtrans_engine    ON voice_transcriptions(engine);

-- Full-text search index on transcript text (PostgreSQL tsvector)
CREATE INDEX IF NOT EXISTS idx_vtrans_fts
    ON voice_transcriptions USING GIN (to_tsvector('english', transcript_text));

-- ---------------------------------------------------------------------------
-- Quality metrics — computed per recording on ingestion
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS voice_quality_metrics (
    metric_id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    recording_id        UUID        NOT NULL UNIQUE REFERENCES voice_recordings(recording_id) ON DELETE CASCADE,

    -- Signal quality
    snr_db              NUMERIC(7,3),   -- signal-to-noise ratio; NULL if not computable
    rms_db              NUMERIC(7,3),   -- root-mean-square loudness
    peak_db             NUMERIC(7,3),
    dynamic_range_db    NUMERIC(7,3),

    -- Content ratios (0.0–1.0)
    silence_ratio       NUMERIC(5,4) CHECK (silence_ratio BETWEEN 0 AND 1),
    speech_ratio        NUMERIC(5,4) CHECK (speech_ratio BETWEEN 0 AND 1),
    clipping_ratio      NUMERIC(5,4) CHECK (clipping_ratio BETWEEN 0 AND 1),

    -- Computed scores
    clarity_score       NUMERIC(5,4) CHECK (clarity_score BETWEEN 0 AND 1),
    quality_grade       TEXT         CHECK (quality_grade IN ('excellent','good','acceptable','poor','unusable')),

    -- Anomaly flags
    is_silent           BOOLEAN     NOT NULL DEFAULT FALSE,
    has_clipping        BOOLEAN     NOT NULL DEFAULT FALSE,
    has_background_noise BOOLEAN    NOT NULL DEFAULT FALSE,

    computed_at         TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vqm_recording    ON voice_quality_metrics(recording_id);
CREATE INDEX IF NOT EXISTS idx_vqm_grade        ON voice_quality_metrics(quality_grade);
CREATE INDEX IF NOT EXISTS idx_vqm_silent       ON voice_quality_metrics(is_silent) WHERE is_silent;

-- ---------------------------------------------------------------------------
-- Validation log (written by voice_pipeline.py)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS voice_validation_results (
    id              SERIAL      PRIMARY KEY,
    run_id          TEXT        REFERENCES voice_pipeline_runs(run_id),
    external_id     TEXT        NOT NULL,
    rule_name       TEXT        NOT NULL,
    passed          BOOLEAN     NOT NULL,
    message         TEXT,
    severity        TEXT        NOT NULL DEFAULT 'error'
                                CHECK (severity IN ('info','warning','error','critical')),
    checked_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vval_run     ON voice_validation_results(run_id);
CREATE INDEX IF NOT EXISTS idx_vval_ext     ON voice_validation_results(external_id);
CREATE INDEX IF NOT EXISTS idx_vval_failed  ON voice_validation_results(passed) WHERE NOT passed;

-- ---------------------------------------------------------------------------
-- Convenience view: recordings with their quality grade
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW voice_recordings_summary AS
SELECT
    r.recording_id,
    r.external_id,
    r.speaker_id,
    s.external_id           AS speaker_external_id,
    r.format,
    r.duration_seconds,
    r.sample_rate_hz,
    r.channels,
    r.file_size_bytes,
    r.language_bcp47,
    r.task_type,
    r.environment,
    r.consent_given,
    r.recorded_at,
    r.ingested_at,
    q.snr_db,
    q.clarity_score,
    q.quality_grade,
    q.is_silent,
    q.has_clipping,
    t.engine                AS transcription_engine,
    t.confidence_score      AS transcription_confidence,
    LENGTH(t.transcript_text) AS transcript_chars
FROM voice_recordings r
LEFT JOIN voice_speakers         s ON s.speaker_id    = r.speaker_id
LEFT JOIN voice_quality_metrics  q ON q.recording_id  = r.recording_id
LEFT JOIN voice_transcriptions   t ON t.recording_id  = r.recording_id;
