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
