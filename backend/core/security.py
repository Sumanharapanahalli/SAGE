"""
core/security.py — JWT token creation and verification.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from backend.core.config import get_settings


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {"sub": str(subject), "exp": expire, "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict:
    """
    Decode and verify a JWT.  Raises jose.JWTError on failure.
    """
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


def verify_token(token: str) -> str | None:
    """Return subject (user_id) or None if token is invalid."""
    try:
        payload = decode_access_token(token)
        return payload.get("sub")
    except JWTError:
        return None
