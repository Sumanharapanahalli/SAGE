"""
SAGE Authentication — JWT (OIDC) + API key fallback.

When auth.enabled is false (default):
  - optional_auth returns None
  - get_current_user returns an anonymous UserIdentity with role="admin"
    so all existing endpoints continue to work without any change.

Supported OIDC providers: Okta, Azure AD, Google Workspace (standard OIDC).
JWT library: python-jose[cryptography]
"""

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

from fastapi import Request

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# UserIdentity
# ---------------------------------------------------------------------------

@dataclass
class UserIdentity:
    sub:      str           # unique subject ID
    email:    str
    name:     str
    role:     str           # resolved via RBAC lookup
    provider: str           # "oidc" | "api_key" | "anonymous"


_ANONYMOUS = UserIdentity(
    sub="anonymous",
    email="anonymous@sage.local",
    name="Anonymous",
    role="admin",           # when auth disabled, allow everything
    provider="anonymous",
)


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _auth_config() -> dict:
    """Return the auth section from config.yaml. Cached for the process lifetime."""
    try:
        import yaml
        cfg_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "config", "config.yaml",
        )
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("auth", {})
    except Exception as exc:
        logger.warning("Could not read auth config: %s", exc)
        return {}


def _auth_enabled() -> bool:
    return bool(_auth_config().get("enabled", False))


def _active_solution() -> str:
    try:
        from src.core.project_loader import project_config
        return project_config.project_name
    except Exception:
        return os.environ.get("SAGE_PROJECT", "default")


# ---------------------------------------------------------------------------
# JWKS cache (1-hour TTL)
# ---------------------------------------------------------------------------

_jwks_cache: dict = {"keys": None, "fetched_at": 0.0, "issuer": ""}
_JWKS_TTL = 3600  # seconds


def _get_jwks(issuer_url: str) -> dict:
    """Fetch and cache the JWKS from the OIDC discovery endpoint."""
    now = time.time()
    if (
        _jwks_cache["keys"] is not None
        and _jwks_cache["issuer"] == issuer_url
        and now - _jwks_cache["fetched_at"] < _JWKS_TTL
    ):
        return _jwks_cache["keys"]

    import httpx
    url = f"{issuer_url.rstrip('/')}/.well-known/jwks.json"
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        jwks = resp.json()
        _jwks_cache["keys"] = jwks
        _jwks_cache["fetched_at"] = now
        _jwks_cache["issuer"] = issuer_url
        logger.debug("JWKS refreshed from %s", url)
        return jwks
    except Exception as exc:
        logger.error("Failed to fetch JWKS from %s: %s", url, exc)
        raise


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------

async def verify_token(token: str) -> Optional[UserIdentity]:
    """
    Verify a Bearer token.

    - If it starts with 'sk-sage-': treat as API key.
    - Otherwise: decode as JWT against the configured OIDC issuer.

    Returns UserIdentity on success, None on failure.
    """
    from src.core.api_keys import verify_api_key

    if token.startswith("sk-sage-"):
        identity = verify_api_key(token)
        if identity is None:
            logger.warning("Invalid or revoked API key presented")
        return identity

    # JWT path
    auth_cfg = _auth_config()
    oidc = auth_cfg.get("oidc", {})
    issuer_url = oidc.get("issuer_url", "")
    audience   = oidc.get("audience", "")

    if not issuer_url:
        logger.warning("JWT received but auth.oidc.issuer_url is not configured")
        return None

    try:
        from jose import jwt, JWTError, ExpiredSignatureError
        jwks = _get_jwks(issuer_url)
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
            audience=audience or None,
            issuer=issuer_url,
            options={"verify_at_hash": False},
        )
    except ExpiredSignatureError:
        logger.warning("JWT expired")
        return None
    except Exception as exc:
        logger.warning("JWT decode failed: %s", exc)
        return None

    email = payload.get("email") or payload.get("upn") or ""
    name  = payload.get("name") or payload.get("preferred_username") or email
    sub   = payload.get("sub", "")

    solution = _active_solution()
    from src.core.rbac import get_user_role
    role = get_user_role(email, solution).value

    return UserIdentity(
        sub=sub,
        email=email,
        name=name,
        role=role,
        provider="oidc",
    )


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

async def get_current_user(request: Request) -> UserIdentity:
    """
    FastAPI dependency — returns authenticated UserIdentity.

    When auth is disabled returns the anonymous admin identity so all
    existing endpoints continue to work without modification.
    """
    if not _auth_enabled():
        return _ANONYMOUS

    from fastapi import HTTPException
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")

    token = auth_header[len("Bearer "):]
    identity = await verify_token(token)
    if identity is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return identity


async def optional_auth(request: Request) -> Optional[UserIdentity]:
    """
    FastAPI dependency — returns UserIdentity when auth is enabled and a
    valid token is present, otherwise returns None.
    """
    if not _auth_enabled():
        return None

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[len("Bearer "):]
    return await verify_token(token)
