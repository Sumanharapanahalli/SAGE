#!/usr/bin/env bash
# Sign the Windows release artifacts with the Tauri updater ed25519 key.
#
# Tauri's own bundler signs `.msi` and `-setup.exe` at build time when
# TAURI_SIGNING_PRIVATE_KEY + TAURI_SIGNING_PRIVATE_KEY_PASSWORD are set.
# This script is for the out-of-band case: you already have the
# installer artifacts (built via `tauri build --no-bundle` + a separate
# bundler, or pulled from CI cache) and need to produce the `.sig`
# files that the updater manifest references.
#
# Usage:
#   TAURI_SIGNING_PRIVATE_KEY=<key_path_or_contents> \
#   TAURI_SIGNING_PRIVATE_KEY_PASSWORD=<passphrase> \
#   scripts/sign-release.sh src-tauri/target/release/bundle
#
# Output: a <artifact>.sig file next to every .msi and -setup.exe in
# the given directory tree.
set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "usage: $0 <bundle-dir>" >&2
    exit 2
fi

bundle_dir="$1"

if [[ ! -d "${bundle_dir}" ]]; then
    echo "error: ${bundle_dir} is not a directory" >&2
    exit 2
fi

if [[ -z "${TAURI_SIGNING_PRIVATE_KEY:-}" ]]; then
    echo "error: TAURI_SIGNING_PRIVATE_KEY is not set" >&2
    exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
desktop_dir="$(cd "${script_dir}/.." && pwd)"
cd "${desktop_dir}"

signed=0

# Portable "find & iterate" without relying on find -print0 on Git Bash
while IFS= read -r -d '' artifact; do
    echo "signing: ${artifact}"
    npx -y @tauri-apps/cli@2 signer sign \
        --private-key "${TAURI_SIGNING_PRIVATE_KEY}" \
        "${artifact}"
    if [[ ! -f "${artifact}.sig" ]]; then
        echo "error: expected ${artifact}.sig to exist after signing" >&2
        exit 3
    fi
    signed=$((signed + 1))
done < <(find "${bundle_dir}" \( -name "*.msi" -o -name "*-setup.exe" \) -type f -print0)

if [[ ${signed} -eq 0 ]]; then
    echo "error: no .msi or -setup.exe found under ${bundle_dir}" >&2
    exit 3
fi

echo ""
echo "Signed ${signed} artifact(s)."
echo "The resulting .sig files feed into scripts/generate-latest-json.py"
echo "and must be committed alongside the updater feed manifest."
