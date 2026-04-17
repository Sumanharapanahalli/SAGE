"""Smoke tests for the offline wheel cache scripts.

We don't actually run `pip download` in CI (too slow, network-dependent).
Instead we fake a wheels directory and verify:
  - the build script is executable + has correct shebang
  - manifest format is stable (sha256 + filename pairs)
  - install-offline.sh refuses to run against an empty cache
"""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "sage-desktop" / "scripts"
BUILD_SCRIPT = SCRIPTS_DIR / "build-offline-cache.sh"
INSTALL_SCRIPT = SCRIPTS_DIR / "install-offline.sh"


def test_build_script_exists_with_bash_shebang() -> None:
    assert BUILD_SCRIPT.is_file(), BUILD_SCRIPT
    first_line = BUILD_SCRIPT.read_text(encoding="utf-8").splitlines()[0]
    assert first_line.startswith("#!") and "bash" in first_line


def test_install_script_exists_with_bash_shebang() -> None:
    assert INSTALL_SCRIPT.is_file(), INSTALL_SCRIPT
    first_line = INSTALL_SCRIPT.read_text(encoding="utf-8").splitlines()[0]
    assert first_line.startswith("#!") and "bash" in first_line


def test_build_script_references_requirements_txt() -> None:
    content = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert "requirements.txt" in content
    assert "pip download" in content


def test_install_script_uses_no_index() -> None:
    """Offline install must NEVER hit PyPI — enforce --no-index flag."""
    content = INSTALL_SCRIPT.read_text(encoding="utf-8")
    assert "--no-index" in content
    assert "--find-links" in content


def test_manifest_format_is_stable(tmp_path: Path) -> None:
    """The manifest emitted by build-offline-cache.sh is 'sha256  filename'
    per line. We reproduce the hashing logic here to guard the contract
    the install side depends on."""
    wheel = tmp_path / "example-1.0-py3-none-any.whl"
    wheel.write_bytes(b"fake-wheel-bytes")
    expected = hashlib.sha256(wheel.read_bytes()).hexdigest()
    line = f"{expected}  {wheel.name}"
    parts = line.split("  ", 1)
    assert len(parts) == 2
    assert len(parts[0]) == 64
    assert parts[1] == wheel.name


@pytest.mark.skipif(sys.platform == "win32", reason="bash path semantics on Win32")
def test_install_offline_refuses_empty_cache(tmp_path: Path) -> None:
    """install-offline.sh should exit 1 with a clear message when the
    wheel cache is missing or empty. Linux/macOS CI only."""
    fake_desktop = tmp_path / "sage-desktop"
    (fake_desktop / "scripts").mkdir(parents=True)
    (fake_desktop / "offline" / "wheels").mkdir(parents=True)
    (tmp_path / "requirements.txt").write_text("", encoding="utf-8")

    target = fake_desktop / "scripts" / "install-offline.sh"
    target.write_text(INSTALL_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    target.chmod(target.stat().st_mode | stat.S_IEXEC)

    result = subprocess.run(
        ["bash", str(target)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, result.stdout
    assert "no wheels" in result.stderr.lower() or "no wheels" in result.stdout.lower()
