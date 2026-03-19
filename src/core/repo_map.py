"""
SAGE Repo Map — lightweight codebase symbol scanner.

Walks a directory, extracts class/function names from Python files using
regex (no AST required — works on partial/broken code too).
Returns a Markdown summary injected into DeveloperAgent system prompts.
"""

import os
import re
import logging

logger = logging.getLogger(__name__)

_SKIP_DIRS = {".venv", "venv", "env", ".git", "__pycache__", "node_modules", ".sage", "dist", "build"}
_CLASS_RE = re.compile(r"^class\s+(\w+)", re.MULTILINE)
_FUNC_RE  = re.compile(r"^def\s+(\w+)", re.MULTILINE)


def generate_repo_map(root: str, max_files: int = 50) -> str:
    """
    Scan *root* directory for Python files and return a Markdown symbol map.

    Returns a compact Markdown string listing files with their top-level
    classes and functions. Truncated at max_files to keep context size bounded.
    """
    lines = ["## Repo Map\n"]
    file_count = 0

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded directories in-place
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]

        for fname in sorted(filenames):
            if not fname.endswith(".py"):
                continue
            if file_count >= max_files:
                lines.append(f"\n_... truncated at {max_files} files_")
                return "\n".join(lines)

            fpath = os.path.join(dirpath, fname)
            rel   = os.path.relpath(fpath, root).replace("\\", "/")
            try:
                src = open(fpath, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue

            classes = _CLASS_RE.findall(src)
            funcs   = _FUNC_RE.findall(src)
            symbols = ", ".join(classes + funcs)
            if symbols:
                lines.append(f"- `{rel}`: {symbols}")
                file_count += 1

    return "\n".join(lines) if len(lines) > 1 else "_(no Python files found)_"
