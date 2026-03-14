"""
SAGE Framework — Multi-Tenant Context
=======================================
Provides request-scoped tenant isolation when multiple teams share one
SAGE instance. Each tenant maps to a separate solution namespace:
  - vector store collection: <tenant>_knowledge
  - audit log filter: tenant column in SQLite
  - task queue: tagged with tenant_id

Usage (FastAPI dependency):
    from src.core.tenant import get_tenant_id
    @app.post("/analyze")
    async def analyze(tenant: str = Depends(get_tenant_id)):
        ...

Header: X-SAGE-Tenant (optional)
  - If present: use this value as tenant_id
  - If absent:  use the active solution name (backwards-compatible default)

The tenant ID is a simple string (e.g., "medtech", "team_alpha").
It is injected into:
  - Vector store collection naming (via VectorMemory._get_collection_name())
  - Audit log rows (metadata.tenant_id)
  - Task queue submissions (payload.tenant_id)
"""

import contextvars
import logging
from fastapi import Request

logger = logging.getLogger("Tenant")

# Per-request context variable — set at request boundary, read anywhere
_current_tenant: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_tenant", default=""
)


def get_current_tenant() -> str:
    """
    Return the tenant ID for the current request context.
    Falls back to the active solution name when no tenant header is present.
    """
    tenant = _current_tenant.get("")
    if tenant:
        return tenant
    # Fallback: active solution name
    try:
        from src.core.project_loader import project_config
        return project_config.project_name or "default"
    except Exception:
        return "default"


def set_tenant(tenant_id: str) -> None:
    """Set the tenant ID for the current execution context."""
    _current_tenant.set(tenant_id)


async def get_tenant_id(request: Request) -> str:
    """
    FastAPI dependency that extracts X-SAGE-Tenant header and sets context.
    Returns the resolved tenant ID.
    """
    header_tenant = request.headers.get("X-SAGE-Tenant", "").strip()
    if header_tenant:
        _current_tenant.set(header_tenant)
        return header_tenant
    # No header — use active solution (backwards-compatible)
    return get_current_tenant()


def tenant_scoped_collection(base_collection: str = None) -> str:
    """
    Return a tenant-scoped vector collection name.
    If base_collection is provided, returns "<tenant>_<base>".
    Otherwise returns "<tenant>_knowledge".
    """
    tenant = get_current_tenant()
    if base_collection:
        return f"{tenant}_{base_collection}"
    return f"{tenant}_knowledge"
