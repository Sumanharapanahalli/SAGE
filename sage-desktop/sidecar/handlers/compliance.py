"""Compliance handler — exposes src.core.compliance_flags to the desktop.

Phase 5 gap: the audit LOG (audit.*) was already on desktop — the
tamper-evident record of what happened. This handler adds the periodic
ASSESSMENT tooling (domain checklists, gap assessment against IEC 62304 /
21 CFR Part 11 / ISO 26262 / etc.) so a compliance operator can check
conformance, not just retrieve evidence after the fact.

Unlike every other handler, compliance_flags.py is a pure, stateless module
(a static domain -> requirements dict + pure functions over it) — there is
no store/instance to wire at startup, so these handlers import it directly
at call time rather than reading an injected module-level variable.
"""
from __future__ import annotations

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError


def _require_domain(params: dict, valid_domains: list) -> str:
    domain = params.get("domain")
    if not domain or not isinstance(domain, str):
        raise RpcError(RPC_INVALID_PARAMS, "missing or invalid 'domain'")
    if domain.lower() not in valid_domains:
        raise RpcError(
            RPC_INVALID_PARAMS,
            f"unknown domain '{domain}'. Valid domains: {valid_domains}",
        )
    return domain


def domains(params: dict) -> dict:
    try:
        from src.core.compliance_flags import COMPLIANCE_FLAGS
        result = []
        for domain, entry in COMPLIANCE_FLAGS.items():
            result.append({
                "domain":           domain,
                "standard":         entry.get("standard", ""),
                "description":      entry.get("description", ""),
                "authority":        entry.get("authority", ""),
                "risk_levels":      entry.get("risk_levels", []),
                "hil_required_for": entry.get("hil_required_for", []),
            })
        return {"domains": result}
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"compliance.domains failed: {e}") from e


def flags(params: dict) -> dict:
    try:
        from src.core.compliance_flags import (
            COMPLIANCE_FLAGS, get_required_flags, get_hil_required_tests, list_domains,
        )
        domain = _require_domain(params, list_domains())
        risk_level = params.get("risk_level", "HIGH")
        req_flags = get_required_flags(domain, risk_level)
        hil_tests = get_hil_required_tests(domain, risk_level)
        entry = COMPLIANCE_FLAGS[domain.lower()]
        return {
            "domain":                domain,
            "risk_level":            risk_level.upper(),
            "standard":              entry.get("standard", ""),
            "description":           entry.get("description", ""),
            "authority":             entry.get("authority", ""),
            "flags":                 req_flags,
            "hil_required_flag_ids": hil_tests,
            "total_flags":           len(req_flags),
        }
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"compliance.flags failed: {e}") from e


def checklist(params: dict) -> dict:
    try:
        from src.core.compliance_flags import generate_compliance_checklist, list_domains
        domain = _require_domain(params, list_domains())
        risk_level = params.get("risk_level", "HIGH")
        return generate_compliance_checklist(domain, risk_level)
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"compliance.checklist failed: {e}") from e


def gap_assessment(params: dict) -> dict:
    try:
        from src.core.compliance_flags import assess_compliance_gap, list_domains
        risk_level = params.get("risk_level")
        if not risk_level or not isinstance(risk_level, str):
            raise RpcError(RPC_INVALID_PARAMS, "missing or invalid 'risk_level'")
        domain = _require_domain(params, list_domains())
        completed_tasks = params.get("completed_tasks", [])
        if not isinstance(completed_tasks, list):
            raise RpcError(RPC_INVALID_PARAMS, "'completed_tasks' must be a list")
        return assess_compliance_gap(domain, risk_level, completed_tasks)
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"compliance.gap_assessment failed: {e}") from e
