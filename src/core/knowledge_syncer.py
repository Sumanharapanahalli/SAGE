"""
SAGE Knowledge Syncer — import files from disk into the vector store.

Used by the KNOWLEDGE_SYNC task type and POST /knowledge/sync.
Walks a directory, reads text files, chunks them, and calls bulk_import().
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_SKIP_DIRS = {".venv", "venv", ".git", "__pycache__", "node_modules", ".sage", "dist", "build", ".sage_worktrees"}
_TEXT_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".txt", ".yaml", ".yml",
    ".json", ".toml", ".cfg", ".ini", ".sh", ".rst", ".html", ".css",
}
_MAX_FILE_BYTES = 100_000   # skip files larger than 100KB
_CHUNK_SIZE     = 1_500     # characters per knowledge chunk


def _chunk_text(text: str, chunk_size: int = _CHUNK_SIZE) -> list:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        start += chunk_size - 200  # 200-char overlap
    return [c for c in chunks if len(c) > 10]


def sync_directory(root: str, vector_store=None, extensions: set = None) -> int:
    """
    Walk *root*, chunk text files, and bulk_import into *vector_store*.
    Returns total number of chunks imported.
    """
    if vector_store is None:
        from src.memory.vector_store import vector_memory
        vector_store = vector_memory

    if extensions is None:
        extensions = _TEXT_EXTENSIONS

    entries = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in extensions:
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                if os.path.getsize(fpath) > _MAX_FILE_BYTES:
                    continue
                with open(fpath, encoding="utf-8", errors="ignore") as fh:
                    text = fh.read().strip()
                if not text:
                    continue
                rel = os.path.relpath(fpath, root).replace("\\", "/")
                for chunk in _chunk_text(text):
                    entries.append({
                        "text": chunk,
                        "metadata": {"source": rel, "type": "knowledge_sync"},
                    })
            except OSError as exc:
                logger.debug("Skipping %s: %s", fpath, exc)

    if not entries:
        logger.info("knowledge_sync: no entries to import from %s", root)
        return 0

    count = vector_store.bulk_import(entries)
    logger.info("knowledge_sync: imported %d chunks from %s", count, root)
    return count
