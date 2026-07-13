"""Regulatory handler — exposes src.core.regulatory_compliance to the desktop.

Distinct from `compliance.py` (which wraps compliance_flags.py — 5 bundled
engineering domains + risk-level flags). This is the multi-standard REGULATORY
framework: a global standards registry (FDA / EU / UK / Canada / Japan / TGA /
IEC / ISO / DO-178C / …), auto-detection of applicable standards from a product
profile, per-standard scoring with artifact gaps, and a phased submission
roadmap.

Like compliance_flags, regulatory_compliance is a stateless singleton over a
static registry — no store to wire at startup, no solution-scoped db_path — so
these handlers import it lazily at call time.

Porting notes vs. the web routes:
  * /regulatory/standards returned a bare JSON array; here it's wrapped as
    {"standards": [...], "total": n} so the RPC result is always an object.
  * get_standard() returns None and generate_gap_analysis()/generate_checklist()
    return {"error": ...} dicts for an unknown standard_id. The web layer turned
    those into HTTP 404; here they become RpcError(RPC_INVALID_PARAMS) rather
    than leaking an error-shaped success result to the UI.
"""
from __future__ import annotations

from typing import List, Optional

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError


def _framework():
    from src.core.regulatory_compliance import regulatory_compliance
    return regulatory_compliance


def _require_product(params: dict) -> dict:
    product = params.get("product")
    if not isinstance(product, dict):
        raise RpcError(RPC_INVALID_PARAMS, "missing or invalid 'product' (expected object)")
    return product


def _require_standard_id(params: dict) -> str:
    standard_id = params.get("standard_id")
    if not standard_id or not isinstance(standard_id, str):
        raise RpcError(RPC_INVALID_PARAMS, "missing or invalid 'standard_id'")
    return standard_id


def _optional_standard_ids(params: dict) -> Optional[List[str]]:
    standard_ids = params.get("standard_ids")
    if standard_ids is None:
        return None
    if not isinstance(standard_ids, list) or not all(isinstance(s, str) for s in standard_ids):
        raise RpcError(RPC_INVALID_PARAMS, "'standard_ids' must be a list of strings")
    # An explicitly empty list means "auto-detect" — otherwise the operator
    # would get a zero-standard assessment with a meaningless 0.0 score.
    return standard_ids or None


def standards(params: dict) -> dict:
    try:
        result = _framework().list_standards()
        return {"standards": result, "total": len(result)}
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"regulatory.standards failed: {e}") from e


def standard(params: dict) -> dict:
    try:
        standard_id = _require_standard_id(params)
        result = _framework().get_standard(standard_id)
        if not result:
            raise RpcError(RPC_INVALID_PARAMS, f"unknown standard '{standard_id}'")
        return result
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"regulatory.standard failed: {e}") from e


def assess(params: dict) -> dict:
    """Score a product profile against explicit or auto-detected standards."""
    try:
        product = _require_product(params)
        standard_ids = _optional_standard_ids(params)
        return _framework().assess_compliance(product=product, standard_ids=standard_ids)
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"regulatory.assess failed: {e}") from e


def gap_analysis(params: dict) -> dict:
    try:
        product = _require_product(params)
        standard_id = _require_standard_id(params)
        result = _framework().generate_gap_analysis(product=product, standard_id=standard_id)
        if "error" in result:
            raise RpcError(RPC_INVALID_PARAMS, result["error"])
        return result
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"regulatory.gap_analysis failed: {e}") from e


def checklist(params: dict) -> dict:
    try:
        standard_id = _require_standard_id(params)
        result = _framework().generate_checklist(standard_id)
        if "error" in result:
            raise RpcError(RPC_INVALID_PARAMS, result["error"])
        return result
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"regulatory.checklist failed: {e}") from e


def roadmap(params: dict) -> dict:
    try:
        product = _require_product(params)
        return _framework().generate_submission_roadmap(product)
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"regulatory.roadmap failed: {e}") from e
