#!/usr/bin/env bash
# Generate an ed25519 keypair for Tauri updater signatures.
#
# Outputs:
#   sage-desktop/keys/sage-desktop.key   # SECRET — gitignored
#   sage-desktop/keys/sage-desktop.pub   # pubkey — committed, pasted into tauri.conf.json
#
# The private key is password-protected by the signer command — keep the
# passphrase in a password manager. For CI signing, export TAURI_SIGNING_PRIVATE_KEY
# + TAURI_SIGNING_PRIVATE_KEY_PASSWORD before running `tauri build`.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
desktop_dir="$(cd "${script_dir}/.." && pwd)"
keys_dir="${desktop_dir}/keys"

mkdir -p "${keys_dir}"

cd "${desktop_dir}"
npx -y @tauri-apps/cli@2 signer generate \
    --write-keys "${keys_dir}/sage-desktop.key"

echo ""
echo "Keys written to: ${keys_dir}/"
echo "  sage-desktop.key  (PRIVATE — gitignored, keep passphrase safe)"
echo "  sage-desktop.key.pub  (PUBLIC — paste content into tauri.conf.json)"
