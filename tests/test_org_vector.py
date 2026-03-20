# tests/test_org_vector.py
import pytest
from unittest.mock import patch, MagicMock


def test_get_vector_memory_factory_returns_instance():
    from src.memory.vector_store import get_vector_memory, VectorMemory
    vm = get_vector_memory("some_solution")
    assert isinstance(vm, VectorMemory)


def test_factory_instances_for_different_solutions_differ():
    from src.memory.vector_store import get_vector_memory
    vm_a = get_vector_memory("sol_a")
    vm_b = get_vector_memory("sol_b")
    # Their resolved db paths should differ
    path_a = vm_a._get_vector_db_path()
    path_b = vm_b._get_vector_db_path()
    assert path_a != path_b


def test_factory_explicit_solution_attribute():
    """Factory-created VectorMemory instances carry the explicit_solution attribute."""
    from src.memory.vector_store import get_vector_memory
    vm = get_vector_memory("my_solution")
    assert vm._explicit_solution == "my_solution"


def test_singleton_has_no_explicit_solution():
    """The module-level singleton must still work with no explicit_solution."""
    from src.memory.vector_store import vector_memory
    assert getattr(vector_memory, "_explicit_solution", None) is None


def test_org_aware_query_searches_parent_chain():
    """org_aware_query() calls search() for each solution in the parent chain."""
    from src.memory.vector_store import org_aware_query

    call_log = []

    # search() returns List[str] — plain strings, no distance dicts
    def mock_search(self, query, k=3):
        sol = getattr(self, "_explicit_solution", None)
        call_log.append(sol)
        if sol == "parent":
            return ["parent knowledge"]
        return ["child knowledge"]

    with patch("src.memory.vector_store.VectorMemory.search", mock_search):
        from src.core.org_loader import OrgLoader
        mock_loader = MagicMock(spec=OrgLoader)
        mock_loader.org_name = "test_org"
        mock_loader.get_parent_chain.return_value = ["child", "parent"]

        results = org_aware_query("test query", "child", mock_loader, n_results=5)

    assert "child" in call_log
    assert "parent" in call_log
    assert len(call_log) == 2


def test_org_aware_query_returns_list():
    """org_aware_query always returns a list, even with no results."""
    from src.memory.vector_store import org_aware_query

    with patch("src.memory.vector_store.VectorMemory.search", return_value=[]):
        from src.core.org_loader import OrgLoader
        mock_loader = MagicMock(spec=OrgLoader)
        mock_loader.get_parent_chain.return_value = ["child"]

        results = org_aware_query("test query", "child", mock_loader)

    assert isinstance(results, list)


def test_org_aware_query_deduplicates():
    """Duplicate strings across the parent chain appear only once in results."""
    from src.memory.vector_store import org_aware_query

    def mock_search(self, query, k=3):
        return ["shared knowledge", "unique to " + (getattr(self, "_explicit_solution", "") or "")]

    with patch("src.memory.vector_store.VectorMemory.search", mock_search):
        from src.core.org_loader import OrgLoader
        mock_loader = MagicMock(spec=OrgLoader)
        mock_loader.get_parent_chain.return_value = ["child", "parent"]

        results = org_aware_query("test query", "child", mock_loader, n_results=10)

    # "shared knowledge" should appear only once despite being returned by both stores
    assert results.count("shared knowledge") == 1


def test_org_aware_query_respects_n_results():
    """org_aware_query truncates to n_results."""
    from src.memory.vector_store import org_aware_query

    def mock_search(self, query, k=3):
        return ["item1", "item2", "item3"]

    with patch("src.memory.vector_store.VectorMemory.search", mock_search):
        from src.core.org_loader import OrgLoader
        mock_loader = MagicMock(spec=OrgLoader)
        mock_loader.get_parent_chain.return_value = ["child", "parent"]

        results = org_aware_query("test query", "child", mock_loader, n_results=2)

    assert len(results) <= 2


def test_org_aware_query_graceful_on_error():
    """org_aware_query returns [] when the loader raises an exception."""
    from src.memory.vector_store import org_aware_query

    mock_loader = MagicMock()
    mock_loader.get_parent_chain.side_effect = RuntimeError("loader broken")

    results = org_aware_query("test query", "child", mock_loader)
    assert results == []
