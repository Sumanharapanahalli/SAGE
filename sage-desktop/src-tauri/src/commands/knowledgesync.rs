//! Knowledge Sync command — proxy to `knowledge.sync` on the sidecar.
//!
//! Bulk directory import into the active solution's vector memory, so the
//! knowledge base can be bootstrapped from the solution's own files instead
//! of one hand-typed entry at a time.
//!
//! `directory` is optional: the sidecar defaults it to the active solution's
//! root, which is the common case (and the only one available when the
//! operator has no path to hand).

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn knowledge_sync(
    sidecar: State<'_, RwLock<Sidecar>>,
    directory: Option<String>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("knowledge.sync", json!({ "directory": directory }))
        .await
}
