//! MR commands — proxy to `mr.*` on the sidecar (GitLab merge requests).
//!
//! Distinct from SAGE's own Merge-Gate: these wrap the DeveloperAgent's GitLab
//! integration, addressed by numeric project/MR IDs.
//!
//! `mr_propose_create` does NOT open the merge request. It files an EXTERNAL,
//! non-reversible proposal for the Approvals inbox; only the approved-proposal
//! executor POSTs to GitLab. `mr_review` returns a job_id — the review is a
//! multi-round ReAct loop, so it runs in the background rather than blocking
//! the sidecar's serial dispatch.

use serde_json::{json, Value};
use tauri::State;
use tokio::sync::RwLock;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn mr_config(sidecar: State<'_, RwLock<Sidecar>>) -> Result<Value, DesktopError> {
    sidecar.read().await.call("mr.config", json!({})).await
}

#[tauri::command]
pub async fn mr_list_open(
    sidecar: State<'_, RwLock<Sidecar>>,
    project_id: i64,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call("mr.list_open", json!({ "project_id": project_id }))
        .await
}

#[tauri::command]
pub async fn mr_pipeline(
    sidecar: State<'_, RwLock<Sidecar>>,
    project_id: i64,
    mr_iid: i64,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "mr.pipeline",
            json!({ "project_id": project_id, "mr_iid": mr_iid }),
        )
        .await
}

#[tauri::command]
pub async fn mr_review(
    sidecar: State<'_, RwLock<Sidecar>>,
    project_id: i64,
    mr_iid: i64,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "mr.review",
            json!({ "project_id": project_id, "mr_iid": mr_iid }),
        )
        .await
}

#[tauri::command]
pub async fn mr_propose_create(
    sidecar: State<'_, RwLock<Sidecar>>,
    project_id: i64,
    issue_iid: i64,
    source_branch: Option<String>,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "mr.propose_create",
            json!({
                "project_id": project_id,
                "issue_iid": issue_iid,
                "source_branch": source_branch,
            }),
        )
        .await
}

#[tauri::command]
pub async fn mr_comment(
    sidecar: State<'_, RwLock<Sidecar>>,
    project_id: i64,
    mr_iid: i64,
    comment: String,
) -> Result<Value, DesktopError> {
    sidecar
        .read()
        .await
        .call(
            "mr.comment",
            json!({ "project_id": project_id, "mr_iid": mr_iid, "comment": comment }),
        )
        .await
}
