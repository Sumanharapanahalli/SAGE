#!/usr/bin/env bash
# Build the standalone sage-sidecar executable from sage-sidecar.spec.
#
# Output:
#   Windows: sage-desktop/sidecar/dist/sage-sidecar.exe
#   macOS:   sage-desktop/sidecar/dist/sage-sidecar
#   Linux:   sage-desktop/sidecar/dist/sage-sidecar
#
# Prereq: the repo-root .venv exists and has pyinstaller installed
#         (make venv; .venv/{Scripts,bin}/pip install pyinstaller).
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
desktop_dir="$(cd "${script_dir}/.." && pwd)"
repo_root="$(cd "${desktop_dir}/.." && pwd)"

# Resolve the venv Python — Windows Git Bash uses Scripts/, POSIX uses bin/.
if [[ -x "${repo_root}/.venv/Scripts/python.exe" ]]; then
    py="${repo_root}/.venv/Scripts/python.exe"
    exe_ext=".exe"
elif [[ -x "${repo_root}/.venv/bin/python" ]]; then
    py="${repo_root}/.venv/bin/python"
    exe_ext=""
else
    echo "ERROR: no .venv found at ${repo_root}/.venv — run 'make venv' first" >&2
    exit 1
fi

cd "${desktop_dir}/sidecar"
rm -rf build dist

"${py}" -m PyInstaller \
    --distpath dist \
    --workpath build \
    --clean \
    sage-sidecar.spec

exe="dist/sage-sidecar${exe_ext}"
if [[ ! -f "${exe}" ]]; then
    echo "ERROR: build completed but ${exe} missing" >&2
    exit 1
fi

# Portable byte-size (GNU stat vs BSD stat).
size_bytes=$(stat -c '%s' "${exe}" 2>/dev/null || stat -f '%z' "${exe}")
echo "built: ${exe} ($((size_bytes / 1024 / 1024)) MB)"
