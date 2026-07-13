//! Solutions commands — read-only proxies to `solutions.*` on the sidecar.
//!
//! The writeable counterpart (`switch_solution`) lives in `commands::switch`
//! because it needs exclusive access to the sidecar handle for respawn.

use serde_json::{json, Value};
use tauri::State;
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
#[tauri::command]
pub async fn remove_solution(
    name: String,
    mode: Option<String>,
    confirm: Option<String>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
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
