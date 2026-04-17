use serde_json::{json, Value};
use tauri::State;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn list_feature_requests(
    status: Option<String>,
    scope: Option<String>,
    sidecar: State<'_, Sidecar>,
) -> Result<Value, DesktopError> {
    sidecar
        .call("backlog.list", json!({"status": status, "scope": scope}))
        .await
}

#[tauri::command]
pub async fn submit_feature_request(
    title: String,
    description: String,
    priority: Option<String>,
    scope: Option<String>,
    requested_by: Option<String>,
    module_id: Option<String>,
    module_name: Option<String>,
    sidecar: State<'_, Sidecar>,
) -> Result<Value, DesktopError> {
    sidecar
        .call(
            "backlog.submit",
            json!({
                "title": title,
                "description": description,
                "priority": priority.unwrap_or_else(|| "medium".into()),
                "scope": scope.unwrap_or_else(|| "solution".into()),
                "requested_by": requested_by.unwrap_or_else(|| "anonymous".into()),
                "module_id": module_id.unwrap_or_else(|| "general".into()),
                "module_name": module_name.unwrap_or_else(|| "General".into()),
            }),
        )
        .await
}

#[tauri::command]
pub async fn update_feature_request(
    id: String,
    action: String,
    reviewer_note: Option<String>,
    sidecar: State<'_, Sidecar>,
) -> Result<Value, DesktopError> {
    sidecar
        .call(
            "backlog.update",
            json!({
                "id": id,
                "action": action,
                "reviewer_note": reviewer_note.unwrap_or_default(),
            }),
        )
        .await
}
