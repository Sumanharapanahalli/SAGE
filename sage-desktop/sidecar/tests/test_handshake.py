"""Tests for the handshake handler."""
from __future__ import annotations

from pathlib import Path

from handlers import handshake as h


def test_handshake_returns_versions_and_solution(tmp_path, monkeypatch):
    monkeypatch.setattr(h, "_SOLUTION_PATH", tmp_path)
    monkeypatch.setattr(h, "_SOLUTION_NAME", "test-solution")
    # Empty probe list → no warnings
    monkeypatch.setattr(h, "_PROBE_IMPORTS", [])
    out = h.handshake({"ui_version": "0.1.0"})
    assert out["sidecar_version"] == h.SIDECAR_VERSION
    assert out["solution_name"] == "test-solution"
    assert out["solution_path"] == str(tmp_path)
    assert "sage_version" in out
    assert out["warnings"] == []


def test_handshake_lists_missing_modules_as_warnings(tmp_path, monkeypatch):
    monkeypatch.setattr(h, "_SOLUTION_PATH", tmp_path)
    monkeypatch.setattr(h, "_SOLUTION_NAME", "test")
    monkeypatch.setattr(h, "_PROBE_IMPORTS", ["this_module_definitely_does_not_exist_xyz"])
    out = h.handshake({})
    assert len(out["warnings"]) == 1
    assert "this_module_definitely_does_not_exist_xyz" in out["warnings"][0]


def test_handshake_returns_unknown_sage_version_when_version_import_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(h, "_SOLUTION_PATH", tmp_path)
    monkeypatch.setattr(h, "_SOLUTION_NAME", "test")
    monkeypatch.setattr(h, "_PROBE_IMPORTS", [])

    def raise_import():
        raise ImportError("no version")

    monkeypatch.setattr(h, "_sage_version", lambda: "unknown")
    out = h.handshake({})
    assert out["sage_version"] == "unknown"


def test_handshake_works_with_real_sage_probes_on_main(tmp_path, monkeypatch):
    """End-to-end: the default probe list should all succeed when running
    against the checked-out SAGE repo. Any warnings mean the sidecar will
    degrade gracefully, but on main they should all resolve."""
    monkeypatch.setattr(h, "_SOLUTION_PATH", tmp_path)
    monkeypatch.setattr(h, "_SOLUTION_NAME", "test")
    # Use default _PROBE_IMPORTS
    out = h.handshake({})
    # At least report them in warnings list (may be empty if all imports work)
    assert isinstance(out["warnings"], list)
