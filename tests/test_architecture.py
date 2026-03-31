"""
Architecture Tests — validates the structural improvements from Architecture_Study.md

Tests cover:
  1. Exception hierarchy (R5)
  2. SQLite WAL mode helper (R2)
  3. Provider-aware LLM semaphore (R1)
  4. Vector store thread safety (§5.6)
  5. Route module structure (R3)
"""

import os
import sqlite3
import tempfile
import threading
import time

import pytest


# ─── 1. Exception Hierarchy ──────────────────────────────────────────


class TestExceptionHierarchy:
    """Verify the exception tree is correctly structured."""

    def test_base_exception_exists(self):
        from src.core.exceptions import SAGEError
        assert issubclass(SAGEError, Exception)

    def test_llm_errors_chain(self):
        from src.core.exceptions import (
            SAGEError,
            LLMProviderError,
            LLMTimeoutError,
            LLMRateLimitError,
        )
        assert issubclass(LLMProviderError, SAGEError)
        assert issubclass(LLMTimeoutError, LLMProviderError)
        assert issubclass(LLMRateLimitError, LLMProviderError)

    def test_proposal_errors_chain(self):
        from src.core.exceptions import (
            SAGEError,
            ProposalError,
            ProposalNotFoundError,
            ProposalExpiredError,
        )
        assert issubclass(ProposalError, SAGEError)
        assert issubclass(ProposalNotFoundError, ProposalError)
        assert issubclass(ProposalExpiredError, ProposalError)

    def test_runner_errors_chain(self):
        from src.core.exceptions import (
            SAGEError,
            RunnerError,
            RunnerUnavailableError,
            RunnerTimeoutError,
            SandboxError,
        )
        assert issubclass(RunnerError, SAGEError)
        assert issubclass(RunnerUnavailableError, RunnerError)
        assert issubclass(RunnerTimeoutError, RunnerError)
        assert issubclass(SandboxError, RunnerError)

    def test_config_errors_chain(self):
        from src.core.exceptions import (
            SAGEError,
            ConfigError,
            SolutionNotFoundError,
            YAMLValidationError,
        )
        assert issubclass(ConfigError, SAGEError)
        assert issubclass(SolutionNotFoundError, ConfigError)
        assert issubclass(YAMLValidationError, ConfigError)

    def test_catch_sage_error_catches_all(self):
        """A single `except SAGEError` should catch every framework exception."""
        from src.core.exceptions import (
            SAGEError,
            LLMTimeoutError,
            ProposalExpiredError,
            RunnerUnavailableError,
            YAMLValidationError,
        )
        for exc_class in [
            LLMTimeoutError,
            ProposalExpiredError,
            RunnerUnavailableError,
            YAMLValidationError,
        ]:
            with pytest.raises(SAGEError):
                raise exc_class("test")

    def test_exceptions_carry_message(self):
        from src.core.exceptions import LLMProviderError
        err = LLMProviderError("Gemini CLI timed out after 30s")
        assert "Gemini CLI" in str(err)


# ─── 2. SQLite WAL Mode Helper ───────────────────────────────────────


class TestSQLiteWAL:
    """Verify get_connection() enforces WAL and busy_timeout."""

    def test_wal_mode_enabled(self):
        from src.core.db import get_connection
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = get_connection(db_path)
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            assert mode == "wal", f"Expected WAL, got {mode}"
            conn.close()
        finally:
            os.unlink(db_path)

    def test_busy_timeout_set(self):
        from src.core.db import get_connection
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = get_connection(db_path, busy_timeout_ms=3000)
            timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
            assert timeout == 3000
            conn.close()
        finally:
            os.unlink(db_path)

    def test_row_factory_default_is_row(self):
        from src.core.db import get_connection
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = get_connection(db_path)
            assert conn.row_factory is sqlite3.Row
            conn.close()
        finally:
            os.unlink(db_path)

    def test_row_factory_none_gives_tuples(self):
        from src.core.db import get_connection
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = get_connection(db_path, row_factory=None)
            assert conn.row_factory is None
            conn.close()
        finally:
            os.unlink(db_path)

    def test_concurrent_writes_with_wal(self):
        """WAL mode should allow concurrent writes without 'database is locked'."""
        from src.core.db import get_connection
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = get_connection(db_path, row_factory=None)
            conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
            conn.commit()
            conn.close()

            errors = []

            def writer(thread_id):
                try:
                    c = get_connection(db_path, row_factory=None)
                    for i in range(20):
                        c.execute(
                            "INSERT INTO t (val) VALUES (?)",
                            (f"thread-{thread_id}-row-{i}",),
                        )
                        c.commit()
                    c.close()
                except Exception as e:
                    errors.append(str(e))

            threads = [threading.Thread(target=writer, args=(i,)) for i in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

            assert not errors, f"Concurrent write errors: {errors}"

            # Verify all rows were written
            c = get_connection(db_path, row_factory=None)
            count = c.execute("SELECT COUNT(*) FROM t").fetchone()[0]
            assert count == 80, f"Expected 80 rows, got {count}"
            c.close()
        finally:
            os.unlink(db_path)


# ─── 3. Provider-Aware LLM Semaphore ─────────────────────────────────


class TestLLMSemaphore:
    """Verify the LLMGateway uses provider-aware concurrency."""

    def test_provider_concurrency_map_exists(self):
        from src.core.llm_gateway import LLMGateway
        assert hasattr(LLMGateway, "PROVIDER_CONCURRENCY")
        pc = LLMGateway.PROVIDER_CONCURRENCY
        assert pc["local"] == 1, "Local GPU must be single-lane"
        assert pc["gemini"] > 1, "Cloud API should allow concurrency"
        assert pc["claude"] > 1, "Cloud API should allow concurrency"

    def test_gateway_has_inference_semaphore(self):
        """After init, the gateway should have a semaphore, not just a lock."""
        from src.core.llm_gateway import LLMGateway
        gw = LLMGateway()
        assert hasattr(gw, "_inference_semaphore")
        assert isinstance(gw._inference_semaphore, threading.Semaphore)

    def test_class_lock_still_exists_for_singleton(self):
        """The class-level _lock must remain for thread-safe singleton creation."""
        from src.core.llm_gateway import LLMGateway
        assert hasattr(LLMGateway, "_lock")
        assert isinstance(LLMGateway._lock, type(threading.Lock()))


# ─── 4. Vector Store Thread Safety ───────────────────────────────────


class TestVectorStoreThreadSafety:
    """Verify in-memory fallback is protected by a lock."""

    def test_fallback_lock_exists(self):
        from src.memory.vector_store import VectorMemory
        vm = VectorMemory()
        assert hasattr(vm, "_fallback_lock")
        assert isinstance(vm._fallback_lock, type(threading.Lock()))

    def test_concurrent_add_and_search(self):
        """Multiple threads adding feedback while others search should not crash."""
        from src.memory.vector_store import VectorMemory
        vm = VectorMemory()  # minimal mode — uses fallback only
        errors = []

        def adder(thread_id):
            try:
                for i in range(50):
                    vm.add_feedback(f"thread-{thread_id} feedback item {i}")
            except Exception as e:
                errors.append(f"adder-{thread_id}: {e}")

        def searcher(thread_id):
            try:
                for _ in range(50):
                    vm.search("feedback item", k=5)
            except Exception as e:
                errors.append(f"searcher-{thread_id}: {e}")

        threads = []
        for i in range(3):
            threads.append(threading.Thread(target=adder, args=(i,)))
            threads.append(threading.Thread(target=searcher, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Thread safety errors: {errors}"

    def test_concurrent_add_entry_and_list(self):
        """add_entry + list_entries should not race."""
        from src.memory.vector_store import VectorMemory
        vm = VectorMemory()
        errors = []

        def add_entries():
            try:
                for i in range(30):
                    vm.add_entry(f"entry-{i}")
            except Exception as e:
                errors.append(str(e))

        def list_entries():
            try:
                for _ in range(30):
                    vm.list_entries(limit=10)
            except Exception as e:
                errors.append(str(e))

        t1 = threading.Thread(target=add_entries)
        t2 = threading.Thread(target=list_entries)
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert not errors, f"Thread safety errors: {errors}"


# ─── 5. Route Module Structure ────────────────────────────────────────


class TestRouteModuleStructure:
    """Verify api.py includes route modules and they are proper APIRouters."""

    def test_routes_directory_exists(self):
        routes_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "src", "interface", "routes",
        )
        assert os.path.isdir(routes_dir), "src/interface/routes/ must exist"

    def test_existing_routes_are_api_routers(self):
        """Each .py file in routes/ (except __init__) should define a router."""
        routes_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "src", "interface", "routes",
        )
        route_files = [
            f for f in os.listdir(routes_dir)
            if f.endswith(".py") and f != "__init__.py"
        ]
        assert len(route_files) >= 2, "Should have at least 2 route modules"

        for rf in route_files:
            module_name = rf.removesuffix(".py")
            # Dynamic import to check for router attribute
            import importlib
            mod = importlib.import_module(f"src.interface.routes.{module_name}")
            assert hasattr(mod, "router"), f"{rf} missing 'router' attribute"
