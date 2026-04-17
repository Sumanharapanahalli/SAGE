//! sage-desktop library root — holds the Tauri app builder plus pure
//! modules (errors, rpc, sidecar) that are unit-testable without a live
//! window.
//!
//! The `desktop` feature (default on) pulls in Tauri and the `commands`
//! module. `cargo test --no-default-features` runs the pure-Rust tests
//! alone, sidestepping the WebView2Loader.dll startup dependency.

pub mod errors;
pub mod rpc;
pub mod sidecar;

#[cfg(feature = "desktop")]
pub mod commands;

#[cfg(feature = "desktop")]
mod desktop_app {
    use std::path::PathBuf;

    use tauri::Manager;
    use tokio::sync::RwLock;

    use crate::sidecar::{Sidecar, SidecarConfig};

    fn default_sidecar_config() -> SidecarConfig {
        let sage_root = std::env::var("SAGE_ROOT")
            .map(PathBuf::from)
            .unwrap_or_else(|_| {
                std::env::current_exe()
                    .ok()
                    .and_then(|p| p.parent().and_then(|p| p.parent()).map(PathBuf::from))
                    .unwrap_or_else(|| PathBuf::from("."))
            });
        let sidecar_dir = sage_root.join("sage-desktop").join("sidecar");
        let python = std::env::var("SAGE_PYTHON")
            .map(PathBuf::from)
            .unwrap_or_else(|_| PathBuf::from("python"));
        let solution_name = std::env::var("SAGE_SOLUTION_NAME").ok();
        let solution_path = std::env::var("SAGE_SOLUTION_PATH").ok().map(PathBuf::from);

        SidecarConfig {
            python,
            sidecar_dir,
            solution_name,
            solution_path,
            sage_root,
        }
    }

    pub fn run() {
        tracing_subscriber::fmt()
            .with_env_filter(
                tracing_subscriber::EnvFilter::try_from_default_env()
                    .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
            )
            .init();

        tauri::Builder::default()
            .plugin(tauri_plugin_shell::init())
            .setup(|app| {
                let cfg = default_sidecar_config();
                let handle = app.handle().clone();
                tauri::async_runtime::spawn(async move {
                    match Sidecar::spawn(cfg).await {
                        Ok(sidecar) => {
                            handle.manage(RwLock::new(sidecar));
                            tracing::info!("sidecar online");
                        }
                        Err(e) => {
                            tracing::error!("sidecar failed to start: {e}");
                        }
                    }
                });
                Ok(())
            })
            .invoke_handler(tauri::generate_handler![
                crate::commands::status::handshake,
                crate::commands::status::get_status,
                crate::commands::approvals::list_pending_approvals,
                crate::commands::approvals::get_approval,
                crate::commands::approvals::approve_proposal,
                crate::commands::approvals::reject_proposal,
                crate::commands::approvals::batch_approve,
                crate::commands::audit::list_audit_events,
                crate::commands::audit::get_audit_by_trace,
                crate::commands::audit::audit_stats,
                crate::commands::agents::list_agents,
                crate::commands::agents::get_agent,
                crate::commands::llm::get_llm_info,
                crate::commands::llm::switch_llm,
                crate::commands::backlog::list_feature_requests,
                crate::commands::backlog::submit_feature_request,
                crate::commands::backlog::update_feature_request,
                crate::commands::queue::get_queue_status,
                crate::commands::queue::list_queue_tasks,
                crate::commands::solutions::list_solutions,
                crate::commands::solutions::get_current_solution,
                crate::commands::switch::switch_solution,
                crate::commands::onboarding::onboarding_generate,
                crate::commands::builds::start_build,
                crate::commands::builds::list_builds,
                crate::commands::builds::get_build,
                crate::commands::builds::approve_build_stage,
                crate::commands::yaml_edit::read_yaml,
                crate::commands::yaml_edit::write_yaml,
                crate::commands::constitution::constitution_get,
                crate::commands::constitution::constitution_update,
                crate::commands::constitution::constitution_preamble,
                crate::commands::constitution::constitution_check_action,
                crate::commands::collective::collective_list_learnings,
                crate::commands::collective::collective_get_learning,
                crate::commands::collective::collective_search_learnings,
                crate::commands::collective::collective_publish_learning,
                crate::commands::collective::collective_validate_learning,
                crate::commands::collective::collective_list_help_requests,
                crate::commands::collective::collective_create_help_request,
                crate::commands::collective::collective_claim_help_request,
                crate::commands::collective::collective_respond_to_help_request,
                crate::commands::collective::collective_close_help_request,
                crate::commands::collective::collective_sync,
                crate::commands::collective::collective_stats,
                crate::commands::knowledge::knowledge_list,
                crate::commands::knowledge::knowledge_search,
                crate::commands::knowledge::knowledge_add,
                crate::commands::knowledge::knowledge_delete,
                crate::commands::knowledge::knowledge_stats,
            ])
            .run(tauri::generate_context!())
            .expect("error while running sage-desktop app");
    }
}

#[cfg(feature = "desktop")]
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    desktop_app::run();
}

#[cfg(not(feature = "desktop"))]
pub fn run() {
    // Non-desktop builds (unit tests) have no entry point — use `main.rs`
    // with the default features if you want to launch the app.
}
