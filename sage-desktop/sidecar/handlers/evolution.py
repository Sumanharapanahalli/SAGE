"""Handler for agent-gym (evolution) RPCs.

Thin wrapper over ``src.core.agent_gym.AgentGym``. The gym does the
heavy lifting (Glicko-2 updates, SQLite persistence, LLM-driven
training). We validate inputs, forward kwargs, and map gym exceptions
to JSON-RPC error codes.

Error mapping:
    RuntimeError (LLM unavailable)     → ``RPC_SIDECAR_ERROR``  (-32000)
    ValueError   (bad role/difficulty) → ``RPC_INVALID_PARAMS`` (-32602)
"""
from typing import Any, Optional

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError

# Wired at startup by app._wire_handlers (None when AgentGym import fails).
_gym: Optional[Any] = None


def _require_gym() -> Any:
    if _gym is None:
        raise RpcError(
            RPC_SIDECAR_ERROR,
            "evolution handlers are not wired (AgentGym import failed)",
        )
    return _gym


def leaderboard(params: Any):
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    gym = _require_gym()
    rows = list(gym.get_leaderboard())
    total_sessions = sum(int(r.get("sessions", 0)) for r in rows)
    total_agents = len(rows)
    avg_rating = (
        sum(float(r.get("rating", 0.0)) for r in rows) / total_agents
        if total_agents
        else 0.0
    )
    return {
        "leaderboard": rows,
        "stats": {
            "total_agents": total_agents,
            "total_sessions": total_sessions,
            "avg_rating": round(avg_rating, 2),
        },
    }


def history(params: Any):
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    limit_raw = params.get("limit", 50)
    try:
        limit = int(limit_raw)
    except (TypeError, ValueError):
        raise RpcError(RPC_INVALID_PARAMS, "limit must be an integer")
    if limit <= 0:
        raise RpcError(RPC_INVALID_PARAMS, "limit must be positive")
    gym = _require_gym()
    return {"sessions": list(gym.get_history(limit=limit))}


def analytics(params: Any):
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    role = params.get("role", "")
    skill = params.get("skill", "")
    if role is not None and not isinstance(role, str):
        raise RpcError(RPC_INVALID_PARAMS, "role must be a string")
    if skill is not None and not isinstance(skill, str):
        raise RpcError(RPC_INVALID_PARAMS, "skill must be a string")
    gym = _require_gym()
    return gym.analytics(role=role or "", skill=skill or "")


def train(params: Any):
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    role = params.get("role")
    if not isinstance(role, str) or not role.strip():
        raise RpcError(RPC_INVALID_PARAMS, "role is required")
    difficulty = params.get("difficulty") or ""
    skill_name = params.get("skill_name") or ""
    exercise_id = params.get("exercise_id") or ""
    gym = _require_gym()
    try:
        session = gym.train(
            role=role,
            difficulty=difficulty,
            skill_name=skill_name,
            exercise_id=exercise_id,
        )
    except ValueError as e:
        raise RpcError(RPC_INVALID_PARAMS, f"invalid training params: {e}") from e
    except RuntimeError as e:
        raise RpcError(RPC_SIDECAR_ERROR, f"gym unavailable: {e}") from e
    if hasattr(session, "to_dict"):
        session = session.to_dict()
    return session
