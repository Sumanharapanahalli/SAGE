//! Agents commands — proxy to `agents.*` on the sidecar.

use serde_json::{json, Value};
use tauri::State;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn list_agents(sidecar: State<'_, Sidecar>) -> Result<Value, DesktopError> {
    sidecar.call("agents.list", json!({})).await
}

#[tauri::command]
pub async fn get_agent(
    sidecar: State<'_, Sidecar>,
    name: String,
) -> Result<Value, DesktopError> {
    sidecar.call("agents.get", json!({ "name": name })).await
}
