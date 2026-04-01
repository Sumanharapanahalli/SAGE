"""
db/connection.py — Production database connection manager.

Features:
- Connection pooling via SQLAlchemy
- Environment-based configuration (no credentials in code)
- Health-check probe
- Context-manager interface for safe resource cleanup
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)


def _build_url() -> str:
    """Build DSN from environment variables — never from hard-coded values."""
    driver = os.environ.get("DB_DRIVER", "postgresql+psycopg2")
    user = os.environ["DB_USER"]           # intentionally raise on missing
    password = os.environ["DB_PASSWORD"]   # intentionally raise on missing
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")
    dbname = os.environ["DB_NAME"]
    return f"{driver}://{user}:{password}@{host}:{port}/{dbname}"


def build_engine(
    pool_size: int = 5,
    max_overflow: int = 10,
    pool_timeout: int = 30,
    pool_recycle: int = 1800,
    echo: bool = False,
) -> Engine:
    """
    Create and return a SQLAlchemy Engine with a QueuePool.

    Args:
        pool_size:    Number of connections kept open.
        max_overflow: Connections allowed beyond pool_size.
        pool_timeout: Seconds to wait for a connection before raising.
        pool_recycle: Recycle connections older than this (avoids stale TCP).
        echo:         Set True only in development — logs all SQL.
    """
    url = _build_url()
    engine = create_engine(
        url,
        poolclass=QueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
        echo=echo,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _set_search_path(dbapi_conn, _):
        schema = os.environ.get("DB_SCHEMA", "public")
        cursor = dbapi_conn.cursor()
        cursor.execute(f"SET search_path TO {schema}")
        cursor.close()
        dbapi_conn.commit()

    logger.info(
        "Engine created: host=%s db=%s pool_size=%d",
        os.environ.get("DB_HOST", "localhost"),
        os.environ.get("DB_NAME", "?"),
        pool_size,
    )
    return engine


# Module-level singleton — call build_engine() once at application startup.
_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def init(
    pool_size: int = 5,
    max_overflow: int = 10,
    echo: bool = False,
) -> None:
    """Initialise the module-level engine and session factory (call once)."""
    global _engine, _SessionLocal
    _engine = build_engine(pool_size=pool_size, max_overflow=max_overflow, echo=echo)
    _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    logger.info("Database module initialised.")


def health_check() -> bool:
    """Return True if the database is reachable, False otherwise."""
    if _engine is None:
        raise RuntimeError("Call db.connection.init() before health_check().")
    try:
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("DB health-check failed: %s", exc)
        return False


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Yield a SQLAlchemy Session; commit on success, rollback on error.

    Usage:
        with get_session() as session:
            session.execute(...)
    """
    if _SessionLocal is None:
        raise RuntimeError("Call db.connection.init() before get_session().")
    session: Session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
