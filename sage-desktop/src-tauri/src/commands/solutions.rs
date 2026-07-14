//! Solutions commands — read-only proxies to `solutions.*` on the sidecar.
//!
//! The writeable counterpart (`switch_solution`) lives in `commands::switch`
//! because it needs exclusive access to the sidecar handle for respawn.

use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, State};
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn list_solutions(
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("solutions.list", json!({}))
        .await
}

#[tauri::command]
pub async fn get_current_solution(
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("solutions.get_current", json!({}))
        .await
}

/// Deregister a solution. `mode` is `"archive"` (default — moves the directory
/// into `<solutions_dir>/.archive/`, nothing is destroyed) or `"delete"`, which
/// requires `confirm == name` and is gated behind a typed confirmation in the
/// UI. The sidecar refuses any path outside the solutions dir, and refuses the
/// currently-active solution.
/// If `name` is the ACTIVE solution, unload it first, then remove it.
///
/// The sidecar refuses to remove the active solution — it holds that solution's `.sage/`
/// SQLite handles open, so the directory cannot be moved out from under it. That refusal is
/// correct, but on its own it made Remove unusable in practice: the app auto-reopens the
/// last solution on launch, so the solution an operator wants to remove is almost always the
/// active one. The button was present, and always failed.
///
/// "Unload it first" is a demand to perform a step the UI can perform itself. So do it here:
/// respawn the sidecar in minimal mode (releasing every handle), then remove.
#[tauri::command]
pub async fn remove_solution(
    name: String,
    mode: Option<String>,
    confirm: Option<String>,
    sidecar: State<'_, RwLock<Sidecar>>,
    app: AppHandle,
) -> Result<Value, DesktopError> {
    let is_active = {
        let guard = sidecar.read().await;
        guard
            .call("solutions.get_current", json!({}))
            .await
            .ok()
            .and_then(|v| v.get("name").and_then(Value::as_str).map(str::to_owned))
            .as_deref()
            == Some(name.as_str())
    };

    if is_active {
        {
            let mut guard = sidecar.write().await;
            guard.unload_solution().await?;
            // Same health gate as unload_solution: the fresh minimal-mode sidecar must
            // answer before we act on the filesystem it just let go of.
            guard.call("handshake", json!({})).await?;
        }
        // Every listener already treats a null name as "active solution changed, drop caches".
        let _ = app.emit(
            "solution-switched",
            json!({ "name": Value::Null, "path": Value::Null }),
        );
    }

    sidecar
        .read()
        .await
        .call(
            "solutions.remove",
            json!({
                "name": name,
                "mode": mode.unwrap_or_else(|| "archive".to_string()),
                "confirm": confirm,
            }),
        )
        .await
}
