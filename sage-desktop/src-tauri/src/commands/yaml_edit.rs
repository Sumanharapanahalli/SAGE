//! YAML authoring commands — proxies to `yaml.read` / `yaml.write` on
//! the sidecar.
//!
//! Read-path only from the Rust side (the sidecar serializes on its own
//! stdin mutex), so `State<'_, RwLock<Sidecar>>` with `.read().await`.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn read_yaml(
    file: String,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("yaml.read", json!({ "file": file }))
        .await
}

#[tauri::command]
pub async fn write_yaml(
    file: String,
    content: String,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "yaml.write",
            json!({ "file": file, "content": content }),
        )
        .await
}
