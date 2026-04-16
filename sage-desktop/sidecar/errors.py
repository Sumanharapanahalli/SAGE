"""Central mapping of SAGE/SQLite exceptions to JSON-RPC error codes.

Handlers raise these directly rather than constructing RpcError ad-hoc so
that error codes stay consistent between modules and match the Rust
`DesktopError::from_rpc` mapper on the other end of the pipe.
"""
from __future__ import annotations

from rpc import (
    RpcError,
    RPC_PROPOSAL_NOT_FOUND,
    RPC_PROPOSAL_EXPIRED,
    RPC_ALREADY_DECIDED,
    RPC_RBAC_DENIED,
    RPC_SOLUTION_UNAVAILABLE,
    RPC_SAGE_IMPORT_ERROR,
)


class ProposalNotFound(RpcError):
    def __init__(self, trace_id: str) -> None:
        super().__init__(
            RPC_PROPOSAL_NOT_FOUND,
            f"proposal not found: {trace_id}",
            {"trace_id": trace_id},
        )


class ProposalExpired(RpcError):
    def __init__(self, trace_id: str) -> None:
        super().__init__(
            RPC_PROPOSAL_EXPIRED,
            f"proposal expired: {trace_id}",
            {"trace_id": trace_id},
        )


class AlreadyDecided(RpcError):
    def __init__(self, trace_id: str, status: str) -> None:
        super().__init__(
            RPC_ALREADY_DECIDED,
            f"proposal already {status}: {trace_id}",
            {"trace_id": trace_id, "status": status},
        )


class RbacDenied(RpcError):
    def __init__(self, required_role: str) -> None:
        super().__init__(
            RPC_RBAC_DENIED,
            f"RBAC: role required: {required_role}",
            {"required_role": required_role},
        )


class SolutionUnavailable(RpcError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            RPC_SOLUTION_UNAVAILABLE,
            f"solution unavailable: {detail}",
            {"detail": detail},
        )


class SageImportError(RpcError):
    def __init__(self, module: str, detail: str) -> None:
        super().__init__(
            RPC_SAGE_IMPORT_ERROR,
            f"cannot import {module}: {detail}",
            {"module": module, "detail": detail},
        )
