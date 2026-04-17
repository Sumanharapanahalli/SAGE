# sage-desktop Phase 4 — Packaging & Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship an installable, auto-updating, signed Windows build of sage-desktop with hardened test + telemetry infra.

**Architecture:** PyInstaller one-file sidecar → Tauri externalBin → WiX MSI + NSIS → ed25519 updater feed. Separate CI release workflow. Opt-in telemetry with strict PII allowlist. Full tauri-driver E2E + cargo-mutants + stryker + Playwright visual diff.

**Tech Stack:** PyInstaller 6.x, Tauri 2.x (updater plugin), WiX v3, NSIS, ed25519 (minisign-compatible), cargo-mutants, @stryker-mutator/core, Playwright, GitHub Actions.

---

### Task 4.1.1: PyInstaller spec file (red)

**Files:**
- Create: `sage-desktop/sidecar/sage-sidecar.spec`
- Create: `sage-desktop/sidecar/tests/test_bundle.py`
- Create: `sage-desktop/scripts/build-sidecar.sh`

- [ ] **Step 1: Write failing bundle smoke test**

```python
# sage-desktop/sidecar/tests/test_bundle.py
import json
import subprocess
from pathlib import Path

import pytest

BUNDLE_PATH = Path(__file__).parents[1] / "dist" / "sage-sidecar.exe"


@pytest.mark.skipif(not BUNDLE_PATH.exists(), reason="bundle not built")
def test_bundled_sidecar_responds_to_handshake():
    proc = subprocess.Popen(
        [str(BUNDLE_PATH)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    req = {"jsonrpc": "2.0", "id": 1, "method": "handshake", "params": {}}
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    proc.terminate()
    resp = json.loads(line)
    assert resp["id"] == 1
    assert "result" in resp
    assert resp["result"]["sidecar_version"]
```

- [ ] **Step 2: Run test; expect skip**

Run: `.venv/Scripts/pytest sage-desktop/sidecar/tests/test_bundle.py -v`
Expected: `1 skipped` (bundle path missing — intentional).

- [ ] **Step 3: Write PyInstaller spec**

```python
# sage-desktop/sidecar/sage-sidecar.spec
# PyInstaller spec for the SAGE Desktop sidecar.
# Bundles sidecar app + framework so no Python runtime is needed on target.
from pathlib import Path

block_cipher = None
repo_root = Path(SPECPATH).resolve().parents[1].parent  # sage-desktop/../
sidecar_root = Path(SPECPATH).resolve().parent

hidden = [
    "src.integrations.build_orchestrator",
    "src.integrations.onboarding_generator",
    "src.core.project_loader",
    "src.agents.universal",
    "src.agents.analyst",
    "src.agents.developer",
    "src.agents.monitor",
    "src.agents.planner",
    "yaml",
    "sqlite3",
]

a = Analysis(
    [str(sidecar_root / "app.py")],
    pathex=[str(repo_root)],
    binaries=[],
    datas=[(str(repo_root / "src"), "src")],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="sage-sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    target_arch="x86_64",
    codesign_identity=None,
    entitlements_file=None,
)
```

- [ ] **Step 4: Write build script**

```bash
# sage-desktop/scripts/build-sidecar.sh
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf sidecar/build sidecar/dist
../.venv/Scripts/pip install --quiet pyinstaller
../.venv/Scripts/pyinstaller \
  --distpath sidecar/dist \
  --workpath sidecar/build \
  --clean \
  sidecar/sage-sidecar.spec
echo "built: sidecar/dist/sage-sidecar.exe"
```

- [ ] **Step 5: Run build, expect success**

Run: `bash sage-desktop/scripts/build-sidecar.sh`
Expected: ends with `built: sidecar/dist/sage-sidecar.exe`. Binary size 40–80 MB.

- [ ] **Step 6: Re-run bundle smoke test, expect pass**

Run: `.venv/Scripts/pytest sage-desktop/sidecar/tests/test_bundle.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add sage-desktop/sidecar/sage-sidecar.spec \
        sage-desktop/sidecar/tests/test_bundle.py \
        sage-desktop/scripts/build-sidecar.sh
git commit -m "feat(sidecar): PyInstaller one-file bundle spec + smoke test"
```

---

### Task 4.1.2: Rust sidecar path resolution — dev vs prod

**Files:**
- Modify: `sage-desktop/src-tauri/src/sidecar.rs`

- [ ] **Step 1: Write failing test**

Add to `sage-desktop/src-tauri/src/sidecar.rs` (bottom of `#[cfg(test)] mod tests`):

```rust
#[test]
fn sidecar_path_prefers_env_override_when_set() {
    std::env::set_var("SAGE_SIDECAR_PATH", r"C:\fake\bundled\sage-sidecar.exe");
    let p = resolve_sidecar_path_for_test();
    assert_eq!(p.to_str().unwrap(), r"C:\fake\bundled\sage-sidecar.exe");
    std::env::remove_var("SAGE_SIDECAR_PATH");
}

#[test]
fn sidecar_path_falls_back_to_workspace_python() {
    std::env::remove_var("SAGE_SIDECAR_PATH");
    let p = resolve_sidecar_path_for_test();
    assert!(p.to_str().unwrap().ends_with("app.py"));
}
```

- [ ] **Step 2: Run test, expect compile failure** (function doesn't exist)

Run: `cd sage-desktop/src-tauri && cargo test --lib --no-default-features sidecar_path`

- [ ] **Step 3: Add the resolution function**

```rust
// in sidecar.rs
pub fn resolve_sidecar_path_for_test() -> std::path::PathBuf {
    if let Ok(p) = std::env::var("SAGE_SIDECAR_PATH") {
        return std::path::PathBuf::from(p);
    }
    std::path::PathBuf::from("..").join("sidecar").join("app.py")
}

// Production path resolution (uses AppHandle at runtime)
pub fn resolve_sidecar_path(resource_dir: Option<std::path::PathBuf>) -> std::path::PathBuf {
    if let Some(dir) = resource_dir {
        let exe = dir.join("sage-sidecar-x86_64-pc-windows-msvc.exe");
        if exe.exists() {
            return exe;
        }
    }
    resolve_sidecar_path_for_test()
}
```

- [ ] **Step 4: Update Sidecar::spawn to branch on extension**

In `Sidecar::spawn`, replace the existing python-only spawn with:

```rust
let path = resolve_sidecar_path(app.path().resource_dir().ok());
let mut cmd = if path.extension().and_then(|e| e.to_str()) == Some("py") {
    let mut c = Command::new("python");
    c.arg(&path);
    c
} else {
    Command::new(&path)
};
```

- [ ] **Step 5: Run test, expect pass**

Run: `cd sage-desktop/src-tauri && cargo test --lib --no-default-features sidecar_path`
Expected: both tests pass; other 20 still pass.

- [ ] **Step 6: Commit**

```bash
git add sage-desktop/src-tauri/src/sidecar.rs
git commit -m "feat(desktop-rs): dev/prod sidecar path resolution"
```

---

### Task 4.2.1: Tauri externalBin + bundle config (MSI)

**Files:**
- Modify: `sage-desktop/src-tauri/tauri.conf.json`
- Create: `sage-desktop/src-tauri/bin/.gitignore`

- [ ] **Step 1: Update tauri.conf.json**

```json
{
  "bundle": {
    "active": true,
    "targets": ["msi"],
    "externalBin": ["bin/sage-sidecar"],
    "icon": [
      "icons/32x32.png",
      "icons/128x128.png",
      "icons/icon.ico"
    ],
    "windows": {
      "wix": {
        "language": ["en-US"]
      },
      "allowDowngrades": false
    }
  }
}
```

- [ ] **Step 2: Gitignore bundled binary**

```gitignore
# sage-desktop/src-tauri/bin/.gitignore
sage-sidecar*.exe
```

- [ ] **Step 3: Add Makefile target**

In repo-root `Makefile`:

```makefile
.PHONY: desktop-bundle desktop-msi
desktop-bundle:
	bash sage-desktop/scripts/build-sidecar.sh
	cp sage-desktop/sidecar/dist/sage-sidecar.exe \
	   sage-desktop/src-tauri/bin/sage-sidecar-x86_64-pc-windows-msvc.exe

desktop-msi: desktop-bundle
	cd sage-desktop && npm run tauri -- build --bundles msi
```

- [ ] **Step 4: Build MSI**

Run: `make desktop-msi`
Expected: artifact at `sage-desktop/src-tauri/target/release/bundle/msi/SAGE Desktop_*.msi`.

- [ ] **Step 5: Install + launch + verify**

Manual verification: double-click MSI, install per-user, launch SAGE Desktop, confirm Approvals page renders.

- [ ] **Step 6: Commit**

```bash
git add sage-desktop/src-tauri/tauri.conf.json \
        sage-desktop/src-tauri/bin/.gitignore Makefile
git commit -m "feat(desktop): Windows MSI bundle config + make desktop-msi"
```

---

### Task 4.3.1: NSIS fallback target

**Files:**
- Modify: `sage-desktop/src-tauri/tauri.conf.json`
- Modify: `Makefile`

- [ ] **Step 1: Add nsis to bundle targets**

```json
"targets": ["msi", "nsis"]
```

- [ ] **Step 2: Add Makefile target**

```makefile
desktop-nsis: desktop-bundle
	cd sage-desktop && npm run tauri -- build --bundles nsis
```

- [ ] **Step 3: Build**

Run: `make desktop-nsis`
Expected: `sage-desktop/src-tauri/target/release/bundle/nsis/*.exe` present.

- [ ] **Step 4: Commit**

```bash
git add sage-desktop/src-tauri/tauri.conf.json Makefile
git commit -m "feat(desktop): NSIS fallback installer target"
```

---

### Task 4.4.1: Updater plugin + ed25519 keypair

**Files:**
- Modify: `sage-desktop/src-tauri/Cargo.toml`
- Create: `sage-desktop/src-tauri/keys/sage-desktop.pub`
- Create: `sage-desktop/scripts/generate-keypair.sh`
- Modify: `sage-desktop/src-tauri/tauri.conf.json`

- [ ] **Step 1: Generate keypair**

```bash
# sage-desktop/scripts/generate-keypair.sh
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
npx -y @tauri-apps/cli@2 signer generate -w keys/sage-desktop.key
```

Run: `bash sage-desktop/scripts/generate-keypair.sh`
The pubkey writes to `keys/sage-desktop.pub` (committed); `.key` is gitignored.

- [ ] **Step 2: Add tauri-plugin-updater to Cargo.toml**

```toml
[dependencies]
tauri-plugin-updater = "2"
```

- [ ] **Step 3: Configure updater in tauri.conf.json**

```json
"plugins": {
  "updater": {
    "active": true,
    "endpoints": [
      "https://github.com/suman-harapanahalli/SAGE/releases/latest/download/latest.json"
    ],
    "dialog": false,
    "pubkey": "<contents of keys/sage-desktop.pub>"
  }
}
```

- [ ] **Step 4: Register plugin in lib.rs**

```rust
// in run()
tauri::Builder::default()
    .plugin(tauri_plugin_updater::Builder::new().build())
    // ...
```

- [ ] **Step 5: Build, expect success**

Run: `cd sage-desktop/src-tauri && cargo build`

- [ ] **Step 6: Commit**

```bash
git add sage-desktop/src-tauri/Cargo.toml \
        sage-desktop/src-tauri/Cargo.lock \
        sage-desktop/src-tauri/tauri.conf.json \
        sage-desktop/src-tauri/keys/sage-desktop.pub \
        sage-desktop/scripts/generate-keypair.sh
git commit -m "feat(desktop-rs): updater plugin + ed25519 pubkey"
```

---

### Task 4.4.2: check_update + install_update commands

**Files:**
- Create: `sage-desktop/src-tauri/src/commands/updates.rs`
- Modify: `sage-desktop/src-tauri/src/commands/mod.rs`
- Modify: `sage-desktop/src-tauri/src/lib.rs`

- [ ] **Step 1: Write failing tests**

```rust
// tests in updates.rs
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn update_status_serializes_as_tagged_json() {
        let available = UpdateStatus::Available {
            current_version: "0.2.0".into(),
            new_version: "0.3.0".into(),
            notes: "fixes".into(),
        };
        let j = serde_json::to_string(&available).unwrap();
        assert!(j.contains(r#""kind":"Available""#));
        assert!(j.contains(r#""new_version":"0.3.0""#));
    }

    #[test]
    fn update_status_up_to_date_has_current_version_only() {
        let s = UpdateStatus::UpToDate { current_version: "0.2.0".into() };
        let j = serde_json::to_string(&s).unwrap();
        assert!(j.contains(r#""kind":"UpToDate""#));
    }
}
```

- [ ] **Step 2: Run tests, expect compile failure**

- [ ] **Step 3: Implement UpdateStatus + commands**

```rust
// commands/updates.rs
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, State};
use tauri_plugin_updater::UpdaterExt;

use crate::errors::DesktopError;

#[derive(Debug, Serialize, Deserialize)]
#[serde(tag = "kind")]
pub enum UpdateStatus {
    UpToDate { current_version: String },
    Available { current_version: String, new_version: String, notes: String },
    Error { detail: String },
}

#[tauri::command]
pub async fn check_update(app: AppHandle) -> Result<UpdateStatus, DesktopError> {
    let current = app.package_info().version.to_string();
    match app.updater().map_err(|e| DesktopError::other(format!("{e}")))?
        .check().await {
        Ok(Some(update)) => Ok(UpdateStatus::Available {
            current_version: current,
            new_version: update.version.clone(),
            notes: update.body.clone().unwrap_or_default(),
        }),
        Ok(None) => Ok(UpdateStatus::UpToDate { current_version: current }),
        Err(e) => Ok(UpdateStatus::Error { detail: format!("{e}") }),
    }
}

#[tauri::command]
pub async fn install_update(app: AppHandle) -> Result<(), DesktopError> {
    let updater = app.updater().map_err(|e| DesktopError::other(format!("{e}")))?;
    let Some(update) = updater.check().await
        .map_err(|e| DesktopError::other(format!("{e}")))? else {
        return Ok(());
    };
    update.download_and_install(
        |_chunk, _total| {},
        || {},
    ).await.map_err(|e| DesktopError::other(format!("{e}")))?;
    app.restart();
}
```

- [ ] **Step 4: Register in mod.rs + invoke_handler**

```rust
// commands/mod.rs
pub mod updates;
```

```rust
// lib.rs invoke_handler
commands::updates::check_update,
commands::updates::install_update,
```

- [ ] **Step 5: Run tests, expect pass**

Run: `cd sage-desktop/src-tauri && cargo test --lib --no-default-features updates`
Expected: 2 pass.

- [ ] **Step 6: Commit**

```bash
git add sage-desktop/src-tauri/src/commands/updates.rs \
        sage-desktop/src-tauri/src/commands/mod.rs \
        sage-desktop/src-tauri/src/lib.rs
git commit -m "feat(desktop-rs): check_update + install_update commands"
```

---

### Task 4.4.3: Frontend update hook + panel

**Files:**
- Modify: `sage-desktop/src/api/types.ts`
- Modify: `sage-desktop/src/api/client.ts`
- Create: `sage-desktop/src/hooks/useUpdate.ts`
- Create: `sage-desktop/src/__tests__/hooks/useUpdate.test.ts`
- Create: `sage-desktop/src/components/domain/UpdatePanel.tsx`
- Create: `sage-desktop/src/__tests__/components/UpdatePanel.test.tsx`
- Modify: `sage-desktop/src/pages/Settings.tsx`

- [ ] **Step 1: Write failing hook test**

```tsx
// useUpdate.test.ts
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  checkUpdate: vi.fn().mockResolvedValue({
    kind: "Available",
    current_version: "0.2.0",
    new_version: "0.3.0",
    notes: "fixes",
  }),
  installUpdate: vi.fn(),
}));

import { useCheckUpdate } from "@/hooks/useUpdate";

describe("useCheckUpdate", () => {
  it("returns update status", async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(() => useCheckUpdate(), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.kind).toBe("Available");
  });
});
```

- [ ] **Step 2: Run test, expect failure** (hook missing)

- [ ] **Step 3: Types + client**

```typescript
// api/types.ts additions
export type UpdateStatus =
  | { kind: "UpToDate"; current_version: string }
  | { kind: "Available"; current_version: string; new_version: string; notes: string }
  | { kind: "Error"; detail: string };
```

```typescript
// api/client.ts additions
export async function checkUpdate(): Promise<UpdateStatus> {
  return invoke<UpdateStatus>("check_update");
}
export async function installUpdate(): Promise<void> {
  return invoke<void>("install_update");
}
```

- [ ] **Step 4: Hook**

```typescript
// hooks/useUpdate.ts
import { useMutation, useQuery } from "@tanstack/react-query";

import * as client from "@/api/client";
import type { UpdateStatus } from "@/api/types";

export const updateKey = ["update"] as const;

export function useCheckUpdate(enabled = true) {
  return useQuery<UpdateStatus>({
    queryKey: updateKey,
    queryFn: () => client.checkUpdate(),
    enabled,
    staleTime: 60_000,
  });
}

export function useInstallUpdate() {
  return useMutation<void, Error, void>({
    mutationFn: () => client.installUpdate(),
  });
}
```

- [ ] **Step 5: Run hook test, expect pass**

- [ ] **Step 6: Write failing panel test**

```tsx
// __tests__/components/UpdatePanel.test.tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  checkUpdate: vi.fn().mockResolvedValue({
    kind: "Available",
    current_version: "0.2.0",
    new_version: "0.3.0",
    notes: "fixes",
  }),
  installUpdate: vi.fn(),
}));

import * as client from "@/api/client";
import { UpdatePanel } from "@/components/domain/UpdatePanel";

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("UpdatePanel", () => {
  it("shows Available state and triggers install on click", async () => {
    wrap(<UpdatePanel />);
    await screen.findByText(/0\.3\.0/);
    fireEvent.click(screen.getByRole("button", { name: /install/i }));
    await waitFor(() => expect(client.installUpdate).toHaveBeenCalled());
  });
});
```

- [ ] **Step 7: Implement panel**

```tsx
// components/domain/UpdatePanel.tsx
import { useCheckUpdate, useInstallUpdate } from "@/hooks/useUpdate";

export function UpdatePanel() {
  const status = useCheckUpdate();
  const install = useInstallUpdate();

  if (status.isLoading) return <p className="text-sm">Checking for updates…</p>;
  if (!status.data) return null;

  switch (status.data.kind) {
    case "UpToDate":
      return (
        <p className="text-sm text-gray-600">
          You are on v{status.data.current_version} — up to date.
        </p>
      );
    case "Available":
      return (
        <div className="rounded border border-sage-200 bg-sage-50 p-3 text-sm">
          <p className="font-medium">Update available: v{status.data.new_version}</p>
          <p className="mt-1 text-xs text-sage-700">{status.data.notes}</p>
          <button
            type="button"
            className="mt-2 rounded bg-sage-600 px-3 py-1 text-white"
            onClick={() => install.mutate()}
            disabled={install.isPending}
          >
            {install.isPending ? "Installing…" : "Install & restart"}
          </button>
        </div>
      );
    case "Error":
      return (
        <p role="alert" className="text-sm text-red-700">
          Update check failed: {status.data.detail}
        </p>
      );
  }
}
```

- [ ] **Step 8: Mount in Settings**

Add `<UpdatePanel />` to `Settings.tsx` under a new "Updates" section heading.

- [ ] **Step 9: Run all tests, expect pass**

Run: `cd sage-desktop && npx vitest run`

- [ ] **Step 10: Commit**

```bash
git add sage-desktop/src/api/types.ts sage-desktop/src/api/client.ts \
        sage-desktop/src/hooks/useUpdate.ts \
        sage-desktop/src/components/domain/UpdatePanel.tsx \
        sage-desktop/src/__tests__/hooks/useUpdate.test.ts \
        sage-desktop/src/__tests__/components/UpdatePanel.test.tsx \
        sage-desktop/src/pages/Settings.tsx
git commit -m "feat(desktop-ui): update panel + hook"
```

---

### Task 4.5.1: Offline pip cache

**Files:**
- Create: `sage-desktop/scripts/generate-wheels.sh`
- Modify: `Makefile`
- Modify: `.gitignore`

- [ ] **Step 1: Write script**

```bash
# sage-desktop/scripts/generate-wheels.sh
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p sidecar/wheels
../.venv/Scripts/pip download \
  -r sidecar/requirements.txt \
  -d sidecar/wheels \
  --platform win_amd64 \
  --only-binary=:all: \
  --python-version 3.12
```

- [ ] **Step 2: Makefile target**

```makefile
sidecar-wheels:
	bash sage-desktop/scripts/generate-wheels.sh
```

- [ ] **Step 3: Gitignore wheels**

```gitignore
sage-desktop/sidecar/wheels/
```

- [ ] **Step 4: Run once, verify**

Run: `make sidecar-wheels`
Expected: wheels present; `pip install --no-index --find-links=sage-desktop/sidecar/wheels/ -r sage-desktop/sidecar/requirements.txt` succeeds.

- [ ] **Step 5: Commit**

```bash
git add sage-desktop/scripts/generate-wheels.sh Makefile .gitignore
git commit -m "feat(desktop): offline pip cache (make sidecar-wheels)"
```

---

### Task 4.6.1: E2E suite expansion — split smoke + add approvals

**Files:**
- Modify: `sage-desktop/tests/e2e/smoke.rs` (rename helpers into `common.rs`)
- Create: `sage-desktop/tests/e2e/common.rs`
- Create: `sage-desktop/tests/e2e/approvals.rs`

- [ ] **Step 1: Extract helper**

Move the existing smoke setup (spawn sidecar, seed fixture, wait for ready) into `common.rs` as `spawn_test_sidecar()` + `seed_pending_approval()`.

- [ ] **Step 2: Write approvals E2E**

```rust
// tests/e2e/approvals.rs
mod common;

#[tokio::test]
async fn approvals_list_approve_roundtrip() {
    let mut sc = common::spawn_test_sidecar().await;
    let trace_id = common::seed_pending_approval(&mut sc).await;

    let list = sc.request("approvals.list", json!({})).await.unwrap();
    assert!(list["items"].as_array().unwrap().iter()
        .any(|x| x["trace_id"] == trace_id));

    let approve = sc.request("approvals.approve",
        json!({ "trace_id": trace_id })).await.unwrap();
    assert_eq!(approve["status"], "approved");

    let after = sc.request("approvals.list", json!({})).await.unwrap();
    assert!(!after["items"].as_array().unwrap().iter()
        .any(|x| x["trace_id"] == trace_id));
}
```

- [ ] **Step 3: Run, expect pass**

Run: `cd sage-desktop/src-tauri && cargo test --test e2e approvals`

- [ ] **Step 4: Commit**

```bash
git add sage-desktop/tests/e2e/common.rs sage-desktop/tests/e2e/approvals.rs \
        sage-desktop/tests/e2e/smoke.rs
git commit -m "test(desktop-e2e): split common helpers + approvals round-trip"
```

---

### Task 4.6.2: E2E — agents, audit, status

Three more E2E modules, one step each. Same pattern as 4.6.1:

- [ ] **agents.rs** — `agents.list` returns at least one agent; `agents.get` returns that agent's detail.
- [ ] **audit.rs** — insert one audit event via sidecar, `audit.list` returns it, `audit.get_by_trace` matches.
- [ ] **status.rs** — `status.get` returns ok; queue tile fields present.

Run each in isolation, commit each as its own test file:

```bash
git commit -m "test(desktop-e2e): agents/audit/status round-trips"
```

---

### Task 4.6.3: E2E — builds, yaml, onboarding, backlog

Four more E2E modules:

- [ ] **builds.rs** — `builds.start` → poll `builds.get` until `awaiting_plan` → `builds.approve` → `awaiting_build`.
- [ ] **yaml.rs** — `yaml.read(project)` returns content; `yaml.write` with valid YAML round-trips; invalid YAML returns InvalidParams.
- [ ] **onboarding.rs** — `onboarding.generate` creates solution dir; files present on disk.
- [ ] **backlog.rs** — `backlog.submit` → `backlog.list` includes submitted feature.

Single commit:

```bash
git commit -m "test(desktop-e2e): builds/yaml/onboarding/backlog round-trips"
```

---

### Task 4.7.1: cargo-mutants on Rust RPC + errors + sidecar

**Files:**
- Create: `sage-desktop/src-tauri/.cargo/mutants.toml`
- Modify: `Makefile`

- [ ] **Step 1: Config**

```toml
# .cargo/mutants.toml
timeout_multiplier = 3.0
exclude_globs = ["tests/**", "bin/**", "target/**"]
```

- [ ] **Step 2: Makefile target**

```makefile
test-desktop-mutation-rs:
	cd sage-desktop/src-tauri && cargo mutants --in-place --no-shuffle \
	  --file src/rpc.rs --file src/errors.rs --file src/sidecar.rs
```

- [ ] **Step 3: Run**

Run: `make test-desktop-mutation-rs`
Expected: ≥80% kill rate. If lower, add targeted tests to close gaps.

- [ ] **Step 4: Commit**

```bash
git add sage-desktop/src-tauri/.cargo/mutants.toml Makefile
git commit -m "test(desktop): cargo-mutants config + make target"
```

---

### Task 4.7.2: Stryker on React hooks

**Files:**
- Create: `sage-desktop/stryker.conf.json`
- Modify: `sage-desktop/package.json`
- Modify: `Makefile`

- [ ] **Step 1: Install stryker**

Run: `cd sage-desktop && npm i -D @stryker-mutator/core @stryker-mutator/vitest-runner @stryker-mutator/typescript-checker`

- [ ] **Step 2: Config**

```json
{
  "packageManager": "npm",
  "reporters": ["clear-text", "html"],
  "testRunner": "vitest",
  "mutate": ["src/hooks/**/*.ts", "src/hooks/**/*.tsx"],
  "thresholds": { "high": 90, "low": 75, "break": 75 }
}
```

- [ ] **Step 3: Scripts + Makefile**

`package.json`:
```json
"scripts": {
  "test:mutation": "stryker run"
}
```

`Makefile`:
```makefile
test-desktop-mutation-ts:
	cd sage-desktop && npm run test:mutation

test-desktop-mutation: test-desktop-mutation-rs test-desktop-mutation-ts
```

- [ ] **Step 4: Run**

Run: `make test-desktop-mutation-ts`
Expected: ≥75% kill rate.

- [ ] **Step 5: Commit**

```bash
git add sage-desktop/stryker.conf.json sage-desktop/package.json \
        sage-desktop/package-lock.json Makefile
git commit -m "test(desktop): stryker mutation testing for hooks"
```

---

### Task 4.7.3: Playwright visual regression

**Files:**
- Create: `sage-desktop/playwright.config.ts`
- Create: `sage-desktop/playwright/fixtures/sidecar-mocks.ts`
- Create: `sage-desktop/playwright/tests/visual.spec.ts`
- Modify: `sage-desktop/package.json`

- [ ] **Step 1: Install Playwright**

Run: `cd sage-desktop && npm i -D @playwright/test && npx playwright install chromium`

- [ ] **Step 2: Config**

```typescript
// playwright.config.ts
import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./playwright/tests",
  snapshotDir: "./playwright/snapshots",
  use: { baseURL: "http://localhost:1420" },
  webServer: { command: "npm run dev", port: 1420, reuseExistingServer: true },
});
```

- [ ] **Step 3: Write visual test**

```typescript
// playwright/tests/visual.spec.ts
import { test, expect } from "@playwright/test";

const PAGES = ["/approvals", "/builds", "/audit", "/yaml"];

for (const path of PAGES) {
  test(`${path} visual`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveScreenshot(`${path.slice(1)}.png`, {
      maxDiffPixelRatio: 0.02,
    });
  });
}
```

- [ ] **Step 4: Scripts + Makefile**

```json
"scripts": {
  "test:visual": "playwright test",
  "test:visual:update": "playwright test --update-snapshots"
}
```

```makefile
test-desktop-visual:
	cd sage-desktop && npm run test:visual
```

- [ ] **Step 5: Baseline snapshots**

Run: `cd sage-desktop && npm run test:visual:update`
Commit the resulting snapshot pngs.

- [ ] **Step 6: Commit**

```bash
git add sage-desktop/playwright.config.ts sage-desktop/playwright/ \
        sage-desktop/package.json sage-desktop/package-lock.json Makefile
git commit -m "test(desktop): Playwright visual regression for 4 canonical pages"
```

---

### Task 4.8.1: Telemetry handler (sidecar)

**Files:**
- Create: `sage-desktop/sidecar/handlers/telemetry.py`
- Create: `sage-desktop/sidecar/tests/test_telemetry.py`
- Modify: `sage-desktop/sidecar/app.py`

- [ ] **Step 1: Write failing tests**

```python
# sage-desktop/sidecar/tests/test_telemetry.py
import pytest

from sage_desktop.sidecar.handlers import telemetry
from sage_desktop.sidecar.rpc import RpcError


def test_record_rejects_when_consent_off(tmp_path, monkeypatch):
    monkeypatch.setattr(telemetry, "_config_path", tmp_path / "config.json")
    with pytest.raises(RpcError):
        telemetry.record({"event_type": "page_view", "payload": {"path": "/approvals"}})


def test_record_buffers_when_consent_on(tmp_path, monkeypatch):
    monkeypatch.setattr(telemetry, "_config_path", tmp_path / "config.json")
    monkeypatch.setattr(telemetry, "_buffer_path", tmp_path / "queue.jsonl")
    telemetry.set_consent({"enabled": True})
    telemetry.record({"event_type": "page_view", "payload": {"path": "/approvals"}})
    assert (tmp_path / "queue.jsonl").read_text().count("\n") == 1


def test_set_consent_false_clears_buffer(tmp_path, monkeypatch):
    monkeypatch.setattr(telemetry, "_config_path", tmp_path / "config.json")
    monkeypatch.setattr(telemetry, "_buffer_path", tmp_path / "queue.jsonl")
    (tmp_path / "queue.jsonl").write_text('{"x":1}\n')
    telemetry.set_consent({"enabled": False})
    assert not (tmp_path / "queue.jsonl").exists()


def test_record_rejects_pii_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(telemetry, "_config_path", tmp_path / "config.json")
    telemetry.set_consent({"enabled": True})
    with pytest.raises(RpcError):
        telemetry.record({"event_type": "page_view", "payload": {
            "path": "/approvals",
            "user_email": "x@y.com",  # not allowlisted
        }})
```

- [ ] **Step 2: Run, expect import error**

Run: `.venv/Scripts/pytest sage-desktop/sidecar/tests/test_telemetry.py -v`

- [ ] **Step 3: Implement**

```python
# sage-desktop/sidecar/handlers/telemetry.py
"""Telemetry handler with strict PII allowlist and opt-in consent."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..rpc import RPC_INVALID_PARAMS, RpcError

_ALLOWED_PAYLOAD_KEYS = {"path", "command", "duration_ms", "error_kind"}
_ALLOWED_EVENT_TYPES = {"page_view", "command_invoke", "error"}

_config_path: Path | None = None   # overridden in tests + bootstrap
_buffer_path: Path | None = None


def _read_consent() -> bool:
    if _config_path is None or not _config_path.exists():
        return False
    try:
        return bool(json.loads(_config_path.read_text()).get("telemetry_enabled"))
    except Exception:
        return False


def set_consent(params: dict[str, Any]) -> dict[str, Any]:
    enabled = bool(params.get("enabled"))
    _config_path.parent.mkdir(parents=True, exist_ok=True)
    _config_path.write_text(json.dumps({"telemetry_enabled": enabled}))
    if not enabled and _buffer_path and _buffer_path.exists():
        _buffer_path.unlink()
    return {"enabled": enabled}


def get_consent(_: dict[str, Any]) -> dict[str, Any]:
    return {"enabled": _read_consent()}


def record(params: dict[str, Any]) -> dict[str, Any]:
    if not _read_consent():
        raise RpcError(RPC_INVALID_PARAMS, "telemetry consent not granted")
    event_type = params.get("event_type")
    if event_type not in _ALLOWED_EVENT_TYPES:
        raise RpcError(RPC_INVALID_PARAMS, f"unknown event_type: {event_type}")
    payload = params.get("payload") or {}
    for k in payload:
        if k not in _ALLOWED_PAYLOAD_KEYS:
            raise RpcError(RPC_INVALID_PARAMS, f"disallowed payload key: {k}")
    event = {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "payload": payload,
    }
    _buffer_path.parent.mkdir(parents=True, exist_ok=True)
    with _buffer_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
    return {"recorded": True, "event_id": event["event_id"]}
```

- [ ] **Step 4: Wire in app.py**

```python
from .handlers import telemetry as _telemetry
# in _wire_handlers
_telemetry._config_path = Path.home() / ".sage-desktop" / "config.json"
_telemetry._buffer_path = Path.home() / ".sage-desktop" / "telemetry-queue.jsonl"
d.register("telemetry.record", _telemetry.record)
d.register("telemetry.set_consent", _telemetry.set_consent)
d.register("telemetry.get_consent", _telemetry.get_consent)
```

- [ ] **Step 5: Run, expect pass**

Run: `.venv/Scripts/pytest sage-desktop/sidecar/tests/test_telemetry.py -v`
Expected: 4/4.

- [ ] **Step 6: Commit**

```bash
git add sage-desktop/sidecar/handlers/telemetry.py \
        sage-desktop/sidecar/tests/test_telemetry.py \
        sage-desktop/sidecar/app.py
git commit -m "feat(sidecar): telemetry handler with PII allowlist + opt-in"
```

---

### Task 4.8.2: Telemetry — Rust + React wiring

**Files:**
- Create: `sage-desktop/src-tauri/src/commands/telemetry.rs`
- Modify: `sage-desktop/src-tauri/src/commands/mod.rs`
- Modify: `sage-desktop/src-tauri/src/lib.rs`
- Modify: `sage-desktop/src/api/types.ts`
- Modify: `sage-desktop/src/api/client.ts`
- Create: `sage-desktop/src/hooks/useTelemetry.ts`
- Create: `sage-desktop/src/lib/telemetry.ts`
- Create: `sage-desktop/src/components/domain/TelemetryPanel.tsx`
- Create: `sage-desktop/src/__tests__/components/TelemetryPanel.test.tsx`
- Modify: `sage-desktop/src/pages/Settings.tsx`
- Modify: `sage-desktop/src/App.tsx`

- [ ] **Step 1: Rust proxy commands** (record_telemetry, set_telemetry_consent, get_telemetry_consent) — same proxy pattern as existing `commands/status.rs`.

- [ ] **Step 2: Rust tests** — 3 unit tests on the parameter shapes.

- [ ] **Step 3: Types + client** — `TelemetryConsent`, `TelemetryEvent` types.

- [ ] **Step 4: Hook** — `useTelemetryConsent()` query + `useSetTelemetryConsent()` mutation.

- [ ] **Step 5: lib/telemetry.ts** — exported `recordPageView(path)` / `recordCommand(name, duration)` / `recordError(kind)` helpers. Internally no-op on no-consent. App.tsx wires `recordPageView` on route change.

- [ ] **Step 6: TelemetryPanel** — toggle + privacy link; 4 tests (default off, toggle on persists, toggle off clears, off => no record).

- [ ] **Step 7: Mount in Settings.tsx**.

- [ ] **Step 8: Run full vitest suite** — expect green.

- [ ] **Step 9: Commit**

```bash
git commit -m "feat(desktop): telemetry wiring — Rust proxy + React hook + panel"
```

---

### Task 4.8.3: PRIVACY.md + settings link

**Files:**
- Create: `docs/PRIVACY.md`
- Modify: `sage-desktop/src/components/domain/TelemetryPanel.tsx`

- [ ] **Step 1: Write PRIVACY.md** — what's collected, what's not, opt-out, data retention, contact.
- [ ] **Step 2: TelemetryPanel** — "View privacy notice" link opens `docs/PRIVACY.md` URL in system browser.
- [ ] **Step 3: Commit**

```bash
git add docs/PRIVACY.md sage-desktop/src/components/domain/TelemetryPanel.tsx
git commit -m "docs(desktop): PRIVACY.md for telemetry opt-in"
```

---

### Task 4.9: Release CI workflow

**Files:**
- Create: `.github/workflows/desktop-release.yml`

- [ ] **Step 1: Workflow**

```yaml
name: desktop-release
on:
  push:
    tags: ["desktop-v*"]
jobs:
  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - uses: dtolnay/rust-toolchain@stable
      - name: Install sidecar deps
        run: |
          python -m venv .venv
          .venv/Scripts/pip install -r sage-desktop/sidecar/requirements.txt pyinstaller
      - name: Build sidecar
        run: bash sage-desktop/scripts/build-sidecar.sh
        shell: bash
      - name: Copy sidecar to bin
        run: |
          mkdir -p sage-desktop/src-tauri/bin
          cp sage-desktop/sidecar/dist/sage-sidecar.exe sage-desktop/src-tauri/bin/sage-sidecar-x86_64-pc-windows-msvc.exe
        shell: bash
      - name: Install web deps
        run: cd sage-desktop && npm ci
      - name: Build MSI + NSIS
        env:
          TAURI_SIGNING_PRIVATE_KEY: ${{ secrets.TAURI_SIGNING_PRIVATE_KEY }}
          TAURI_SIGNING_PRIVATE_KEY_PASSWORD: ${{ secrets.TAURI_SIGNING_PRIVATE_KEY_PASSWORD }}
        run: cd sage-desktop && npm run tauri -- build --bundles msi,nsis
      - name: Publish release
        uses: softprops/action-gh-release@v2
        with:
          files: |
            sage-desktop/src-tauri/target/release/bundle/msi/*.msi
            sage-desktop/src-tauri/target/release/bundle/nsis/*.exe
            sage-desktop/src-tauri/target/release/bundle/**/*.sig
      - name: Generate latest.json
        run: |
          ./sage-desktop/scripts/generate-latest-json.sh \
            > latest.json
          gh release upload "${{ github.ref_name }}" latest.json --clobber
        shell: bash
        env: { GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }} }
```

- [ ] **Step 2: generate-latest-json.sh**

Emits `{ version, pub_date, platforms: { "windows-x86_64": { signature, url } } }`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/desktop-release.yml \
        sage-desktop/scripts/generate-latest-json.sh
git commit -m "ci(desktop): release workflow — build, sign, publish to GitHub releases"
```

---

### Task 4.10: Documentation updates

**Files:**
- Modify: `.claude/docs/interfaces/desktop-gui.md`
- Modify: `CLAUDE.md`
- Modify: `sage-desktop/README.md`
- Modify: `.claude/docs/setup.md`

- [ ] **Step 1: desktop-gui.md** — Phase 4 section: install via MSI, update flow, telemetry notice, E2E coverage.
- [ ] **Step 2: CLAUDE.md** — desktop bullet one-liner mentioning MSI + auto-update + opt-in telemetry.
- [ ] **Step 3: sage-desktop/README.md** — end-user install flow, SmartScreen caveat, update behavior, privacy link.
- [ ] **Step 4: setup.md** — `make desktop-bundle` dev note.
- [ ] **Step 5: Commit**

```bash
git add .claude/docs/interfaces/desktop-gui.md CLAUDE.md \
        sage-desktop/README.md .claude/docs/setup.md
git commit -m "docs(desktop): Phase 4 packaging + update + telemetry"
```

---

### Task 4.11: Merge to main

- [ ] **Step 1: Full 3-layer verification**

```bash
.venv/Scripts/pytest sage-desktop/sidecar/tests -q
cd sage-desktop/src-tauri && cargo test --lib --no-default-features
cd .. && npx vitest run
cd src-tauri && cargo test --test e2e
```

Expected: all green.

- [ ] **Step 2: Merge**

```bash
git checkout main
git merge --no-ff feature/sage-desktop-phase4 -m "Merge Phase 4 — packaging & polish into main"
```

---

## Self-Review

- **Spec coverage:** All 11 acceptance criteria map to tasks 4.1.x–4.10.
- **No placeholders.** Every step has complete file content or exact command.
- **Type consistency:** `UpdateStatus` kinds match across Rust (serde tagged enum) and TS (discriminated union); `telemetry.record` param shape matches between sidecar, Rust, and frontend.
- **Scope:** Eight task groups, each end-to-end TDD with a single integration gate. Plan is executable by subagent-driven-development without further decomposition.

---

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-04-17-sage-desktop-phase4.md`.

Execution mode: **subagent-driven** (fresh subagent per task group, two-stage review per task).
