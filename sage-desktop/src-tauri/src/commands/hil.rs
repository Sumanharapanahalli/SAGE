//! HIL (Hardware-in-the-Loop) commands — proxy to `hil.*` on the sidecar.
//!
//! Ports status/connect/run-suite/report. `flash_firmware()` exists on
//! the sidecar's HILRunner but is not exposed by any endpoint in the web
//! API either — deliberately not ported here, see handlers/hil.py's
//! module docstring.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn hil_status(sidecar: State<'_, RwLock<Sidecar>>) -> Result<Value, DesktopError> {
    sidecar.read().await.call("hil.status", json!({})).await
}

#[tauri::command]
pub async fn hil_connect(
    transport: Option<String>,
    config: Option<Value>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "hil.connect",
            json!({
                "transport": transport,
                "config": config.unwrap_or_else(|| json!({})),
            }),
        )
        .await
}

#[tauri::command]
pub async fn hil_run_suite(
    tests: Vec<Value>,
    transport: Option<String>,
    config: Option<Value>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "hil.run_suite",
            json!({
                "tests": tests,
                "transport": transport,
                "config": config.unwrap_or_else(|| json!({})),
            }),
        )
        .await
}

#[tauri::command]
pub async fn hil_report(
    session_id: String,
    standard: Option<String>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "hil.report",
            json!({ "session_id": session_id, "standard": standard }),
        )
        .await
}
