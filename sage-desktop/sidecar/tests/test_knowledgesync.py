"""Tests for the Knowledge Sync handler.

The load-bearing assertion is ``test_sync_passes_solution_scoped_vector_store``:
``sync_directory``'s ``vector_store`` default is the framework-GLOBAL singleton,
so if the handler ever stops passing the sidecar's VectorMemory explicitly the
operator's documents silently import into the wrong solution's collection.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import handlers.knowledge as knowledge  # noqa: E402
import handlers.knowledgesync as knowledgesync  # noqa: E402
from rpc import RpcError  # noqa: E402


class _FakeVM:
    """VectorMemory stand-in — only bulk_import is exercised by the syncer."""

    def __init__(self) -> None:
        self.imported: list[dict] = []
        self.mode = "full"

    def bulk_import(self, entries: list) -> int:
        self.imported.extend(entries)
        return len(entries)


class _FakeAuditLogger:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def log_event(self, **kwargs) -> str:
        self.events.append(kwargs)
        return "evt-1"


@pytest.fixture
def solution_dir(tmp_path: Path) -> Path:
    root = tmp_path / "demo"
    root.mkdir()
    (root / "project.yaml").write_text(
        "name: demo\n" + "x: y\n" * 200, encoding="utf-8"
    )
    (root / "README.md").write_text(
        "# Demo\n" + "Knowledge body. " * 200, encoding="utf-8"
    )
    (root / "image.png").write_bytes(b"\x89PNG binary not text")
    (root / "empty.md").write_text("   \n", encoding="utf-8")
    skipped = root / "node_modules"
    skipped.mkdir()
    (skipped / "dep.js").write_text("should never be indexed" * 50, encoding="utf-8")
    return root


@pytest.fixture
def wired(monkeypatch, solution_dir: Path):
    vm = _FakeVM()
    audit = _FakeAuditLogger()
    monkeypatch.setattr(knowledge, "_vm", vm)
    monkeypatch.setattr(knowledgesync, "_solution_name", "demo")
    monkeypatch.setattr(knowledgesync, "_solution_path", solution_dir)
    monkeypatch.setattr(knowledgesync, "_logger", audit)
    return vm, audit


def test_sync_defaults_to_active_solution_dir(wired, solution_dir):
    vm, _ = wired
    out = knowledgesync.sync({})
    assert Path(out["directory"]) == solution_dir.resolve()
    assert out["solution"] == "demo"
    assert out["chunks_added"] > 0
    assert out["chunks_added"] == len(vm.imported)


def test_sync_passes_solution_scoped_vector_store(monkeypatch, wired, solution_dir):
    """The whole point of the slice: never fall through to the global singleton."""
    vm, _ = wired
    seen = {}

    import src.core.knowledge_syncer as syncer

    real = syncer.sync_directory

    def spy(root, vector_store=None, extensions=None):
        seen["vector_store"] = vector_store
        return real(root, vector_store=vector_store, extensions=extensions)

    monkeypatch.setattr(syncer, "sync_directory", spy)

    knowledgesync.sync({})
    assert seen["vector_store"] is vm, (
        "sync_directory must receive the sidecar VectorMemory"
    )


def test_sync_reports_scan_accounting(wired, solution_dir):
    out = knowledgesync.sync({})
    # 4 files at the root; node_modules/ is excluded from the walk entirely.
    assert out["files_scanned"] == 4
    assert out["files_indexed"] == 2  # project.yaml + README.md
    assert out["skipped"] == 2  # image.png (ext) + empty.md (blank)
    assert out["errors"] == []


def test_sync_never_indexes_skipped_dirs(wired, solution_dir):
    vm, _ = wired
    knowledgesync.sync({})
    sources = {e["metadata"]["source"] for e in vm.imported}
    assert not any(s.startswith("node_modules/") for s in sources)
    assert sources == {"project.yaml", "README.md"}


def test_sync_accepts_explicit_directory(wired, tmp_path):
    other = tmp_path / "docs"
    other.mkdir()
    (other / "notes.md").write_text("Some durable knowledge. " * 100, encoding="utf-8")
    out = knowledgesync.sync({"directory": str(other)})
    assert Path(out["directory"]) == other.resolve()
    assert out["files_indexed"] == 1
    assert out["chunks_added"] > 0


def test_sync_audit_logs_chunk_count(wired):
    _, audit = wired
    out = knowledgesync.sync({})
    assert len(audit.events) == 1
    event = audit.events[0]
    assert event["action_type"] == "knowledge_sync"
    assert event["metadata"]["chunks_added"] == out["chunks_added"]
    assert event["metadata"]["solution"] == "demo"


def test_sync_survives_audit_logger_failure(monkeypatch, wired):
    class _Boom:
        def log_event(self, **kwargs):
            raise RuntimeError("db locked")

    monkeypatch.setattr(knowledgesync, "_logger", _Boom())
    out = knowledgesync.sync({})
    assert out["chunks_added"] > 0


def test_sync_rejects_missing_directory(wired, tmp_path):
    with pytest.raises(RpcError) as e:
        knowledgesync.sync({"directory": str(tmp_path / "nope")})
    assert e.value.code == -32602


def test_sync_rejects_non_string_directory(wired):
    with pytest.raises(RpcError) as e:
        knowledgesync.sync({"directory": 42})
    assert e.value.code == -32602


def test_sync_rejects_non_dict_params(wired):
    with pytest.raises(RpcError):
        knowledgesync.sync("not a dict")


def test_sync_requires_a_directory_when_no_solution(monkeypatch, wired):
    monkeypatch.setattr(knowledgesync, "_solution_path", None)
    with pytest.raises(RpcError) as e:
        knowledgesync.sync({})
    assert e.value.code == -32602


def test_sync_fails_when_vector_memory_unwired(monkeypatch, solution_dir):
    monkeypatch.setattr(knowledge, "_vm", None)
    monkeypatch.setattr(knowledgesync, "_solution_path", solution_dir)
    with pytest.raises(RpcError) as e:
        knowledgesync.sync({})
    assert e.value.code == -32000


def test_sync_empty_directory_imports_nothing(wired, tmp_path):
    empty = tmp_path / "blank"
    empty.mkdir()
    out = knowledgesync.sync({"directory": str(empty)})
    assert out == {
        "directory": str(empty.resolve()),
        "solution": "demo",
        "chunks_added": 0,
        "files_scanned": 0,
        "files_indexed": 0,
        "skipped": 0,
        "errors": [],
    }


def test_real_vector_memory_roundtrip(tmp_path, monkeypatch):
    """End-to-end against a real minimal-mode VectorMemory."""
    monkeypatch.setenv("SAGE_MINIMAL", "1")
    monkeypatch.setenv("SAGE_SOLUTIONS_DIR", str(tmp_path))
    root = tmp_path / "demo"
    root.mkdir()
    (root / "guide.md").write_text(
        "Vector sync knowledge body. " * 100, encoding="utf-8"
    )

    from src.memory.vector_store import VectorMemory

    vm = VectorMemory(explicit_solution="demo")
    monkeypatch.setattr(knowledge, "_vm", vm)
    monkeypatch.setattr(knowledgesync, "_solution_name", "demo")
    monkeypatch.setattr(knowledgesync, "_solution_path", root)
    monkeypatch.setattr(knowledgesync, "_logger", _FakeAuditLogger())

    out = knowledgesync.sync({})
    assert out["chunks_added"] > 0

    hits = knowledge.search({"query": "Vector sync knowledge"})
    assert hits["count"] >= 1
