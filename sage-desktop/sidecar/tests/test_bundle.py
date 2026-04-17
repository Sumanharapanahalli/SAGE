"""Smoke test for the PyInstaller-bundled sidecar.

Runs the standalone ``sage-sidecar.exe`` in a subprocess and verifies it
responds to the handshake RPC identically to ``python app.py``. Skipped
automatically when the bundle hasn't been built (``make desktop-bundle``).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_EXE_NAME = "sage-sidecar.exe" if sys.platform == "win32" else "sage-sidecar"
BUNDLE_PATH = Path(__file__).resolve().parents[1] / "dist" / _EXE_NAME


def _send(proc: subprocess.Popen[str], method: str, params: dict | None = None) -> dict:
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {},
    }
    assert proc.stdin is not None
    assert proc.stdout is not None
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    return json.loads(line)


@pytest.mark.skipif(not BUNDLE_PATH.exists(), reason=f"bundle not built: {BUNDLE_PATH}")
def test_bundled_sidecar_handshake_roundtrip():
    env = os.environ.copy()
    # PyInstaller bundle must NOT need SAGE_ROOT; the repo is embedded.
    env.pop("SAGE_ROOT", None)
    proc = subprocess.Popen(
        [str(BUNDLE_PATH), "--solution-name", "starter"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        resp = _send(proc, "handshake")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    assert str(resp["id"]) == "1", resp
    assert "result" in resp, resp
    assert resp["result"]["sidecar_version"]


@pytest.mark.skipif(not BUNDLE_PATH.exists(), reason=f"bundle not built: {BUNDLE_PATH}")
def test_bundled_sidecar_responds_to_status():
    env = os.environ.copy()
    env.pop("SAGE_ROOT", None)
    proc = subprocess.Popen(
        [str(BUNDLE_PATH), "--solution-name", "starter"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        _send(proc, "handshake")
        resp = _send(proc, "status.get")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    assert str(resp["id"]) == "1", resp
    assert "result" in resp, resp
    assert resp["result"]["health"]
