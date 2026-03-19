import subprocess
from unittest.mock import patch, MagicMock
import pytest


def test_get_task_hooks_returns_empty_when_none():
    from src.core.project_loader import ProjectConfig
    cfg = ProjectConfig.__new__(ProjectConfig)
    cfg._tasks = {"task_types": ["ANALYZE_LOG"]}
    hooks = cfg.get_task_hooks("ANALYZE_LOG")
    assert hooks == {"pre": [], "post": []}


def test_get_task_hooks_returns_declared_hooks():
    from src.core.project_loader import ProjectConfig
    cfg = ProjectConfig.__new__(ProjectConfig)
    cfg._tasks = {
        "task_hooks": {
            "ANALYZE_LOG": {
                "pre": ["echo pre-hook"],
                "post": ["echo post-hook"],
            }
        }
    }
    hooks = cfg.get_task_hooks("ANALYZE_LOG")
    assert hooks["pre"] == ["echo pre-hook"]
    assert hooks["post"] == ["echo post-hook"]


def test_hooks_executed_in_order(tmp_path):
    """Pre hook runs before handler, post hook after."""
    flag_file = tmp_path / "order.txt"
    from src.core.queue_manager import _run_hooks
    _run_hooks([f"echo PRE >> {flag_file}"])
    flag_file.write_text(flag_file.read_text() + "HANDLER\n")
    _run_hooks([f"echo POST >> {flag_file}"])
    content = flag_file.read_text()
    assert content.index("PRE") < content.index("HANDLER") < content.index("POST")
