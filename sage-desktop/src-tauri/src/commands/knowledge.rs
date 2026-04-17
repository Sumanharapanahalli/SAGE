//! Knowledge Browser commands — proxies to `knowledge.*` on the sidecar.
//!
//! Operator-driven add/delete skip the proposal queue by design; agent
//! proposals still flow through the existing STATEFUL/DESTRUCTIVE
//! proposal kinds, unchanged.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn knowledge_list(
    limit: Option<u32>,
    offset: Option<u32>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    let mut params = json!({});
    if let Some(l) = limit {
        params["limit"] = Value::from(l);
    }
    if let Some(o) = offset {
        params["offset"] = Value::from(o);
    }
    sidecar.read().await.call("knowledge.list", params).await
}

#[tauri::command]
pub async fn knowledge_search(
    query: String,
    top_k: Option<u32>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    let mut params = json!({ "query": query });
    if let Some(k) = top_k {
        params["top_k"] = Value::from(k);
    }
    sidecar.read().await.call("knowledge.search", params).await
}

#[tauri::command]
pub async fn knowledge_add(
    text: String,
    metadata: Option<Value>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    let mut params = json!({ "text": text });
    if let Some(m) = metadata {
        params["metadata"] = m;
    }
    sidecar.read().await.call("knowledge.add", params).await
}

#[tauri::command]
pub async fn knowledge_delete(
    id: String,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("knowledge.delete", json!({ "id": id }))
        .await
}

#[tauri::command]
pub async fn knowledge_stats(
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("knowledge.stats", json!({}))
        .await
}
