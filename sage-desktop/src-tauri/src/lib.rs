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

use std::path::{Path, PathBuf};

/// Resolve the SAGE repo root used to locate the sidecar package and to set
/// the sidecar's working directory / `SAGE_ROOT` env.
///
/// Resolution order:
/// 1. The `SAGE_ROOT` env var, when set to a non-empty value (the documented
///    `make desktop-dev` path). This is required in dev because the dev exe
///    lives deep under `src-tauri/target/debug/`, where exe-derivation lands
///    on `src-tauri/target` — a directory that does not contain the sidecar
///    package, so the sidecar spawn fails.
/// 2. Fallback: two directories up from the executable. (Roughly correct for
///    some packaged layouts; packaging is out of scope here.)
/// 3. Last resort: the current directory (".").
///
/// Kept as a pure function (no env/filesystem access of its own) so it is
/// compiled and unit-tested even under `--no-default-features`, where the
/// `desktop` feature — and thus `default_sidecar_config` — is gated out.
pub fn resolve_sage_root(exe: &Path, env: Option<String>) -> PathBuf {
    if let Some(root) = env.filter(|s| !s.is_empty()) {
        return PathBuf::from(root);
    }
    exe.parent()
        .and_then(|p| p.parent())
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
}

#[cfg(test)]
mod root_tests {
    use super::resolve_sage_root;
    use std::path::{Path, PathBuf};

    #[test]
    fn env_set_wins_over_exe_derivation() {
        let exe = Path::new("/some/deep/target/debug/sage-desktop");
        let root = resolve_sage_root(exe, Some("/repo/root".to_string()));
        assert_eq!(root, PathBuf::from("/repo/root"));
    }

    #[test]
    fn env_unset_falls_back_to_two_up_derivation() {
        // Mirrors the dev layout: exe two levels below the intended root.
        let exe = Path::new("/a/b/c/sage-desktop");
        let root = resolve_sage_root(exe, None);
        assert_eq!(root, PathBuf::from("/a/b"));
    }

    #[test]
    fn empty_env_treated_as_unset() {
        let exe = Path::new("/a/b/c/sage-desktop");
        let root = resolve_sage_root(exe, Some(String::new()));
        assert_eq!(root, PathBuf::from("/a/b"));
    }
}

#[cfg(feature = "desktop")]
mod desktop_app {
    use std::path::PathBuf;
    use std::sync::Arc;

    use serde_json::json;
    use tauri::{AppHandle, Emitter, Manager};
    use tokio::sync::RwLock;

    use crate::sidecar::{respawn_with_backoff, CrashHook, Sidecar, SidecarConfig};

    /// Build the crash hook wired into every (re)spawn: on an unexpected
    /// exit, emit `sidecar-status: {online:false}`, then attempt recovery
    /// with backoff (1s/3s/9s). On success, swap the fresh `Sidecar` into
    /// the managed `RwLock<Sidecar>` state and emit `{online:true}`; on
    /// exhaustion, emit a final `{online:false, exhausted:true}` — the app
    /// stays usable (every command already surfaces a recoverable
    /// `SidecarDown`), it just needs a manual solution switch or restart.
    ///
    /// Scope note: the recovered sidecar is spawned WITHOUT a crash hook of
    /// its own (single-shot recovery) — a second crash after a successful
    /// recovery is not auto-retried. Re-arming would need a self-referential
    /// `Arc<dyn Fn>`; not worth the complexity for a double-fault edge case.
    fn make_crash_hook(handle: AppHandle, cfg: SidecarConfig) -> CrashHook {
        Arc::new(move || {
            let handle = handle.clone();
            let cfg = cfg.clone();
            tauri::async_runtime::spawn(async move {
                let _ = handle.emit(
                    "sidecar-status",
                    json!({"online": false, "reason": "sidecar exited unexpectedly"}),
                );
                match respawn_with_backoff(cfg, None).await {
                    Ok(fresh) => {
                        if let Some(state) = handle.try_state::<RwLock<Sidecar>>() {
                            *state.write().await = fresh;
                        }
                        let _ = handle.emit("sidecar-status", json!({"online": true}));
                        tracing::info!("sidecar recovered after crash");
                    }
                    Err(e) => {
                        tracing::error!("sidecar recovery exhausted: {e}");
                        let _ = handle.emit(
                            "sidecar-status",
                            json!({"online": false, "reason": "recovery exhausted", "exhausted": true}),
                        );
                    }
                }
            });
        })
    }

    fn default_sidecar_config() -> SidecarConfig {
        // Prefer SAGE_ROOT (set by `make desktop-dev`); fall back to deriving
        // it from the executable path. Resolution lives in the pure,
        // unit-tested `crate::resolve_sage_root`.
        let exe = std::env::current_exe().unwrap_or_else(|_| PathBuf::from("."));
        let sage_root = crate::resolve_sage_root(&exe, std::env::var("SAGE_ROOT").ok());
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
            .setup(|app| {
                let cfg = default_sidecar_config();
                let handle = app.handle().clone();
                let hook = make_crash_hook(handle.clone(), cfg.clone());
                tauri::async_runtime::spawn(async move {
                    match Sidecar::spawn_with_hook(cfg.clone(), Some(hook)).await {
                        Ok(sidecar) => {
                            handle.manage(RwLock::new(sidecar));
                            tracing::info!("sidecar online");
                        }
                        Err(e) => {
                            // Register an offline sidecar so the State is always
                            // managed. Without this, commands hit Tauri's opaque
                            // unmanaged-state rejection; with it, they surface a
                            // recoverable `SidecarDown` the UI can render, and a
                            // later solution switch can spawn a fresh process.
                            tracing::error!("sidecar failed to start: {e}; registering offline state");
                            handle.manage(RwLock::new(Sidecar::offline(cfg)));
                        }
                    }
                });
                Ok(())
            })
            .invoke_handler(tauri::generate_handler![
                crate::commands::status::handshake,
                crate::commands::status::get_status,
                crate::commands::analyze::analyze_run,
                crate::commands::compliance::compliance_domains,
                crate::commands::compliance::compliance_flags,
                crate::commands::compliance::compliance_checklist,
                crate::commands::compliance::compliance_gap_assessment,
                crate::commands::costs::costs_summary,
                crate::commands::costs::costs_daily,
                crate::commands::costs::costs_set_budget,
                crate::commands::org::org_get,
                crate::commands::org::org_update,
                crate::commands::org::org_reload,
                crate::commands::skills::list_skills,
                crate::commands::skills::set_skill_visibility,
                crate::commands::skills::reload_skills,
                crate::commands::skills::list_mcp_tools,
                crate::commands::workflow::list_workflows,
                crate::commands::workflow::run_workflow,
                crate::commands::workflow::resume_workflow,
                crate::commands::workflow::get_workflow_status,
                crate::commands::monitor::monitor_status,
                crate::commands::monitor::scheduler_status,
                crate::commands::goals::list_goals,
                crate::commands::goals::create_goal,
                crate::commands::goals::get_goal,
                crate::commands::goals::update_goal,
                crate::commands::goals::delete_goal,
                crate::commands::eval::list_eval_suites,
                crate::commands::eval::run_eval,
                crate::commands::eval::get_eval_history,
                crate::commands::hil::hil_status,
                crate::commands::hil::hil_connect,
                crate::commands::hil::hil_run_suite,
                crate::commands::hil::hil_report,
                crate::commands::approvals::list_pending_approvals,
                crate::commands::approvals::get_approval,
                crate::commands::approvals::approve_proposal,
                crate::commands::approvals::reject_proposal,
                crate::commands::approvals::batch_approve,
                crate::commands::jobs::job_status,
                crate::commands::jobs::list_jobs,
                crate::commands::operator::get_operator,
                crate::commands::operator::set_operator,
                crate::commands::activity::list_activity,
                crate::commands::regulatory::regulatory_standards,
                crate::commands::regulatory::regulatory_standard,
                crate::commands::regulatory::regulatory_checklist,
                crate::commands::regulatory::regulatory_assess,
                crate::commands::regulatory::regulatory_gap_analysis,
                crate::commands::regulatory::regulatory_roadmap,
                crate::commands::audit::list_audit_events,
                crate::commands::audit::get_audit_by_trace,
                crate::commands::audit::audit_stats,
                crate::commands::agents::list_agents,
                crate::commands::agents::get_agent,
                crate::commands::agents::get_agent_performance,
                crate::commands::logs::logs_tail,
                crate::commands::llm::get_llm_info,
                crate::commands::llm::switch_llm,
                crate::commands::backlog::list_feature_requests,
                crate::commands::backlog::submit_feature_request,
                crate::commands::backlog::update_feature_request,
                crate::commands::backlog::plan_feature_request,
                crate::commands::queue::get_queue_status,
                crate::commands::queue::list_queue_tasks,
                crate::commands::queue::cancel_queue_task,
                crate::commands::queue::retry_queue_task,
                crate::commands::solutions::list_solutions,
                crate::commands::solutions::get_current_solution,
                crate::commands::solutions::remove_solution,
                crate::commands::switch::switch_solution,
                crate::commands::switch::unload_solution,
                crate::commands::onboarding::onboarding_generate,
                crate::commands::builds::start_build,
                crate::commands::builds::list_builds,
                crate::commands::builds::get_build,
                crate::commands::builds::approve_build_stage,
                crate::commands::builds::reject_build_stage,
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
                crate::commands::knowledgesync::knowledge_sync,
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
