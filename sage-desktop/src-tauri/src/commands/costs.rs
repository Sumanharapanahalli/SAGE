//! Costs commands — proxy to `costs.*` on the sidecar.
//!
//! Ports the /costs/* REST endpoints (api.py:4501-4579) so an operator can
//! review LLM spend and set monthly budgets without leaving the desktop
//! app. Pure proxy, like compliance.rs — the sidecar owns all validation
//! and the config.yaml read/merge/write.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn costs_summary(
    sidecar: State<'_, RwLock<Sidecar>>,
    tenant: Option<String>,
    solution: Option<String>,
    period_days: Option<i64>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "costs.summary",
            json!({ "tenant": tenant, "solution": solution, "period_days": period_days }),
        )
        .await
}

#[tauri::command]
pub async fn costs_daily(
    sidecar: State<'_, RwLock<Sidecar>>,
    tenant: Option<String>,
    solution: Option<String>,
    period_days: Option<i64>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "costs.daily",
            json!({ "tenant": tenant, "solution": solution, "period_days": period_days }),
        )
        .await
}

#[tauri::command]
pub async fn costs_set_budget(
    sidecar: State<'_, RwLock<Sidecar>>,
    monthly_usd: f64,
    tenant: Option<String>,
    solution: Option<String>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "costs.set_budget",
            json!({ "monthly_usd": monthly_usd, "tenant": tenant, "solution": solution }),
        )
        .await
}
