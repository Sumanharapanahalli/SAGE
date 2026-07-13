//! Durable task-queue commands — proxies to `queue.list_all` / `queue.subtasks`.
//!
//! Distinct from `commands::queue`, which proxies the in-memory
//! `queue.get_status` / `queue.list_tasks`. Only these two see task history.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn queue_list_all(
    status: Option<String>,
    source: Option<String>,
    limit: Option<u32>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    let mut params = json!({});
    if let Some(s) = status {
        params["status"] = Value::from(s);
    }
    if let Some(s) = source {
        params["source"] = Value::from(s);
    }
    if let Some(l) = limit {
        params["limit"] = Value::from(l);
    }
    sidecar.read().await.call("queue.list_all", params).await
}

#[tauri::command]
pub async fn queue_subtasks(
    task_id: String,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("queue.subtasks", json!({ "task_id": task_id }))
        .await
}
