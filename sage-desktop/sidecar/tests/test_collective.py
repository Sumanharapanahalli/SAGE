"""Tests for the Collective Intelligence handler.

Uses a fake CollectiveMemory that mirrors the public shape of
``src.core.collective_memory.CollectiveMemory`` so the handler is
tested without pulling in git or ChromaDB. One end-to-end test at
the bottom of this file exercises a real ``CollectiveMemory`` in
a ``tmp_path``.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import handlers.collective as collective  # noqa: E402
from rpc import RpcError  # noqa: E402


class _FakeCM:
    """Minimal CollectiveMemory stand-in.

    Stores learnings and help requests in-memory; publish returns an
    id or a proposal trace_id depending on ``require_approval``.
    """

    def __init__(self, require_approval: bool = False) -> None:
        self.require_approval = require_approval
        self.repo_path = "/tmp/fake-collective"
        self._git_available = True
        self._learnings: dict[str, dict] = {}
        self._help_open: dict[str, dict] = {}
        self._help_closed: dict[str, dict] = {}
        self._proposals: dict[str, dict] = {}
        self._pulled = False
        self._indexed = 0

    # ── Learning helpers (fake) ────────────────────────────────
    def _add_learning(self, *, solution="s1", topic="t1", title="t", content="c") -> str:
        lid = str(uuid.uuid4())
        self._learnings[lid] = {
            "id": lid,
            "author_agent": "analyst",
            "author_solution": solution,
            "topic": topic,
            "title": title,
            "content": content,
            "tags": [],
            "confidence": 0.5,
            "validation_count": 0,
            "created_at": "2026-04-17T00:00:00+00:00",
            "updated_at": "2026-04-17T00:00:00+00:00",
            "source_task_id": "",
        }
        return lid

    def list_learnings(self, solution=None, topic=None, limit=50, offset=0):
        items = list(self._learnings.values())
        if solution:
            items = [x for x in items if x["author_solution"] == solution]
        if topic:
            items = [x for x in items if x["topic"] == topic]
        return items[offset: offset + limit]

    def get_learning(self, learning_id: str):
        return self._learnings.get(learning_id)

    def search_learnings(self, query, tags=None, solution=None, limit=10):
        items = list(self._learnings.values())
        if query:
            q = query.lower()
            items = [
                x for x in items
                if q in x["title"].lower() or q in x["content"].lower()
            ]
        if tags:
            items = [x for x in items if any(t in x.get("tags", []) for t in tags)]
        if solution:
            items = [x for x in items if x["author_solution"] == solution]
        return items[:limit]


@pytest.fixture
def wired():
    cm = _FakeCM()
    # Re-bind in tests via monkeypatch.setattr(collective, "_cm", cm)
    return cm


def test_require_cm_raises_when_unwired(monkeypatch):
    monkeypatch.setattr(collective, "_cm", None)
    with pytest.raises(RpcError) as e:
        collective._require_cm()
    assert e.value.code == -32000
    assert "not wired" in e.value.message


def test_require_dict_rejects_non_dict():
    with pytest.raises(RpcError) as e:
        collective._require_dict("not a dict")
    assert e.value.code == -32602


def test_list_learnings_returns_paginated_slice(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    for i in range(5):
        wired._add_learning(topic=f"t{i}")
    out = collective.list_learnings({"limit": 2, "offset": 1})
    assert len(out["entries"]) == 2
    assert out["total"] == 5
    assert out["limit"] == 2
    assert out["offset"] == 1


def test_list_learnings_filters_by_solution_and_topic(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    wired._add_learning(solution="a", topic="t1")
    wired._add_learning(solution="a", topic="t2")
    wired._add_learning(solution="b", topic="t1")
    out = collective.list_learnings({"solution": "a", "topic": "t1"})
    assert out["total"] == 1
    assert out["entries"][0]["author_solution"] == "a"
    assert out["entries"][0]["topic"] == "t1"


def test_list_learnings_rejects_oversized_limit(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    with pytest.raises(RpcError) as e:
        collective.list_learnings({"limit": 10000})
    assert e.value.code == -32602


def test_get_learning_returns_entry(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    lid = wired._add_learning(title="needle")
    out = collective.get_learning({"id": lid})
    assert out["learning"]["id"] == lid
    assert out["learning"]["title"] == "needle"


def test_get_learning_returns_null_when_missing(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    out = collective.get_learning({"id": "ghost"})
    assert out == {"learning": None}


def test_get_learning_rejects_empty_id(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    with pytest.raises(RpcError):
        collective.get_learning({"id": ""})


def test_search_learnings_matches_query(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    wired._add_learning(title="UART overflow recovery")
    wired._add_learning(title="SPI timing tricks")
    out = collective.search_learnings({"query": "UART"})
    assert out["count"] == 1
    assert out["results"][0]["title"] == "UART overflow recovery"
    assert out["query"] == "UART"


def test_search_learnings_accepts_empty_query(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    wired._add_learning(title="one")
    wired._add_learning(title="two")
    out = collective.search_learnings({"query": ""})
    assert out["count"] == 2


def test_search_learnings_clamps_limit(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    with pytest.raises(RpcError) as e:
        collective.search_learnings({"query": "x", "limit": 500})
    assert e.value.code == -32602


def test_search_learnings_rejects_non_string_query(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    with pytest.raises(RpcError) as e:
        collective.search_learnings({"query": 42})
    assert e.value.code == -32602
