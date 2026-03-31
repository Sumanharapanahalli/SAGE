"""
SAGE Framework — SQLite Connection Helper
==========================================

Centralised ``get_connection()`` that enforces WAL mode and busy timeout
on every connection.  All framework code should use this instead of raw
``sqlite3.connect()``.

WAL (Write-Ahead Logging) allows concurrent readers while a writer is
active — eliminates "database is locked" errors under moderate concurrency.
"""

import sqlite3
import threading

# Per-database WAL initialisation guard — PRAGMA journal_mode only needs
# to be executed once per database file per process lifetime.
_wal_init_lock = threading.Lock()
_wal_initialised: set[str] = set()

# Default busy timeout in milliseconds.  If another connection holds a
# write lock, SQLite will retry for this duration before raising.
DEFAULT_BUSY_TIMEOUT_MS = 5_000


def get_connection(
    db_path: str,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    row_factory: type | None = sqlite3.Row,
) -> sqlite3.Connection:
    """Return a :class:`sqlite3.Connection` with WAL mode and busy timeout.

    Parameters
    ----------
    db_path:
        Filesystem path to the SQLite database file.
    busy_timeout_ms:
        How long (ms) to wait when another writer holds the lock.
    row_factory:
        Passed through to ``conn.row_factory``.  Defaults to
        :class:`sqlite3.Row` for dict-like access.  Pass ``None`` for
        plain tuple rows.
    """
    conn = sqlite3.connect(db_path)
    conn.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")

    if row_factory is not None:
        conn.row_factory = row_factory

    # Enable WAL once per database file per process.
    resolved = str(db_path)
    if resolved not in _wal_initialised:
        with _wal_init_lock:
            if resolved not in _wal_initialised:
                conn.execute("PRAGMA journal_mode = WAL")
                _wal_initialised.add(resolved)

    return conn
