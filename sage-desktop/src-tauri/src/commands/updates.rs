//! Auto-update commands — frontend-invokable wrappers around
//! `tauri-plugin-updater`.
//!
//! The `UpdateStatus` enum lives in the feature-agnostic
//! `crate::update_status` module so its serialization contract can be
//! unit-tested without pulling in Tauri/WebView2.

use tauri::AppHandle;
use tauri_plugin_updater::UpdaterExt;

use crate::errors::DesktopError;
use crate::update_status::UpdateStatus;

/// Shared update-probing helper. Used by both the manual
/// ``check_update`` command (user clicks "Check for updates" in
/// Settings) and the background probe fired once on launch from
/// ``lib.rs::setup`` (Phase 4.6). Returns an ``UpdateStatus`` variant
/// — errors propagate as ``UpdateStatus::Error`` rather than as Err so
/// the frontend renders them uniformly.
pub async fn probe_update(app: &AppHandle) -> Result<UpdateStatus, DesktopError> {
    let current = app.package_info().version.to_string();
    let updater = app.updater().map_err(|e| DesktopError::Other {
        code: -1,
        message: format!("updater init failed: {e}"),
    })?;
    match updater.check().await {
        Ok(Some(update)) => Ok(UpdateStatus::Available {
            current_version: current,
            new_version: update.version.clone(),
            notes: update.body.clone().unwrap_or_default(),
        }),
        Ok(None) => Ok(UpdateStatus::UpToDate {
            current_version: current,
        }),
        Err(e) => Ok(UpdateStatus::Error {
            detail: format!("{e}"),
        }),
    }
}

#[tauri::command]
pub async fn check_update(app: AppHandle) -> Result<UpdateStatus, DesktopError> {
    probe_update(&app).await
}

#[tauri::command]
pub async fn install_update(app: AppHandle) -> Result<(), DesktopError> {
    let updater = app.updater().map_err(|e| DesktopError::Other {
        code: -1,
        message: format!("updater init failed: {e}"),
    })?;
    let Some(update) = updater.check().await.map_err(|e| DesktopError::Other {
        code: -1,
        message: format!("update check failed: {e}"),
    })?
    else {
        return Ok(());
    };
    update
        .download_and_install(|_chunk, _total| {}, || {})
        .await
        .map_err(|e| DesktopError::Other {
            code: -1,
            message: format!("install failed: {e}"),
        })?;
    app.restart();
}
