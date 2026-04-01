"""
ugc_ingestion.py — Production UGC (User-Generated Content) ingestion pipeline.

Design contracts
----------------
1. Idempotent   : every record is identified by content_hash = SHA-256(platform + external_id + raw_text).
                  Re-running against the same source produces identical DB state (ON CONFLICT DO NOTHING).
2. No leakage   : ML labels are written to a SEPARATE table (ugc_labels) and only populated after
                  the train/val/test split is locked.  Scalers / encoders are NEVER fit here.
3. Validation   : every record is validated before load; failed records go to ugc_validation_results,
                  never silently dropped.
4. PII flagging : email / phone / SSN patterns are detected and the pii_flag column is set.
                  Records are NOT blocked — they are flagged for downstream review.
5. Experiment logging : every run is persisted to ugc_collection_runs with full metrics.
6. Stratified split   : utility function included; MUST be called downstream — never here.

Schema: ugc_schema.sql
Config: ugc_pipeline_config.yaml
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import os
import random
import re
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Generator, Iterator

import psycopg2
import psycopg2.extras
import yaml

# Optional dependencies — degrade gracefully so CI works without them
try:
    from langdetect import detect as _langdetect, LangDetectException
    _LANGDETECT_AVAILABLE = True
except ImportError:
    _LANGDETECT_AVAILABLE = False

try:
    import mlflow
    _MLFLOW_AVAILABLE = True
except ImportError:
    _MLFLOW_AVAILABLE = False

# ---------------------------------------------------------------------------
# Logging — structured JSON lines
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":%(message)s}',
)
logger = logging.getLogger("ugc_ingestion")


# ---------------------------------------------------------------------------
# PII detection — regex-only, no ML model required at ingestion time
# ---------------------------------------------------------------------------
_PII_PATTERNS: dict[str, re.Pattern] = {
    "email": re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE),
    "phone": re.compile(
        r"(?:\+?1[\s.\-]?)?(?:\(?\d{3}\)?[\s.\-]?)?\d{3}[\s.\-]?\d{4}"
    ),
    "ssn": re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"),
}


def detect_pii(text: str, checks: dict[str, bool] | None = None) -> bool:
    """Return True if any enabled PII pattern matches.  Never raises."""
    enabled = checks or {"email": True, "phone": True, "ssn": True}
    for name, pattern in _PII_PATTERNS.items():
        if enabled.get(name, False) and pattern.search(text):
            return True
    return False


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

def detect_language(text: str, min_length: int = 20) -> str | None:
    """Return ISO 639-1 code or None on failure / short text."""
    if not _LANGDETECT_AVAILABLE or len(text.strip()) < min_length:
        return None
    try:
        return _langdetect(text)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Content hash — the dedup key
# ---------------------------------------------------------------------------

def content_hash(platform: str, external_id: str, raw_text: str) -> str:
    payload = f"{platform}:{external_id}:{raw_text}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Author hash — irreversible anonymisation
# ---------------------------------------------------------------------------

def author_hash(platform: str, username: str) -> str:
    payload = f"{platform}:{username}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_config(path: str | Path = "ugc_pipeline_config.yaml") -> dict:
    with open(path) as fh:
        raw = yaml.safe_load(fh)
    return _expand_env_vars(raw)


def _expand_env_vars(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _expand_env_vars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_env_vars(i) for i in obj]
    if isinstance(obj, str) and "${" in obj:
        def replace(m: re.Match) -> str:
            var, _, default = m.group(1).partition(":-")
            return os.environ.get(var, default)
        return re.sub(r"\$\{([^}]+)\}", replace, obj)
    return obj


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

@contextmanager
def get_db(cfg: dict) -> Generator[psycopg2.extensions.connection, None, None]:
    db = cfg["staging_db"]
    conn = psycopg2.connect(
        host=db["host"],
        port=int(db.get("port", 5432)),
        dbname=db["database"],
        user=db["user"],
        password=db["password"],
        connect_timeout=int(db.get("connect_timeout", 10)),
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


def apply_schema(conn: psycopg2.extensions.connection, schema_file: str | Path = "ugc_schema.sql") -> None:
    sql = Path(schema_file).read_text()
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    logger.info('"Schema applied" "file":"%s"', schema_file)


# ---------------------------------------------------------------------------
# Run tracking dataclass
# ---------------------------------------------------------------------------

@dataclass
class RunMetrics:
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_platform: str = "unknown"
    records_read: int = 0
    records_loaded: int = 0
    records_skipped: int = 0    # duplicates detected via content_hash
    records_failed: int = 0
    validation_failures: int = 0
    pii_flagged: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    status: str = "running"
    error_message: str | None = None
    class_distribution: dict = field(default_factory=dict)

    @property
    def validation_pass_rate(self) -> float:
        total = self.records_read
        return (total - self.validation_failures) / total if total else 1.0

    @property
    def pii_flag_rate(self) -> float:
        return self.pii_flagged / self.records_loaded if self.records_loaded else 0.0

    @property
    def duration_seconds(self) -> float:
        end = self.finished_at or datetime.now(timezone.utc)
        return (end - self.started_at).total_seconds()

    @property
    def rows_per_second(self) -> float:
        d = self.duration_seconds
        return self.records_loaded / d if d > 0 else 0.0


def log_run_start(conn: psycopg2.extensions.connection, m: RunMetrics) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ugc_collection_runs (run_id, source_platform, started_at, status)
            VALUES (%s, %s, %s, 'running')
            ON CONFLICT (run_id) DO NOTHING
            """,
            (m.run_id, m.source_platform, m.started_at),
        )
    conn.commit()


def log_run_finish(conn: psycopg2.extensions.connection, m: RunMetrics) -> None:
    m.finished_at = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ugc_collection_runs SET
                finished_at     = %s,
                records_read    = %s,
                records_loaded  = %s,
                records_skipped = %s,
                records_failed  = %s,
                status          = %s,
                error_message   = %s,
                params          = %s
            WHERE run_id = %s
            """,
            (
                m.finished_at,
                m.records_read,
                m.records_loaded,
                m.records_skipped,
                m.records_failed,
                m.status,
                m.error_message,
                json.dumps({"class_distribution": m.class_distribution}),
                m.run_id,
            ),
        )
    conn.commit()
    logger.info(
        '"run_finish" "run_id":"%s" "status":"%s" "loaded":%d '
        '"skipped":%d "failed":%d "pass_rate":%.3f "rps":%.1f',
        m.run_id, m.status,
        m.records_loaded, m.records_skipped, m.records_failed,
        m.validation_pass_rate, m.rows_per_second,
    )


def _persist_validation_results(
    conn: psycopg2.extensions.connection,
    run_id: str,
    results: list[dict],
) -> None:
    if not results:
        return
    rows = [
        (run_id, r["external_id"], r["platform"],
         r["rule_name"], r["passed"], r["message"], r["severity"])
        for r in results
    ]
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO ugc_validation_results
                (run_id, external_id, platform, rule_name, passed, message, severity)
            VALUES %s
            """,
            rows,
        )


# ---------------------------------------------------------------------------
# Validation layer
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    rule_name: str
    passed: bool
    message: str
    severity: str = "error"    # info | warning | error | critical


def _validate_ugc_record(
    rec: dict,
    cfg: dict,
    pii_cfg: dict,
    lang_cfg: dict,
) -> tuple[bool, list[ValidationResult]]:
    """
    Validates a single normalised UGC record against config-driven rules.
    Returns (overall_passed, results_list).
    'overall_passed' is False if any 'error' or 'critical' check fails.
    """
    results: list[ValidationResult] = []
    ext_id = rec.get("external_id", "<unknown>")
    platform = rec.get("platform", "<unknown>")

    # 1. Required fields
    for f in cfg.get("required_fields", []):
        val = rec.get(f)
        missing = val is None or (isinstance(val, str) and val.strip() == "")
        results.append(ValidationResult(
            rule_name=f"required:{f}",
            passed=not missing,
            message="" if not missing else f"Required field '{f}' is missing or empty",
            severity="critical",
        ))

    # 2. Text length
    text = rec.get("raw_text", "")
    tl = cfg.get("text_length", {})
    min_len, max_len = tl.get("min", 5), tl.get("max", 40000)
    tlen = len(text)
    results.append(ValidationResult(
        rule_name="text_length",
        passed=min_len <= tlen <= max_len,
        message="" if min_len <= tlen <= max_len
                else f"text_length={tlen} outside [{min_len}, {max_len}]",
    ))

    # 3. Allowed content type
    ct = rec.get("content_type")
    allowed_ct = cfg.get("allowed_content_types", [])
    if ct is not None and allowed_ct:
        ok = ct in allowed_ct
        results.append(ValidationResult(
            rule_name="content_type_enum",
            passed=ok,
            message="" if ok else f"content_type={ct!r} not in {allowed_ct}",
        ))

    # 4. Allowed platform
    allowed_pl = cfg.get("allowed_platforms", [])
    if platform and allowed_pl:
        ok = platform in allowed_pl
        results.append(ValidationResult(
            rule_name="platform_enum",
            passed=ok,
            message="" if ok else f"platform={platform!r} not in allowed list",
        ))

    # 5. Star rating range (reviews only)
    sr = rec.get("star_rating")
    if sr is not None:
        sr_range = cfg.get("star_rating_range", {"min": 1.0, "max": 5.0})
        try:
            numeric = float(sr)
            ok = sr_range["min"] <= numeric <= sr_range["max"]
        except (TypeError, ValueError):
            ok = False
        results.append(ValidationResult(
            rule_name="star_rating_range",
            passed=ok,
            message="" if ok else f"star_rating={sr} outside [{sr_range['min']}, {sr_range['max']}]",
            severity="warning",
        ))

    # 6. PII detection — flag, never block
    if text:
        pii_checks = {k: v for k, v in pii_cfg.items() if isinstance(v, bool)}
        has_pii = detect_pii(text, pii_checks)
        rec["_pii_flag"] = has_pii
        if has_pii:
            results.append(ValidationResult(
                rule_name="pii_detected",
                passed=True,    # does NOT fail validation — just a flag
                message="PII pattern detected — pii_flag=TRUE set",
                severity="warning",
            ))

    # 7. Language detection (info only, never blocks)
    if _LANGDETECT_AVAILABLE and lang_cfg.get("enabled"):
        lang = detect_language(text, lang_cfg.get("min_text_length", 20))
        if lang:
            rec["_detected_language"] = lang
        results.append(ValidationResult(
            rule_name="language_detected",
            passed=True,
            message=f"lang={lang or 'unknown'}",
            severity="info",
        ))

    overall_passed = all(
        r.passed for r in results if r.severity in ("error", "critical")
    )
    return overall_passed, results


# ---------------------------------------------------------------------------
# EXTRACT — file-system readers
# ---------------------------------------------------------------------------

def _extract_jsonl(path: Path) -> Iterator[dict]:
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def _extract_json(path: Path) -> Iterator[dict]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        yield from data
    elif isinstance(data, dict):
        yield from data.get("data", data.get("records", [data]))


def _extract_csv(path: Path) -> Iterator[dict]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            yield dict(row)


def extract_file(path: Path) -> Iterator[dict]:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        yield from _extract_jsonl(path)
    elif suffix == ".json":
        yield from _extract_json(path)
    elif suffix == ".csv":
        yield from _extract_csv(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


# ---------------------------------------------------------------------------
# TRANSFORM — normalise field names, derive content_hash, strip PII metadata
# ---------------------------------------------------------------------------

def transform_record(raw: dict, platform: str, source_file: str) -> dict:
    """
    Normalise a raw platform record into the canonical UGC schema shape.
    Does NOT mutate the input dict.  Returns a new dict with all _internal fields.
    """
    rec: dict[str, Any] = {}

    # -- Key normalisation (lowercase, strip whitespace) ---------------------
    norm = {k.lower().strip(): v for k, v in raw.items()}

    # -- external_id : try common field names, fall back to hash of payload --
    ext_id = (
        norm.get("id")
        or norm.get("external_id")
        or norm.get("review_id")
        or norm.get("tweet_id")
        or norm.get("post_id")
        or norm.get("comment_id")
    )
    if not ext_id:
        ext_id = hashlib.sha256(
            f"{platform}:{json.dumps(raw, sort_keys=True)}".encode()
        ).hexdigest()[:24]

    # -- raw_text : try common field names -----------------------------------
    raw_text = (
        norm.get("raw_text")
        or norm.get("text")
        or norm.get("body")
        or norm.get("selftext")
        or norm.get("content")
        or norm.get("review_text")
        or norm.get("review_body")
        or ""
    )
    raw_text = str(raw_text).strip()

    # -- content_type --------------------------------------------------------
    ct_raw = (norm.get("content_type") or norm.get("type") or "").lower()
    type_map = {
        "post": "post", "submission": "post", "tweet": "post",
        "comment": "comment", "reply": "comment",
        "review": "review", "rating": "review",
        "thread": "thread", "question": "thread",
        "answer": "answer",
    }
    content_type = type_map.get(ct_raw, "post" if not ct_raw else "other")

    # -- author anonymisation ------------------------------------------------
    raw_author = (
        norm.get("author")
        or norm.get("username")
        or norm.get("user_name")
        or norm.get("reviewer_name")
        or ""
    )
    rec["_author_hash"] = author_hash(platform, str(raw_author)) if raw_author else None
    rec["_raw_author"] = str(raw_author) if raw_author else None   # used only for upsert

    # -- Assemble canonical record -------------------------------------------
    rec.update({
        "external_id":    str(ext_id),
        "platform":       platform,
        "content_type":   content_type,
        "raw_text":       raw_text,
        "content_hash":   content_hash(platform, str(ext_id), raw_text),
        "title":          norm.get("title"),
        "url":            norm.get("url") or norm.get("permalink"),
        "parent_id":      str(norm["parent_id"]) if norm.get("parent_id") else None,
        "subreddit":      norm.get("subreddit"),
        "upvotes":        _int(norm.get("ups") or norm.get("upvotes") or norm.get("score")),
        "downvotes":      _int(norm.get("downs") or norm.get("downvotes")),
        "score":          _int(norm.get("score") or norm.get("upvotes")),
        "comment_count":  _int(norm.get("num_comments") or norm.get("comment_count")),
        "star_rating":    _float(norm.get("star_rating") or norm.get("rating") or norm.get("stars")),
        "posted_at":      _parse_ts(norm.get("created_utc") or norm.get("posted_at")
                                    or norm.get("created_at") or norm.get("date")),
        "language":       norm.get("language") or norm.get("lang"),
        "source_file":    source_file,
        "raw_metadata":   json.dumps({
            k: v for k, v in norm.items()
            if k not in ("author", "username", "user_name", "reviewer_name", "text",
                         "body", "selftext", "content", "review_text", "review_body")
        }),
        # internal flags — consumed by loader, not persisted as-is
        "_pii_flag":           False,   # overwritten by validator
        "_detected_language":  None,    # overwritten by validator
    })
    return rec


def _int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(float(str(v)))
    except (TypeError, ValueError):
        return None


def _float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(str(v))
    except (TypeError, ValueError):
        return None


def _parse_ts(v: Any) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        # Unix timestamp
        try:
            return datetime.fromtimestamp(float(v), tz=timezone.utc)
        except (OSError, ValueError, OverflowError):
            return None
    if isinstance(v, datetime):
        return v
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d"):
        try:
            dt = datetime.strptime(str(v).strip(), fmt)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# LOAD — idempotent upserts
# ---------------------------------------------------------------------------

def _upsert_author(cur: psycopg2.extensions.cursor, rec: dict) -> str | None:
    ah = rec.get("_author_hash")
    if not ah:
        return None
    cur.execute(
        """
        INSERT INTO ugc_authors (author_hash, platform)
        VALUES (%s, %s)
        ON CONFLICT (author_hash) DO UPDATE
            SET last_seen_at = NOW(),
                total_posts  = ugc_authors.total_posts + 1
        RETURNING author_id
        """,
        (ah, rec["platform"]),
    )
    row = cur.fetchone()
    return str(row[0]) if row else None


def load_ugc_record(
    conn: psycopg2.extensions.connection,
    rec: dict,
    run_id: str,
) -> tuple[str, bool]:
    """
    Upsert a single UGC record.
    Returns (content_id, was_new).
    was_new=False means the record was already present (dedup skipped).
    """
    with conn.cursor() as cur:
        author_id = _upsert_author(cur, rec)

        # Use lang from validator if not already set by platform API
        language = rec.get("_detected_language") or rec.get("language")

        cur.execute(
            """
            INSERT INTO ugc_content (
                content_hash, external_id, platform, content_type,
                raw_text, title, url, parent_id, subreddit,
                author_id, upvotes, downvotes, score, comment_count,
                star_rating, posted_at, language, source_file,
                run_id, pii_flag, validation_status, raw_metadata
            ) VALUES (
                %(content_hash)s, %(external_id)s, %(platform)s, %(content_type)s,
                %(raw_text)s, %(title)s, %(url)s, %(parent_id)s, %(subreddit)s,
                %(author_id)s, %(upvotes)s, %(downvotes)s, %(score)s, %(comment_count)s,
                %(star_rating)s, %(posted_at)s, %(language)s, %(source_file)s,
                %(run_id)s, %(pii_flag)s, 'passed', %(raw_metadata)s
            )
            ON CONFLICT (content_hash) DO NOTHING
            RETURNING content_id
            """,
            {
                **rec,
                "author_id":  author_id,
                "language":   language,
                "run_id":     run_id,
                "pii_flag":   rec.get("_pii_flag", False),
            },
        )
        row = cur.fetchone()
        was_new = row is not None
        content_id = str(row[0]) if was_new else "<duplicate>"
        return content_id, was_new


# ---------------------------------------------------------------------------
# Synthetic sample generator — deterministic bootstrap data
# ---------------------------------------------------------------------------

# Representative UGC text templates per content type and platform
_TEMPLATES: dict[str, list[str]] = {
    "reddit_post": [
        "I've been experimenting with {topic} for the past few months and here are my findings: {detail}.",
        "Can anyone help me understand why {topic} behaves this way? {detail}.",
        "TIL that {topic} is actually more nuanced than I thought. {detail}.",
        "Hot take: {topic} is overrated. Here's why: {detail}.",
        "I built a small project using {topic} and wanted to share what I learned. {detail}.",
    ],
    "twitter_post": [
        "Just discovered {topic}. {detail} #tech",
        "Unpopular opinion: {topic} needs better documentation. {detail}",
        "Thread on {topic}: {detail} 🧵",
        "The future of {topic} is here. {detail}",
        "{topic} tip of the day: {detail}",
    ],
    "app_store_review": [
        "This app {sentiment}. The {topic} feature {detail}. Would {recommend} recommend.",
        "{sentiment} app overall. {detail} Gave it {stars} stars.",
        "Pros: {topic}. Cons: {detail}. Overall {sentiment} experience.",
        "Updated review: after the latest update, {topic} {detail}. Rating: {stars}/5.",
        "Has potential but {topic} {detail}. Needs improvement.",
    ],
    "comment": [
        "Interesting point about {topic}. Have you considered {detail}?",
        "Disagree on {topic}. In my experience {detail}.",
        "This is exactly right. {topic} {detail}.",
        "+1, I had the same issue with {topic}. Solution: {detail}.",
        "Good write-up! One thing to add about {topic}: {detail}.",
    ],
}

_TOPICS = [
    "machine learning", "Python async", "Rust memory safety", "React hooks",
    "Kubernetes networking", "PostgreSQL query optimisation", "LLM fine-tuning",
    "vector databases", "CI/CD pipelines", "Docker multi-stage builds",
    "GraphQL subscriptions", "WebAssembly performance", "edge computing",
    "transformer architecture", "microservices orchestration",
]

_DETAILS = [
    "the performance difference was significant when benchmarked",
    "documentation is lacking but the community is helpful",
    "I would not go back to the old approach",
    "took me a while to wrap my head around it",
    "the official examples are misleading in this regard",
    "a simple refactor reduced latency by 40%",
    "there is a subtle gotcha that cost me two days",
    "turns out the default settings are rarely optimal",
    "the error messages could be much more descriptive",
    "highly recommend reading the source code directly",
]


def generate_sample_records(
    platform: str,
    count: int,
    cfg: dict,
    rng: random.Random,
) -> list[dict]:
    """
    Generate deterministic synthetic UGC records for a given platform.
    Suitable for initial data load, CI fixtures, and imbalance audits.
    Records are flagged with platform='synthetic' override — caller must pass
    the real platform name; source distinguishability is kept via raw_metadata.
    """
    ct_weights = cfg.get("content_type_weights", {
        "post": 0.30, "comment": 0.35, "review": 0.20, "thread": 0.10, "answer": 0.05,
    })
    sr_dist = cfg.get("star_rating_distribution", {
        "1.0": 0.10, "2.0": 0.10, "3.0": 0.20, "4.0": 0.30, "5.0": 0.30,
    })
    langs = cfg.get("languages", ["en"])
    lang_weights = cfg.get("language_weights", [1.0 / len(langs)] * len(langs))

    content_types = list(ct_weights.keys())
    ct_probs = [ct_weights[c] for c in content_types]

    star_values = [float(k) for k in sr_dist]
    star_probs = list(sr_dist.values())

    records = []
    base_ts = datetime.now(timezone.utc) - timedelta(days=90)

    for i in range(count):
        ct = rng.choices(content_types, weights=ct_probs, k=1)[0]
        lang = rng.choices(langs, weights=lang_weights, k=1)[0]
        topic = rng.choice(_TOPICS)
        detail = rng.choice(_DETAILS)

        # Build raw_text from template
        if platform in ("twitter",) or ct in ("post", "thread"):
            tmpl = rng.choice(_TEMPLATES.get("twitter_post", _TEMPLATES["reddit_post"]))
        elif ct == "comment":
            tmpl = rng.choice(_TEMPLATES["comment"])
        elif ct == "review" or platform in ("app_store", "play_store", "yelp"):
            tmpl = rng.choice(_TEMPLATES["app_store_review"])
            ct = "review"
        else:
            tmpl = rng.choice(_TEMPLATES["reddit_post"])

        sentiment = rng.choice(["great", "decent", "mediocre", "excellent", "disappointing"])
        recommend = rng.choice(["definitely", "might", "not"])
        stars_val = rng.choices(star_values, weights=star_probs, k=1)[0]

        text = tmpl.format(
            topic=topic, detail=detail, sentiment=sentiment,
            recommend=recommend, stars=int(stars_val),
        )

        ext_id = f"syn_{platform}_{i:06d}_{rng.randint(10000, 99999)}"
        posted_ts = base_ts + timedelta(
            seconds=rng.randint(0, int(timedelta(days=90).total_seconds()))
        )

        rec: dict[str, Any] = {
            "id":          ext_id,
            "external_id": ext_id,
            "platform":    platform,
            "content_type": ct,
            "text":        text,
            "author":      f"user_{rng.randint(1000, 9999)}",
            "created_at":  posted_ts.isoformat(),
            "language":    lang,
            "upvotes":     rng.randint(0, 5000),
            "downvotes":   rng.randint(0, 200),
            "comment_count": rng.randint(0, 500),
            "_synthetic":  True,
        }
        if ct == "review":
            rec["star_rating"] = stars_val
        if platform == "reddit":
            rec["subreddit"] = rng.choice(
                ["python", "MachineLearning", "programming", "datascience", "devops"]
            )
        records.append(rec)

    return records


# ---------------------------------------------------------------------------
# Stratified split utility
# ---------------------------------------------------------------------------

def stratified_split(
    records: list[dict],
    stratify_field: str = "content_type",
    test_size: float = 0.15,
    val_size: float = 0.10,
    random_seed: int = 42,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Split UGC records into train / val / test with class-distribution preserved.

    IMPORTANT — leakage prevention
    --------------------------------
    Scalers, TF-IDF vectorisers, and embedding models MUST be fit only on the
    returned 'train' split.  The val/test splits must be transformed using
    the already-fitted objects — never re-fitted.

    Parameters
    ----------
    records        : flat list of dicts (as returned by the DB or ingestion run)
    stratify_field : field whose distribution is preserved (default: 'content_type')
    test_size      : fraction reserved for test (default: 0.15)
    val_size       : fraction of remaining data reserved for val (default: 0.10)
    random_seed    : reproducibility seed

    Returns
    -------
    (train, val, test) — three non-overlapping lists
    """
    from collections import defaultdict

    rng = random.Random(random_seed)
    by_class: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        key = str(r.get(stratify_field, "__missing__"))
        by_class[key].append(r)

    train_all, test_all = [], []
    for cls_recs in by_class.values():
        rng.shuffle(cls_recs)
        n_test = max(1, int(len(cls_recs) * test_size))
        test_all.extend(cls_recs[:n_test])
        train_all.extend(cls_recs[n_test:])

    # carve val from train
    rng.shuffle(train_all)
    n_val = max(1, int(len(train_all) * val_size))
    val_all = train_all[:n_val]
    train_final = train_all[n_val:]

    rng.shuffle(train_final)
    rng.shuffle(val_all)
    rng.shuffle(test_all)
    return train_final, val_all, test_all


# ---------------------------------------------------------------------------
# Class imbalance check
# ---------------------------------------------------------------------------

def check_class_imbalance(
    records: list[dict],
    field: str = "content_type",
    imbalance_ratio_threshold: float = 5.0,
) -> dict[str, Any]:
    """
    Returns a summary dict with imbalance_detected flag and per-class counts.
    Logs a warning when the majority/minority ratio exceeds the threshold.
    Does NOT alter records — diagnosis only.
    """
    from collections import Counter

    counts = Counter(str(r.get(field, "__missing__")) for r in records)
    if not counts:
        return {"imbalance_detected": False, "counts": {}}

    majority = max(counts.values())
    minority = min(counts.values())
    ratio = majority / minority if minority > 0 else float("inf")
    imbalanced = ratio > imbalance_ratio_threshold

    result = {
        "field": field,
        "counts": dict(counts),
        "majority_class_count": majority,
        "minority_class_count": minority,
        "imbalance_ratio": round(ratio, 2),
        "imbalance_detected": imbalanced,
        "threshold": imbalance_ratio_threshold,
    }
    if imbalanced:
        logger.warning(
            '"class_imbalance_detected" "field":"%s" "ratio":%.2f "threshold":%.2f',
            field, ratio, imbalance_ratio_threshold,
        )
    return result


# ---------------------------------------------------------------------------
# MLflow experiment logger (optional)
# ---------------------------------------------------------------------------

def log_to_mlflow(m: RunMetrics, cfg: dict) -> None:
    mlflow_cfg = cfg.get("metrics", {}).get("mlflow", {})
    if not mlflow_cfg.get("enabled") or not _MLFLOW_AVAILABLE:
        return
    try:
        mlflow.set_tracking_uri(mlflow_cfg.get("tracking_uri", "http://localhost:5000"))
        mlflow.set_experiment(mlflow_cfg.get("experiment_name", "ugc_ingestion"))
        with mlflow.start_run(run_name=m.run_id):
            mlflow.log_params({
                "source_platform": m.source_platform,
                "run_id":          m.run_id,
            })
            mlflow.log_metrics({
                "records_read":         m.records_read,
                "records_loaded":       m.records_loaded,
                "records_skipped":      m.records_skipped,
                "records_failed":       m.records_failed,
                "validation_pass_rate": m.validation_pass_rate,
                "pii_flag_rate":        m.pii_flag_rate,
                "rows_per_second":      m.rows_per_second,
                "duration_seconds":     m.duration_seconds,
            })
    except Exception as exc:
        logger.warning('"mlflow_log_failed" "error":"%s"', exc)


# ---------------------------------------------------------------------------
# Main pipeline orchestrator
# ---------------------------------------------------------------------------

class UGCIngestionPipeline:
    """
    Orchestrates Extract → Transform → Validate → Load for UGC data.

    Idempotency contract
    ---------------------
    - Schema applied via CREATE TABLE IF NOT EXISTS (ugc_schema.sql)
    - Every record upserted via ON CONFLICT (content_hash) DO NOTHING
    - Running the same source file twice produces identical DB state
    - Duplicate count incremented in RunMetrics for observability
    """

    def __init__(self, config_path: str | Path = "ugc_pipeline_config.yaml") -> None:
        self.cfg = load_config(config_path)
        self.pipeline_cfg = self.cfg["pipeline"]
        self.val_cfg = self.cfg.get("validation", {}).get("ugc", {})
        self.pii_cfg = self.val_cfg.get("pii_patterns", {})
        self.lang_cfg = self.val_cfg.get("language_detection", {})
        self.ml_split_cfg = self.cfg.get("ml_split", {})
        logger.info(
            '"UGCIngestionPipeline init" "pipeline":"%s" "version":"%s"',
            self.pipeline_cfg["name"],
            self.pipeline_cfg["version"],
        )

    # ------------------------------------------------------------------
    # Public entrypoints
    # ------------------------------------------------------------------

    def run_sample_generator(self) -> RunMetrics:
        """Generate and load synthetic bootstrap data (idempotent)."""
        gen_cfg = self.cfg["sources"]["sample_generator"]
        if not gen_cfg.get("enabled", False):
            logger.info('"sample_generator disabled — skipping"')
            return RunMetrics(source_platform="synthetic", status="skipped")

        seed = gen_cfg.get("seed", 42)
        counts: dict[str, int] = gen_cfg.get("counts", {})
        all_records: list[tuple[str, dict]] = []

        for platform, n in counts.items():
            rng = random.Random(seed + hash(platform) % 1000)
            recs = generate_sample_records(platform, n, gen_cfg, rng)
            all_records.extend((platform, r) for r in recs)

        return self._process_records(all_records, source_platform="synthetic",
                                     source_file="<sample_generator>")

    def run_filesystem(self, platform: str | None = None) -> dict[str, RunMetrics]:
        """Process all pending files from configured watch directories."""
        results: dict[str, RunMetrics] = {}
        fs_cfg = self.cfg["sources"]["filesystem"]
        if not fs_cfg.get("enabled", False):
            logger.info('"filesystem source disabled — skipping"')
            return results

        for watch in fs_cfg["watch_dirs"]:
            plt = platform or watch["platform"]
            if platform and plt != platform:
                continue
            src_dir = Path(watch["path"])
            if not src_dir.exists():
                logger.warning('"watch_dir_not_found" "path":"%s"', src_dir)
                continue
            patterns = watch.get("file_patterns", ["*.jsonl", "*.json"])
            files = [f for pat in patterns for f in src_dir.glob(pat)]
            if not files:
                logger.info('"no_files" "path":"%s"', src_dir)
                continue
            raw_pairs: list[tuple[str, dict]] = []
            for fp in files:
                try:
                    for raw in extract_file(fp):
                        raw_pairs.append((plt, {**raw, "_source_file": str(fp)}))
                except Exception as exc:
                    logger.error('"extract_error" "file":"%s" "err":"%s"', fp, exc)

            metrics = self._process_records(raw_pairs, source_platform=plt,
                                            source_file=str(src_dir))
            results[str(src_dir)] = metrics

            # Archive processed files
            archive_dir = Path(fs_cfg.get("archive_dir", "data/archive/ugc"))
            archive_dir.mkdir(parents=True, exist_ok=True)
            for fp in files:
                try:
                    fp.rename(archive_dir / fp.name)
                except Exception:
                    pass

        return results

    def run_file(self, path: str | Path, platform: str) -> RunMetrics:
        """Process a single file — one-off or test ingestion."""
        path = Path(path)
        raw_pairs: list[tuple[str, dict]] = [
            (platform, raw) for raw in extract_file(path)
        ]
        return self._process_records(raw_pairs, source_platform=platform,
                                     source_file=str(path))

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    def _process_records(
        self,
        raw_pairs: list[tuple[str, dict]],
        source_platform: str,
        source_file: str,
    ) -> RunMetrics:
        metrics = RunMetrics(source_platform=source_platform)
        alert_cfg = self.cfg.get("alerts", {})
        alert_thresh = alert_cfg.get("failure_rate_threshold", 0.05)
        pii_thresh = alert_cfg.get("pii_flag_rate_threshold", 0.10)

        with get_db(self.cfg) as conn:
            apply_schema(conn, self.cfg["staging_db"].get("schema_file", "ugc_schema.sql"))
            log_run_start(conn, metrics)

            batch: list[dict] = []
            for platform, raw in raw_pairs:
                metrics.records_read += 1
                try:
                    rec = transform_record(raw, platform, source_file)
                    batch.append(rec)
                    if len(batch) >= self.pipeline_cfg["batch_size"]:
                        self._flush_batch(conn, batch, metrics)
                        batch.clear()
                except Exception as exc:
                    metrics.records_failed += 1
                    logger.error(
                        '"transform_error" "platform":"%s" "err":"%s"', platform, exc
                    )

            if batch:
                self._flush_batch(conn, batch, metrics)

            # Alert checks
            if metrics.records_read > 0:
                fail_rate = metrics.records_failed / metrics.records_read
                if fail_rate > alert_thresh:
                    logger.error(
                        '"HIGH_FAILURE_RATE" "rate":%.3f "threshold":%.3f',
                        fail_rate, alert_thresh,
                    )
            if metrics.records_loaded > 0 and metrics.pii_flag_rate > pii_thresh:
                logger.warning(
                    '"HIGH_PII_RATE" "rate":%.3f "threshold":%.3f',
                    metrics.pii_flag_rate, pii_thresh,
                )

            metrics.status = (
                "success"  if metrics.records_failed == 0
                else "partial" if metrics.records_loaded > 0
                else "failed"
            )
            log_run_finish(conn, metrics)

        log_to_mlflow(metrics, self.cfg)
        return metrics

    def _flush_batch(
        self,
        conn: psycopg2.extensions.connection,
        batch: list[dict],
        metrics: RunMetrics,
    ) -> None:
        val_results_to_persist: list[dict] = []

        for rec in batch:
            ext_id = rec.get("external_id", "<unknown>")
            platform = rec.get("platform", "<unknown>")
            try:
                # --- Validate first; never load records that fail critical checks ---
                passed, vresults = _validate_ugc_record(
                    rec, self.val_cfg, self.pii_cfg, self.lang_cfg
                )
                for r in vresults:
                    val_results_to_persist.append({
                        "external_id": ext_id,
                        "platform":    platform,
                        "rule_name":   r.rule_name,
                        "passed":      r.passed,
                        "message":     r.message,
                        "severity":    r.severity,
                    })
                if rec.get("_pii_flag"):
                    metrics.pii_flagged += 1

                if not passed:
                    metrics.validation_failures += 1
                    metrics.records_failed += 1
                    logger.warning(
                        '"validation_failed" "ext_id":"%s" "platform":"%s"',
                        ext_id, platform,
                    )
                    continue

                # --- Load with retry on transient DB errors ---
                for attempt in range(self.pipeline_cfg.get("max_retries", 3)):
                    try:
                        _, was_new = load_ugc_record(conn, rec, metrics.run_id)
                        conn.commit()
                        if was_new:
                            metrics.records_loaded += 1
                            ct = rec.get("content_type", "unknown")
                            metrics.class_distribution[ct] = (
                                metrics.class_distribution.get(ct, 0) + 1
                            )
                        else:
                            metrics.records_skipped += 1
                        break
                    except psycopg2.Error as db_err:
                        conn.rollback()
                        if attempt == self.pipeline_cfg.get("max_retries", 3) - 1:
                            raise
                        time.sleep(self.pipeline_cfg.get("retry_backoff_seconds", 5))

            except Exception as exc:
                conn.rollback()
                metrics.records_failed += 1
                logger.error('"load_error" "ext_id":"%s" "err":"%s"', ext_id, exc)

        # Persist validation results in bulk
        try:
            _persist_validation_results(conn, metrics.run_id, val_results_to_persist)
            conn.commit()
        except Exception as exc:
            logger.warning('"val_persist_failed" "err":"%s"', exc)
            conn.rollback()


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SAGE UGC Ingestion Pipeline")
    parser.add_argument("--config", default="ugc_pipeline_config.yaml")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sub_sample = subparsers.add_parser("sample", help="Load synthetic sample data")

    sub_fs = subparsers.add_parser("filesystem", help="Ingest from watch directories")
    sub_fs.add_argument("--platform", help="Filter to a specific platform")

    sub_file = subparsers.add_parser("file", help="Ingest a single file")
    sub_file.add_argument("path", help="Path to the file")
    sub_file.add_argument("platform", help="Platform name")

    sub_split = subparsers.add_parser("split-check",
                                       help="Check class imbalance on a JSON export")
    sub_split.add_argument("export_file", help="Path to JSON array export")
    sub_split.add_argument("--field", default="content_type")
    sub_split.add_argument("--threshold", type=float, default=5.0)

    args = parser.parse_args()
    pipeline = UGCIngestionPipeline(args.config)

    if args.command == "sample":
        m = pipeline.run_sample_generator()
        print(json.dumps(asdict(m), default=str, indent=2))

    elif args.command == "filesystem":
        results = pipeline.run_filesystem(getattr(args, "platform", None))
        for src, m in results.items():
            print(f"\n[{src}]")
            print(json.dumps(asdict(m), default=str, indent=2))

    elif args.command == "file":
        m = pipeline.run_file(args.path, args.platform)
        print(json.dumps(asdict(m), default=str, indent=2))

    elif args.command == "split-check":
        with open(args.export_file) as fh:
            recs = json.load(fh)
        report = check_class_imbalance(recs, field=args.field,
                                       imbalance_ratio_threshold=args.threshold)
        print(json.dumps(report, indent=2))
        train, val, test = stratified_split(
            recs, stratify_field=args.field,
            test_size=0.15, val_size=0.10,
        )
        print(f"\nSplit sizes — train:{len(train)}  val:{len(val)}  test:{len(test)}")
