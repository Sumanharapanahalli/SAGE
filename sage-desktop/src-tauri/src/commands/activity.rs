//! Activity commands — proxy to `activity.*` on the sidecar.
//!
//! The live triage feed, distinct from `audit.*` (the paginated evidence
//! table). Category classification and free-text search run sidecar-side so
//! totals and pagination stay correct across the whole log, not just a page.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn list_activity(
    sidecar: State<'_, RwLock<Sidecar>>,
    limit: Option<u32>,
    offset: Option<u32>,
    category: Option<String>,
    query: Option<String>,
) -> Result<Value, DesktopError> {
    let mut params = json!({
        "limit": limit.unwrap_or(50),
        "offset": offset.unwrap_or(0),
    });
    if let Some(c) = category {
        params["category"] = json!(c);
    }
    if let Some(q) = query {
        params["query"] = json!(q);
    }
    sidecar.read().await.call("activity.list", params).await
}
