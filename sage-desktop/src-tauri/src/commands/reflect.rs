//! Reflect commands — proxy to `reflect.*` on the sidecar.
//!
//! Ports the reflection engine (bounded generate -> critique -> refine loop) so
//! a desktop operator can run and inspect self-correction runs without leaving
//! the app.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn reflect_run(
    task: String,
    context: Option<String>,
    max_iterations: Option<i64>,
    acceptance_threshold: Option<f64>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "reflect.run",
            json!({
                "task": task,
                "context": context.unwrap_or_default(),
                "max_iterations": max_iterations.unwrap_or(3),
                "acceptance_threshold": acceptance_threshold.unwrap_or(0.7),
            }),
        )
        .await
}

#[tauri::command]
pub async fn reflect_stats(sidecar: State<'_, RwLock<Sidecar>>) -> Result<Value, DesktopError> {
    sidecar.read().await.call("reflect.stats", json!({})).await
}

#[tauri::command]
pub async fn reflect_recent(
    limit: Option<i64>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("reflect.recent", json!({ "limit": limit.unwrap_or(20) }))
        .await
}

#[tauri::command]
pub async fn reflect_get(
    reflection_id: String,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("reflect.get", json!({ "reflection_id": reflection_id }))
        .await
}
