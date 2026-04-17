"""Unit tests for scripts/generate-latest-json.py.

The release workflow pipes bundle artifacts into this script to produce
the `latest.json` manifest the Tauri updater reads. Getting the platform
keys wrong means auto-update silently fails for some users on update day,
so drift-guard these with fast unit tests rather than waiting for the
release to blow up.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts" / "generate-latest-json.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("generate_latest_json", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def mod():
    return _load_module()


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("SAGE Desktop_0.1.0_x64_en-US.msi", "windows-x86_64"),
        ("SAGE Desktop_0.1.0_x64-setup.exe", "windows-x86_64"),
        ("SAGE Desktop_0.1.0_x64.dmg", "darwin-x86_64"),
        ("SAGE Desktop_0.1.0_aarch64.dmg", "darwin-aarch64"),
        ("SAGE Desktop_0.1.0_arm64.dmg", "darwin-aarch64"),
        ("sage-desktop_0.1.0_amd64.AppImage", "linux-x86_64"),
        ("sage-desktop_0.1.0_aarch64.AppImage", "linux-aarch64"),
        ("sage-desktop_0.1.0_arm64.AppImage", "linux-aarch64"),
        ("sage-desktop_0.1.0_amd64.deb", None),  # .deb is not a Tauri updater target
        ("README.md", None),
    ],
)
def test_detect_platform_maps_every_supported_bundle(mod, filename, expected):
    assert mod._detect_platform(filename) == expected


def test_build_manifest_wires_signatures_and_urls(tmp_path, mod):
    # Lay out a Windows MSI + macOS arm DMG + Linux AppImage with .sig siblings.
    fixtures = {
        "SAGE Desktop_0.1.0_x64_en-US.msi": "sig-win-msi",
        "SAGE Desktop_0.1.0_aarch64.dmg": "sig-mac-arm",
        "sage-desktop_0.1.0_amd64.AppImage": "sig-linux-x64",
    }
    for name, sig in fixtures.items():
        (tmp_path / name).write_bytes(b"bundle")
        (tmp_path / f"{name}.sig").write_text(sig, encoding="utf-8")

    manifest = mod.build_manifest(
        version="0.1.0",
        repo="acme/sage",
        dist=tmp_path,
        tag="sage-desktop-v0.1.0",
    )

    assert manifest["version"] == "0.1.0"
    assert set(manifest["platforms"].keys()) == {
        "windows-x86_64",
        "darwin-aarch64",
        "linux-x86_64",
    }
    assert manifest["platforms"]["darwin-aarch64"]["signature"] == "sig-mac-arm"
    assert manifest["platforms"]["linux-x86_64"]["url"].startswith(
        "https://github.com/acme/sage/releases/download/sage-desktop-v0.1.0/"
    )


def test_build_manifest_skips_unsigned_bundles(tmp_path, mod, capsys):
    (tmp_path / "SAGE Desktop_0.1.0_x64_en-US.msi").write_bytes(b"x")
    # no sig file for the MSI, but include a signed dmg so we don't raise.
    (tmp_path / "SAGE Desktop_0.1.0_x64.dmg").write_bytes(b"y")
    (tmp_path / "SAGE Desktop_0.1.0_x64.dmg.sig").write_text("sig-mac", encoding="utf-8")

    manifest = mod.build_manifest(
        version="0.1.0",
        repo="acme/sage",
        dist=tmp_path,
        tag="sage-desktop-v0.1.0",
    )
    captured = capsys.readouterr()
    assert "missing signature" in captured.err
    assert set(manifest["platforms"]) == {"darwin-x86_64"}


def test_build_manifest_raises_when_nothing_signed(tmp_path, mod):
    (tmp_path / "README.md").write_text("noop", encoding="utf-8")
    with pytest.raises(SystemExit):
        mod.build_manifest(
            version="0.1.0",
            repo="acme/sage",
            dist=tmp_path,
            tag="sage-desktop-v0.1.0",
        )


def test_manifest_is_valid_json(tmp_path, mod):
    (tmp_path / "SAGE Desktop_0.1.0_x64.dmg").write_bytes(b"y")
    (tmp_path / "SAGE Desktop_0.1.0_x64.dmg.sig").write_text("sig", encoding="utf-8")
    manifest = mod.build_manifest(
        version="0.1.0",
        repo="acme/sage",
        dist=tmp_path,
        tag="sage-desktop-v0.1.0",
    )
    # Round-trip through json to ensure no non-serializable types leaked in.
    json.loads(json.dumps(manifest))
