"""Assemble a Tauri updater `latest.json` from signed bundle artifacts.

The Tauri updater plugin expects a JSON document at the endpoint URL that
lists per-platform download URL + detached signature. This script walks
the `--dist` directory looking for `.msi` / `-setup.exe` / `.dmg` /
`.AppImage` files plus their `.sig` siblings and emits the manifest.

Usage (CI):
    python sage-desktop/scripts/generate-latest-json.py \
        --version 0.1.0 \
        --repo suman-harapanahalli/SAGE \
        --dist dist \
        --out dist/latest.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Tauri 2 platform identifiers documented at tauri.app/plugin/updater
PLATFORM_KEYS = {
    ".msi": "windows-x86_64",
    "-setup.exe": "windows-x86_64",
    ".dmg": "darwin-x86_64",
    ".AppImage": "linux-x86_64",
}


def _download_url(repo: str, tag: str, filename: str) -> str:
    return f"https://github.com/{repo}/releases/download/{tag}/{filename}"


def _detect_platform(filename: str) -> str | None:
    for suffix, key in PLATFORM_KEYS.items():
        if filename.endswith(suffix):
            return key
    return None


def build_manifest(version: str, repo: str, dist: Path, tag: str) -> dict:
    platforms: dict[str, dict[str, str]] = {}
    for path in sorted(dist.iterdir()):
        if not path.is_file() or path.suffix == ".sig":
            continue
        platform = _detect_platform(path.name)
        if platform is None:
            continue
        sig_path = path.with_name(path.name + ".sig")
        if not sig_path.exists():
            print(f"warn: missing signature for {path.name}", file=sys.stderr)
            continue
        platforms[platform] = {
            "signature": sig_path.read_text(encoding="utf-8").strip(),
            "url": _download_url(repo, tag, path.name),
        }

    if not platforms:
        raise SystemExit(f"no signed bundles found under {dist}")

    return {
        "version": version,
        "pub_date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": f"SAGE Desktop {version}",
        "platforms": platforms,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--version", required=True)
    p.add_argument("--repo", required=True)
    p.add_argument("--dist", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument(
        "--tag",
        default=None,
        help="git tag (default: sage-desktop-v<version>)",
    )
    args = p.parse_args()

    tag = args.tag or f"sage-desktop-v{args.version}"
    manifest = build_manifest(args.version, args.repo, args.dist, tag)
    args.out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
