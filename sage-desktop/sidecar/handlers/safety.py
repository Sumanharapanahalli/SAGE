"""Safety handler — exposes src.core.functional_safety to the desktop.

Complements the compliance handler rather than duplicating it: /compliance
takes the safety class as an INPUT (which checklist do I owe for CLASS_C?),
whereas this DERIVES it (what class/ASIL/SIL does this hazard imply?).

Like compliance_flags.py, functional_safety.py is a stateless, stdlib-only
singleton (deterministic computation engines — no LLM, no store, no db_path),
so there is nothing to wire at startup: these handlers import the module at
call time rather than reading an injected module-level variable.

Contract note (load-bearing): the FTA engine keys probability off
``"probability"`` and cut sets off ``"event"`` — a leaf node must carry BOTH
or one of the two results silently degrades (0.0 probability / [] cut sets).
"""

from __future__ import annotations

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError

_FMEA_FIELDS = ("component", "failure_mode", "effect")
_FMEA_SCORES = ("severity", "occurrence", "detection")


def _engine():
    from src.core.functional_safety import functional_safety

    return functional_safety


def _require_str(params: dict, key: str) -> str:
    val = params.get(key)
    if not val or not isinstance(val, str):
        raise RpcError(RPC_INVALID_PARAMS, f"missing or invalid '{key}'")
    return val


def _validate_entry(entry, idx: int) -> dict:
    if not isinstance(entry, dict):
        raise RpcError(RPC_INVALID_PARAMS, f"entries[{idx}] must be an object")
    clean = {}
    for field in _FMEA_FIELDS:
        val = entry.get(field, "")
        if not isinstance(val, str):
            raise RpcError(
                RPC_INVALID_PARAMS, f"entries[{idx}].{field} must be a string"
            )
        clean[field] = val
    for field in _FMEA_SCORES:
        val = entry.get(field)
        if isinstance(val, bool) or not isinstance(val, int):
            raise RpcError(
                RPC_INVALID_PARAMS, f"entries[{idx}].{field} must be an integer 1-10"
            )
        clean[field] = val
    return clean


def fmea(params: dict) -> dict:
    """Compute the FMEA table (RPN, risk level, action items) — sorted by RPN."""
    entries = params.get("entries")
    if not isinstance(entries, list) or not entries:
        raise RpcError(RPC_INVALID_PARAMS, "'entries' must be a non-empty list")
    clean = [_validate_entry(e, i) for i, e in enumerate(entries)]
    try:
        return _engine().generate_fmea_table(clean)
    except ValueError as e:  # severity/occurrence/detection out of the 1-10 range
        raise RpcError(RPC_INVALID_PARAMS, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"safety.fmea failed: {e}") from e


def fta(params: dict) -> dict:
    """Compute fault-tree probability + minimal cut sets from a nested tree.

    Tree: {"top_event": str, "gate": "AND"|"OR", "children": [...]} where a
    child is either a nested gate or a leaf {"event": str, "probability": float}.
    """
    tree = params.get("tree")
    if not isinstance(tree, dict) or not tree:
        raise RpcError(RPC_INVALID_PARAMS, "'tree' must be a non-empty object")
    try:
        return _engine().calculate_fta(tree)
    except RpcError:
        raise
    except (TypeError, KeyError) as e:
        raise RpcError(RPC_INVALID_PARAMS, f"malformed fault tree: {e}") from e
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"safety.fta failed: {e}") from e


def asil(params: dict) -> dict:
    """Derive the ISO 26262 ASIL from severity x exposure x controllability."""
    severity = _require_str(params, "severity")
    exposure = _require_str(params, "exposure")
    controllability = _require_str(params, "controllability")
    try:
        return _engine().classify_asil(severity, exposure, controllability)
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"safety.asil failed: {e}") from e


def sil(params: dict) -> dict:
    """Derive the IEC 61508 SIL from the dangerous-failure probability per hour."""
    pfh = params.get("probability_dangerous_failure_per_hour")
    if isinstance(pfh, bool) or not isinstance(pfh, (int, float)):
        raise RpcError(
            RPC_INVALID_PARAMS,
            "'probability_dangerous_failure_per_hour' must be a number",
        )
    if pfh < 0:
        raise RpcError(
            RPC_INVALID_PARAMS,
            "'probability_dangerous_failure_per_hour' must be >= 0",
        )
    try:
        return _engine().classify_sil(float(pfh))
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"safety.sil failed: {e}") from e


def iec62304(params: dict) -> dict:
    """Derive the IEC 62304 software safety class (A/B/C) from the risk level."""
    risk_level = _require_str(params, "risk_level")
    try:
        return _engine().classify_iec62304(risk_level)
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"safety.iec62304 failed: {e}") from e
