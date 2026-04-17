//! Evolution (Agent Gym) — proxies to `evolution.*` on the sidecar.
//!
//! `evolution_train` is long-running (full gym training round) but the
//! sidecar already serializes through its own stdin/stdout mutex, so a
//! read-lock on the Tauri side is sufficient.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn evolution_leaderboard(
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("evolution.leaderboard", json!({}))
        .await
}

#[tauri::command]
pub async fn evolution_history(
    limit: Option<u32>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("evolution.history", json!({"limit": limit.unwrap_or(50)}))
        .await
}

#[tauri::command]
pub async fn evolution_analytics(
    role: Option<String>,
    skill: Option<String>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "evolution.analytics",
            json!({
                "role": role.unwrap_or_default(),
                "skill": skill.unwrap_or_default(),
            }),
        )
        .await
}

#[tauri::command]
pub async fn evolution_train(
    role: String,
    difficulty: Option<String>,
    skill_name: Option<String>,
    exercise_id: Option<String>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "evolution.train",
            json!({
                "role": role,
                "difficulty": difficulty.unwrap_or_default(),
                "skill_name": skill_name.unwrap_or_default(),
                "exercise_id": exercise_id.unwrap_or_default(),
            }),
        )
        .await
}
