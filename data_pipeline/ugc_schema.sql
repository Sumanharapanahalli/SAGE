-- =============================================================================
-- UGC (User-Generated Content) Ingestion Pipeline — DDL
-- Schema version: 1.0.0
--
-- Column dictionary
-- -----------------
-- ugc_sources      : registered source platforms (reddit, twitter, app_store, …)
-- ugc_authors      : anonymised author registry — PII stripped at ingestion
-- ugc_content      : primary UGC record; dedup key = content_hash (SHA-256)
-- ugc_labels       : ML-assigned labels attached AFTER ingestion (no leakage)
-- ugc_collection_runs : per-run audit log mirroring the generic pipeline_runs pattern
-- ugc_validation_results : per-field validation outcomes written by Python layer
--
-- Idempotency contract
-- --------------------
-- Every statement uses IF NOT EXISTS / ON CONFLICT DO NOTHING or DO UPDATE.
-- Running this file twice against the same schema produces identical state.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Source platform registry
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ugc_sources (
    source_id       SERIAL      PRIMARY KEY,
    platform        TEXT        UNIQUE NOT NULL,   -- 'reddit','twitter','app_store',…
    description     TEXT,
    base_url        TEXT,
    rate_limit_rpm  INTEGER,                       -- requests / minute cap
    enabled         BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Seed known platforms (idempotent)
INSERT INTO ugc_sources (platform, description, base_url, rate_limit_rpm) VALUES
    ('reddit',     'Reddit posts and comments',             'https://www.reddit.com', 60),
    ('twitter',    'Twitter/X posts',                       'https://api.twitter.com', 15),
    ('app_store',  'Apple App Store reviews',               'https://itunes.apple.com', 120),
    ('play_store', 'Google Play Store reviews',             'https://play.google.com', 120),
    ('yelp',       'Yelp business reviews',                 'https://api.yelp.com', 60),
    ('hackernews', 'Hacker News posts and comments',        'https://news.ycombinator.com', 120),
    ('stackover',  'Stack Overflow questions and answers',  'https://api.stackexchange.com', 300),
    ('synthetic',  'Synthetically generated sample data',   NULL, NULL)
ON CONFLICT (platform) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Anonymised author registry
-- PII contract: real usernames NEVER stored; only a deterministic hash.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ugc_authors (
    author_id       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    -- SHA-256( platform || ':' || original_username ) — irreversible
    author_hash     TEXT        UNIQUE NOT NULL,
    platform        TEXT        NOT NULL REFERENCES ugc_sources(platform),
    -- aggregate stats updated incrementally — no per-post PII
    total_posts     INTEGER     NOT NULL DEFAULT 0,
    avg_score       NUMERIC(10,4),
    first_seen_at   TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at    TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ugc_authors_hash     ON ugc_authors(author_hash);
CREATE INDEX IF NOT EXISTS idx_ugc_authors_platform ON ugc_authors(platform);

-- ---------------------------------------------------------------------------
-- Collection run audit log  (defined before ugc_content to satisfy FK)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ugc_collection_runs (
    run_id          TEXT        PRIMARY KEY,
    source_platform TEXT        REFERENCES ugc_sources(platform),
    started_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at     TIMESTAMP,
    records_read    INTEGER     NOT NULL DEFAULT 0,
    records_loaded  INTEGER     NOT NULL DEFAULT 0,
    records_skipped INTEGER     NOT NULL DEFAULT 0,   -- duplicate / already-ingested
    records_failed  INTEGER     NOT NULL DEFAULT 0,
    status          TEXT        NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running','success','partial','failed')),
    error_message   TEXT,
    params          JSONB                              -- arbitrary run-time params for replay
);

-- ---------------------------------------------------------------------------
-- Primary UGC content table
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ugc_content (
    content_id      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Deduplication keys (two levels)
    content_hash    TEXT        UNIQUE NOT NULL,   -- SHA-256(platform+external_id+raw_text)
    external_id     TEXT        NOT NULL,          -- platform-native ID
    platform        TEXT        NOT NULL REFERENCES ugc_sources(platform),

    -- Content classification
    --   post       : top-level original post / tweet / review
    --   comment    : reply to a post
    --   review     : structured star-rated review (app_store, play_store, yelp)
    --   thread     : forum thread opener
    --   answer     : answer to a question (SO pattern)
    content_type    TEXT        NOT NULL
                    CHECK (content_type IN
                        ('post','comment','review','thread','answer','other')),

    -- Raw text — always stored verbatim for reproducibility
    raw_text        TEXT        NOT NULL,
    text_length     INTEGER     GENERATED ALWAYS AS (length(raw_text)) STORED,

    -- Optional structured fields (populated when available from the platform)
    title           TEXT,
    url             TEXT,
    parent_id       TEXT,                          -- external_id of parent post/comment
    subreddit       TEXT,                          -- Reddit-specific; NULL for others

    -- Author reference (anonymised)
    author_id       UUID        REFERENCES ugc_authors(author_id),

    -- Engagement signals (raw platform counts at time of ingestion)
    upvotes         INTEGER,
    downvotes       INTEGER,
    score           INTEGER,
    comment_count   INTEGER,
    star_rating     NUMERIC(3,1) CHECK (star_rating IS NULL OR star_rating BETWEEN 1 AND 5),

    -- Temporal
    posted_at       TIMESTAMP,                     -- when published on the platform
    ingested_at     TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Language (ISO 639-1, e.g. 'en', 'fr') — detected at ingestion
    language        CHAR(5),

    -- Provenance
    source_file     TEXT,                          -- NULL for API-collected content
    run_id          TEXT        REFERENCES ugc_collection_runs(run_id),

    -- PII / quality flags set during validation
    pii_flag        BOOLEAN     NOT NULL DEFAULT FALSE,  -- regex-detected PII hint
    validation_status TEXT      NOT NULL DEFAULT 'pending'
                    CHECK (validation_status IN ('pending','passed','warning','failed')),

    -- Raw platform payload for full fidelity replay
    raw_metadata    JSONB,

    UNIQUE (platform, external_id)
);

CREATE INDEX IF NOT EXISTS idx_ugc_platform       ON ugc_content(platform);
CREATE INDEX IF NOT EXISTS idx_ugc_content_type   ON ugc_content(content_type);
CREATE INDEX IF NOT EXISTS idx_ugc_author         ON ugc_content(author_id);
CREATE INDEX IF NOT EXISTS idx_ugc_posted_at      ON ugc_content(posted_at);
CREATE INDEX IF NOT EXISTS idx_ugc_language       ON ugc_content(language);
CREATE INDEX IF NOT EXISTS idx_ugc_pii_flag       ON ugc_content(pii_flag) WHERE pii_flag = TRUE;
CREATE INDEX IF NOT EXISTS idx_ugc_validation     ON ugc_content(validation_status);
-- Full-text search index (PostgreSQL tsvector)
CREATE INDEX IF NOT EXISTS idx_ugc_fts
    ON ugc_content USING gin(to_tsvector('english', coalesce(raw_text,'')));

-- ---------------------------------------------------------------------------
-- ML labels (populated AFTER ingestion — strict separation prevents leakage)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ugc_labels (
    label_id        UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id      UUID        NOT NULL REFERENCES ugc_content(content_id) ON DELETE CASCADE,

    -- Label family: 'sentiment','topic','toxicity','intent','language', …
    label_type      TEXT        NOT NULL,
    label_value     TEXT        NOT NULL,          -- e.g. 'positive','neutral','negative'
    confidence      NUMERIC(6,4) CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),

    -- Model provenance (prevents silent label drift)
    model_name      TEXT,
    model_version   TEXT,
    labelled_at     TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Allow one label per (content, type, model_version)
    UNIQUE (content_id, label_type, model_version)
);

CREATE INDEX IF NOT EXISTS idx_ugc_labels_content ON ugc_labels(content_id);
CREATE INDEX IF NOT EXISTS idx_ugc_labels_type    ON ugc_labels(label_type, label_value);

-- ---------------------------------------------------------------------------
-- Per-record validation results
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ugc_validation_results (
    id              SERIAL      PRIMARY KEY,
    run_id          TEXT        REFERENCES ugc_collection_runs(run_id),
    external_id     TEXT        NOT NULL,
    platform        TEXT        NOT NULL,
    rule_name       TEXT        NOT NULL,
    passed          BOOLEAN     NOT NULL,
    message         TEXT,
    severity        TEXT        NOT NULL DEFAULT 'error'
                    CHECK (severity IN ('info','warning','error','critical')),
    checked_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ugc_val_run    ON ugc_validation_results(run_id);
CREATE INDEX IF NOT EXISTS idx_ugc_val_ext    ON ugc_validation_results(external_id, platform);
CREATE INDEX IF NOT EXISTS idx_ugc_val_failed ON ugc_validation_results(passed) WHERE NOT passed;

-- ---------------------------------------------------------------------------
-- Materialised view: content distribution snapshot for class-imbalance audits
-- (REFRESH MATERIALIZED VIEW ugc_class_distribution; on schedule)
-- ---------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS ugc_class_distribution AS
SELECT
    platform,
    content_type,
    language,
    COUNT(*)                                    AS record_count,
    ROUND(AVG(text_length), 1)                  AS avg_text_length,
    COUNT(*) FILTER (WHERE pii_flag)            AS pii_flagged,
    COUNT(*) FILTER (WHERE validation_status = 'failed') AS validation_failed,
    NOW()                                       AS refreshed_at
FROM ugc_content
GROUP BY platform, content_type, language
WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_ugc_class_dist
    ON ugc_class_distribution(platform, content_type, COALESCE(language,'__null__'));
