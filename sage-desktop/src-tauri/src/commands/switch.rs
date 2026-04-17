//! Solution-switch command — respawns the sidecar with a new `(name, path)`.
//!
//! Takes a write lock on the sidecar state so all other RPC calls are
//! blocked for the duration of the swap. After the fresh sidecar comes up
//! we re-handshake to confirm it's healthy, then emit a `solution-switched`
//! Tauri event so React Query caches can invalidate.

use std::path::PathBuf;

use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, State};
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn switch_solution(
    name: String,
    path: String,
    sidecar: State<'_, RwLock<Sidecar>>,
    app: AppHandle,
) -> Result<Value, DesktopError> {
    let path_buf = PathBuf::from(&path);
    {
        let mut guard = sidecar.write().await;
        guard.replace_solution(name.clone(), path_buf).await?;
        // Re-handshake while we still hold the write lock so no other
        // command can slip through against a half-ready sidecar.
        guard.call("handshake", json!({})).await?;
    }

    let payload = json!({ "name": name, "path": path });
    let _ = app.emit("solution-switched", payload.clone());
    Ok(payload)
}
