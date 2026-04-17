"""Handler for solution onboarding via the SAGE onboarding wizard.

Thin wrapper over ``src.core.onboarding.generate_solution``. The framework
function does the heavy lifting (LLM generation, YAML validation, disk
write); we validate inputs, forward kwargs, and map framework exceptions
to JSON-RPC error codes the UI already understands.

Error mapping:
    RuntimeError (LLM unavailable) → ``RPC_SIDECAR_ERROR``  (-32000)
    ValueError   (bad YAML / name) → ``RPC_INVALID_PARAMS`` (-32602)
"""
from typing import Any, Optional

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError

# Wired at startup by app._wire_handlers (None when the framework import fails)
_generate_fn: Optional[Any] = None


def generate(params: Any):
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")

    description = params.get("description")
    solution_name = params.get("solution_name")
    if not isinstance(description, str) or not description.strip():
        raise RpcError(RPC_INVALID_PARAMS, "description is required")
    if not isinstance(solution_name, str) or not solution_name.strip():
        raise RpcError(RPC_INVALID_PARAMS, "solution_name is required")

    if _generate_fn is None:
        raise RpcError(
            RPC_SIDECAR_ERROR,
            "onboarding.generate is not wired (SAGE import failed)",
        )

    try:
        return _generate_fn(
            description=description,
            solution_name=solution_name,
            compliance_standards=params.get("compliance_standards") or [],
            integrations=params.get("integrations") or [],
            parent_solution=params.get("parent_solution") or "",
        )
    except ValueError as e:
        raise RpcError(RPC_INVALID_PARAMS, f"invalid onboarding input: {e}") from e
    except RuntimeError as e:
        raise RpcError(RPC_SIDECAR_ERROR, f"LLM unavailable: {e}") from e
