//! Constitution authoring commands — proxies to `constitution.*` on
//! the sidecar.
//!
//! All commands use `.read().await` on the Sidecar state because the
//! sidecar serializes per-request on its stdin mutex.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn constitution_get(
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("constitution.get", json!({}))
        .await
}

#[tauri::command]
pub async fn constitution_update(
    data: Value,
    changed_by: Option<String>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    let mut params = json!({ "data": data });
    if let Some(who) = changed_by {
        params["changed_by"] = Value::String(who);
    }
    sidecar
        .read()
        .await
        .call("constitution.update", params)
        .await
}

#[tauri::command]
pub async fn constitution_preamble(
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("constitution.preamble", json!({}))
        .await
}

#[tauri::command]
pub async fn constitution_check_action(
    action_description: String,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "constitution.check_action",
            json!({ "action_description": action_description }),
        )
        .await
}
