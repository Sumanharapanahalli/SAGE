//! Onboarding wizard — proxy to `onboarding.generate` on the sidecar.
//!
//! Long-running LLM call on the sidecar side, but the sidecar already
//! serializes through its own stdin/stdout mutex so a read-lock on the
//! Tauri side is sufficient.

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
