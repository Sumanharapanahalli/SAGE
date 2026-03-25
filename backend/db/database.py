"""
Async SQLAlchemy 2.0 engine + session factory.

Usage (per-request dependency injection in FastAPI):
    async with get_db_session() as session:
        session.execute(text("SET LOCAL app.user_id = :uid"), {"uid": str(user_id)})
        session.execute(text("SET LOCAL app.user_role = :role"), {"role": user.role})
        ...
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.db.models import Base  # noqa: F401 – imported so Alembic sees metadata

DATABASE_URL = "postgresql+asyncpg://app_user:changeme@localhost:5432/elder_fall_detection"

# The encryption key is *never* hard-coded in production.
# Set via: ALTER DATABASE elder_fall_detection SET app.encryption_key = '<key>';
# or pass it per-session (see set_session_context).
ENCRYPTION_KEY_SETTING = "app.encryption_key"

engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def set_session_context(
    session: AsyncSession,
    user_id: str,
    user_role: str,
    encryption_key: str,
) -> None:
    """
    Sets per-transaction PostgreSQL session variables used by RLS policies
    and pgcrypto TypeDecorators.  MUST be called inside a transaction before
    any query that touches encrypted or RLS-protected tables.
    """
    from sqlalchemy import text

    await session.execute(
        text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id}
    )
    await session.execute(
        text("SELECT set_config('app.user_role', :role, true)"), {"role": user_role}
    )
    await session.execute(
        text("SELECT set_config('app.encryption_key', :key, true)"),
        {"key": encryption_key},
    )


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yields a session that is automatically committed or rolled back."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
