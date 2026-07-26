"""Regression: _get_db_path() must honor a patched _get_audit_logger().

The system-test client isolates the DB by patching
``src.interface.api._get_audit_logger``. Feature-request writes resolve their
DB via ``_get_db_path()``; if that helper imports the module-level audit_logger
singleton directly it bypasses the patch and writes leak into the real .sage
DB (observed: 61 duplicate 'Add WebSocket streaming' rows in the sage backlog).
"""

from types import SimpleNamespace
from unittest.mock import patch

from src.interface import api


def test_get_db_path_honors_patched_audit_logger():
    fake = SimpleNamespace(db_path="/tmp/isolated-test.db")
    with patch.object(api, "_get_audit_logger", return_value=fake):
        assert api._get_db_path() == "/tmp/isolated-test.db"


def test_get_db_path_uses_the_accessor_seam():
    """It must go through _get_audit_logger(), not a direct singleton import —
    proven by the accessor being called exactly once."""
    fake = SimpleNamespace(db_path="/tmp/seam.db")
    with patch.object(api, "_get_audit_logger", return_value=fake) as mock_acc:
        api._get_db_path()
    mock_acc.assert_called_once()
