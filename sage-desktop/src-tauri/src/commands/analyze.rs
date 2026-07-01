//! Analyze command — proxy to `analyze.run` on the sidecar.
//!
//! The desktop operator's SURFACE -> PROPOSE trigger: runs the AnalystAgent
//! against a log/signal and creates a real ProposalStore proposal, which
//! immediately shows up in the Approvals inbox.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn analyze_run(
    sidecar: State<'_, RwLock<Sidecar>>,
    log_entry: String,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("analyze.run", json!({ "log_entry": log_entry }))
        .await
}
