# SAGE Desktop

A native Windows desktop app that gives a SAGE operator the full
human-in-the-loop approval workflow **without any listening sockets,
ports, or admin privileges**. Designed for locked-down corporate
environments where endpoint security blocks loopback access.

- No ports, no FastAPI, no admin elevation.
- One `.exe`; the Python sidecar is bundled inside.
- Consumes the same `.sage/` SQLite + Chroma files as the web UI and
  VS Code extension — single source of truth.

The deep architecture doc lives at
[`.claude/docs/interfaces/desktop-gui.md`](../.claude/docs/interfaces/desktop-gui.md).
This README covers **install, update, and privacy** for the packaged
Phase 4 release.

---

## Install (end user)

### 1. Download

Grab the latest `SAGE Desktop_<version>_x64_en-US.msi` from the
repository's Releases page. If MSI is blocked by policy on your
machine, the same release also publishes a `SAGE Desktop_<version>_x64-setup.exe`
(NSIS) — identical payload, different installer format.

Both installers are **per-user**: they install to
`%LOCALAPPDATA%\Programs\sage-desktop\` and never prompt for admin.

### 2. SmartScreen caveat (Phase 4 only)

Phase 4 ships the installer **unsigned**. The first time you run it,
Windows SmartScreen will display:

```
Windows protected your PC

Microsoft Defender SmartScreen prevented an unrecognized app from
starting. Running this app might put your PC at risk.
```

Click **"More info"** → **"Run anyway"**. This is expected. Code
signing with an EV cert lands in Phase 4.6; until then, each release
is verified by its ed25519 signature at update time — SmartScreen is
Microsoft's Authenticode layer, which is separate.

### 3. Launch

After install, launch **SAGE Desktop** from the Start menu. On first
launch the app uses the default solution it was built against
(`solutions/starter` unless your build was customized). Switch
solutions from **Sidebar → current solution footer → "Switch"**.

If the app window is blank, the sidecar subprocess probably failed to
start. Open **Status** from the sidebar — if the page reads "Offline",
click **Retry** on the recovery panel for copy-pasteable diagnostics.

---

## Auto-update

Go to **Settings → Application updates** and click **Check for
updates**.

- **Up to date** — your installed version matches the latest release.
- **Update available** — shows the new version number + release notes.
  Click **Download and install** to replace the installed exe. The app
  restarts automatically after install.
- **Error** — a red banner with the underlying error (bad signature,
  offline, release feed unavailable).

Every release is signed with the ed25519 key whose public counterpart
ships committed at `src-tauri/keys/sage-desktop.pub` and baked into
the app via `tauri.conf.json.plugins.updater.pubkey`. An unsigned or
tampered installer is rejected at install time by the Tauri updater
— it never touches your disk. There is no opt-out on the signature
check; that is the safety property.

Phase 4 does **not** check for updates in the background at launch.
Every update check is user-initiated from the Settings panel. The
next release feed URL is read from `tauri.conf.json.plugins.updater.endpoints`
— currently the GitHub Releases `latest.json` for this repo.

---

## Privacy & telemetry

**Telemetry is OFF by default** and is a strictly bounded opt-in. The
full contract is documented at [`docs/PRIVACY.md`](../docs/PRIVACY.md);
the short version:

- Go to **Settings → Telemetry**. The checkbox is unchecked on a fresh
  install. Nothing is sent while it is unchecked.
- When you opt in, the app generates a random anonymous UUID
  (`anon_id`) and a per-launch `session_id`. The `anon_id` is stored
  in `%APPDATA%\sage-desktop\config.json` and kept across opt-out so
  re-enabling doesn't look like a new user. `session_id` never
  touches disk.
- Each event carries at most: an allowlisted `event` name (e.g.
  `approval.decided`, `build.completed`, `update.installed`) and a
  handful of allowlisted non-content fields: `kind`, `status`,
  `action_type`, `route`, `duration_ms`, `count`, `ok`, `error_kind`.
- **Guaranteed not sent**: proposal content, `trace_id` values, your
  email, your user name, the solution name, file paths, raw prompts,
  LLM outputs, stack traces. The allowlist is enforced by construction
  — `filter_payload()` builds a new dict from scratch and only copies
  keys that pass the frozen allowlist; anything unknown is dropped,
  period.
- Opting back out clears the buffered events on disk
  (`%APPDATA%\sage-desktop\telemetry.ndjson`).

Phase 4 ships the **local buffer only** — no HTTPS uploader is wired.
That means even with telemetry enabled, no events leave your device
in Phase 4. The upload transport is Phase 4.6; the release notes for
that version will name the destination before any network egress is
added.

---

## File locations

| What | Path (Windows) |
|---|---|
| App binaries | `%LOCALAPPDATA%\Programs\sage-desktop\` |
| Consent + anon ID | `%APPDATA%\sage-desktop\config.json` |
| Telemetry buffer | `%APPDATA%\sage-desktop\telemetry.ndjson` |
| Updater pubkey | bundled inside `sage-desktop.exe` |
| Active solution's data | `<solution-root>\.sage\*` |

To wipe every trace of the app: uninstall from **Settings → Apps**,
then delete `%APPDATA%\sage-desktop\`. `.sage/` data under your
solution directory is preserved — the framework never touches it on
uninstall.

---

## Build from source (developers)

For the dev loop, follow the top-level `CLAUDE.md` **Quick Start**
section and the deep dive at
[`.claude/docs/interfaces/desktop-gui.md`](../.claude/docs/interfaces/desktop-gui.md).

Packaging-relevant commands from the repo root:

```bash
# One-time: install npm deps into sage-desktop/
make desktop-install

# Dev loop (Vite + Rust + source Python sidecar)
make desktop-dev

# Package the PyInstaller sidecar exe
make desktop-bundle

# Build the installer(s) — requires make desktop-bundle first
make desktop-msi           # Windows MSI
make desktop-nsis          # NSIS fallback

# Air-gapped-friendly pip cache for contributor machines
make desktop-offline-cache

# Mutation testing (Rust only in Phase 4)
make desktop-mutate-rs

# Full local test sweep (sidecar pytest + cargo test --lib + vitest)
make test-desktop

# Real-sidecar round-trip
make test-desktop-e2e
```

### Ed25519 updater keypair

Contributors publishing releases need the updater keypair. Generate it
once with `scripts/generate-keypair.sh`; commit only the `.pub` half.
The private key is gitignored. CI signs releases via the
`TAURI_SIGNING_PRIVATE_KEY` + `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`
environment variables — never by reading the key from the repo.

---

## Status and limits

Phase 4 is **Windows only**. macOS notarization and Linux AppImage are
scoped to a follow-up phase. The MSI/NSIS target is x86_64 Windows
10+ with WebView2 runtime (installed via the Tauri bootstrapper).

For bug reports, open an issue on the upstream SAGE repository and tag
`sage-desktop` + `phase-4`.
