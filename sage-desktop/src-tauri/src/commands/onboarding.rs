//! Onboarding wizard — proxy to `onboarding.*` on the sidecar.
//!
//! Long-running LLM calls on the sidecar side, but the sidecar already
//! serializes through its own stdin/stdout mutex so a read-lock on the
//! Tauri side is sufficient.
//!
//! Two ways in: describe a new solution (`onboarding_generate`, which writes
//! on success) or import an existing codebase (`onboarding_scan_folder`, which
//! writes nothing — `onboarding_save_solution` is the separate write step, so
//! the operator reviews the drafts first).

use std::collections::HashMap;

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn onboarding_generate(
    description: String,
    solution_name: String,
    compliance_standards: Option<Vec<String>>,
    integrations: Option<Vec<String>>,
    parent_solution: Option<String>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "onboarding.generate",
            json!({
                "description": description,
                "solution_name": solution_name,
                "compliance_standards": compliance_standards.unwrap_or_default(),
                "integrations": integrations.unwrap_or_default(),
                "parent_solution": parent_solution.unwrap_or_default(),
            }),
        )
        .await
}

#[tauri::command]
pub async fn onboarding_scan_folder(
    folder_path: String,
    solution_name: String,
    intent: Option<String>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "onboarding.scan_folder",
            json!({
                "folder_path": folder_path,
                "solution_name": solution_name,
                "intent": intent.unwrap_or_default(),
            }),
        )
        .await
}

#[tauri::command]
pub async fn onboarding_save_solution(
    solution_name: String,
    files: HashMap<String, String>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "onboarding.save_solution",
            json!({ "solution_name": solution_name, "files": files }),
        )
        .await
}
