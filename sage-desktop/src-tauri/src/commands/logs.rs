//! Live Console commands — proxy to `logs.*` on the sidecar.
//!
//! The web UI streams the same records over SSE; the sidecar's NDJSON channel
//! is one-request/one-response, so the frontend polls `logs.tail` with an
//! `after_seq` cursor instead. Same data, same controls, no protocol change.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

/// Fetch buffered log records newer than `after_seq` (sidecar clamps `limit`
/// to [1, 500]; omitting it defaults to 200).
#[tauri::command]
pub async fn logs_tail(
    sidecar: State<'_, RwLock<Sidecar>>,
    after_seq: Option<u64>,
    limit: Option<u32>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "logs.tail",
            json!({ "after_seq": after_seq.unwrap_or(0), "limit": limit }),
        )
        .await
}
