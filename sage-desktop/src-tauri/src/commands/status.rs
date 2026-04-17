//! Status commands — proxy to `status.*` on the sidecar.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn get_status(sidecar: State<'_, RwLock<Sidecar>>) -> Result<Value, DesktopError> {
    sidecar.read().await.call("status.get", json!({})).await
}

#[tauri::command]
pub async fn handshake(sidecar: State<'_, RwLock<Sidecar>>) -> Result<Value, DesktopError> {
    sidecar.read().await.call("handshake", json!({})).await
}
