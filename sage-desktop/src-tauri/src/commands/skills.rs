//! Skills & Tools commands — proxy to `skills.*` / `mcp.tools` on the sidecar.
//!
//! Read-and-toggle only: list skills, toggle visibility, hot-reload from
//! disk, and browse MCP tools. Visibility toggles and reload are framework
//! control (no HITL approval, matching the web API's `/skills/visibility`
//! and `/skills/reload` docstrings) — the sidecar handler calls the skill
//! registry directly rather than routing through the proposal queue.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn list_skills(
    sidecar: State<'_, RwLock<Sidecar>>,
    include_disabled: Option<bool>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "skills.list",
            json!({ "include_disabled": include_disabled.unwrap_or(false) }),
        )
        .await
}

#[tauri::command]
pub async fn set_skill_visibility(
    sidecar: State<'_, RwLock<Sidecar>>,
    name: String,
    visibility: String,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "skills.set_visibility",
            json!({ "name": name, "visibility": visibility }),
        )
        .await
}

#[tauri::command]
pub async fn reload_skills(sidecar: State<'_, RwLock<Sidecar>>) -> Result<Value, DesktopError> {
    sidecar.read().await.call("skills.reload", json!({})).await
}

#[tauri::command]
pub async fn list_mcp_tools(sidecar: State<'_, RwLock<Sidecar>>) -> Result<Value, DesktopError> {
    sidecar.read().await.call("mcp.tools", json!({})).await
}
