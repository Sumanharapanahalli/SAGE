//! Collective Intelligence commands — proxies to `collective.*` on the sidecar.
//!
//! Operator actions (validate, claim, respond, close, create) bypass
//! the proposal queue by design; `publish_learning` honors the
//! framework's `require_approval` setting via the sidecar's gated/id
//! response shape.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn collective_list_learnings(
    solution: Option<String>,
    topic: Option<String>,
    limit: Option<u32>,
    offset: Option<u32>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    let mut params = json!({});
    if let Some(s) = solution {
        params["solution"] = Value::from(s);
    }
    if let Some(t) = topic {
        params["topic"] = Value::from(t);
    }
    if let Some(l) = limit {
        params["limit"] = Value::from(l);
    }
    if let Some(o) = offset {
        params["offset"] = Value::from(o);
    }
    sidecar
        .read()
        .await
        .call("collective.list_learnings", params)
        .await
}

#[tauri::command]
pub async fn collective_get_learning(
    id: String,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("collective.get_learning", json!({ "id": id }))
        .await
}

#[tauri::command]
pub async fn collective_search_learnings(
    query: String,
    tags: Option<Vec<String>>,
    solution: Option<String>,
    limit: Option<u32>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    let mut params = json!({ "query": query });
    if let Some(t) = tags {
        params["tags"] = Value::from(t);
    }
    if let Some(s) = solution {
        params["solution"] = Value::from(s);
    }
    if let Some(l) = limit {
        params["limit"] = Value::from(l);
    }
    sidecar
        .read()
        .await
        .call("collective.search_learnings", params)
        .await
}

#[tauri::command]
pub async fn collective_publish_learning(
    author_agent: String,
    author_solution: String,
    topic: String,
    title: String,
    content: String,
    tags: Option<Vec<String>>,
    confidence: Option<f64>,
    source_task_id: Option<String>,
    proposed_by: Option<String>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    let mut params = json!({
        "author_agent": author_agent,
        "author_solution": author_solution,
        "topic": topic,
        "title": title,
        "content": content,
    });
    if let Some(t) = tags {
        params["tags"] = Value::from(t);
    }
    if let Some(c) = confidence {
        params["confidence"] = Value::from(c);
    }
    if let Some(s) = source_task_id {
        params["source_task_id"] = Value::from(s);
    }
    if let Some(p) = proposed_by {
        params["proposed_by"] = Value::from(p);
    }
    sidecar
        .read()
        .await
        .call("collective.publish_learning", params)
        .await
}

#[tauri::command]
pub async fn collective_validate_learning(
    id: String,
    validated_by: String,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "collective.validate_learning",
            json!({ "id": id, "validated_by": validated_by }),
        )
        .await
}

#[tauri::command]
pub async fn collective_list_help_requests(
    status: Option<String>,
    expertise: Option<Vec<String>>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    let mut params = json!({});
    if let Some(s) = status {
        params["status"] = Value::from(s);
    }
    if let Some(e) = expertise {
        params["expertise"] = Value::from(e);
    }
    sidecar
        .read()
        .await
        .call("collective.list_help_requests", params)
        .await
}

#[tauri::command]
pub async fn collective_create_help_request(
    title: String,
    requester_agent: String,
    requester_solution: String,
    urgency: Option<String>,
    required_expertise: Option<Vec<String>>,
    context: Option<String>,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    let mut params = json!({
        "title": title,
        "requester_agent": requester_agent,
        "requester_solution": requester_solution,
    });
    if let Some(u) = urgency {
        params["urgency"] = Value::from(u);
    }
    if let Some(e) = required_expertise {
        params["required_expertise"] = Value::from(e);
    }
    if let Some(c) = context {
        params["context"] = Value::from(c);
    }
    sidecar
        .read()
        .await
        .call("collective.create_help_request", params)
        .await
}

#[tauri::command]
pub async fn collective_claim_help_request(
    id: String,
    agent: String,
    solution: String,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "collective.claim_help_request",
            json!({ "id": id, "agent": agent, "solution": solution }),
        )
        .await
}

#[tauri::command]
pub async fn collective_respond_to_help_request(
    id: String,
    responder_agent: String,
    responder_solution: String,
    content: String,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "collective.respond_to_help_request",
            json!({
                "id": id,
                "responder_agent": responder_agent,
                "responder_solution": responder_solution,
                "content": content,
            }),
        )
        .await
}

#[tauri::command]
pub async fn collective_close_help_request(
    id: String,
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("collective.close_help_request", json!({ "id": id }))
        .await
}

#[tauri::command]
pub async fn collective_sync(
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("collective.sync", json!({}))
        .await
}

#[tauri::command]
pub async fn collective_stats(
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("collective.stats", json!({}))
        .await
}
