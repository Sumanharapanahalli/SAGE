//! Operator identity commands — proxy to `operator.*` on the sidecar.
//!
//! This is the desktop's signer record. There is deliberately no OIDC/API-key
//! surface: those gate the FastAPI HTTP server, which this app does not run.
//! See `sidecar/handlers/operator.py` for the full rationale.
//!
//! Note the asymmetry with `approve_proposal`: the signer is NEVER passed from
//! the frontend into an approval. The sidecar resolves it itself, so a renderer
//! cannot forge the signature on a 21 CFR Part 11 record.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn get_operator(sidecar: State<'_, RwLock<Sidecar>>) -> Result<Value, DesktopError> {
    sidecar.read().await.call("operator.get", json!({})).await
}

#[tauri::command]
pub async fn set_operator(
    sidecar: State<'_, RwLock<Sidecar>>,
    name: String,
    email: Option<String>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "operator.set",
            json!({ "name": name, "email": email.unwrap_or_default() }),
        )
        .await
}
