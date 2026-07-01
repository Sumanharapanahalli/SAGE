//! Eval commands — proxy to `eval.*` on the sidecar.
//!
//! Ports the Agent Gym evaluation-suite endpoints (list/run/history) so a
//! desktop operator can score agent quality against the active solution's
//! evals/ catalog without leaving the app.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn list_eval_suites(sidecar: State<'_, RwLock<Sidecar>>) -> Result<Value, DesktopError> {
    sidecar.read().await.call("eval.list_suites", json!({})).await
}

#[tauri::command]
pub async fn run_eval(
    suite: Option<String>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("eval.run", json!({ "suite": suite }))
        .await
}

#[tauri::command]
pub async fn get_eval_history(
    suite: Option<String>,
    limit: Option<i64>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "eval.history",
            json!({ "suite": suite, "limit": limit.unwrap_or(20) }),
        )
        .await
}
