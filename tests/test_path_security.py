"""
Security tests for path validation — prevent path traversal vulnerabilities.

Tests cover:
1. Path traversal attacks (.. sequences)
2. Absolute paths attempting to escape boundary
3. Symlink-based escape attempts (if symlinks exist)
4. Control character injection
5. Null byte attacks
6. Directory separator injection
7. Valid project names accepted correctly
8. Boundary validation prevents escapes
"""

import os
import tempfile
from pathlib import Path

import pytest

from src.modules.path_validator import (
    validate_project_name,
    validate_path_boundary,
    get_safe_project_dir,
    get_safe_sage_dir,
    safe_mkdir,
)


class TestProjectNameValidation:
    """Test project name validation against attack patterns."""

    def test_valid_project_name(self):
        """Valid alphanumeric names should pass."""
        valid_names = ["medtech", "four_in_a_line", "my-solution", "starter123", "UPPERCASE"]
        for name in valid_names:
            is_valid, err = validate_project_name(name)
            assert is_valid, f"Expected '{name}' to be valid, got error: {err}"
            assert err == ""

    def test_empty_project_name(self):
        """Empty project name should be rejected."""
        is_valid, err = validate_project_name("")
        assert not is_valid
        assert "empty" in err.lower()

    def test_path_traversal_attack_dotdot(self):
        """Path traversal with .. should be rejected."""
        attack_names = ["../../../etc", "..", "foo/bar", "test/../escape"]
        for name in attack_names:
            is_valid, err = validate_project_name(name)
            assert not is_valid, f"Expected '{name}' to be rejected"
            assert err != ""

    def test_absolute_path_attack(self):
        """Absolute paths should be rejected."""
        attack_names = ["/etc/passwd", "C:\\Windows\\System32", "/tmp/evil"]
        for name in attack_names:
            is_valid, err = validate_project_name(name)
            assert not is_valid, f"Expected '{name}' to be rejected"
            assert err != ""

    def test_backslash_injection(self):
        """Backslashes should be rejected."""
        is_valid, err = validate_project_name("foo\\bar")
        assert not is_valid

    def test_null_byte_injection(self):
        """Null bytes should be rejected."""
        is_valid, err = validate_project_name("foo\x00bar")
        assert not is_valid

    def test_control_character_injection(self):
        """Control characters should be rejected."""
        attack_names = ["foo\nbar", "foo\rbar", "foo\tbar"]
        for name in attack_names:
            is_valid, err = validate_project_name(name)
            assert not is_valid, f"Expected control chars in '{name}' to be rejected"

    def test_unicode_characters(self):
        """Unicode characters should be rejected."""
        is_valid, err = validate_project_name("café")
        assert not is_valid

    def test_special_characters(self):
        """Special characters (except _ and -) should be rejected."""
        attack_names = ["foo@bar", "foo#bar", "foo$bar", "foo.bar", "foo,bar"]
        for name in attack_names:
            is_valid, err = validate_project_name(name)
            assert not is_valid, f"Expected '{name}' to be rejected"

    def test_max_length_boundary(self):
        """Project names exceeding 64 characters should be rejected."""
        is_valid, err = validate_project_name("a" * 65)
        assert not is_valid
        assert "exceeds" in err.lower() or "64" in err

    def test_max_length_valid(self):
        """Project names at 64 character limit should be valid."""
        is_valid, err = validate_project_name("a" * 64)
        assert is_valid


class TestPathBoundaryValidation:
    """Test that resolved paths stay within boundaries."""

    def test_valid_path_within_boundary(self):
        """Path within boundary should be valid."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "solutions", "medtech")
            os.makedirs(subdir, exist_ok=True)

            is_safe, err = validate_path_boundary(subdir, tmpdir)
            assert is_safe, f"Expected path within boundary to be valid, got: {err}"
            assert err == ""

    def test_path_equals_boundary(self):
        """Path equal to boundary should be valid."""
        with tempfile.TemporaryDirectory() as tmpdir:
            is_safe, err = validate_path_boundary(tmpdir, tmpdir)
            assert is_safe

    def test_path_escapes_with_dotdot(self):
        """Path that escapes with .. should be rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            boundary = os.path.join(tmpdir, "solutions")
            os.makedirs(boundary, exist_ok=True)
            attack_path = os.path.join(boundary, "..", "..", "etc")

            is_safe, err = validate_path_boundary(attack_path, boundary)
            assert not is_safe, f"Expected escaped path to be rejected"
            assert err != ""

    def test_path_escapes_absolute(self):
        """Absolute paths outside boundary should be rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            boundary = os.path.join(tmpdir, "solutions")
            os.makedirs(boundary, exist_ok=True)

            # Try to use /tmp (or absolute path outside boundary)
            is_safe, err = validate_path_boundary("/etc/passwd", boundary)
            assert not is_safe

    def test_symlink_escape_attempt(self):
        """Symlink-based path escapes should be rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            boundary = os.path.join(tmpdir, "solutions")
            os.makedirs(boundary, exist_ok=True)

            # Create a target directory outside boundary
            outside = os.path.join(tmpdir, "outside_data")
            os.makedirs(outside, exist_ok=True)

            # Create symlink inside boundary pointing outside
            link_path = os.path.join(boundary, "escape_link")
            try:
                os.symlink(outside, link_path)

                # Following the symlink should be detected as escape
                is_safe, err = validate_path_boundary(link_path, boundary)
                assert not is_safe, "Expected symlink escape to be rejected"
            except OSError:
                # Skip test if symlinks not supported (Windows without admin)
                pytest.skip("Symlinks not supported on this system")


class TestSafeProjectDir:
    """Test safe project directory construction."""

    def test_valid_project_directory(self):
        """Valid project should construct safe directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir, err = get_safe_project_dir("medtech", tmpdir)

            assert err == "", f"Expected no error, got: {err}"
            assert project_dir != ""
            assert "medtech" in project_dir
            assert tmpdir in project_dir

    def test_invalid_project_name_rejected(self):
        """Invalid project name should return error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir, err = get_safe_project_dir("../../../etc", tmpdir)

            assert err != "", "Expected error for path traversal"
            assert project_dir == ""

    def test_boundary_validation_enforced(self):
        """Resolved path must stay within boundary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Even if somehow a path escapes, boundary validation should catch it
            boundary = os.path.join(tmpdir, "solutions")
            os.makedirs(boundary, exist_ok=True)

            # This should be caught by name validation first
            project_dir, err = get_safe_project_dir("..", boundary)
            assert err != ""


class TestSafeSageDir:
    """Test safe .sage directory construction."""

    def test_valid_sage_directory(self):
        """Valid project should construct safe .sage directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sage_dir, err = get_safe_sage_dir("medtech", tmpdir)

            assert err == "", f"Expected no error, got: {err}"
            assert sage_dir != ""
            assert ".sage" in sage_dir
            assert "medtech" in sage_dir
            assert tmpdir in sage_dir

    def test_empty_project_name_fallback(self):
        """Empty project name should be treated as framework fallback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sage_dir, err = get_safe_sage_dir("", tmpdir)

            assert err == ""
            assert sage_dir == ""  # Framework fallback returns empty

    def test_invalid_project_rejected(self):
        """Invalid project name should be rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sage_dir, err = get_safe_sage_dir("foo/bar", tmpdir)

            assert err != ""
            assert sage_dir == ""


class TestSafeMkdir:
    """Test safe directory creation."""

    def test_create_new_directory(self):
        """Should successfully create new directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = os.path.join(tmpdir, "newdir")

            success, err = safe_mkdir(new_dir)

            assert success, f"Expected mkdir to succeed, got: {err}"
            assert err == ""
            assert os.path.isdir(new_dir)

    def test_existing_directory(self):
        """Should succeed for existing directory (idempotent)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            success, err = safe_mkdir(tmpdir)

            assert success
            assert err == ""

    def test_empty_path(self):
        """Should fail for empty path."""
        success, err = safe_mkdir("")

        assert not success
        assert err != ""

    def test_nested_directory_creation(self):
        """Should create nested directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = os.path.join(tmpdir, "a", "b", "c")

            success, err = safe_mkdir(nested)

            assert success
            assert os.path.isdir(nested)


class TestIntegrationWithEvolutionDb:
    """Integration tests with the evolution database path resolution."""

    def test_evolution_db_path_valid_project(self):
        """Evolution DB should resolve to valid path for project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from unittest.mock import patch
            from src.core.evolution.program_db import get_evolution_db_path

            with patch.dict(os.environ, {
                "SAGE_PROJECT": "medtech",
                "SAGE_SOLUTIONS_DIR": tmpdir
            }):
                db_path = get_evolution_db_path()

                assert db_path != ""
                assert "medtech" in db_path
                assert ".sage" in db_path
                assert "evolution.db" in db_path
                assert tmpdir in db_path

    def test_evolution_db_path_rejects_traversal(self):
        """Evolution DB should reject path traversal in project name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from unittest.mock import patch
            from src.core.evolution.program_db import get_evolution_db_path

            with patch.dict(os.environ, {
                "SAGE_PROJECT": "../../../etc",
                "SAGE_SOLUTIONS_DIR": tmpdir
            }):
                with pytest.raises(ValueError) as exc_info:
                    get_evolution_db_path()

                assert "invalid" in str(exc_info.value).lower()


class TestIntegrationWithAuditLogger:
    """Integration tests with the audit logger path resolution."""

    def test_audit_db_path_valid_project(self):
        """Audit DB should resolve to valid path for project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from unittest.mock import patch
            from src.memory.audit_logger import _resolve_db_path

            with patch.dict(os.environ, {
                "SAGE_PROJECT": "medtech",
                "SAGE_SOLUTIONS_DIR": tmpdir
            }):
                db_path = _resolve_db_path()

                assert db_path != ""
                assert "medtech" in db_path
                assert ".sage" in db_path
                assert "audit_log.db" in db_path
                assert tmpdir in db_path

    def test_audit_db_path_rejects_traversal(self):
        """Audit DB should reject path traversal in project name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from unittest.mock import patch
            from src.memory.audit_logger import _resolve_db_path

            with patch.dict(os.environ, {
                "SAGE_PROJECT": "../../../etc",
                "SAGE_SOLUTIONS_DIR": tmpdir
            }):
                with pytest.raises(ValueError) as exc_info:
                    _resolve_db_path()

                assert "invalid" in str(exc_info.value).lower()
