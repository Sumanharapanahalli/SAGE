//! Orchestrator commands — proxy to `orchestrator.*` on the sidecar.
//!
//! Read-only observability over the nine intelligence modules. `stats` is an
//! aggregate over all of them; `recent` is parameterised by module, since the
//! six per-module history endpoints differ only in which singleton they read.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn orchestrator_stats(
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar.read().await.call("orchestrator.stats", json!({})).await
}

#[tauri::command]
pub async fn orchestrator_recent(
    sidecar: State<'_, RwLock<Sidecar>>,
    module: String,
    limit: Option<u32>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "orchestrator.recent",
            json!({ "module": module, "limit": limit.unwrap_or(50) }),
        )
        .await
}
