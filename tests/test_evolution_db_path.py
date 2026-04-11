import os
import tempfile
from unittest.mock import patch

from src.core.evolution.program_db import get_evolution_db_path


def test_get_evolution_db_path_with_project():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.dict(os.environ, {
            "SAGE_PROJECT": "medtech",
            "SAGE_SOLUTIONS_DIR": tmpdir
        }):
            db_path = get_evolution_db_path()
            expected = os.path.join(tmpdir, "medtech", ".sage", "evolution.db")
            assert db_path == expected


def test_get_evolution_db_path_fallback():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.dict(os.environ, {
            "SAGE_PROJECT": "",  # No project set
            "SAGE_SOLUTIONS_DIR": tmpdir
        }):
            db_path = get_evolution_db_path()
            # Should fall back to framework .sage directory
            assert ".sage" in db_path
            assert "evolution.db" in db_path


def test_program_database_uses_project_path():
    """Test that ProgramDatabase automatically uses the project-specific path."""
    from src.core.evolution.program_db import ProgramDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.dict(os.environ, {
            "SAGE_PROJECT": "testproj",
            "SAGE_SOLUTIONS_DIR": tmpdir
        }):
            # ProgramDatabase should auto-resolve path when no path given
            db = ProgramDatabase()  # No explicit path
            expected_dir = os.path.join(tmpdir, "testproj", ".sage")
            assert expected_dir in db.db_path
            assert db.db_path.endswith("evolution.db")
