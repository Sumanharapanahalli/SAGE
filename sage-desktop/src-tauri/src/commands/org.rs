//! Organization commands — proxy to `org.*` on the sidecar.
//!
//! org.yaml is a SAGE_ROOT-level file (not per-solution): identity fields
//! (name/mission/vision/core_values) shape every solution's onboarding and
//! agent context. Channel/solution/route CRUD is out of scope for this
//! pass — this is read (including read-only cross-team routes) + edit
//! identity fields + reload.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn org_get(sidecar: State<'_, RwLock<Sidecar>>) -> Result<Value, DesktopError> {
    sidecar.read().await.call("org.get", json!({})).await
}

#[tauri::command]
pub async fn org_update(
    sidecar: State<'_, RwLock<Sidecar>>,
    name: Option<String>,
    mission: Option<String>,
    vision: Option<String>,
    core_values: Option<Vec<String>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "org.update",
            json!({
                "name": name,
                "mission": mission,
                "vision": vision,
                "core_values": core_values,
            }),
        )
        .await
}

#[tauri::command]
pub async fn org_reload(sidecar: State<'_, RwLock<Sidecar>>) -> Result<Value, DesktopError> {
    sidecar.read().await.call("org.reload", json!({})).await
}

#[tauri::command]
pub async fn org_channel_create(
    sidecar: State<'_, RwLock<Sidecar>>,
    name: String,
    producers: Option<Vec<String>>,
    consumers: Option<Vec<String>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "org.channel_create",
            json!({
                "name": name,
                "producers": producers.unwrap_or_default(),
                "consumers": consumers.unwrap_or_default(),
            }),
        )
        .await
}

#[tauri::command]
pub async fn org_channel_delete(
    sidecar: State<'_, RwLock<Sidecar>>,
    name: String,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("org.channel_delete", json!({ "name": name }))
        .await
}

#[tauri::command]
pub async fn org_route_add(
    sidecar: State<'_, RwLock<Sidecar>>,
    solution: String,
    target: String,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("org.route_add", json!({ "solution": solution, "target": target }))
        .await
}

#[tauri::command]
pub async fn org_route_delete(
    sidecar: State<'_, RwLock<Sidecar>>,
    solution: String,
    target: String,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("org.route_delete", json!({ "solution": solution, "target": target }))
        .await
}

#[tauri::command]
pub async fn org_solution_set_parent(
    sidecar: State<'_, RwLock<Sidecar>>,
    solution: String,
    parent: String,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "org.solution_set_parent",
            json!({ "solution": solution, "parent": parent }),
        )
        .await
}

#[tauri::command]
pub async fn org_solution_clear_parent(
    sidecar: State<'_, RwLock<Sidecar>>,
    solution: String,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("org.solution_clear_parent", json!({ "solution": solution }))
        .await
}
