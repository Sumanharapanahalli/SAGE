"""Chat handler — the conversational agent, plus its history.

Routes a message through ``src.core.chat_router`` and persists the exchange in
a solution-scoped ChatStore.

One deliberate divergence from the web API, and it is the important one. The
web's ``POST /chat/execute`` runs a chat-proposed action directly, gated only
by a confirm button in the chat UI. This handler does not port that dispatcher:
when the router returns ``type: "action"``, it persists a REAL ProposalStore
proposal, and the operator decides in the Approvals inbox — same store, same
queue, same audit trail as every other agent proposal (SOUL.md Law 1, matching
analyze.run and agentrun.run).

Safer *and* smaller: ``/chat/execute`` reimplements ~150 lines of action
dispatch that ``proposal_executor`` already owns, so porting it would have put
execution logic in a second place.

Streaming (``/agent/stream``, ``/analyze/stream``) stays deliberately deferred;
``POST /chat`` is the non-streaming path and is what this mirrors.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError

logger = logging.getLogger("sidecar.chat")

# Injected by app._wire_handlers.
_store: Optional[Any] = None  # ChatStore — <solution>/.sage/chat_conversations.db
_proposal_store: Optional[Any] = None  # the same store the Approvals inbox reads
_project: Optional[Any] = None
_solution_name: str = ""

# Test override for src.core.chat_router.route.
_router_fn: Optional[Any] = None

# The desktop is a single-operator app: physical access to the machine is the
# trust boundary, so there is no per-user partitioning to do here.
_USER_ID = "desktop-operator"

# Enough turns for the agent to follow a thread without blowing the context.
_HISTORY_TURNS = 20


def _require_store():
    if _store is None:
        raise RpcError(RPC_SIDECAR_ERROR, "chat store is not wired")
    return _store


def _require_str(params: Any, key: str) -> str:
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RpcError(RPC_INVALID_PARAMS, f"'{key}' is required")
    return value.strip()


def _route(**kwargs) -> dict:
    if _router_fn is not None:
        return _router_fn(**kwargs)
    from src.core.chat_router import route

    return route(**kwargs)


def _domain() -> str:
    try:
        meta = _project.metadata or {} if _project is not None else {}
        return meta.get("domain") or meta.get("project") or ""
    except Exception:  # noqa: BLE001
        return ""


def _history_text(messages: list) -> str:
    """Render prior turns for the router prompt. Without this the agent cannot
    hold a conversation — every message would arrive with no context."""
    lines = []
    for m in messages[-_HISTORY_TURNS:]:
        role = "User" if m.get("role") == "user" else "Assistant"
        lines.append(f"{role}: {m.get('content', '')}")
    return "\n".join(lines) + ("\n" if lines else "")


def _load_conversation(conversation_id: str) -> dict:
    conv = _require_store().get(conversation_id)
    if conv is None:
        raise RpcError(
            RPC_INVALID_PARAMS, f"conversation '{conversation_id}' not found"
        )
    return conv


def send(params: Any) -> dict:
    """Send a message; returns the reply, and a proposal when it is an action."""
    message = _require_str(params, "message")
    page_context = params.get("page_context") or ""
    if not isinstance(page_context, str):
        raise RpcError(RPC_INVALID_PARAMS, "'page_context' must be a string")

    store = _require_store()
    conversation_id = params.get("conversation_id")

    if conversation_id:
        if not isinstance(conversation_id, str):
            raise RpcError(RPC_INVALID_PARAMS, "'conversation_id' must be a string")
        conv = _load_conversation(conversation_id)
        messages = list(conv.get("messages") or [])
    else:
        conv = None
        messages = []

    result = _route(
        message=message,
        solution=_solution_name or "",
        domain=_domain(),
        page_context=page_context,
        history_text=_history_text(messages),
    )
    if not isinstance(result, dict):
        raise RpcError(RPC_SIDECAR_ERROR, "chat router returned a non-dict result")

    reply = str(result.get("reply", ""))
    messages = messages + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": reply},
    ]

    if conv is None:
        conv = store.create(
            _USER_ID,
            _solution_name or "",
            "chat",
            "Chat",
            messages,
        )
        conversation_id = conv["id"]
    else:
        store.update(conversation_id, messages=messages)

    proposal = None
    if result.get("type") == "action":
        proposal = _propose_action(result, message)

    return {
        "conversation_id": conversation_id,
        "reply": reply,
        "type": result.get("type", "answer"),
        "action": result.get("action"),
        "proposal": proposal,
    }


def _propose_action(result: dict, message: str) -> Optional[dict]:
    """Persist a chat-proposed action as a pending proposal.

    Never executes. The web API executes on a chat-UI confirm; here the action
    joins the normal HITL queue so it carries the same audit record as any
    other agent proposal.
    """
    if _proposal_store is None:
        raise RpcError(
            RPC_SIDECAR_ERROR,
            "proposal store is not wired — refusing to drop a chat action",
        )

    from src.core.proposal_store import RiskClass

    action = str(result.get("action") or "unknown")
    summary = str(result.get("reply") or message)[:160]

    proposal = _proposal_store.create(
        action_type="chat_action",
        # STATEFUL, not INFORMATIONAL: a chat action is a request to change
        # something. The executor decides what it touches.
        risk_class=RiskClass.STATEFUL,
        payload={
            "action": action,
            "params": result.get("params") or {},
            "message": message,
            "reply": result.get("reply", ""),
        },
        description=f"Chat action: {action} — {summary}",
        reversible=True,
        proposed_by="chat",
    )
    return proposal.model_dump(mode="json")


def list_conversations(params: Any = None) -> dict:
    store = _require_store()
    return {"conversations": store.list(_USER_ID, _solution_name or "")}


def get_conversation(params: Any) -> dict:
    conversation_id = _require_str(params, "conversation_id")
    return {"conversation": _load_conversation(conversation_id)}


def delete_conversation(params: Any) -> dict:
    conversation_id = _require_str(params, "conversation_id")
    if not _require_store().delete(conversation_id):
        raise RpcError(
            RPC_INVALID_PARAMS, f"conversation '{conversation_id}' not found"
        )
    return {"status": "deleted", "conversation_id": conversation_id}


def clear_history(params: Any = None) -> dict:
    store = _require_store()
    return {"deleted": store.delete_all(_USER_ID, _solution_name or "")}
