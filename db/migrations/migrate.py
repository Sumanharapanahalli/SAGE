"""
Migration runner for the fintech + PSP payment gateway database schema.

Transaction isolation levels:
  READ COMMITTED (default) : DDL migrations and general reads.
  REPEATABLE READ           : Balance reads within transfers.
  SERIALIZABLE              : All financial writes — debit, credit,
                              card charges, refunds.

    Per-operation override in application code:
        with engine.connect() as conn:
            conn = conn.execution_options(isolation_level="SERIALIZABLE")
            conn.execute(text("INSERT INTO transactions ..."))
            conn.commit()

Usage:
  python migrate.py up            # Apply all pending migrations
  python migrate.py up V002       # Apply up to and including V002
  python migrate.py down          # Roll back the last applied migration
  python migrate.py down 2        # Roll back the last 2 migrations
  python migrate.py status        # Show applied / pending state

Environment variables:
  DATABASE_URL  PostgreSQL DSN
                (default: postgresql://postgres:postgres@localhost:5432/psp)
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import NamedTuple

import sqlalchemy as sa
from sqlalchemy import text

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/psp",
)
MIGRATIONS_DIR: Path = Path(__file__).parent

# ── schema_migrations bootstrap DDL ──────────────────────────────────────────
_BOOTSTRAP_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     VARCHAR(255) PRIMARY KEY,
    applied_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
"""


class MigrationEntry(NamedTuple):
    version: str
    up_file: str
    down_file: str


# ── Migration manifest (ordered) ─────────────────────────────────────────────
# Add new migrations here in version order. Never reorder existing entries.
MIGRATIONS: list[MigrationEntry] = [
    MigrationEntry("V001", "001_up.sql",                       "001_down.sql"),
    MigrationEntry("V002", "V002__psp_payment_gateway.up.sql", "V002__psp_payment_gateway.down.sql"),
]


# ── Engine ───────────────────────────────────────────────────────────────────
def get_engine() -> sa.Engine:
    """
    Return a SQLAlchemy engine with READ COMMITTED isolation.

    Isolation level reference:
      - DDL migrations            -> READ COMMITTED   (this engine default)
      - Balance / limit reads     -> REPEATABLE READ  (override per-connection)
      - Financial writes (PSP)    -> SERIALIZABLE     (override per-connection)

    Example per-connection override for a card charge:
        with engine.connect() as conn:
            conn = conn.execution_options(isolation_level="SERIALIZABLE")
            conn.execute(text(
                "INSERT INTO transactions (sender_id, amount, ...) VALUES ..."
            ))
            conn.commit()
    """
    return sa.create_engine(
        DATABASE_URL,
        isolation_level="READ COMMITTED",
        pool_pre_ping=True,
        echo=False,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────
def _bootstrap(conn: sa.Connection) -> None:
    """Ensure the schema_migrations tracking table exists."""
    conn.execute(text(_BOOTSTRAP_SQL))
    conn.commit()


def _applied_versions(conn: sa.Connection) -> set[str]:
    rows = conn.execute(
        text("SELECT version FROM schema_migrations ORDER BY version")
    ).fetchall()
    return {r[0] for r in rows}


def _run_sql_file(conn: sa.Connection, path: Path) -> None:
    """
    Execute a SQL file via the raw DBAPI cursor.

    The migration SQL files own their own BEGIN/COMMIT blocks.
    We release any SQLAlchemy-managed transaction first to avoid
    nested-transaction conflicts with psycopg2.
    """
    if not path.exists():
        raise FileNotFoundError(f"Migration file not found: {path}")
    sql = path.read_text(encoding="utf-8")
    raw_conn = conn.connection
    if not raw_conn.autocommit:
        raw_conn.rollback()
    cursor = raw_conn.cursor()
    try:
        cursor.execute(sql)
        raw_conn.commit()
    except Exception:
        raw_conn.rollback()
        raise
    finally:
        cursor.close()


# ── Commands ──────────────────────────────────────────────────────────────────
def migrate_up(engine: sa.Engine, target: str | None = None) -> None:
    """
    Apply all pending migrations up to (and including) *target* version.
    If *target* is None every pending migration is applied.
    """
    with engine.connect() as conn:
        _bootstrap(conn)
        applied = _applied_versions(conn)

        pending = [
            m for m in MIGRATIONS
            if m.version not in applied
            and (target is None or m.version <= target)
        ]
        if not pending:
            logger.info("No pending migrations — database is up to date.")
            return

        for entry in pending:
            path = MIGRATIONS_DIR / entry.up_file
            logger.info("Applying %s (%s) ...", entry.version, entry.up_file)
            _run_sql_file(conn, path)
            conn.execute(
                text(
                    "INSERT INTO schema_migrations (version, applied_at) "
                    "VALUES (:v, NOW()) ON CONFLICT (version) DO NOTHING"
                ),
                {"v": entry.version},
            )
            conn.commit()
            logger.info("Applied %s.", entry.version)


def migrate_down(engine: sa.Engine, steps: int = 1) -> None:
    """
    Roll back the last *steps* applied migrations in reverse order.
    Default: 1 (roll back only the most recent migration).

    No data loss: each down script runs in its own transaction;
    a failure mid-rollback leaves the database at the last clean state.
    """
    with engine.connect() as conn:
        _bootstrap(conn)
        applied = sorted(_applied_versions(conn), reverse=True)

        if not applied:
            logger.info("No migrations to roll back.")
            return

        manifest = {m.version: m for m in MIGRATIONS}
        to_rollback = [v for v in applied if v in manifest][:steps]

        for version in to_rollback:
            entry = manifest[version]
            path = MIGRATIONS_DIR / entry.down_file
            logger.info("Rolling back %s (%s) ...", version, entry.down_file)
            _run_sql_file(conn, path)
            conn.execute(
                text("DELETE FROM schema_migrations WHERE version = :v"),
                {"v": version},
            )
            conn.commit()
            logger.info("Rolled back %s.", version)


def migrate_status(engine: sa.Engine) -> None:
    """Print migration state to stdout."""
    with engine.connect() as conn:
        _bootstrap(conn)
        applied = _applied_versions(conn)

    print("\nMigration status:")
    print(f"  {'Version':<12}  {'State':<10}  File")
    print(f"  {'-'*12}  {'-'*10}  {'-'*45}")
    for entry in MIGRATIONS:
        state = "applied" if entry.version in applied else "pending"
        print(f"  {entry.version:<12}  {state:<10}  {entry.up_file}")
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    valid_commands = {"up", "down", "status"}
    if len(sys.argv) < 2 or sys.argv[1] not in valid_commands:
        print(f"Usage: python {Path(__file__).name} <{'|'.join(sorted(valid_commands))}>")
        sys.exit(1)

    command = sys.argv[1]
    db_engine = get_engine()

    try:
        if command == "up":
            target_version = sys.argv[2] if len(sys.argv) > 2 else None
            migrate_up(db_engine, target=target_version)
        elif command == "down":
            steps = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            migrate_down(db_engine, steps=steps)
        elif command == "status":
            migrate_status(db_engine)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.error("Migration failed: %s", exc, exc_info=True)
        sys.exit(1)
