//! Regulatory commands — proxy to `regulatory.*` on the sidecar.
//!
//! Multi-standard REGULATORY assessment (FDA / EU / UK / IEC / ISO / DO-178C …)
//! over `src/core/regulatory_compliance.py`. Distinct from the `compliance_*`
//! commands, which wrap `compliance_flags.py` (5 bundled engineering domains).

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn regulatory_standards(
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar.read().await.call("regulatory.standards", json!({})).await
}

#[tauri::command]
pub async fn regulatory_standard(
    sidecar: State<'_, RwLock<Sidecar>>,
    standard_id: String,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("regulatory.standard", json!({ "standard_id": standard_id }))
        .await
}

#[tauri::command]
pub async fn regulatory_assess(
    sidecar: State<'_, RwLock<Sidecar>>,
    product: Value,
    standard_ids: Option<Vec<String>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "regulatory.assess",
            json!({ "product": product, "standard_ids": standard_ids }),
        )
        .await
}

#[tauri::command]
pub async fn regulatory_gap_analysis(
    sidecar: State<'_, RwLock<Sidecar>>,
    product: Value,
    standard_id: String,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "regulatory.gap_analysis",
            json!({ "product": product, "standard_id": standard_id }),
        )
        .await
}

#[tauri::command]
pub async fn regulatory_checklist(
    sidecar: State<'_, RwLock<Sidecar>>,
    standard_id: String,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("regulatory.checklist", json!({ "standard_id": standard_id }))
        .await
}

#[tauri::command]
pub async fn regulatory_roadmap(
    sidecar: State<'_, RwLock<Sidecar>>,
    product: Value,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("regulatory.roadmap", json!({ "product": product }))
        .await
}
