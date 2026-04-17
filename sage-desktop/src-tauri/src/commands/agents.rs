//! Agents commands — proxy to `agents.*` on the sidecar.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn list_agents(sidecar: State<'_, RwLock<Sidecar>>) -> Result<Value, DesktopError> {
    sidecar.read().await.call("agents.list", json!({})).await
}

#[tauri::command]
pub async fn get_agent(
    sidecar: State<'_, RwLock<Sidecar>>,
    name: String,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("agents.get", json!({ "name": name }))
        .await
}
