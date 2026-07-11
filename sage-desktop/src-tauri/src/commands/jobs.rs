//! Background job commands — proxy to `jobs.*` on the sidecar.
//!
//! Approving an `implementation_plan` or `code_diff` kicks off multi-minute LLM
//! work on a sidecar worker thread and returns a `job_id` instead of blocking
//! the serial dispatch loop. These commands let the UI follow that work.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn job_status(
    sidecar: State<'_, RwLock<Sidecar>>,
    job_id: String,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("jobs.status", json!({ "job_id": job_id }))
        .await
}

#[tauri::command]
pub async fn list_jobs(sidecar: State<'_, RwLock<Sidecar>>) -> Result<Value, DesktopError> {
    sidecar.read().await.call("jobs.list", json!({})).await
}
