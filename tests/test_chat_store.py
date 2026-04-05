"""Tests for chat conversation persistence store."""
import json
import os
import tempfile

import pytest

from src.stores.chat_store import ChatStore


@pytest.fixture
def store(tmp_path):
    db_path = str(tmp_path / "test_chat.db")
    return ChatStore(db_path)


class TestChatStore:
    def test_create_conversation(self, store: ChatStore):
        conv = store.create("user1", "default", "analyst", "Analyst", [])
        assert conv["id"]
        assert conv["user_id"] == "user1"
        assert conv["solution"] == "default"
        assert conv["role_id"] == "analyst"
        assert conv["title"] == "New conversation"
        assert conv["messages"] == []

    def test_list_conversations(self, store: ChatStore):
        store.create("user1", "sol-a", "analyst", "Analyst", [])
        store.create("user1", "sol-a", "developer", "Developer", [])
        store.create("user2", "sol-a", "analyst", "Analyst", [])

        results = store.list("user1", "sol-a")
        assert len(results) == 2

        results = store.list("user2", "sol-a")
        assert len(results) == 1

    def test_get_conversation(self, store: ChatStore):
        conv = store.create("user1", "default", "analyst", "Analyst", [])
        fetched = store.get(conv["id"])
        assert fetched is not None
        assert fetched["id"] == conv["id"]

    def test_get_nonexistent_returns_none(self, store: ChatStore):
        assert store.get("nonexistent") is None

    def test_update_conversation(self, store: ChatStore):
        conv = store.create("user1", "default", "analyst", "Analyst", [])
        msgs = [{"role": "user", "content": "hello", "id": "m1", "timestamp": 1000}]
        updated = store.update(conv["id"], title="My Chat", messages=msgs)
        assert updated["title"] == "My Chat"
        assert len(updated["messages"]) == 1
        assert updated["messages"][0]["content"] == "hello"

    def test_delete_conversation(self, store: ChatStore):
        conv = store.create("user1", "default", "analyst", "Analyst", [])
        assert store.delete(conv["id"]) is True
        assert store.get(conv["id"]) is None

    def test_delete_nonexistent(self, store: ChatStore):
        assert store.delete("nonexistent") is False

    def test_delete_all_for_user(self, store: ChatStore):
        store.create("user1", "sol-a", "analyst", "Analyst", [])
        store.create("user1", "sol-a", "developer", "Developer", [])
        store.create("user1", "sol-b", "analyst", "Analyst", [])
        count = store.delete_all("user1", "sol-a")
        assert count == 2
        assert len(store.list("user1", "sol-a")) == 0
        assert len(store.list("user1", "sol-b")) == 1

    def test_conversations_ordered_by_updated_at_desc(self, store: ChatStore):
        c1 = store.create("user1", "default", "analyst", "Analyst", [])
        c2 = store.create("user1", "default", "developer", "Developer", [])
        # Update c1 to make it more recent
        store.update(c1["id"], title="Updated first")
        results = store.list("user1", "default")
        assert results[0]["id"] == c1["id"]
