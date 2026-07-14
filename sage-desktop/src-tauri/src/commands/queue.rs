use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn get_queue_status(sidecar: State<'_, RwLock<Sidecar>>) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("queue.get_status", json!({}))
        .await
}

#[tauri::command]
pub async fn list_queue_tasks(
    status: Option<String>,
    limit: Option<i64>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "queue.list_tasks",
            json!({"status": status, "limit": limit.unwrap_or(50)}),
        )
        .await
}

/// Cancel a queued/blocked/running task.
///
/// Framework control (Law 1) — the operator's own action on their own tooling,
/// so it executes immediately and never enters the proposal queue.
#[tauri::command]
pub async fn cancel_queue_task(
    task_id: String,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("queue.cancel", json!({ "task_id": task_id }))
        .await
}

/// Re-queue a failed/cancelled/blocked task. Framework control — immediate.
#[tauri::command]
pub async fn retry_queue_task(
    task_id: String,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("queue.retry", json!({ "task_id": task_id }))
        .await
}
