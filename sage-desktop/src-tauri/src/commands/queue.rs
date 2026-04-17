use serde_json::{json, Value};
use tauri::State;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn get_queue_status(sidecar: State<'_, Sidecar>) -> Result<Value, DesktopError> {
    sidecar.call("queue.get_status", json!({})).await
}

#[tauri::command]
pub async fn list_queue_tasks(
    status: Option<String>,
    limit: Option<i64>,
    sidecar: State<'_, Sidecar>,
) -> Result<Value, DesktopError> {
    sidecar
        .call(
            "queue.list_tasks",
            json!({"status": status, "limit": limit.unwrap_or(50)}),
        )
        .await
}
