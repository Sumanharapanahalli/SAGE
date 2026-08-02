//! Chat commands — proxy to `chat.*` on the sidecar.
//!
//! A chat-proposed ACTION is never executed here. The sidecar turns it into a
//! pending proposal for the Approvals inbox, so `chat_send` may return a
//! `proposal` alongside the reply. The web API's `/chat/execute` instead runs
//! the action directly on a chat-UI confirm.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn chat_send(
    sidecar: State<'_, RwLock<Sidecar>>,
    message: String,
    conversation_id: Option<String>,
    page_context: Option<String>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "chat.send",
            json!({
                "message": message,
                "conversation_id": conversation_id,
                "page_context": page_context.unwrap_or_default(),
            }),
        )
        .await
}

#[tauri::command]
pub async fn chat_list_conversations(
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("chat.list_conversations", json!({}))
        .await
}

#[tauri::command]
pub async fn chat_get_conversation(
    sidecar: State<'_, RwLock<Sidecar>>,
    conversation_id: String,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "chat.get_conversation",
            json!({ "conversation_id": conversation_id }),
        )
        .await
}

#[tauri::command]
pub async fn chat_delete_conversation(
    sidecar: State<'_, RwLock<Sidecar>>,
    conversation_id: String,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "chat.delete_conversation",
            json!({ "conversation_id": conversation_id }),
        )
        .await
}

#[tauri::command]
pub async fn chat_clear_history(
    sidecar: State<'_, RwLock<Sidecar>>,
) -> Result<Value, DesktopError> {
    sidecar.read().await.call("chat.clear_history", json!({})).await
}
