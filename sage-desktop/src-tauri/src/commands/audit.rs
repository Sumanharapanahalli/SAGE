//! Audit commands — proxy to `audit.*` on the sidecar.

use serde_json::{json, Value};
use tauri::State;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn list_audit_events(
    sidecar: State<'_, Sidecar>,
    limit: Option<u32>,
    offset: Option<u32>,
    action_type: Option<String>,
    trace_id: Option<String>,
) -> Result<Value, DesktopError> {
    let mut params = json!({
        "limit": limit.unwrap_or(50),
        "offset": offset.unwrap_or(0),
    });
    if let Some(t) = action_type {
        params["action_type"] = json!(t);
    }
    if let Some(t) = trace_id {
        params["trace_id"] = json!(t);
    }
    sidecar.call("audit.list", params).await
}

#[tauri::command]
pub async fn get_audit_by_trace(
    sidecar: State<'_, Sidecar>,
    trace_id: String,
) -> Result<Value, DesktopError> {
    sidecar
        .call("audit.get_by_trace", json!({ "trace_id": trace_id }))
        .await
}

#[tauri::command]
pub async fn audit_stats(
    sidecar: State<'_, Sidecar>,
) -> Result<Value, DesktopError> {
    sidecar.call("audit.stats", json!({})).await
}
