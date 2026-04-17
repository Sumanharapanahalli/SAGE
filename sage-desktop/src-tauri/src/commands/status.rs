//! Status commands — proxy to `status.*` on the sidecar.

use serde_json::{json, Value};
use tauri::State;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn get_status(sidecar: State<'_, Sidecar>) -> Result<Value, DesktopError> {
    sidecar.call("status.get", json!({})).await
}

#[tauri::command]
pub async fn handshake(sidecar: State<'_, Sidecar>) -> Result<Value, DesktopError> {
    sidecar.call("handshake", json!({})).await
}
