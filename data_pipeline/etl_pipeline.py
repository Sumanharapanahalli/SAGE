"""
etl_pipeline.py — Production ETL pipeline: Extract → Transform → Load

Design decisions:
  - Idempotent: every upsert uses external_id as the dedup key (ON CONFLICT DO UPDATE)
  - No data leakage: scalers/encoders (if added later) must be fit on training split only
  - Schema is applied on startup from models.sql (CREATE TABLE IF NOT EXISTS)
  - All experiment runs logged to pipeline_runs + validation_results tables
  - Stratified split utility included for downstream classification tasks
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Iterator

import psycopg2
import psycopg2.extras
import yaml

from validators import validate, ValidationReport

# ---------------------------------------------------------------------------
# Logging — structured JSON lines for log aggregators
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":%(message)s}',
)
logger = logging.getLogger("etl_pipeline")


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_config(path: str | Path = "pipeline_config.yaml") -> dict:
    with open(path) as fh:
        raw = yaml.safe_load(fh)
    return _expand_env_vars(raw)


def _expand_env_vars(obj: Any) -> Any:
    """Recursively substitute ${VAR:-default} in string values."""
    if isinstance(obj, dict):
        return {k: _expand_env_vars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_env_vars(i) for i in obj]
    if isinstance(obj, str) and "${" in obj:
        import re
        def replace(m):
            var, _, default = m.group(1).partition(":-")
            return os.environ.get(var, default)
        return re.sub(r"\$\{([^}]+)\}", replace, obj)
    return obj


# ---------------------------------------------------------------------------
# Database connection pool (simple wrapper — swap for SQLAlchemy if needed)
# ---------------------------------------------------------------------------

@contextmanager
def get_db(cfg: dict) -> Generator[psycopg2.extensions.connection, None, None]:
    db_cfg = cfg["staging_db"]
    conn = psycopg2.connect(
        host=db_cfg["host"],
        port=int(db_cfg.get("port", 5432)),
        dbname=db_cfg["database"],
        user=db_cfg["user"],
        password=db_cfg["password"],
        connect_timeout=int(db_cfg.get("connect_timeout", 10)),
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


# ---------------------------------------------------------------------------
# Schema bootstrap — idempotent (CREATE TABLE IF NOT EXISTS everywhere)
# ---------------------------------------------------------------------------

def apply_schema(conn: psycopg2.extensions.connection, schema_file: str | Path = "models.sql") -> None:
    sql = Path(schema_file).read_text()
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    logger.info('"Schema applied from %s"', schema_file)


# ---------------------------------------------------------------------------
# Run tracking
# ---------------------------------------------------------------------------

@dataclass
class RunMetrics:
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_type: str = "invoice"
    records_read: int = 0
    records_transformed: int = 0
    records_loaded: int = 0
    records_failed: int = 0
    validation_failures: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    status: str = "running"
    error_message: str | None = None

    @property
    def validation_pass_rate(self) -> float:
        total = self.records_read
        return (total - self.validation_failures) / total if total else 1.0

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
            INSERT INTO pipeline_runs (run_id, source_type, started_at, status)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (run_id) DO NOTHING
            """,
            (m.run_id, m.source_type, m.started_at, "running"),
        )
    conn.commit()


def log_run_finish(conn: psycopg2.extensions.connection, m: RunMetrics) -> None:
    m.finished_at = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE pipeline_runs SET
                finished_at     = %s,
                records_read    = %s,
                records_written = %s,
                records_failed  = %s,
                status          = %s,
                error_message   = %s
            WHERE run_id = %s
            """,
            (
                m.finished_at, m.records_read, m.records_loaded,
                m.records_failed, m.status, m.error_message, m.run_id,
            ),
        )
    conn.commit()
    logger.info(
        '"run_id":"%s" "status":"%s" "loaded":%d "failed":%d '
        '"pass_rate":%.3f "rows_per_sec":%.1f',
        m.run_id, m.status, m.records_loaded, m.records_failed,
        m.validation_pass_rate, m.rows_per_second,
    )


def persist_validation_results(
    conn: psycopg2.extensions.connection,
    run_id: str,
    report: ValidationReport,
) -> None:
    rows = [
        (run_id, report.document_type, report.external_id,
         r.rule_name, r.passed, r.message, r.severity)
        for r in report.results
    ]
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO validation_results
                (run_id, document_type, external_id, rule_name, passed, message, severity)
            VALUES %s
            """,
            rows,
        )


def log_ingestion_error(
    conn: psycopg2.extensions.connection,
    run_id: str,
    source_file: str,
    raw_record: dict,
    error_type: str,
    error_detail: str,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ingestion_errors
                (run_id, source_file, raw_record, error_type, error_detail)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (run_id, source_file, json.dumps(raw_record), error_type, error_detail),
        )


# ---------------------------------------------------------------------------
# EXTRACT — file-system readers
# ---------------------------------------------------------------------------

def extract_json_file(path: Path) -> Iterator[dict]:
    with open(path) as fh:
        data = json.load(fh)
    if isinstance(data, list):
        yield from data
    elif isinstance(data, dict):
        if "records" in data:
            yield from data["records"]
        else:
            yield data


def extract_csv_file(path: Path) -> Iterator[dict]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            yield dict(row)


def extract_file(path: Path) -> Iterator[dict]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        yield from extract_json_file(path)
    elif suffix == ".csv":
        yield from extract_csv_file(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


# ---------------------------------------------------------------------------
# TRANSFORM — normalise field names, coerce types, attach metadata
# ---------------------------------------------------------------------------

def transform_record(raw: dict, document_type: str, source_file: str) -> dict:
    """
    Returns a normalised record ready for loading.
    Does NOT mutate the original dict.
    Coercions are type-safe — bad values left as-is for the validator to flag.
    """
    rec = {k.lower().strip(): v for k, v in raw.items()}    # normalise keys

    # Deterministic external_id if missing: hash of source file + content
    if not rec.get("external_id"):
        digest = hashlib.sha256(
            f"{source_file}:{json.dumps(raw, sort_keys=True)}".encode()
        ).hexdigest()[:32]
        rec["external_id"] = f"{document_type[:3].upper()}-{digest}"

    # Coerce numeric strings
    for f in ("subtotal", "tax_amount", "discount_amount", "tip_amount",
              "total_amount", "contract_value", "unit_price", "line_total"):
        if f in rec and isinstance(rec[f], str):
            try:
                rec[f] = float(rec[f].replace(",", "").strip())
            except ValueError:
                pass

    # Attach provenance
    rec["_source_file"] = source_file
    rec["_document_type"] = document_type
    return rec


# ---------------------------------------------------------------------------
# LOAD — idempotent upserts per document type
# ---------------------------------------------------------------------------

def upsert_party(cur: psycopg2.extensions.cursor, rec: dict) -> str | None:
    """Upsert a party (vendor/merchant/counterparty) and return its party_id UUID."""
    ext_id = rec.get("vendor_id") or rec.get("merchant_id") or rec.get("party_external_id")
    name = rec.get("vendor_name") or rec.get("merchant_name") or rec.get("party_name")
    if not name:
        return None
    cur.execute(
        """
        INSERT INTO parties (external_id, name, tax_id, address, contact)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (external_id) DO UPDATE
            SET name       = EXCLUDED.name,
                tax_id     = COALESCE(EXCLUDED.tax_id, parties.tax_id),
                updated_at = NOW()
        RETURNING party_id
        """,
        (
            ext_id or name,
            name,
            rec.get("tax_id"),
            json.dumps(rec.get("address")) if rec.get("address") else None,
            json.dumps(rec.get("contact")) if rec.get("contact") else None,
        ),
    )
    row = cur.fetchone()
    return str(row[0]) if row else None


def load_invoice(conn: psycopg2.extensions.connection, rec: dict) -> str:
    with conn.cursor() as cur:
        vendor_id = upsert_party(cur, rec)
        cur.execute(
            """
            INSERT INTO invoices (
                external_id, invoice_number, vendor_id, invoice_date,
                due_date, currency, subtotal, tax_amount, discount_amount,
                total_amount, status, payment_terms, notes, source_file, raw_data
            ) VALUES (
                %(external_id)s, %(invoice_number)s, %(vendor_id)s, %(invoice_date)s,
                %(due_date)s, %(currency)s, %(subtotal)s, %(tax_amount)s, %(discount_amount)s,
                %(total_amount)s, %(status)s, %(payment_terms)s, %(notes)s,
                %(source_file)s, %(raw_data)s
            )
            ON CONFLICT (external_id) DO UPDATE SET
                invoice_number  = EXCLUDED.invoice_number,
                vendor_id       = COALESCE(EXCLUDED.vendor_id, invoices.vendor_id),
                invoice_date    = EXCLUDED.invoice_date,
                due_date        = EXCLUDED.due_date,
                currency        = EXCLUDED.currency,
                subtotal        = EXCLUDED.subtotal,
                tax_amount      = EXCLUDED.tax_amount,
                discount_amount = EXCLUDED.discount_amount,
                total_amount    = EXCLUDED.total_amount,
                status          = EXCLUDED.status,
                payment_terms   = EXCLUDED.payment_terms,
                notes           = EXCLUDED.notes,
                source_file     = EXCLUDED.source_file,
                raw_data        = EXCLUDED.raw_data,
                updated_at      = NOW()
            RETURNING invoice_id
            """,
            {
                "external_id":     rec["external_id"],
                "invoice_number":  rec.get("invoice_number", rec["external_id"]),
                "vendor_id":       vendor_id,
                "invoice_date":    rec.get("invoice_date"),
                "due_date":        rec.get("due_date"),
                "currency":        rec.get("currency"),
                "subtotal":        rec.get("subtotal"),
                "tax_amount":      rec.get("tax_amount"),
                "discount_amount": rec.get("discount_amount", 0),
                "total_amount":    rec.get("total_amount"),
                "status":          rec.get("status", "draft"),
                "payment_terms":   rec.get("payment_terms"),
                "notes":           rec.get("notes"),
                "source_file":     rec.get("_source_file"),
                "raw_data":        json.dumps({k: v for k, v in rec.items() if not k.startswith("_")}),
            },
        )
        row = cur.fetchone()
        return str(row[0])


def load_receipt(conn: psycopg2.extensions.connection, rec: dict) -> str:
    with conn.cursor() as cur:
        merchant_id = upsert_party(cur, rec)
        cur.execute(
            """
            INSERT INTO receipts (
                external_id, receipt_number, merchant_id, transaction_date,
                transaction_time, currency, subtotal, tax_amount, tip_amount,
                total_amount, payment_method, card_last_four, category,
                reimbursable, source_file, raw_data
            ) VALUES (
                %(external_id)s, %(receipt_number)s, %(merchant_id)s, %(transaction_date)s,
                %(transaction_time)s, %(currency)s, %(subtotal)s, %(tax_amount)s, %(tip_amount)s,
                %(total_amount)s, %(payment_method)s, %(card_last_four)s, %(category)s,
                %(reimbursable)s, %(source_file)s, %(raw_data)s
            )
            ON CONFLICT (external_id) DO UPDATE SET
                receipt_number  = EXCLUDED.receipt_number,
                merchant_id     = COALESCE(EXCLUDED.merchant_id, receipts.merchant_id),
                transaction_date = EXCLUDED.transaction_date,
                currency        = EXCLUDED.currency,
                total_amount    = EXCLUDED.total_amount,
                payment_method  = EXCLUDED.payment_method,
                category        = EXCLUDED.category,
                source_file     = EXCLUDED.source_file,
                raw_data        = EXCLUDED.raw_data,
                updated_at      = NOW()
            RETURNING receipt_id
            """,
            {
                "external_id":      rec["external_id"],
                "receipt_number":   rec.get("receipt_number"),
                "merchant_id":      merchant_id,
                "transaction_date": rec.get("transaction_date"),
                "transaction_time": rec.get("transaction_time"),
                "currency":         rec.get("currency"),
                "subtotal":         rec.get("subtotal"),
                "tax_amount":       rec.get("tax_amount", 0),
                "tip_amount":       rec.get("tip_amount", 0),
                "total_amount":     rec.get("total_amount"),
                "payment_method":   rec.get("payment_method", "unknown"),
                "card_last_four":   rec.get("card_last_four"),
                "category":         rec.get("category"),
                "reimbursable":     rec.get("reimbursable", False),
                "source_file":      rec.get("_source_file"),
                "raw_data":         json.dumps({k: v for k, v in rec.items() if not k.startswith("_")}),
            },
        )
        row = cur.fetchone()
        return str(row[0])


def load_contract(conn: psycopg2.extensions.connection, rec: dict) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO contracts (
                external_id, contract_number, title, contract_type, status,
                effective_date, expiration_date, auto_renew, renewal_notice_days,
                contract_value, currency, governing_law, jurisdiction,
                summary, source_file, raw_data
            ) VALUES (
                %(external_id)s, %(contract_number)s, %(title)s, %(contract_type)s, %(status)s,
                %(effective_date)s, %(expiration_date)s, %(auto_renew)s, %(renewal_notice_days)s,
                %(contract_value)s, %(currency)s, %(governing_law)s, %(jurisdiction)s,
                %(summary)s, %(source_file)s, %(raw_data)s
            )
            ON CONFLICT (external_id) DO UPDATE SET
                contract_number     = EXCLUDED.contract_number,
                title               = EXCLUDED.title,
                contract_type       = EXCLUDED.contract_type,
                status              = EXCLUDED.status,
                effective_date      = EXCLUDED.effective_date,
                expiration_date     = EXCLUDED.expiration_date,
                contract_value      = EXCLUDED.contract_value,
                currency            = EXCLUDED.currency,
                summary             = EXCLUDED.summary,
                source_file         = EXCLUDED.source_file,
                raw_data            = EXCLUDED.raw_data,
                updated_at          = NOW()
            RETURNING contract_id
            """,
            {
                "external_id":         rec["external_id"],
                "contract_number":     rec.get("contract_number", rec["external_id"]),
                "title":               rec.get("title", ""),
                "contract_type":       rec.get("contract_type", "other"),
                "status":              rec.get("status", "draft"),
                "effective_date":      rec.get("effective_date"),
                "expiration_date":     rec.get("expiration_date"),
                "auto_renew":          rec.get("auto_renew", False),
                "renewal_notice_days": rec.get("renewal_notice_days"),
                "contract_value":      rec.get("contract_value"),
                "currency":            rec.get("currency"),
                "governing_law":       rec.get("governing_law"),
                "jurisdiction":        rec.get("jurisdiction"),
                "summary":             rec.get("summary"),
                "source_file":         rec.get("_source_file"),
                "raw_data":            json.dumps({k: v for k, v in rec.items() if not k.startswith("_")}),
            },
        )
        row = cur.fetchone()
        return str(row[0])


LOADERS = {
    "invoice":  load_invoice,
    "receipt":  load_receipt,
    "contract": load_contract,
}


# ---------------------------------------------------------------------------
# Stratified split utility (for downstream ML tasks — no leakage)
# ---------------------------------------------------------------------------

def stratified_split(
    records: list[dict],
    label_field: str,
    test_size: float = 0.2,
    random_seed: int = 42,
) -> tuple[list[dict], list[dict]]:
    """
    Returns (train_records, test_records) with class distribution preserved.
    Scalers/encoders MUST be fit only on train_records to prevent data leakage.
    """
    from collections import defaultdict
    import random

    rng = random.Random(random_seed)
    by_class: dict[Any, list[dict]] = defaultdict(list)
    for r in records:
        by_class[r.get(label_field, "__missing__")].append(r)

    train, test = [], []
    for cls_records in by_class.values():
        rng.shuffle(cls_records)
        n_test = max(1, int(len(cls_records) * test_size))
        test.extend(cls_records[:n_test])
        train.extend(cls_records[n_test:])

    rng.shuffle(train)
    rng.shuffle(test)
    return train, test


# ---------------------------------------------------------------------------
# Main pipeline orchestrator
# ---------------------------------------------------------------------------

class ETLPipeline:
    """
    Orchestrates Extract → Transform → Validate → Load for document ingestion.

    Idempotency contract:
      - Schema applied via CREATE TABLE IF NOT EXISTS (models.sql)
      - Every document upserted via ON CONFLICT (external_id) DO UPDATE
      - Running the same source file twice produces identical DB state
    """

    def __init__(self, config_path: str | Path = "pipeline_config.yaml"):
        self.cfg = load_config(config_path)
        self.pipeline_cfg = self.cfg["pipeline"]
        self.val_cfg = self.cfg.get("validation", {})
        logger.info('"ETLPipeline initialised" "version":"%s"', self.pipeline_cfg["version"])

    # ------------------------------------------------------------------
    # Public entrypoints
    # ------------------------------------------------------------------

    def run_filesystem(self, document_type: str | None = None) -> dict[str, RunMetrics]:
        """Process all pending files from configured watch directories."""
        results: dict[str, RunMetrics] = {}
        fs_cfg = self.cfg["sources"]["filesystem"]
        if not fs_cfg.get("enabled", False):
            logger.info('"filesystem source disabled — skipping"')
            return results

        for watch in fs_cfg["watch_dirs"]:
            dtype = document_type or watch["document_type"]
            if document_type and dtype != document_type:
                continue
            src_dir = Path(watch["path"])
            if not src_dir.exists():
                logger.warning('"watch dir not found: %s"', src_dir)
                continue
            patterns = watch.get("file_patterns", ["*.json"])
            files = [f for pat in patterns for f in src_dir.glob(pat)]
            if not files:
                logger.info('"no files in %s"', src_dir)
                continue
            metrics = self._process_files(files, dtype, fs_cfg)
            results[str(src_dir)] = metrics

        return results

    def run_file(self, path: str | Path, document_type: str) -> RunMetrics:
        """Process a single file — useful for testing or one-off ingestion."""
        return self._process_files([Path(path)], document_type, self.cfg["sources"].get("filesystem", {}))

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    def _process_files(self, files: list[Path], document_type: str, fs_cfg: dict) -> RunMetrics:
        metrics = RunMetrics(source_type=document_type)

        with get_db(self.cfg) as conn:
            apply_schema(conn, self.cfg["staging_db"].get("schema_file", "models.sql"))
            log_run_start(conn, metrics)

            batch: list[dict] = []
            source_map: dict[str, str] = {}   # external_id → source_file

            for file_path in files:
                logger.info('"extracting" "file":"%s"', file_path)
                try:
                    for raw in extract_file(file_path):
                        metrics.records_read += 1
                        rec = transform_record(raw, document_type, str(file_path))
                        source_map[rec["external_id"]] = str(file_path)
                        batch.append(rec)

                        if len(batch) >= self.pipeline_cfg["batch_size"]:
                            self._flush_batch(conn, batch, document_type, metrics)
                            batch.clear()

                except Exception as exc:
                    logger.error('"extract error" "file":"%s" "error":"%s"', file_path, exc)
                    log_ingestion_error(conn, metrics.run_id, str(file_path), {}, "EXTRACT_ERROR", str(exc))
                    metrics.records_failed += 1

            if batch:
                self._flush_batch(conn, batch, document_type, metrics)

            # Archive processed files
            archive_dir = Path(fs_cfg.get("archive_dir", "data/archive"))
            archive_dir.mkdir(parents=True, exist_ok=True)
            for fp in files:
                try:
                    fp.rename(archive_dir / fp.name)
                except Exception:
                    pass

            metrics.status = (
                "success" if metrics.records_failed == 0
                else "partial" if metrics.records_loaded > 0
                else "failed"
            )
            log_run_finish(conn, metrics)

        return metrics

    def _flush_batch(
        self,
        conn: psycopg2.extensions.connection,
        batch: list[dict],
        document_type: str,
        metrics: RunMetrics,
    ) -> None:
        loader = LOADERS.get(document_type)
        if loader is None:
            raise ValueError(f"No loader for document_type={document_type!r}")

        doc_val_cfg = self.val_cfg.get(document_type, {})
        alert_threshold = self.cfg.get("alerts", {}).get("failure_rate_threshold", 0.05)

        for rec in batch:
            ext_id = rec.get("external_id", "<unknown>")
            source_file = rec.get("_source_file", "")
            try:
                # Validate first — never load records that fail critical checks
                report = validate(document_type, rec, doc_val_cfg)
                persist_validation_results(conn, metrics.run_id, report)

                if not report.passed:
                    metrics.validation_failures += 1
                    metrics.records_failed += 1
                    logger.warning(
                        '"validation failed" "ext_id":"%s" "failures":%d',
                        ext_id, len(report.error_failures),
                    )
                    log_ingestion_error(
                        conn, metrics.run_id, source_file, rec,
                        "VALIDATION_FAILED",
                        "; ".join(r.message for r in report.error_failures),
                    )
                    continue

                # Load with retry
                for attempt in range(self.pipeline_cfg.get("max_retries", 3)):
                    try:
                        loader(conn, rec)
                        conn.commit()
                        metrics.records_loaded += 1
                        metrics.records_transformed += 1
                        break
                    except psycopg2.Error as db_err:
                        conn.rollback()
                        if attempt == self.pipeline_cfg.get("max_retries", 3) - 1:
                            raise
                        time.sleep(self.pipeline_cfg.get("retry_backoff_seconds", 5))

            except Exception as exc:
                conn.rollback()
                metrics.records_failed += 1
                logger.error('"load error" "ext_id":"%s" "error":"%s"', ext_id, exc)
                log_ingestion_error(conn, metrics.run_id, source_file, rec, "LOAD_ERROR", str(exc))

        # Alert on high failure rate
        if metrics.records_read > 0:
            fail_rate = metrics.records_failed / metrics.records_read
            if fail_rate > alert_threshold:
                logger.error(
                    '"HIGH FAILURE RATE" "rate":%.3f "threshold":%.3f',
                    fail_rate, alert_threshold,
                )


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SAGE Document Ingestion ETL")
    parser.add_argument("--config", default="pipeline_config.yaml")
    parser.add_argument("--type", dest="document_type",
                        choices=["invoice", "receipt", "contract"],
                        help="Process only this document type")
    parser.add_argument("--file", help="Process a single file")
    args = parser.parse_args()

    pipeline = ETLPipeline(args.config)

    if args.file:
        if not args.document_type:
            parser.error("--type is required when using --file")
        m = pipeline.run_file(args.file, args.document_type)
        print(json.dumps(asdict(m), default=str, indent=2))
    else:
        results = pipeline.run_filesystem(args.document_type)
        for src, m in results.items():
            print(f"\n[{src}]")
            print(json.dumps(asdict(m), default=str, indent=2))
