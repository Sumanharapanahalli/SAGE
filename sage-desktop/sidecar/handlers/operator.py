"""Operator identity — the desktop's signer record.

Why this exists instead of a port of web's AccessControl page:

`src/core/auth.py::get_current_user()` needs a FastAPI Request, an
Authorization bearer JWT or X-API-Key header, and a JWKS fetch against the
issuer's discovery endpoint. The sidecar is a stdin/stdout pipe: there is no
request, no headers, and no browser redirect. OIDC is structurally
unreachable here, and web's API keys and user roles gate the FastAPI HTTP
surface that the desktop app deliberately does not run — administering them
from desktop would configure a deployment the operator cannot reach.

What IS real is the signer. `ProposalStore.approve/reject` and
`AuditLogger.log_event` both carry named-approval fields, and 21 CFR Part 11
§11.50 requires a signed record to name its signer. So the desktop resolves
one operator identity, sidecar-side, from a per-solution operator.yaml.

Two properties matter and are load-bearing:

  * The identity is resolved HERE, never accepted as an RPC parameter. A
    renderer-supplied signer would be a forgeable signature.
  * `provider` is always "desktop-operator" and never "oidc". This satisfies
    §11.50 (signed records) but NOT §11.100 (identity verification), and the
    audit record must not overclaim.

Law 1: `operator.set` is framework control (the operator naming themselves),
not an agent proposal — it executes immediately.
"""

from __future__ import annotations

import logging

import yaml

from rpc import RpcError, RPC_INVALID_PARAMS

logger = logging.getLogger("sidecar.operator")

# Injected by app._wire_handlers. <solution>/.sage/operator.yaml
_path = None  # type: Optional[Path]

PROVIDER = "desktop-operator"


def _blank() -> dict:
    return {"name": "", "email": "", "provider": PROVIDER}


def get(_params: dict) -> dict:
    """Return the operator identity. Never raises — an unset identity is a
    valid state (the UI prompts for it; approvals fall back to 'operator')."""
    if _path is None or not _path.exists():
        return _blank()
    try:
        data = yaml.safe_load(_path.read_text(encoding="utf-8")) or {}
    except Exception as e:  # noqa: BLE001
        logger.warning("operator.yaml unreadable (%s) — treating as unset", e)
        return _blank()
    if not isinstance(data, dict):
        return _blank()
    return {
        "name": str(data.get("name", "") or ""),
        "email": str(data.get("email", "") or ""),
        # Pinned, not read from disk: a hand-edited operator.yaml must not be
        # able to promote itself to provider "oidc" in the audit record.
        "provider": PROVIDER,
    }


def set(params: dict) -> dict:
    """Set the operator identity. `name` is required — an unnamed signer is
    the defect this handler exists to fix."""
    if _path is None:
        raise RpcError(
            RPC_INVALID_PARAMS, "no active solution — cannot set operator identity"
        )

    name = str(params.get("name", "") or "").strip()
    email = str(params.get("email", "") or "").strip()
    if not name:
        raise RpcError(
            RPC_INVALID_PARAMS, "'name' is required — the audit signer cannot be blank"
        )

    _path.parent.mkdir(parents=True, exist_ok=True)
    _path.write_text(
        yaml.safe_dump({"name": name, "email": email}, sort_keys=False),
        encoding="utf-8",
    )
    return {"name": name, "email": email, "provider": PROVIDER}


def current() -> dict:
    """Internal accessor for other handlers (approvals) to sign records with.

    Falls back to a generic "operator" rather than failing the decision: a
    decision that is recorded with a weak signer is far better than a decision
    that is lost because the operator never filled in a settings field.
    """
    ident = get({})
    if not ident["name"]:
        ident["name"] = "operator"
    return ident
