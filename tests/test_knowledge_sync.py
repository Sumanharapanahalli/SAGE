import os
import pytest
from unittest.mock import MagicMock


def test_sync_imports_files(tmp_path):
    """knowledge_syncer.sync_directory() returns count of imported chunks."""
    (tmp_path / "guide.md").write_text("# Guide\nThis is important context.\n")
    (tmp_path / "notes.txt").write_text("Key information here.")

    mock_vs = MagicMock()
    mock_vs.bulk_import.return_value = 2

    from src.core.knowledge_syncer import sync_directory
    count = sync_directory(str(tmp_path), vector_store=mock_vs)
    assert count >= 1
    assert mock_vs.bulk_import.called


def test_sync_skips_binary_files(tmp_path):
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (tmp_path / "readme.md").write_text("# Readme with content")

    mock_vs = MagicMock()
    mock_vs.bulk_import.return_value = 1

    from src.core.knowledge_syncer import sync_directory
    sync_directory(str(tmp_path), vector_store=mock_vs)
    # Check that PNG bytes never appear in imported texts
    if mock_vs.bulk_import.called:
        all_texts = [entry["text"] for call in mock_vs.bulk_import.call_args_list for entry in call[0][0]]
        assert all("PNG" not in t for t in all_texts)


def test_knowledge_sync_endpoint_exists():
    from src.interface.api import app
    routes = [r.path for r in app.routes]
    assert "/knowledge/sync" in routes
