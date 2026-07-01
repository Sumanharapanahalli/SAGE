//! Goals / OKR tracking commands — proxy to `goals.*` on the sidecar.
//!
//! Scope note: unlike the web API's `_get_goals_store()` (a framework-shared
//! `goals.db` resolved next to the audit_logger's db path), the sidecar
//! handler stores `goals.db` inside THIS solution's own `.sage/` directory —
//! genuine per-solution isolation, matching proposals.db/audit_log.db/
//! queue.db. See `sidecar/handlers/goals.py`'s module docstring.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn list_goals(
    user_id: Option<String>,
    solution: Option<String>,
    quarter: Option<String>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "goals.list",
            json!({
                "user_id": user_id,
                "solution": solution,
                "quarter": quarter,
            }),
        )
        .await
}

#[tauri::command]
pub async fn create_goal(
    title: String,
    quarter: String,
    user_id: Option<String>,
    solution: Option<String>,
    status: Option<String>,
    owner: Option<String>,
    key_results: Option<Vec<Value>>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "goals.create",
            json!({
                "title": title,
                "quarter": quarter,
                "user_id": user_id,
                "solution": solution,
                "status": status,
                "owner": owner,
                "key_results": key_results,
            }),
        )
        .await
}

#[tauri::command]
pub async fn get_goal(
    goal_id: String,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("goals.get", json!({"goal_id": goal_id}))
        .await
}

#[tauri::command]
pub async fn update_goal(
    goal_id: String,
    title: Option<String>,
    quarter: Option<String>,
    status: Option<String>,
    owner: Option<String>,
    key_results: Option<Vec<Value>>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "goals.update",
            json!({
                "goal_id": goal_id,
                "title": title,
                "quarter": quarter,
                "status": status,
                "owner": owner,
                "key_results": key_results,
            }),
        )
        .await
}

#[tauri::command]
pub async fn delete_goal(
    goal_id: String,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("goals.delete", json!({"goal_id": goal_id}))
        .await
}
