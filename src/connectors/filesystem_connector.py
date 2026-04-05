"""
Filesystem Connector
=====================

Indexes local files for ingestion into SAGE's knowledge base.
"""

import logging
import os
from pathlib import Path

from src.connectors.base import BaseConnector

logger = logging.getLogger(__name__)

# File extensions to index
_TEXT_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".txt", ".yaml", ".yml",
    ".json", ".toml", ".cfg", ".ini", ".sh", ".bash", ".rs", ".go",
    ".java", ".c", ".cpp", ".h", ".hpp", ".html", ".css", ".sql",
}


class FilesystemConnector(BaseConnector):
    """Indexes local text files from a directory."""

    connector_type = "filesystem"

    def connect(self, config: dict) -> bool:
        path = config.get("path", "")
        if not path or not os.path.isdir(path):
            self._connected = False
            return False
        self._config = config
        self._connected = True
        return True

    def fetch(self, **kwargs) -> list[dict]:
        if not self._connected:
            return []
        root = self._config["path"]
        max_files = kwargs.get("max_files", 500)
        max_size = kwargs.get("max_size_bytes", 100_000)
        results = []
        for fpath in Path(root).rglob("*"):
            if len(results) >= max_files:
                break
            if not fpath.is_file():
                continue
            if fpath.suffix.lower() not in _TEXT_EXTENSIONS:
                continue
            try:
                size = fpath.stat().st_size
                if size > max_size:
                    continue
                content = fpath.read_text(errors="replace")
                results.append({
                    "path": str(fpath),
                    "content": content,
                    "size": size,
                    "extension": fpath.suffix,
                })
            except Exception as e:
                logger.debug("Skipping %s: %s", fpath, e)
        return results

    def sync(self) -> dict:
        items = self.fetch()
        return {"synced": len(items), "source": self._config.get("path", "")}
