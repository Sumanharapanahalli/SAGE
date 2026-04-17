//! Opt-in telemetry consent commands. The sidecar owns the canonical
//! config file; Rust is a thin proxy.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn telemetry_get_status(
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("telemetry.get_status", json!({}))
        .await
}

#[tauri::command]
pub async fn telemetry_set_enabled(
    enabled: bool,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("telemetry.set_enabled", json!({ "enabled": enabled }))
        .await
}

#[tauri::command]
pub async fn telemetry_flush(
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("telemetry.flush", json!({}))
        .await
}
