//! Tauri command entry points.
//!
//! Each module wraps one or more sidecar RPC methods in a Tauri `#[command]`
//! so the frontend can `invoke("list_pending_approvals", ...)` the same way
//! it would any other Tauri command. All commands return
//! `Result<Value, DesktopError>` — `DesktopError` is `Serialize`, so
//! structured errors propagate to the frontend as typed JSON.

pub mod approvals;
pub mod audit;
pub mod agents;
pub mod status;
pub mod llm;
pub mod backlog;
pub mod builds;
pub mod constitution;
pub mod knowledge;
pub mod queue;
pub mod onboarding;
pub mod solutions;
pub mod switch;
pub mod yaml_edit;
