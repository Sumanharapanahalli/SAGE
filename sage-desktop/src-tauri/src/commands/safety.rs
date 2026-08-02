//! Safety commands — proxy to `safety.*` on the sidecar.
//!
//! Complements the compliance commands rather than duplicating them:
//! `compliance.*` takes the safety class as an INPUT (which checklist do I owe
//! for CLASS_C?), whereas these DERIVE it (what class/ASIL/SIL does this
//! hazard imply?).
//!
//! `fta_analyze` takes the fault tree as an opaque `Value` on purpose: it is
//! an arbitrarily deep recursive structure (gates containing gates), so
//! modelling it as a Rust struct here would buy nothing — the sidecar handler
//! and the Python engine already own that contract and validate it.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn safety_fmea(
    sidecar: State<'_, RwLock<Sidecar>>,
    entries: Vec<Value>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("safety.fmea", json!({ "entries": entries }))
        .await
}

#[tauri::command]
pub async fn safety_fta(
    sidecar: State<'_, RwLock<Sidecar>>,
    tree: Value,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("safety.fta", json!({ "tree": tree }))
        .await
}

#[tauri::command]
pub async fn safety_asil(
    sidecar: State<'_, RwLock<Sidecar>>,
    severity: String,
    exposure: String,
    controllability: String,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "safety.asil",
            json!({
                "severity": severity,
                "exposure": exposure,
                "controllability": controllability,
            }),
        )
        .await
}

#[tauri::command]
pub async fn safety_sil(
    sidecar: State<'_, RwLock<Sidecar>>,
    probability_dangerous_failure_per_hour: f64,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "safety.sil",
            json!({
                "probability_dangerous_failure_per_hour":
                    probability_dangerous_failure_per_hour,
            }),
        )
        .await
}

#[tauri::command]
pub async fn safety_iec62304(
    sidecar: State<'_, RwLock<Sidecar>>,
    risk_level: String,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("safety.iec62304", json!({ "risk_level": risk_level }))
        .await
}
