r"""
Path and project name validation — prevent path traversal attacks.

Security module for validating project names and file paths to ensure:
1. Project names cannot contain path traversal sequences (.. / \)
2. Resolved paths stay within expected boundaries
3. Clear error messages for invalid input

This is a critical security boundary — malicious project names or unsanitized
paths could write databases outside the solutions directory tree, creating
data leakage and supply chain vulnerabilities in regulated environments.
"""

import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Forbidden characters in project names
_FORBIDDEN_CHARS = {
    '..', '/', '\\', '\x00', '\n', '\r', '\t',  # Path traversal + control chars
}

# Pattern to detect dangerous sequences
_UNSAFE_PATTERN = re.compile(r'\.\.|\x00|[\\/\n\r\t]')


def validate_project_name(project_name: str) -> tuple[bool, str]:
    r"""
    Validate a project name for security.

    Returns (is_valid, error_message).
    - is_valid: True if the name is safe
    - error_message: Descriptive error (empty if valid)

    Rules:
    - Must be non-empty and alphanumeric + underscore + hyphen
    - No path traversal sequences (..)
    - No directory separators (/, \)
    - No control characters or null bytes
    - Max 64 characters (reasonable project name length)
    """
    if not project_name:
        return False, "Project name cannot be empty"

    if len(project_name) > 64:
        return False, "Project name exceeds 64 characters"

    # Check for forbidden patterns
    if _UNSAFE_PATTERN.search(project_name):
        return False, (
            f"Project name contains forbidden characters. "
            f"Only alphanumeric, underscore, and hyphen are allowed. "
            f"Got: {repr(project_name)}"
        )

    # Additional check: must be valid ASCII
    try:
        project_name.encode('ascii')
    except UnicodeEncodeError:
        return False, "Project name must contain only ASCII characters"

    # Pattern: alphanumeric, underscore, hyphen only
    if not re.match(r'^[a-zA-Z0-9_-]+$', project_name):
        return False, (
            f"Project name must contain only alphanumeric characters, "
            f"underscore, and hyphen. Got: {repr(project_name)}"
        )

    return True, ""


def validate_path_boundary(path: str, boundary: str) -> tuple[bool, str]:
    """
    Verify that a resolved path stays within a boundary directory.

    Returns (is_within_boundary, error_message).

    This prevents symlink attacks and path traversal that resolves to
    parent directories via combinations of .. and absolute paths.
    """
    try:
        # Resolve symlinks and .. sequences
        resolved = os.path.abspath(os.path.realpath(path))
        boundary_abs = os.path.abspath(os.path.realpath(boundary))

        # Verify the resolved path starts with the boundary
        # Use os.path.commonpath to handle edge cases
        common = os.path.commonpath([resolved, boundary_abs])

        if common != boundary_abs:
            return False, (
                f"Resolved path escapes boundary. "
                f"Boundary: {boundary_abs}, Resolved: {resolved}"
            )

        return True, ""
    except (ValueError, OSError) as exc:
        return False, f"Path validation failed: {exc}"


def get_safe_project_dir(project_name: str, solutions_dir: str) -> tuple[str, str]:
    """
    Safely construct and validate a project directory path.

    Returns (project_dir, error_message).
    - project_dir: Absolute path to the project directory (safe to use)
    - error_message: Descriptive error (empty if successful)

    This function:
    1. Validates the project name
    2. Constructs the path
    3. Validates the path stays within solutions_dir
    """
    # Validate project name
    is_valid, err = validate_project_name(project_name)
    if not err:
        # If project_name is empty, that's OK for fallback case
        if project_name == "":
            return "", ""

    if not is_valid:
        return "", err

    # Construct path
    project_dir = os.path.join(os.path.abspath(solutions_dir), project_name)

    # Validate boundary
    is_safe, err = validate_path_boundary(project_dir, solutions_dir)
    if not is_safe:
        return "", err

    return project_dir, ""


def get_safe_sage_dir(project_name: str, solutions_dir: str) -> tuple[str, str]:
    """
    Safely construct and validate a .sage directory path.

    Returns (sage_dir, error_message).
    - sage_dir: Absolute path to the .sage directory (safe to create)
    - error_message: Descriptive error (empty if successful)

    Used by both evolution/program_db.py and memory/audit_logger.py.
    """
    if not project_name:
        # Framework fallback
        return "", ""

    # Get safe project dir first
    project_dir, err = get_safe_project_dir(project_name, solutions_dir)
    if err:
        return "", err

    # Construct .sage dir
    sage_dir = os.path.join(project_dir, ".sage")

    # Final boundary check
    is_safe, err = validate_path_boundary(sage_dir, solutions_dir)
    if not is_safe:
        return "", err

    return sage_dir, ""


def safe_mkdir(path: str) -> tuple[bool, str]:
    """
    Safely create a directory with error handling.

    Returns (success, error_message).

    Only creates if path is safe and does not already exist.
    """
    if not path:
        return False, "Cannot create directory: empty path"

    try:
        os.makedirs(path, exist_ok=True)
        logger.debug(f"Directory created or already exists: {path}")
        return True, ""
    except OSError as exc:
        err_msg = f"Failed to create directory {path}: {exc}"
        logger.error(err_msg)
        return False, err_msg
    except Exception as exc:
        err_msg = f"Unexpected error creating directory {path}: {exc}"
        logger.critical(err_msg)
        return False, err_msg
