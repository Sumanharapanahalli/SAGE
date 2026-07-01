//! Compliance commands — proxy to `compliance.*` on the sidecar.
//!
//! Phase 5's assessment tooling: the audit log already gives desktop the
//! tamper-evident compliance RECORD; these expose the periodic ASSESSMENT
//! (domain checklists, gap assessment) so a compliance operator can check
//! conformance without leaving the app.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn compliance_domains(
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar.read().await.call("compliance.domains", json!({})).await
}

#[tauri::command]
pub async fn compliance_flags(
    sidecar: State<'_, RwLock<Sidecar>>,
    domain: String,
    risk_level: Option<String>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "compliance.flags",
            json!({ "domain": domain, "risk_level": risk_level.unwrap_or_else(|| "HIGH".into()) }),
        )
        .await
}

#[tauri::command]
pub async fn compliance_checklist(
    sidecar: State<'_, RwLock<Sidecar>>,
    domain: String,
    risk_level: Option<String>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "compliance.checklist",
            json!({ "domain": domain, "risk_level": risk_level.unwrap_or_else(|| "HIGH".into()) }),
        )
        .await
}

#[tauri::command]
pub async fn compliance_gap_assessment(
    sidecar: State<'_, RwLock<Sidecar>>,
    domain: String,
    risk_level: String,
    completed_tasks: Vec<String>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "compliance.gap_assessment",
            json!({ "domain": domain, "risk_level": risk_level, "completed_tasks": completed_tasks }),
        )
        .await
}
