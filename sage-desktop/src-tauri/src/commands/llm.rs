use serde_json::{json, Value};
use tauri::State;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn get_llm_info(sidecar: State<'_, Sidecar>) -> Result<Value, DesktopError> {
    sidecar.call("llm.get_info", json!({})).await
}

#[tauri::command]
pub async fn switch_llm(
    provider: String,
    model: Option<String>,
    save_as_default: Option<bool>,
    sidecar: State<'_, Sidecar>,
) -> Result<Value, DesktopError> {
    sidecar
        .call(
            "llm.switch",
            json!({
                "provider": provider,
                "model": model,
                "save_as_default": save_as_default.unwrap_or(false),
            }),
        )
        .await
}
