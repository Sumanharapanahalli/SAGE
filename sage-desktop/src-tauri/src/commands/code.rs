//! Code commands — proxy to `code.*` on the sidecar.
//!
//! Plan -> approve -> execute, with the approval gate enforced inside
//! `autogen_runner` itself. `code_sandbox_status` has no web equivalent: it
//! reports whether execution would be isolated BEFORE the operator approves,
//! since the runner silently falls back to an unisolated local subprocess when
//! Docker is missing and the web API only says so after the code has run.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn code_plan(
    sidecar: State<'_, RwLock<Sidecar>>,
    task: String,
) -> Result<Value, DesktopError> {
    sidecar.read().await.call("code.plan", json!({ "task": task })).await
}

#[tauri::command]
pub async fn code_approve(
    sidecar: State<'_, RwLock<Sidecar>>,
    run_id: String,
    comment: Option<String>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "code.approve",
            json!({ "run_id": run_id, "comment": comment.unwrap_or_default() }),
        )
        .await
}

#[tauri::command]
pub async fn code_execute(
    sidecar: State<'_, RwLock<Sidecar>>,
    run_id: String,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("code.execute", json!({ "run_id": run_id }))
        .await
}

#[tauri::command]
pub async fn code_status(
    sidecar: State<'_, RwLock<Sidecar>>,
    run_id: String,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("code.status", json!({ "run_id": run_id }))
        .await
}

#[tauri::command]
pub async fn code_sandbox_status(
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar.read().await.call("code.sandbox_status", json!({})).await
}
