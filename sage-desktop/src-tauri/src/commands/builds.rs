//! Build pipeline commands — proxies to `builds.*` on the sidecar.
//!
//! All four commands are read-path (no sidecar respawn needed), so they
//! take `State<'_, RwLock<Sidecar>>` with `.read().await`. The orchestrator
//! is single-threaded inside the sidecar, but the Python-side mutex on
//! stdin handles that — Rust doesn't need to serialize further.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn start_build(
    product_description: String,
    solution_name: Option<String>,
    repo_url: Option<String>,
    workspace_dir: Option<String>,
    critic_threshold: Option<u32>,
    hitl_level: Option<String>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "builds.start",
            json!({
                "product_description": product_description,
                "solution_name": solution_name.unwrap_or_default(),
                "repo_url": repo_url.unwrap_or_default(),
                "workspace_dir": workspace_dir.unwrap_or_default(),
                "critic_threshold": critic_threshold.unwrap_or(70),
                "hitl_level": hitl_level.unwrap_or_else(|| "standard".to_string()),
            }),
        )
        .await
}

#[tauri::command]
pub async fn list_builds(
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar.read().await.call("builds.list", json!({})).await
}

#[tauri::command]
pub async fn get_build(
    run_id: String,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("builds.get", json!({ "run_id": run_id }))
        .await
}

#[tauri::command]
pub async fn approve_build_stage(
    run_id: String,
    approved: bool,
    feedback: Option<String>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "builds.approve",
            json!({
                "run_id": run_id,
                "approved": approved,
                "feedback": feedback.unwrap_or_default(),
            }),
        )
        .await
}
