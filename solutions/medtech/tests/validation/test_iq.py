"""
Installation Qualification (IQ) Tests
=======================================
Verifies that SAGE and all dependencies are correctly installed
and configured per IEC 62304 and 21 CFR Part 11 requirements.

IQ confirms: "Is the system installed correctly?"
"""

import importlib
import os
import sys
import sqlite3

import pytest


class TestPythonEnvironment:
    """IQ-001: Python runtime meets minimum requirements."""

    def test_python_version_minimum(self):
        """Python >= 3.10 is required for SAGE."""
        assert sys.version_info >= (3, 10), (
            f"Python {sys.version_info.major}.{sys.version_info.minor} is below minimum 3.10"
        )

    def test_python_version_recommended(self):
        """Python >= 3.12 is recommended."""
        assert sys.version_info >= (3, 12), (
            f"Python {sys.version_info.major}.{sys.version_info.minor} — 3.12+ recommended"
        )


class TestCoreDependencies:
    """IQ-002: All required Python packages are importable."""

    @pytest.mark.parametrize("module_name", [
        "fastapi",
        "uvicorn",
        "pydantic",
        "yaml",
        "sqlite3",
        "chromadb",
        "requests",
    ])
    def test_core_module_importable(self, module_name):
        """Each core dependency must be importable."""
        importlib.import_module(module_name)

    @pytest.mark.parametrize("module_name", [
        "src.core.llm_gateway",
        "src.core.db",
        "src.core.traceability",
        "src.core.audit_integrity",
        "src.core.doc_generator",
        "src.core.change_control",
        "src.core.compliance_verifier",
        "src.core.regulatory_compliance",
        "src.memory.audit_logger",
        "src.interface.api",
    ])
    def test_sage_module_importable(self, module_name):
        """Each SAGE core module must be importable without error."""
        importlib.import_module(module_name)


class TestDatabaseInstallation:
    """IQ-003: SQLite is functional and WAL mode works."""

    def test_sqlite_version(self):
        """SQLite >= 3.35 required for RETURNING clause support."""
        version = sqlite3.sqlite_version_info
        assert version >= (3, 35, 0), f"SQLite {sqlite3.sqlite_version} is below minimum 3.35"

    def test_wal_mode_supported(self, tmp_path):
        """WAL journal mode must be supported."""
        db = str(tmp_path / "iq_test.db")
        conn = sqlite3.connect(db)
        result = conn.execute("PRAGMA journal_mode = WAL").fetchone()
        conn.close()
        assert result[0] == "wal"

    def test_get_connection_helper(self, tmp_path):
        """The SAGE get_connection helper must work correctly."""
        from src.core.db import get_connection
        db = str(tmp_path / "iq_conn.db")
        conn = get_connection(db, row_factory=None)
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO test VALUES (1)")
        conn.commit()
        row = conn.execute("SELECT id FROM test").fetchone()
        conn.close()
        assert row[0] == 1


class TestFileSystemStructure:
    """IQ-004: Required directories and files exist."""

    @pytest.mark.parametrize("path", [
        "src/core",
        "src/agents",
        "src/interface",
        "src/memory",
        "skills/public",
        "solutions/medtech",
    ])
    def test_directory_exists(self, path):
        """Required directory must exist."""
        full_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            ))),
            path,
        )
        assert os.path.isdir(full_path), f"Directory missing: {path}"

    def test_license_file_exists(self):
        """LICENSE file must exist for open-source compliance."""
        root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )))
        assert os.path.isfile(os.path.join(root, "LICENSE"))
