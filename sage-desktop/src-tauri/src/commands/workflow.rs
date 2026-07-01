//! Workflow commands — proxy to `workflow.*` on the sidecar.
//!
//! Ports the LangGraph workflow endpoints (list/run/resume/status) so a
//! desktop operator can start and drive approval-gated LangGraph runs
//! without leaving the app. Mermaid-diagram discovery is a separate,
//! lower-value visualization feature and is deliberately not ported here.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn list_workflows(sidecar: State<'_, RwLock<Sidecar>>) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("workflow.list_workflows", json!({}))
        .await
}

#[tauri::command]
pub async fn run_workflow(
    workflow_name: String,
    state: Option<Value>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "workflow.run",
            json!({
                "workflow_name": workflow_name,
                "state": state.unwrap_or_else(|| json!({})),
            }),
        )
        .await
}

#[tauri::command]
pub async fn resume_workflow(
    run_id: String,
    feedback: Option<Value>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "workflow.resume",
            json!({
                "run_id": run_id,
                "feedback": feedback.unwrap_or_else(|| json!({})),
            }),
        )
        .await
}

#[tauri::command]
pub async fn get_workflow_status(
    run_id: String,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("workflow.status", json!({ "run_id": run_id }))
        .await
}
