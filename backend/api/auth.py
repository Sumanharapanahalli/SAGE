"""
api/auth.py — FastAPI security dependencies.

All protected routes use Depends(get_current_user).
Returns 401 WWW-Authenticate: Bearer for missing/invalid tokens.
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from backend.core.security import verify_token
from backend.services.user_store import UserStore, get_user_store

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    store: Annotated[UserStore, Depends(get_user_store)],
) -> dict:
    """
    Validate JWT and return user dict.
    Raises HTTP 401 on any auth failure.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user_id = verify_token(token)
    if user_id is None:
        raise credentials_exception

    user = store.get_user(user_id)
    if user is None:
        logger.warning("JWT references unknown user_id=%s", user_id)
        raise credentials_exception
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )
    return user


async def require_admin(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user
