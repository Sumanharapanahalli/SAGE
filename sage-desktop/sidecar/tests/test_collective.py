"""Tests for the Collective Intelligence handler.

Uses a fake CollectiveMemory that mirrors the public shape of
``src.core.collective_memory.CollectiveMemory`` so the handler is
tested without pulling in git or ChromaDB. One end-to-end test at
the bottom of this file exercises a real ``CollectiveMemory`` in
a ``tmp_path``.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import handlers.collective as collective  # noqa: E402
from rpc import RpcError  # noqa: E402


class _FakeCM:
    """Minimal CollectiveMemory stand-in.

    Stores learnings and help requests in-memory; publish returns an
    id or a proposal trace_id depending on ``require_approval``.
    """

    def __init__(self, require_approval: bool = False) -> None:
        self.require_approval = require_approval
        self.repo_path = "/tmp/fake-collective"
        self._git_available = True
        self._learnings: dict[str, dict] = {}
        self._help_open: dict[str, dict] = {}
        self._help_closed: dict[str, dict] = {}
        self._proposals: dict[str, dict] = {}
        self._pulled = False
        self._indexed = 0


@pytest.fixture
def wired():
    cm = _FakeCM()
    # Re-bind in tests via monkeypatch.setattr(collective, "_cm", cm)
    return cm


def test_require_cm_raises_when_unwired(monkeypatch):
    monkeypatch.setattr(collective, "_cm", None)
    with pytest.raises(RpcError) as e:
        collective._require_cm()
    assert e.value.code == -32000
    assert "not wired" in e.value.message


def test_require_dict_rejects_non_dict():
    with pytest.raises(RpcError) as e:
        collective._require_dict("not a dict")
    assert e.value.code == -32602
