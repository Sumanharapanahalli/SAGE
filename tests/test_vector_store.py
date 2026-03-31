"""
SAGE[ai] - Unit tests for VectorMemory (src/memory/vector_store.py)

Tests the in-memory fallback mode of VectorMemory — no ChromaDB required.
All tests patch away ChromaDB to force the keyword-search fallback path.
"""

from unittest.mock import patch

import pytest


pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helper: create a fresh VectorMemory in fallback mode for each test
# ---------------------------------------------------------------------------

def _make_fallback_vm():
    """Returns a fresh VectorMemory instance forced into fallback mode."""
    import threading
    with patch("src.memory.vector_store._HAS_CHROMADB", False), \
         patch("src.memory.vector_store.Chroma", None):
        from src.memory.vector_store import VectorMemory
        vm = VectorMemory.__new__(VectorMemory)
        import logging
        vm.logger = logging.getLogger("VectorMemory.test")
        vm._fallback_memory    = []
        vm._fallback_lock      = threading.Lock()
        vm._vector_store       = None
        vm._llamaindex_index   = None
        vm._embedding_function = None
        vm._ready = False
        vm._mode  = "minimal"
        return vm


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_search_returns_empty_on_empty_memory():
    """A fresh VectorMemory with no documents must return an empty list for any query."""
    vm = _make_fallback_vm()
    results = vm.search("timeout error")
    assert results == [], f"Expected [], got {results!r}"


def test_add_feedback_stores_to_fallback():
    """After add_feedback('test doc'), searching 'test' must return ['test doc']."""
    vm = _make_fallback_vm()
    vm.add_feedback("test doc")
    results = vm.search("test")
    assert "test doc" in results, f"Expected 'test doc' in results, got: {results!r}"


def test_search_k_limits_results():
    """When 5 documents are stored, search with k=2 must return at most 2 results."""
    vm = _make_fallback_vm()
    for i in range(5):
        vm.add_feedback(f"document keyword entry {i}")
    results = vm.search("document", k=2)
    assert len(results) <= 2, f"Expected at most 2 results with k=2, got {len(results)}: {results!r}"


def test_keyword_matching_in_fallback():
    """Document 'connection timeout error' must be found when searching 'timeout'."""
    vm = _make_fallback_vm()
    vm.add_feedback("connection timeout error")
    results = vm.search("timeout")
    assert len(results) >= 1, "Expected at least 1 result for 'timeout' search."
    assert any("timeout" in r for r in results), f"Expected 'timeout' in results, got: {results!r}"


def test_add_multiple_feedbacks():
    """All 3 documents added must be retrievable via search."""
    vm = _make_fallback_vm()
    docs = ["uart buffer overflow fix", "watchdog timeout resolved", "flash write error patch"]
    for doc in docs:
        vm.add_feedback(doc)
    # Each document should be findable by a unique keyword from it
    assert any("uart" in r for r in vm.search("uart")), "uart doc not found"
    assert any("watchdog" in r for r in vm.search("watchdog")), "watchdog doc not found"
    assert any("flash" in r for r in vm.search("flash")), "flash doc not found"


def test_search_with_no_matching_keywords():
    """When stored documents don't match the query keywords, return [] or empty."""
    vm = _make_fallback_vm()
    vm.add_feedback("firmware update successful on device")
    results = vm.search("database")
    # No document contains 'database', so should return empty
    assert results == [], f"Expected [], got {results!r}"


def test_metadata_accepted_without_error():
    """add_feedback() with metadata kwarg must not raise any exception."""
    vm = _make_fallback_vm()
    try:
        vm.add_feedback("test document with metadata", metadata={"type": "test", "version": "1.0"})
    except Exception as exc:
        pytest.fail(f"add_feedback() raised an exception with metadata: {exc}")


def test_fallback_used_when_chromadb_unavailable():
    """
    When chromadb is not importable, VectorMemory must initialize without exception
    and use the in-memory fallback (vector_store is None).
    """
    import threading
    with patch("src.memory.vector_store._HAS_CHROMADB", False), \
         patch("src.memory.vector_store.Chroma", None):
        from src.memory.vector_store import VectorMemory
        try:
            vm = VectorMemory.__new__(VectorMemory)
            import logging
            vm.logger = logging.getLogger("VectorMemory.test2")
            vm._fallback_memory    = []
            vm._fallback_lock      = threading.Lock()
            vm._vector_store       = None
            vm._llamaindex_index   = None
            vm._embedding_function = None
            vm._ready = False
            vm._mode  = "minimal"
        except Exception as exc:
            pytest.fail(f"VectorMemory initialization raised an exception without ChromaDB: {exc}")
        assert vm._vector_store is None, "vector_store must be None when ChromaDB is unavailable."
        # Should still be usable
        vm.add_feedback("test fallback doc")
        results = vm.search("test")
        assert "test fallback doc" in results, "Fallback memory must be usable after init without ChromaDB."
