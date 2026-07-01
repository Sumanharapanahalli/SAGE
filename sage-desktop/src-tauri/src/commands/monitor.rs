//! Monitor commands — proxy to `monitor.*` on the sidecar.
//!
//! Exposes the MonitorAgent's polling/thread status and the TaskScheduler's
//! running state so a desktop operator can see whether these (often-off)
//! background subsystems are active, without leaving the app.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn monitor_status(sidecar: State<'_, RwLock<Sidecar>>) -> Result<Value, DesktopError> {
    sidecar.read().await.call("monitor.status", json!({})).await
}

#[tauri::command]
pub async fn scheduler_status(sidecar: State<'_, RwLock<Sidecar>>) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("monitor.scheduler_status", json!({}))
        .await
}
