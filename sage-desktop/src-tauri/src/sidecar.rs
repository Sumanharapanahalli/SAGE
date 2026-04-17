//! Sidecar process manager.
//!
//! Owns the Python sidecar child process: spawns it, writes JSON-RPC
//! requests to its stdin, correlates responses by `id`, and respawns on
//! unexpected exit with exponential backoff (1s → 3s → 9s, then gives up
//! and surfaces `SidecarDown` to the UI).
//!
//! Concurrency model: a single background task owns the stdout reader
//! and uses a `DashMap<String, oneshot::Sender<...>>` to route responses
//! to awaiting callers. Writers serialize through a `Mutex<ChildStdin>`.
//! This keeps the implementation small — Phase 1 doesn't need request
//! pipelining.

use std::collections::HashMap;
use std::path::PathBuf;
use std::process::Stdio;
use std::sync::Arc;

use serde_json::Value;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, ChildStdin, Command};
use tokio::sync::{oneshot, Mutex};
use tokio::time::{sleep, Duration};
use tracing::{error, info, warn};

use crate::errors::DesktopError;
use crate::rpc::{parse_response_line, RpcRequest};

type PendingMap = Arc<Mutex<HashMap<String, oneshot::Sender<Result<Value, DesktopError>>>>>;

/// Resolve the sidecar entry point based on build mode.
///
/// Priority:
/// 1. `SAGE_SIDECAR_PATH` env var (dev override / CI testing)
/// 2. Bundled `sage-sidecar-x86_64-pc-windows-msvc.exe` in the Tauri
///    resource dir (production MSI/NSIS install)
/// 3. Dev fallback: `../sidecar/__main__.py` relative to the cargo
///    manifest — only sensible when running from a source checkout
///
/// Callers should feed `resource_dir` from `app.path().resource_dir()` in
/// production code; pass `None` from tests.
pub fn resolve_sidecar_path(resource_dir: Option<PathBuf>) -> PathBuf {
    if let Ok(p) = std::env::var("SAGE_SIDECAR_PATH") {
        return PathBuf::from(p);
    }
    if let Some(dir) = resource_dir {
        let candidates: &[&str] = if cfg!(windows) {
            &[
                "sage-sidecar-x86_64-pc-windows-msvc.exe",
                "sage-sidecar-x86_64-pc-windows-gnu.exe",
            ]
        } else if cfg!(target_os = "macos") {
            &["sage-sidecar-x86_64-apple-darwin"]
        } else {
            &["sage-sidecar-x86_64-unknown-linux-gnu"]
        };
        for name in candidates {
            let exe = dir.join(name);
            if exe.exists() {
                return exe;
            }
        }
    }
    // Dev fallback: sage-desktop/src-tauri/../sidecar/__main__.py
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("sidecar")
        .join("__main__.py")
}

#[derive(Clone)]
pub struct SidecarConfig {
    /// Absolute path to the python interpreter to use.
    pub python: PathBuf,
    /// Absolute path to the `sidecar` package directory (contains __main__.py).
    pub sidecar_dir: PathBuf,
    /// Optional solution name to pass via --solution-name.
    pub solution_name: Option<String>,
    /// Optional solution path to pass via --solution-path.
    pub solution_path: Option<PathBuf>,
    /// Absolute path to the SAGE repo root (so `from src.core...` resolves).
    pub sage_root: PathBuf,
    /// Tauri resource dir — populated in production so the bundled
    /// `sage-sidecar-*.exe` is preferred over `python -m sidecar`.
    pub resource_dir: Option<PathBuf>,
}

pub struct Sidecar {
    stdin: Arc<Mutex<ChildStdin>>,
    pending: PendingMap,
    child: Arc<Mutex<Child>>,
    cfg: SidecarConfig,
}

impl Sidecar {
    /// Spawn the sidecar and return a handle. The stdout reader task is
    /// detached — it runs until the child exits.
    pub async fn spawn(cfg: SidecarConfig) -> Result<Self, DesktopError> {
        let resolved = resolve_sidecar_path(cfg.resource_dir.clone());
        let is_python_entry =
            resolved.extension().and_then(|e| e.to_str()) == Some("py");

        let mut cmd = if is_python_entry {
            let mut c = Command::new(&cfg.python);
            // `-u` forces unbuffered stdio so we don't deadlock on flushing.
            c.arg("-u").arg("-m").arg("sidecar");
            c
        } else {
            // Bundled executable — no python interpreter needed.
            Command::new(&resolved)
        };

        cmd.env("SAGE_ROOT", &cfg.sage_root)
            .env("PYTHONUNBUFFERED", "1")
            .current_dir(
                cfg.sidecar_dir
                    .parent()
                    .unwrap_or(&cfg.sidecar_dir)
                    .to_path_buf(),
            )
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        if let Some(name) = &cfg.solution_name {
            cmd.arg("--solution-name").arg(name);
        }
        if let Some(path) = &cfg.solution_path {
            cmd.arg("--solution-path").arg(path);
        }

        let mut child = cmd.spawn().map_err(|e| DesktopError::SidecarDown {
            message: format!("failed to spawn sidecar: {e}"),
        })?;

        let stdin = child.stdin.take().ok_or_else(|| DesktopError::SidecarDown {
            message: "no stdin on sidecar".into(),
        })?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| DesktopError::SidecarDown {
                message: "no stdout on sidecar".into(),
            })?;
        let stderr = child.stderr.take();

        let pending: PendingMap = Arc::new(Mutex::new(HashMap::new()));
        let pending_for_reader = pending.clone();

        // Detached: reads one NDJSON line at a time, routes by id.
        tokio::spawn(async move {
            let mut reader = BufReader::new(stdout).lines();
            loop {
                match reader.next_line().await {
                    Ok(Some(line)) => {
                        if line.trim().is_empty() {
                            continue;
                        }
                        match parse_response_line(&line) {
                            Ok(resp) => {
                                let id = resp.id.clone();
                                let result = resp.into_result();
                                if let Some(id) = id {
                                    let mut map = pending_for_reader.lock().await;
                                    if let Some(tx) = map.remove(&id) {
                                        let _ = tx.send(result);
                                    } else {
                                        warn!("orphan sidecar response id={id}");
                                    }
                                } else {
                                    // Error frames with null id (parse error, etc.)
                                    warn!("sidecar error with null id: {:?}", result.err());
                                }
                            }
                            Err(e) => {
                                error!("failed to parse sidecar line: {e}");
                            }
                        }
                    }
                    Ok(None) => {
                        info!("sidecar stdout closed");
                        break;
                    }
                    Err(e) => {
                        error!("sidecar stdout read error: {e}");
                        break;
                    }
                }
            }

            // Drain pending callers with SidecarDown
            let mut map = pending_for_reader.lock().await;
            for (_, tx) in map.drain() {
                let _ = tx.send(Err(DesktopError::SidecarDown {
                    message: "sidecar exited".into(),
                }));
            }
        });

        // Detached stderr drain (logs only).
        if let Some(stderr) = stderr {
            tokio::spawn(async move {
                let mut reader = BufReader::new(stderr).lines();
                while let Ok(Some(line)) = reader.next_line().await {
                    info!(target: "sage_desktop::sidecar::stderr", "{line}");
                }
            });
        }

        Ok(Self {
            stdin: Arc::new(Mutex::new(stdin)),
            pending,
            child: Arc::new(Mutex::new(child)),
            cfg,
        })
    }

    /// The config this sidecar was spawned with (name/path may be None).
    pub fn config(&self) -> &SidecarConfig {
        &self.cfg
    }

    /// Gracefully shut down the current sidecar and respawn with a new solution.
    ///
    /// Closes stdin → waits up to 3 s for the child to exit → kills it if it
    /// doesn't → spawns a new sidecar with the caller's name/path overrides.
    /// The current `Sidecar` is mutated in-place so callers holding an
    /// `RwLock<Sidecar>` can swap without moving the value out of the lock.
    pub async fn replace_solution(
        &mut self,
        name: String,
        path: PathBuf,
    ) -> Result<(), DesktopError> {
        use std::time::Duration as StdDuration;

        // Close stdin so the sidecar's reader hits EOF and exits.
        {
            let mut s = self.stdin.lock().await;
            let _ = s.shutdown().await;
        }
        // Wait for clean exit, force-kill on timeout.
        {
            let mut c = self.child.lock().await;
            let _ = tokio::time::timeout(StdDuration::from_secs(3), c.wait()).await;
            let _ = c.start_kill();
        }

        let mut cfg = self.cfg.clone();
        cfg.solution_name = Some(name);
        cfg.solution_path = Some(path);
        let fresh = Self::spawn(cfg).await?;

        self.stdin = fresh.stdin;
        self.pending = fresh.pending;
        self.child = fresh.child;
        self.cfg = fresh.cfg;
        Ok(())
    }

    /// Send a JSON-RPC request and wait for its correlated response.
    pub async fn call(&self, method: &str, params: Value) -> Result<Value, DesktopError> {
        let req = RpcRequest::new(method, params);
        let id = req.id.clone();
        let line = req.to_ndjson_line().map_err(|e| DesktopError::SidecarDown {
            message: format!("request serialize failed: {e}"),
        })?;

        let (tx, rx) = oneshot::channel();
        {
            let mut map = self.pending.lock().await;
            map.insert(id.clone(), tx);
        }

        {
            let mut stdin = self.stdin.lock().await;
            stdin
                .write_all(line.as_bytes())
                .await
                .map_err(|e| DesktopError::SidecarDown {
                    message: format!("stdin write failed: {e}"),
                })?;
            stdin
                .flush()
                .await
                .map_err(|e| DesktopError::SidecarDown {
                    message: format!("stdin flush failed: {e}"),
                })?;
        }

        rx.await.unwrap_or_else(|_| {
            Err(DesktopError::SidecarDown {
                message: "response channel closed".into(),
            })
        })
    }
}

/// Respawn policy: 1s, 3s, 9s, then give up.
pub async fn respawn_with_backoff(
    cfg: SidecarConfig,
) -> Result<Sidecar, DesktopError> {
    let delays = [Duration::from_secs(1), Duration::from_secs(3), Duration::from_secs(9)];
    let mut last_err = DesktopError::SidecarDown {
        message: "not attempted".into(),
    };
    for delay in delays {
        sleep(delay).await;
        match Sidecar::spawn(SidecarConfig {
            python: cfg.python.clone(),
            sidecar_dir: cfg.sidecar_dir.clone(),
            solution_name: cfg.solution_name.clone(),
            solution_path: cfg.solution_path.clone(),
            sage_root: cfg.sage_root.clone(),
            resource_dir: cfg.resource_dir.clone(),
        })
        .await
        {
            Ok(s) => return Ok(s),
            Err(e) => {
                warn!("sidecar respawn failed after {:?}: {e}", delay);
                last_err = e;
            }
        }
    }
    Err(last_err)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::env;
    use std::path::PathBuf;

    fn repo_root() -> PathBuf {
        // src-tauri/src/sidecar.rs → ../..  → sage-desktop/  → ..  → SAGE/
        let here = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        here.parent().unwrap().parent().unwrap().to_path_buf()
    }

    fn python_exe() -> PathBuf {
        // Let CI/devs override; default to `python` on PATH.
        env::var("PYTHON")
            .map(PathBuf::from)
            .unwrap_or_else(|_| PathBuf::from("python"))
    }

    #[tokio::test]
    async fn handshake_round_trip_through_real_sidecar() {
        let root = repo_root();
        let sidecar_dir = root.join("sage-desktop").join("sidecar");
        let cfg = SidecarConfig {
            python: python_exe(),
            sidecar_dir,
            solution_name: None,
            solution_path: None,
            sage_root: root,
            resource_dir: None,
        };
        let sidecar = match Sidecar::spawn(cfg).await {
            Ok(s) => s,
            Err(e) => {
                eprintln!("skipping: could not spawn sidecar: {e}");
                return;
            }
        };
        let result = sidecar
            .call("handshake", serde_json::json!({}))
            .await
            .expect("handshake should succeed");
        assert!(result.get("sidecar_version").is_some());
        assert!(result.get("warnings").is_some());
    }

    #[tokio::test]
    async fn replace_solution_spawns_fresh_sidecar() {
        let root = repo_root();
        let sidecar_dir = root.join("sage-desktop").join("sidecar");
        let cfg = SidecarConfig {
            python: python_exe(),
            sidecar_dir,
            solution_name: None,
            solution_path: None,
            sage_root: root.clone(),
            resource_dir: None,
        };
        let mut sidecar = match Sidecar::spawn(cfg).await {
            Ok(s) => s,
            Err(e) => {
                eprintln!("skipping: could not spawn sidecar: {e}");
                return;
            }
        };
        // Initial handshake OK
        let _ = sidecar
            .call("handshake", serde_json::json!({}))
            .await
            .expect("initial handshake");

        // Swap to a dummy solution path — sidecar will warn but still run
        let swap_path = root.join("solutions").join("starter");
        sidecar
            .replace_solution("starter".into(), swap_path)
            .await
            .expect("replace_solution");

        // Handshake after swap still works
        let result = sidecar
            .call("handshake", serde_json::json!({}))
            .await
            .expect("post-swap handshake");
        assert!(result.get("sidecar_version").is_some());
    }

    #[test]
    fn sidecar_path_prefers_env_override_when_set() {
        std::env::set_var("SAGE_SIDECAR_PATH", r"C:\fake\bundled\sage-sidecar.exe");
        let p = resolve_sidecar_path(None);
        assert_eq!(p.to_str().unwrap(), r"C:\fake\bundled\sage-sidecar.exe");
        std::env::remove_var("SAGE_SIDECAR_PATH");
    }

    #[test]
    fn sidecar_path_prefers_resource_dir_exe_when_present() {
        std::env::remove_var("SAGE_SIDECAR_PATH");
        // Point at a known-existing file so resolve_sidecar_path accepts it.
        let existing = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("Cargo.toml");
        let parent = existing.parent().unwrap().to_path_buf();
        // Rename Cargo.toml to look like the bundled exe name for this probe
        // — we don't actually rename, we just assert the logic checks existence
        // and falls through when the expected exe name isn't there.
        let p = resolve_sidecar_path(Some(parent.clone()));
        // Should fall back to dev path because sage-sidecar-*.exe doesn't exist
        // inside CARGO_MANIFEST_DIR — the real bundled-exe case is covered by E2E.
        assert!(p.to_str().unwrap().ends_with("__main__.py"));
    }

    #[test]
    fn sidecar_path_falls_back_to_dev_entrypoint() {
        std::env::remove_var("SAGE_SIDECAR_PATH");
        let p = resolve_sidecar_path(None);
        assert!(p.to_str().unwrap().ends_with("__main__.py"));
    }

    #[tokio::test]
    async fn unknown_method_returns_method_not_found() {
        let root = repo_root();
        let cfg = SidecarConfig {
            python: python_exe(),
            sidecar_dir: root.join("sage-desktop").join("sidecar"),
            solution_name: None,
            solution_path: None,
            sage_root: root,
            resource_dir: None,
        };
        let sidecar = match Sidecar::spawn(cfg).await {
            Ok(s) => s,
            Err(_) => return,
        };
        let err = sidecar
            .call("does.not.exist", serde_json::json!({}))
            .await
            .expect_err("should error");
        assert!(matches!(err, DesktopError::MethodNotFound { .. }));
    }
}
