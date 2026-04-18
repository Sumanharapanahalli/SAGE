"""Tests for the Knowledge Browser handler.

Uses a fake VectorMemory that mirrors the public shape of
``src.memory.vector_store.VectorMemory`` so the handler is tested
without pulling in ChromaDB / sentence-transformers. One roundtrip
test exercises a real VectorMemory in minimal mode against a tmp
directory.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import handlers.knowledge as knowledge  # noqa: E402
from rpc import RpcError  # noqa: E402


class _FakeVM:
    """Minimal VectorMemory stand-in.

    Stores entries in-memory with uuid ids; ``list_entries`` truncates
    to the given limit; ``search`` does a case-insensitive substring
    match; delete flips a tombstone.
    """

    def __init__(self, solution: str = "demo") -> None:
        self._entries: list[dict] = []
        self._solution = solution
        self.mode = "full"

    def list_entries(self, limit: int = 50) -> list[dict]:
        return self._entries[:limit]

    def search(self, query: str, k: int = 3) -> list[str]:
        q = query.lower()
        hits = [e["text"] for e in self._entries if q in e["text"].lower()]
        return hits[:k]

    def add_entry(self, text: str, metadata: dict | None = None) -> str:
        import uuid

        entry_id = str(uuid.uuid4())
        self._entries.append({"id": entry_id, "text": text, "metadata": metadata or {}})
        return entry_id

    def delete_entry(self, entry_id: str) -> bool:
        before = len(self._entries)
        self._entries = [e for e in self._entries if e["id"] != entry_id]
        return len(self._entries) < before

    def collection_name(self) -> str:
        return f"{self._solution}_knowledge"

    def total(self) -> int:
        return len(self._entries)


@pytest.fixture
def wired(monkeypatch) -> _FakeVM:
    vm = _FakeVM(solution="demo")
    monkeypatch.setattr(knowledge, "_vm", vm)
    monkeypatch.setattr(knowledge, "_solution_name", "demo")
    return vm


def test_list_returns_paginated_slice(wired):
    for i in range(5):
        wired.add_entry(f"entry-{i}")
    out = knowledge.list_entries({"limit": 2, "offset": 1})
    assert [e["text"] for e in out["entries"]] == ["entry-1", "entry-2"]
    assert out["total"] == 5
    assert out["limit"] == 2
    assert out["offset"] == 1


def test_list_defaults_limit_and_offset(wired):
    wired.add_entry("only")
    out = knowledge.list_entries({})
    assert out["limit"] == 50
    assert out["offset"] == 0
    assert out["entries"][0]["text"] == "only"


def test_list_clamps_limit(wired):
    with pytest.raises(RpcError) as e:
        knowledge.list_entries({"limit": 5000})
    assert e.value.code == -32602


def test_list_rejects_non_dict_params(wired):
    with pytest.raises(RpcError):
        knowledge.list_entries("not a dict")


def test_list_fails_when_unwired(monkeypatch):
    monkeypatch.setattr(knowledge, "_vm", None)
    with pytest.raises(RpcError) as e:
        knowledge.list_entries({})
    assert e.value.code == -32000


def test_search_returns_hits(wired):
    wired.add_entry("Vector search is useful")
    wired.add_entry("YAML parsing uses libyaml")
    out = knowledge.search({"query": "vector", "top_k": 5})
    assert out["count"] == 1
    assert out["query"] == "vector"
    assert out["results"][0]["text"] == "Vector search is useful"


def test_search_defaults_top_k(wired):
    wired.add_entry("hit one")
    out = knowledge.search({"query": "hit"})
    assert out["count"] == 1


def test_search_rejects_empty_query(wired):
    with pytest.raises(RpcError) as e:
        knowledge.search({"query": "   "})
    assert e.value.code == -32602


def test_search_clamps_top_k(wired):
    with pytest.raises(RpcError) as e:
        knowledge.search({"query": "x", "top_k": 1000})
    assert e.value.code == -32602


def test_add_returns_id_and_preserves_metadata(wired):
    out = knowledge.add({"text": "Hello world", "metadata": {"source": "manual"}})
    assert isinstance(out["id"], str) and len(out["id"]) > 0
    assert out["text"] == "Hello world"
    assert out["metadata"] == {"source": "manual"}
    assert wired.total() == 1


def test_add_rejects_empty_text(wired):
    with pytest.raises(RpcError):
        knowledge.add({"text": "   "})


def test_add_rejects_non_string_text(wired):
    with pytest.raises(RpcError):
        knowledge.add({"text": 42})


def test_delete_removes_entry_and_reports_true(wired):
    entry_id = wired.add_entry("go away")
    out = knowledge.delete({"id": entry_id})
    assert out == {"id": entry_id, "deleted": True}
    assert wired.total() == 0


def test_delete_reports_false_for_missing_id(wired):
    out = knowledge.delete({"id": "ghost"})
    assert out == {"id": "ghost", "deleted": False}


def test_delete_rejects_empty_id(wired):
    with pytest.raises(RpcError):
        knowledge.delete({"id": ""})


def test_stats_reports_backend_and_total(wired):
    wired.add_entry("a")
    wired.add_entry("b")
    out = knowledge.stats({})
    assert out["total"] == 2
    assert out["backend"] == "full"
    assert out["solution"] == "demo"
    assert out["collection"] == "demo_knowledge"


def test_stats_maps_llamaindex_to_full(wired):
    wired.mode = "llamaindex"
    out = knowledge.stats({})
    # llamaindex is a "full" superset for the UI's purposes.
    assert out["backend"] == "full"


def test_real_vector_memory_roundtrip(tmp_path, monkeypatch):
    """Guard the real VectorMemory contract end-to-end in minimal mode."""
    monkeypatch.setenv("SAGE_MINIMAL", "1")
    # Isolate the vector DB path to tmp_path so repeated runs don't pollute
    # each other (explicit_solution resolves under SAGE_SOLUTIONS_DIR/.sage).
    monkeypatch.setenv("SAGE_SOLUTIONS_DIR", str(tmp_path))
    (tmp_path / "demo").mkdir()
    from src.memory.vector_store import VectorMemory

    vm = VectorMemory(explicit_solution="demo")
    monkeypatch.setattr(knowledge, "_vm", vm)
    monkeypatch.setattr(knowledge, "_solution_name", "demo")

    empty = knowledge.list_entries({})
    assert empty["total"] == 0

    added = knowledge.add({"text": "Remember to test first."})
    assert added["text"] == "Remember to test first."

    listed = knowledge.list_entries({})
    assert listed["total"] == 1

    searched = knowledge.search({"query": "test"})
    assert searched["count"] >= 1
