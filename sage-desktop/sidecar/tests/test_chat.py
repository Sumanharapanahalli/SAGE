"""Tests for the chat handler — conversational agent plus history.

One deliberate divergence from the web API, and it is the important one.

`POST /chat/execute` runs a chat-proposed action directly, gated only by a
confirm button in the chat UI. Desktop does not port that dispatcher. When the
router returns ``type: "action"``, this handler persists a REAL ProposalStore
proposal and the operator decides in the Approvals inbox — the same store,
queue and audit trail as every other agent proposal (SOUL.md Law 1, and the
pattern already used by analyze.run and agentrun.run).

That is both safer and smaller: `/chat/execute` reimplements ~150 lines of
action dispatch that `proposal_executor` already owns, so porting it would
have duplicated execution logic in a second place.
"""

from __future__ import annotations

import pytest

from handlers import chat as chat_handler
from rpc import RpcError

INVALID_PARAMS = -32602
SIDECAR_ERROR = -32000


class FakeProject:
    project_name = "alpha"
    metadata = {"domain": "medical devices"}


@pytest.fixture
def wired(tmp_path, monkeypatch):
    from src.core.proposal_store import ProposalStore
    from src.stores.chat_store import ChatStore

    store = ChatStore(str(tmp_path / "chat.db"))
    proposals = ProposalStore(str(tmp_path / "proposals.db"))

    monkeypatch.setattr(chat_handler, "_store", store)
    monkeypatch.setattr(chat_handler, "_proposal_store", proposals)
    monkeypatch.setattr(chat_handler, "_project", FakeProject())
    monkeypatch.setattr(chat_handler, "_solution_name", "alpha")
    monkeypatch.setattr(
        chat_handler, "_router_fn", lambda **kw: {"type": "answer", "reply": "hello"}
    )
    return {"store": store, "proposals": proposals}


# ---------- send ----------


def test_send_returns_the_reply_and_creates_a_conversation(wired):
    out = chat_handler.send({"message": "hi"})

    assert out["reply"] == "hello"
    assert out["conversation_id"]
    assert wired["store"].get(out["conversation_id"]) is not None


def test_send_appends_to_an_existing_conversation(wired):
    first = chat_handler.send({"message": "hi"})
    second = chat_handler.send(
        {"message": "again", "conversation_id": first["conversation_id"]}
    )

    assert second["conversation_id"] == first["conversation_id"]
    messages = wired["store"].get(first["conversation_id"])["messages"]
    # user + assistant, twice
    assert len(messages) == 4
    assert messages[0]["content"] == "hi"
    assert messages[-1]["content"] == "hello"


def test_send_passes_prior_turns_to_the_router(wired, monkeypatch):
    """Without history the agent cannot hold a conversation."""
    seen = {}

    def spy(**kw):
        seen.update(kw)
        return {"type": "answer", "reply": "ok"}

    first = chat_handler.send({"message": "my name is Sam"})
    monkeypatch.setattr(chat_handler, "_router_fn", spy)
    chat_handler.send(
        {"message": "what is my name?", "conversation_id": first["conversation_id"]}
    )

    assert "my name is Sam" in seen["history_text"]


def test_send_passes_the_solution_and_domain(wired, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        chat_handler,
        "_router_fn",
        lambda **kw: (seen.update(kw), {"type": "answer", "reply": "ok"})[1],
    )
    chat_handler.send({"message": "hi", "page_context": "/approvals"})

    assert seen["solution"] == "alpha"
    assert seen["domain"] == "medical devices"
    assert seen["page_context"] == "/approvals"


@pytest.mark.parametrize("params", [{}, {"message": ""}, {"message": "   "}])
def test_send_requires_a_message(wired, params):
    with pytest.raises(RpcError) as e:
        chat_handler.send(params)
    assert e.value.code == INVALID_PARAMS


def test_send_rejects_an_unknown_conversation(wired):
    with pytest.raises(RpcError) as e:
        chat_handler.send({"message": "hi", "conversation_id": "nope"})
    assert e.value.code == INVALID_PARAMS


# ---------- Law 1: an action becomes a proposal, never a direct execution ----


def test_an_action_creates_a_pending_proposal(wired, monkeypatch):
    monkeypatch.setattr(
        chat_handler,
        "_router_fn",
        lambda **kw: {
            "type": "action",
            "action": "yaml_edit",
            "reply": "I'll update prompts.yaml",
            "params": {"file": "prompts.yaml"},
        },
    )
    out = chat_handler.send({"message": "tweak the analyst prompt"})

    proposal = out["proposal"]
    assert proposal is not None, "an action must be gated by a proposal"
    assert proposal["status"] == "pending"
    # Visible in the SAME inbox as every other proposal.
    pending = wired["proposals"].get_pending()
    assert proposal["trace_id"] in {p.trace_id for p in pending}


def test_the_proposal_carries_the_action_and_its_params(wired, monkeypatch):
    monkeypatch.setattr(
        chat_handler,
        "_router_fn",
        lambda **kw: {
            "type": "action",
            "action": "yaml_edit",
            "reply": "on it",
            "params": {"file": "prompts.yaml"},
        },
    )
    payload = chat_handler.send({"message": "x"})["proposal"]["payload"]

    assert payload["action"] == "yaml_edit"
    assert payload["params"] == {"file": "prompts.yaml"}


def test_an_answer_creates_no_proposal(wired):
    """Only actions are gated — a plain answer must not spam the inbox."""
    out = chat_handler.send({"message": "hi"})
    assert out["proposal"] is None
    assert wired["proposals"].get_pending() == []


# ---------- history ----------


def test_list_conversations_returns_them_newest_first(wired):
    a = chat_handler.send({"message": "first"})["conversation_id"]
    b = chat_handler.send({"message": "second"})["conversation_id"]

    ids = [c["id"] for c in chat_handler.list_conversations({})["conversations"]]
    assert set(ids) == {a, b}


def test_get_conversation_returns_the_messages(wired):
    conv_id = chat_handler.send({"message": "hi"})["conversation_id"]
    out = chat_handler.get_conversation({"conversation_id": conv_id})

    assert out["conversation"]["id"] == conv_id
    assert out["conversation"]["messages"][0]["content"] == "hi"


def test_get_conversation_rejects_an_unknown_id(wired):
    with pytest.raises(RpcError) as e:
        chat_handler.get_conversation({"conversation_id": "nope"})
    assert e.value.code == INVALID_PARAMS


def test_delete_conversation_removes_it(wired):
    conv_id = chat_handler.send({"message": "hi"})["conversation_id"]
    out = chat_handler.delete_conversation({"conversation_id": conv_id})

    assert out["status"] == "deleted"
    assert wired["store"].get(conv_id) is None


def test_clear_history_removes_every_conversation(wired):
    chat_handler.send({"message": "one"})
    chat_handler.send({"message": "two"})

    out = chat_handler.clear_history({})

    assert out["deleted"] == 2
    assert chat_handler.list_conversations({})["conversations"] == []


def test_handlers_error_cleanly_when_unwired(monkeypatch):
    monkeypatch.setattr(chat_handler, "_store", None)
    with pytest.raises(RpcError) as e:
        chat_handler.list_conversations({})
    assert e.value.code == SIDECAR_ERROR
