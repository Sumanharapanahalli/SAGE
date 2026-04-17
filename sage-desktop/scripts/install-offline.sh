#!/usr/bin/env bash
# Install SAGE Python deps into an existing venv using ONLY the bundled
# wheel cache — no PyPI network traffic.
#
# Usage (inside an activated venv):
#   bash sage-desktop/scripts/install-offline.sh
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
desktop_dir="$(cd "${script_dir}/.." && pwd)"
repo_root="$(cd "${desktop_dir}/.." && pwd)"
wheels_dir="${desktop_dir}/offline/wheels"

if [[ ! -d "${wheels_dir}" ]] || [[ -z "$(ls -A "${wheels_dir}" 2>/dev/null)" ]]; then
    echo "ERROR: no wheels under ${wheels_dir} — run build-offline-cache.sh first" >&2
    exit 1
fi

python -m pip install \
    --no-index \
    --find-links "${wheels_dir}" \
    --requirement "${repo_root}/requirements.txt"

echo "offline install complete (wheels from ${wheels_dir})"
