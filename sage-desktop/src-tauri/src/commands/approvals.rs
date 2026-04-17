//! Approvals commands — proxy to `approvals.*` on the sidecar.

use serde_json::{json, Value};
use tauri::State;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn list_pending_approvals(
    sidecar: State<'_, Sidecar>,
) -> Result<Value, DesktopError> {
    sidecar.call("approvals.list_pending", json!({})).await
}

#[tauri::command]
pub async fn get_approval(
    sidecar: State<'_, Sidecar>,
    trace_id: String,
) -> Result<Value, DesktopError> {
    sidecar
        .call("approvals.get", json!({ "trace_id": trace_id }))
        .await
}

#[tauri::command]
pub async fn approve_proposal(
    sidecar: State<'_, Sidecar>,
    trace_id: String,
    decided_by: Option<String>,
    feedback: Option<String>,
) -> Result<Value, DesktopError> {
    sidecar
        .call(
            "approvals.approve",
            json!({
                "trace_id": trace_id,
                "decided_by": decided_by.unwrap_or_else(|| "human".into()),
                "feedback": feedback.unwrap_or_default(),
            }),
        )
        .await
}

#[tauri::command]
pub async fn reject_proposal(
    sidecar: State<'_, Sidecar>,
    trace_id: String,
    decided_by: Option<String>,
    feedback: Option<String>,
) -> Result<Value, DesktopError> {
    sidecar
        .call(
            "approvals.reject",
            json!({
                "trace_id": trace_id,
                "decided_by": decided_by.unwrap_or_else(|| "human".into()),
                "feedback": feedback.unwrap_or_default(),
            }),
        )
        .await
}

#[tauri::command]
pub async fn batch_approve(
    sidecar: State<'_, Sidecar>,
    trace_ids: Vec<String>,
    decided_by: Option<String>,
    feedback: Option<String>,
) -> Result<Value, DesktopError> {
    sidecar
        .call(
            "approvals.batch_approve",
            json!({
                "trace_ids": trace_ids,
                "decided_by": decided_by.unwrap_or_else(|| "human".into()),
                "feedback": feedback.unwrap_or_default(),
            }),
        )
        .await
}
