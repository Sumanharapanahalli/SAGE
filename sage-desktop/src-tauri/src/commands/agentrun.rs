//! Agent-run commands — proxy to `agents.run` / `agents.hire` /
//! `agents.analyze_jd` / `config.get_project` on the sidecar.
//!
//! The `agents::*` module is the read-only roster. This one is the execution
//! half: running a role produces a REAL pending proposal (Law 1 — the web
//! API's `POST /agent/run` persisted nothing), and hiring a role only ever
//! produces an `agent_hire` proposal, never a YAML write.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn agent_run(
    sidecar: State<'_, RwLock<Sidecar>>,
    role_id: String,
    task: String,
    context: Option<String>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "agents.run",
            json!({
                "role_id": role_id,
                "task": task,
                "context": context.unwrap_or_default(),
            }),
        )
        .await
}

#[tauri::command]
#[allow(clippy::too_many_arguments)]
pub async fn agent_hire(
    sidecar: State<'_, RwLock<Sidecar>>,
    role_id: String,
    name: String,
    description: Option<String>,
    icon: Option<String>,
    system_prompt: String,
    task_types: Option<Vec<String>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "agents.hire",
            json!({
                "role_id": role_id,
                "name": name,
                "description": description.unwrap_or_default(),
                "icon": icon.unwrap_or_else(|| "🤖".into()),
                "system_prompt": system_prompt,
                "task_types": task_types.unwrap_or_default(),
            }),
        )
        .await
}

#[tauri::command]
pub async fn agent_analyze_jd(
    sidecar: State<'_, RwLock<Sidecar>>,
    jd_text: String,
    solution_context: Option<String>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "agents.analyze_jd",
            json!({
                "jd_text": jd_text,
                "solution_context": solution_context.unwrap_or_default(),
            }),
        )
        .await
}

#[tauri::command]
pub async fn config_get_project(
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("config.get_project", json!({}))
        .await
}
